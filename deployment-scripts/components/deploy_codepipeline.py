#!/usr/bin/env python3

# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
CodePipeline Deployment Script
Creates a complete CI/CD pipeline that:
1. Monitors S3 bucket for source code changes (zip file)
2. Triggers CodeBuild to build Docker image
3. Pushes image to ECR
4. Updates ECS service automatically
"""

import boto3
import json
import time
import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CodePipelineDeployer:
    def __init__(self, 
                 stack_name: str = "cloud-optimization-codepipeline",
                 region: str = "us-east-1",
                 profile: Optional[str] = None):
        """
        Initialize the CodePipeline deployer
        
        Args:
            stack_name: CloudFormation stack name for the pipeline
            region: AWS region
            profile: AWS CLI profile name (optional)
        """
        self.stack_name = stack_name
        self.region = region
        self.profile = profile
        
        # Create session with profile if specified
        if profile:
            session = boto3.Session(profile_name=profile)
            logger.info(f"Using AWS profile: {profile}")
        else:
            session = boto3.Session()
            logger.info("Using default AWS credentials")
        
        # Initialize AWS clients
        self.cf_client = session.client('cloudformation', region_name=region)
        self.s3_client = session.client('s3', region_name=region)
        self.sts_client = session.client('sts', region_name=region)
        
        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        logger.info(f"Initialized CodePipeline deployer for account {self.account_id} in region {region}")

    def generate_pipeline_template(self, 
                                 source_bucket: str,
                                 ecr_repository: str,
                                 ecs_cluster: str = None,
                                 ecs_service: str = None) -> Dict[str, Any]:
        """Generate CloudFormation template for CodePipeline"""
        
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "CodePipeline for Cloud Optimization Platform Backend",
            "Parameters": {
                "SourceBucket": {
                    "Type": "String",
                    "Default": source_bucket,
                    "Description": "S3 bucket containing source code zip file"
                },
                "SourceKey": {
                    "Type": "String",
                    "Default": "source.zip",
                    "Description": "S3 key for source code zip file"
                },
                "ECRRepository": {
                    "Type": "String",
                    "Default": ecr_repository,
                    "Description": "ECR repository name for Docker images"
                },
                "ECSCluster": {
                    "Type": "String",
                    "Default": ecs_cluster or f"{self.stack_name}-cluster",
                    "Description": "ECS cluster name for deployment"
                },
                "ECSService": {
                    "Type": "String", 
                    "Default": ecs_service or f"{self.stack_name}-service",
                    "Description": "ECS service name for deployment"
                }
            },
            "Resources": {
                # S3 Bucket for CodePipeline artifacts
                "ArtifactsBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "BucketName": {"Fn::Sub": f"{self.stack_name}-artifacts-${{AWS::AccountId}}-${{AWS::Region}}"},
                        "VersioningConfiguration": {"Status": "Enabled"},
                        "PublicAccessBlockConfiguration": {
                            "BlockPublicAcls": True,
                            "BlockPublicPolicy": True,
                            "IgnorePublicAcls": True,
                            "RestrictPublicBuckets": True
                        },
                        "LifecycleConfiguration": {
                            "Rules": [{
                                "Id": "DeleteOldArtifacts",
                                "Status": "Enabled",
                                "ExpirationInDays": 30
                            }]
                        },
                        "Tags": [
                            {"Key": "Component", "Value": "CodePipeline"},
                            {"Key": "Purpose", "Value": "Artifacts"}
                        ]
                    }
                },
                
                # CodePipeline Service Role
                "CodePipelineServiceRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "RoleName": {"Fn::Sub": f"{self.stack_name}-pipeline-role"},
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Principal": {"Service": "codepipeline.amazonaws.com"},
                                "Action": "sts:AssumeRole"
                            }]
                        },
                        "Policies": [{
                            "PolicyName": "CodePipelinePolicy",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "s3:GetObject",
                                            "s3:GetObjectVersion",
                                            "s3:PutObject",
                                            "s3:GetBucketVersioning"
                                        ],
                                        "Resource": [
                                            {"Fn::Sub": "arn:aws:s3:::${SourceBucket}"},
                                            {"Fn::Sub": "arn:aws:s3:::${SourceBucket}/*"},
                                            {"Fn::GetAtt": ["ArtifactsBucket", "Arn"]},
                                            {"Fn::Sub": "${ArtifactsBucket.Arn}/*"}
                                        ]
                                    },
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "codebuild:BatchGetBuilds",
                                            "codebuild:StartBuild"
                                        ],
                                        "Resource": {"Fn::GetAtt": ["CodeBuildProject", "Arn"]}
                                    },
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "ecs:DescribeServices",
                                            "ecs:DescribeTaskDefinition",
                                            "ecs:DescribeTasks",
                                            "ecs:ListTasks",
                                            "ecs:RegisterTaskDefinition",
                                            "ecs:UpdateService"
                                        ],
                                        "Resource": "*"
                                    },
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "iam:PassRole"
                                        ],
                                        "Resource": "*"
                                    }
                                ]
                            }
                        }],
                        "Tags": [
                            {"Key": "Component", "Value": "CodePipeline"}
                        ]
                    }
                },
                
                # CodeBuild Service Role
                "CodeBuildServiceRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "RoleName": {"Fn::Sub": f"{self.stack_name}-codebuild-role"},
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Principal": {"Service": "codebuild.amazonaws.com"},
                                "Action": "sts:AssumeRole"
                            }]
                        },
                        "Policies": [{
                            "PolicyName": "CodeBuildPolicy",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "logs:CreateLogGroup",
                                            "logs:CreateLogStream",
                                            "logs:PutLogEvents"
                                        ],
                                        "Resource": {"Fn::Sub": "arn:aws:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/codebuild/*"}
                                    },
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "ecr:BatchCheckLayerAvailability",
                                            "ecr:GetDownloadUrlForLayer",
                                            "ecr:BatchGetImage",
                                            "ecr:GetAuthorizationToken",
                                            "ecr:PutImage",
                                            "ecr:InitiateLayerUpload",
                                            "ecr:UploadLayerPart",
                                            "ecr:CompleteLayerUpload"
                                        ],
                                        "Resource": "*"
                                    },
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "s3:GetObject",
                                            "s3:GetObjectVersion"
                                        ],
                                        "Resource": [
                                            {"Fn::Sub": "arn:aws:s3:::${SourceBucket}/*"},
                                            {"Fn::Sub": "${ArtifactsBucket.Arn}/*"}
                                        ]
                                    }
                                ]
                            }
                        }],
                        "Tags": [
                            {"Key": "Component", "Value": "CodeBuild"}
                        ]
                    }
                }