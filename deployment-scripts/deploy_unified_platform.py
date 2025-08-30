#!/usr/bin/env python3
"""
Unified Cloud Optimization Platform Deployment Script - CORRECTED VERSION
Fixes BuildSpec property validation error and deploys with specified profile

20250829:13:03

Latest status, the stack can be deploy correctly. But the CodeBuild/CodePipeline was not yet been integrated.
Need to change the sequence to embedded the Codebuild/pipeline in the process, then "the stack deployment" will be marked as SUCCESS

Also, the frontEnd Cloudfront distribution is missing

"""

import boto3
import json
import time
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UnifiedPlatformCorrectedDeployer:
    def __init__(self, 
                 stack_name: str = "cloud-optimization-platform",
                 region: str = "us-east-1",
                 environment: str = "prod",
                 profile: Optional[str] = None):
        """
        Initialize the unified platform deployer with corrected BuildSpec
        
        Args:
            stack_name: Main CloudFormation stack name
            region: AWS region
            environment: Environment (dev, staging, prod)
            profile: AWS CLI profile name (optional)
        """
        self.stack_name = stack_name
        self.region = region
        self.environment = environment
        self.profile = profile
        
        # Create session with profile if specified
        if profile:
            session = boto3.Session(profile_name=profile)
            logger.info(f"Using AWS profile: {profile}")
        else:
            session = boto3.Session()
            logger.info("Using default AWS credentials")
        
        # Initialize AWS clients with session
        self.cf_client = session.client('cloudformation', region_name=region)
        self.s3_client = session.client('s3', region_name=region)
        self.sts_client = session.client('sts', region_name=region)
        self.ssm_client = session.client('ssm', region_name=region)
        
        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        logger.info(f"Initialized unified deployer for account {self.account_id} in region {region}")

    def create_s3_bucket_for_source(self) -> str:
        """Create S3 bucket for storing backend source code"""
        bucket_name = f"{self.stack_name}-source-{self.account_id}-{self.region}"
        
        try:
            if self.region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            
            # Enable versioning for source code tracking
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            logger.info(f"Created source code bucket: {bucket_name}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                logger.info(f"Source bucket already exists: {bucket_name}")
            else:
                raise
        
        return bucket_name

    def generate_unified_template(self, source_bucket: str) -> Dict[str, Any]:
        """Generate a single CloudFormation template with all resources and corrected BuildSpec"""
        
        # BuildSpec as proper YAML string
        buildspec_yaml = """version: 0.2
phases:
  pre_build:
    commands:
      - echo Logging in to Amazon ECR...
      - aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY_URI
  build:
    commands:
      - echo Build started on `date`
      - echo Building the Docker image...
      - docker build -t backend .
      - docker tag backend:latest $ECR_REPOSITORY_URI:latest
  post_build:
    commands:
      - echo Build completed on `date`
      - echo Pushing the Docker image...
      - docker push $ECR_REPOSITORY_URI:latest
      - echo Updating ECS service...
      - aws ecs update-service --cluster $ECS_CLUSTER_NAME --service $ECS_SERVICE_NAME --force-new-deployment || echo 'ECS service not ready yet'"""
        
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Cloud Optimization Platform - Unified Single Stack Deployment (Corrected BuildSpec)",
            "Parameters": {
                "Environment": {
                    "Type": "String",
                    "Default": self.environment,
                    "AllowedValues": ["dev", "staging", "prod"],
                    "Description": "Environment name"
                },
                "SourceBucket": {
                    "Type": "String",
                    "Default": source_bucket,
                    "Description": "S3 bucket for source code storage"
                }
            },
            "Resources": {
                # ===== COGNITO RESOURCES =====
                "SharedUserPool": {
                    "Type": "AWS::Cognito::UserPool",
                    "Properties": {
                        "UserPoolName": {"Fn::Sub": f"{self.stack_name}-shared-${{Environment}}"},
                        "AutoVerifiedAttributes": ["email"],
                        "Policies": {
                            "PasswordPolicy": {
                                "MinimumLength": 8,
                                "RequireUppercase": True,
                                "RequireLowercase": True,
                                "RequireNumbers": True,
                                "RequireSymbols": True
                            }
                        },
                        "Schema": [
                            {
                                "Name": "email",
                                "AttributeDataType": "String",
                                "Required": True,
                                "Mutable": True
                            }
                        ],
                        "UsernameAttributes": ["email"],
                        "UserPoolTags": {
                            "Environment": {"Ref": "Environment"},
                            "Project": "CloudOptimization",
                            "Component": "Cognito"
                        }
                    }
                },
                "WebAppClient": {
                    "Type": "AWS::Cognito::UserPoolClient",
                    "Properties": {
                        "UserPoolId": {"Ref": "SharedUserPool"},
                        "ClientName": {"Fn::Sub": "web-app-client-${Environment}"},
                        "GenerateSecret": False,
                        "SupportedIdentityProviders": ["COGNITO"],
                        "CallbackURLs": [
                            "http://localhost:3000/callback",
                            "https://localhost:3000/callback"
                        ],
                        "LogoutURLs": [
                            "http://localhost:3000/logout",
                            "https://localhost:3000/logout"
                        ],
                        "AllowedOAuthFlows": ["code"],
                        "AllowedOAuthScopes": ["email", "openid", "profile"],
                        "AllowedOAuthFlowsUserPoolClient": True,
                        "ExplicitAuthFlows": [
                            "ALLOW_USER_PASSWORD_AUTH",
                            "ALLOW_REFRESH_TOKEN_AUTH",
                            "ALLOW_USER_SRP_AUTH"
                        ]
                    }
                },
                "APIClient": {
                    "Type": "AWS::Cognito::UserPoolClient",
                    "Properties": {
                        "UserPoolId": {"Ref": "SharedUserPool"},
                        "ClientName": {"Fn::Sub": "api-client-${Environment}"},
                        "GenerateSecret": False,
                        "ExplicitAuthFlows": [
                            "ALLOW_USER_PASSWORD_AUTH",
                            "ALLOW_REFRESH_TOKEN_AUTH",
                            "ALLOW_ADMIN_USER_PASSWORD_AUTH"
                        ]
                    }
                },
                "MCPServerClient": {
                    "Type": "AWS::Cognito::UserPoolClient",
                    "Properties": {
                        "UserPoolId": {"Ref": "SharedUserPool"},
                        "ClientName": {"Fn::Sub": "mcp-server-client-${Environment}"},
                        "GenerateSecret": False,
                        "ExplicitAuthFlows": [
                            "ALLOW_USER_PASSWORD_AUTH",
                            "ALLOW_REFRESH_TOKEN_AUTH"
                        ]
                    }
                },
                
                # ===== ECR AND BUILD PIPELINE =====
                "ECRRepository": {
                    "Type": "AWS::ECR::Repository",
                    "Properties": {
                        "ImageScanningConfiguration": {"ScanOnPush": True},
                        "EncryptionConfiguration": {"EncryptionType": "AES256"},
                        "LifecyclePolicy": {
                            "LifecyclePolicyText": json.dumps({
                                "rules": [{
                                    "rulePriority": 1,
                                    "description": "Keep last 10 images",
                                    "selection": {
                                        "tagStatus": "any",
                                        "countType": "imageCountMoreThan",
                                        "countNumber": 10
                                    },
                                    "action": {"type": "expire"}
                                }]
                            })
                        },
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "BuildPipeline"}
                        ]
                    }
                },
                "CodeBuildRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
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
                                        "Resource": {"Fn::Sub": "arn:aws:s3:::${SourceBucket}/*"}
                                    },
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "ecs:UpdateService"
                                        ],
                                        "Resource": "*"
                                    }
                                ]
                            }
                        }],
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "BuildPipeline"}
                        ]
                    }
                },
                "CodeBuildProject": {
                    "Type": "AWS::CodeBuild::Project",
                    "Properties": {
                        "Name": {"Fn::Sub": "cop-${Environment}-build"},
                        "ServiceRole": {"Fn::GetAtt": ["CodeBuildRole", "Arn"]},
                        "Artifacts": {"Type": "NO_ARTIFACTS"},
                        "Environment": {
                            "Type": "LINUX_CONTAINER",
                            "ComputeType": "BUILD_GENERAL1_MEDIUM",
                            "Image": "aws/codebuild/standard:7.0",
                            "PrivilegedMode": True,
                            "EnvironmentVariables": [
                                {
                                    "Name": "ECR_REPOSITORY_URI",
                                    "Value": {"Fn::Sub": "${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ECRRepository}"}
                                },
                                {
                                    "Name": "AWS_DEFAULT_REGION",
                                    "Value": {"Ref": "AWS::Region"}
                                },
                                {
                                    "Name": "AWS_ACCOUNT_ID",
                                    "Value": {"Ref": "AWS::AccountId"}
                                },
                                {
                                    "Name": "ECS_CLUSTER_NAME",
                                    "Value": {"Ref": "ECSCluster"}
                                },
                                {
                                    "Name": "ECS_SERVICE_NAME",
                                    "Value": {"Ref": "ECSService"}
                                }
                            ]
                        },
                        "Source": {
                            "Type": "S3",
                            "Location": {"Fn::Sub": "${SourceBucket}/source.zip"},
                            "BuildSpec": buildspec_yaml
                        },
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "BuildPipeline"}
                        ]
                    }
                },
                
                # ===== VPC AND NETWORKING =====
                "VPC": {
                    "Type": "AWS::EC2::VPC",
                    "Properties": {
                        "CidrBlock": "10.0.0.0/16",
                        "EnableDnsHostnames": True,
                        "EnableDnsSupport": True,
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-vpc"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "PublicSubnet1": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "CidrBlock": "10.0.1.0/24",
                        "AvailabilityZone": {"Fn::Select": [0, {"Fn::GetAZs": ""}]},
                        "MapPublicIpOnLaunch": True,
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-public-subnet-1"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}}
                        ]
                    }
                },
                "PublicSubnet2": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "CidrBlock": "10.0.2.0/24",
                        "AvailabilityZone": {"Fn::Select": [1, {"Fn::GetAZs": ""}]},
                        "MapPublicIpOnLaunch": True,
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-public-subnet-2"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}}
                        ]
                    }
                },
                "InternetGateway": {
                    "Type": "AWS::EC2::InternetGateway",
                    "Properties": {
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-igw"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}}
                        ]
                    }
                },
                "AttachGateway": {
                    "Type": "AWS::EC2::VPCGatewayAttachment",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "InternetGatewayId": {"Ref": "InternetGateway"}
                    }
                },
                "PublicRouteTable": {
                    "Type": "AWS::EC2::RouteTable",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-public-rt"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}}
                        ]
                    }
                },
                "PublicRoute": {
                    "Type": "AWS::EC2::Route",
                    "DependsOn": "AttachGateway",
                    "Properties": {
                        "RouteTableId": {"Ref": "PublicRouteTable"},
                        "DestinationCidrBlock": "0.0.0.0/0",
                        "GatewayId": {"Ref": "InternetGateway"}
                    }
                },
                "PublicSubnetRouteTableAssociation1": {
                    "Type": "AWS::EC2::SubnetRouteTableAssociation",
                    "Properties": {
                        "SubnetId": {"Ref": "PublicSubnet1"},
                        "RouteTableId": {"Ref": "PublicRouteTable"}
                    }
                },
                "PublicSubnetRouteTableAssociation2": {
                    "Type": "AWS::EC2::SubnetRouteTableAssociation",
                    "Properties": {
                        "SubnetId": {"Ref": "PublicSubnet2"},
                        "RouteTableId": {"Ref": "PublicRouteTable"}
                    }
                },
                
                # ===== SECURITY GROUPS =====
                "ALBSecurityGroup": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "GroupDescription": "Security group for ALB",
                        "VpcId": {"Ref": "VPC"},
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 80,
                                "ToPort": 80,
                                "CidrIp": "0.0.0.0/0",
                                "Description": "HTTP traffic"
                            },
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 443,
                                "ToPort": 443,
                                "CidrIp": "0.0.0.0/0",
                                "Description": "HTTPS traffic"
                            }
                        ],
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-alb-sg"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}}
                        ]
                    }
                },
                "ECSSecurityGroup": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "GroupDescription": "Security group for ECS tasks",
                        "VpcId": {"Ref": "VPC"},
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 8000,
                                "ToPort": 8000,
                                "SourceSecurityGroupId": {"Ref": "ALBSecurityGroup"},
                                "Description": "Traffic from ALB"
                            }
                        ],
                        "Tags": [
                            {"Key": "Name", "Value": {"Fn::Sub": "${AWS::StackName}-ecs-sg"}},
                            {"Key": "Environment", "Value": {"Ref": "Environment"}}
                        ]
                    }
                },
                
                # ===== APPLICATION LOAD BALANCER =====
                "ApplicationLoadBalancer": {
                    "Type": "AWS::ElasticLoadBalancingV2::LoadBalancer",
                    "Properties": {
                        "Name": {"Fn::Sub": "cop-${Environment}-alb"},
                        "Scheme": "internet-facing",
                        "Type": "application",
                        "Subnets": [{"Ref": "PublicSubnet1"}, {"Ref": "PublicSubnet2"}],
                        "SecurityGroups": [{"Ref": "ALBSecurityGroup"}],
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "TargetGroup": {
                    "Type": "AWS::ElasticLoadBalancingV2::TargetGroup",
                    "Properties": {
                        "Name": {"Fn::Sub": "cop-${Environment}-tg"},
                        "Port": 8000,
                        "Protocol": "HTTP",
                        "VpcId": {"Ref": "VPC"},
                        "TargetType": "ip",
                        "HealthCheckPath": "/health",
                        "HealthCheckProtocol": "HTTP",
                        "HealthCheckIntervalSeconds": 30,
                        "HealthCheckTimeoutSeconds": 5,
                        "HealthyThresholdCount": 2,
                        "UnhealthyThresholdCount": 3,
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "ALBListener": {
                    "Type": "AWS::ElasticLoadBalancingV2::Listener",
                    "Properties": {
                        "DefaultActions": [{
                            "Type": "forward",
                            "TargetGroupArn": {"Ref": "TargetGroup"}
                        }],
                        "LoadBalancerArn": {"Ref": "ApplicationLoadBalancer"},
                        "Port": 80,
                        "Protocol": "HTTP"
                    }
                },
                
                # ===== ECS CLUSTER AND SERVICE =====
                "ECSCluster": {
                    "Type": "AWS::ECS::Cluster",
                    "Properties": {
                        "ClusterName": {"Fn::Sub": "cop-${Environment}-cluster"},
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "ECSTaskRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                                "Action": "sts:AssumeRole"
                            }]
                        },
                        "Policies": [{
                            "PolicyName": "ECSTaskPolicy",
                            "PolicyDocument": {
                                "Version": "2012-10-17",
                                "Statement": [
                                    {
                                        "Effect": "Allow",
                                        "Action": [
                                            "cognito-idp:*",
                                            "ssm:GetParameter",
                                            "ssm:GetParameters",
                                            "ssm:GetParametersByPath"
                                        ],
                                        "Resource": "*"
                                    }
                                ]
                            }
                        }],
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "ECSExecutionRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{
                                "Effect": "Allow",
                                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                                "Action": "sts:AssumeRole"
                            }]
                        },
                        "ManagedPolicyArns": [
                            "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
                        ],
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "LogGroup": {
                    "Type": "AWS::Logs::LogGroup",
                    "Properties": {
                        "LogGroupName": {"Fn::Sub": "/ecs/${AWS::StackName}"},
                        "RetentionInDays": 7,
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "TaskDefinition": {
                    "Type": "AWS::ECS::TaskDefinition",
                    "Properties": {
                        "Family": {"Fn::Sub": "${AWS::StackName}-task"},
                        "NetworkMode": "awsvpc",
                        "RequiresCompatibilities": ["FARGATE"],
                        "Cpu": "256",
                        "Memory": "512",
                        "ExecutionRoleArn": {"Fn::GetAtt": ["ECSExecutionRole", "Arn"]},
                        "TaskRoleArn": {"Fn::GetAtt": ["ECSTaskRole", "Arn"]},
                        "ContainerDefinitions": [{
                            "Name": "backend",
                            "Image": {"Fn::Sub": "${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ECRRepository}:latest"},
                            "PortMappings": [{
                                "ContainerPort": 8000,
                                "Protocol": "tcp"
                            }],
                            "Essential": True,
                            "LogConfiguration": {
                                "LogDriver": "awslogs",
                                "Options": {
                                    "awslogs-group": {"Ref": "LogGroup"},
                                    "awslogs-region": {"Ref": "AWS::Region"},
                                    "awslogs-stream-prefix": "ecs"
                                }
                            },
                            "Environment": [
                                {
                                    "Name": "USER_POOL_ID",
                                    "Value": {"Ref": "SharedUserPool"}
                                },
                                {
                                    "Name": "WEB_APP_CLIENT_ID",
                                    "Value": {"Ref": "WebAppClient"}
                                },
                                {
                                    "Name": "API_CLIENT_ID",
                                    "Value": {"Ref": "APIClient"}
                                },
                                {
                                    "Name": "MCP_SERVER_CLIENT_ID",
                                    "Value": {"Ref": "MCPServerClient"}
                                },
                                {
                                    "Name": "AWS_DEFAULT_REGION",
                                    "Value": {"Ref": "AWS::Region"}
                                }
                            ]
                        }],
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                },
                "ECSService": {
                    "Type": "AWS::ECS::Service",
                    "DependsOn": "ALBListener",
                    "Properties": {
                        "ServiceName": {"Fn::Sub": "cop-${Environment}-service"},
                        "Cluster": {"Ref": "ECSCluster"},
                        "TaskDefinition": {"Ref": "TaskDefinition"},
                        "LaunchType": "FARGATE",
                        "DesiredCount": 1,
                        "NetworkConfiguration": {
                            "AwsvpcConfiguration": {
                                "SecurityGroups": [{"Ref": "ECSSecurityGroup"}],
                                "Subnets": [{"Ref": "PublicSubnet1"}, {"Ref": "PublicSubnet2"}],
                                "AssignPublicIp": "ENABLED"
                            }
                        },
                        "LoadBalancers": [{
                            "ContainerName": "backend",
                            "ContainerPort": 8000,
                            "TargetGroupArn": {"Ref": "TargetGroup"}
                        }],
                        "Tags": [
                            {"Key": "Environment", "Value": {"Ref": "Environment"}},
                            {"Key": "Component", "Value": "WebApp"}
                        ]
                    }
                }
            },
            "Outputs": {
                "UserPoolId": {
                    "Description": "Cognito User Pool ID",
                    "Value": {"Ref": "SharedUserPool"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-UserPoolId"}}
                },
                "WebAppClientId": {
                    "Description": "Web App Client ID",
                    "Value": {"Ref": "WebAppClient"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-WebAppClientId"}}
                },
                "APIClientId": {
                    "Description": "API Client ID",
                    "Value": {"Ref": "APIClient"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-APIClientId"}}
                },
                "MCPServerClientId": {
                    "Description": "MCP Server Client ID",
                    "Value": {"Ref": "MCPServerClient"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-MCPServerClientId"}}
                },
                "ECRRepositoryURI": {
                    "Description": "ECR Repository URI",
                    "Value": {"Fn::Sub": "${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ECRRepository}"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-ECRRepositoryURI"}}
                },
                "LoadBalancerDNS": {
                    "Description": "Application Load Balancer DNS Name",
                    "Value": {"Fn::GetAtt": ["ApplicationLoadBalancer", "DNSName"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-LoadBalancerDNS"}}
                },
                "SourceBucket": {
                    "Description": "S3 bucket for source code",
                    "Value": {"Ref": "SourceBucket"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-SourceBucket"}}
                }
            }
        }
        
        return template

    def deploy_stack(self, template: Dict[str, Any]) -> bool:
        """Deploy the CloudFormation stack"""
        try:
            logger.info(f"Deploying stack: {self.stack_name}")
            
            # Check if stack exists
            try:
                self.cf_client.describe_stacks(StackName=self.stack_name)
                stack_exists = True
                logger.info("Stack exists, updating...")
            except ClientError as e:
                if 'does not exist' in str(e):
                    stack_exists = False
                    logger.info("Stack does not exist, creating...")
                else:
                    raise
            
            # Deploy or update stack
            if stack_exists:
                response = self.cf_client.update_stack(
                    StackName=self.stack_name,
                    TemplateBody=json.dumps(template, indent=2),
                    Capabilities=['CAPABILITY_NAMED_IAM'],
                    Parameters=[
                        {
                            'ParameterKey': 'Environment',
                            'ParameterValue': self.environment
                        }
                    ]
                )
                operation = "UPDATE"
            else:
                response = self.cf_client.create_stack(
                    StackName=self.stack_name,
                    TemplateBody=json.dumps(template, indent=2),
                    Capabilities=['CAPABILITY_NAMED_IAM'],
                    Parameters=[
                        {
                            'ParameterKey': 'Environment',
                            'ParameterValue': self.environment
                        }
                    ],
                    Tags=[
                        {'Key': 'Environment', 'Value': self.environment},
                        {'Key': 'Project', 'Value': 'CloudOptimization'},
                        {'Key': 'DeployedBy', 'Value': 'UnifiedDeployer'}
                    ]
                )
                operation = "CREATE"
            
            stack_id = response['StackId']
            logger.info(f"Stack {operation} initiated. Stack ID: {stack_id}")
            
            # Wait for completion
            return self.wait_for_stack_completion(operation)
            
        except ClientError as e:
            if 'No updates are to be performed' in str(e):
                logger.info("No updates needed for the stack")
                return True
            else:
                logger.error(f"Failed to deploy stack: {e}")
                return False

    def wait_for_stack_completion(self, operation: str) -> bool:
        """Wait for stack operation to complete"""
        if operation == "CREATE":
            waiter = self.cf_client.get_waiter('stack_create_complete')
            success_status = 'CREATE_COMPLETE'
            failure_statuses = ['CREATE_FAILED', 'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED']
        else:
            waiter = self.cf_client.get_waiter('stack_update_complete')
            success_status = 'UPDATE_COMPLETE'
            failure_statuses = ['UPDATE_FAILED', 'UPDATE_ROLLBACK_COMPLETE', 'UPDATE_ROLLBACK_FAILED']
        
        try:
            logger.info(f"Waiting for stack {operation.lower()} to complete...")
            waiter.wait(
                StackName=self.stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 120  # 60 minutes max
                }
            )
            
            # Get final status
            response = self.cf_client.describe_stacks(StackName=self.stack_name)
            final_status = response['Stacks'][0]['StackStatus']
            
            if final_status == success_status:
                logger.info(f"Stack {operation.lower()} completed successfully!")
                return True
            else:
                logger.error(f"Stack {operation.lower()} failed with status: {final_status}")
                return False
                
        except Exception as e:
            logger.error(f"Error waiting for stack completion: {e}")
            return False

    def store_parameters_in_ssm(self):
        """Store important parameters in SSM for other components"""
        try:
            # Get stack outputs
            response = self.cf_client.describe_stacks(StackName=self.stack_name)
            outputs = response['Stacks'][0].get('Outputs', [])
            
            # Store each output in SSM
            for output in outputs:
                param_name = f"/{self.stack_name}/{output['OutputKey']}"
                param_value = output['OutputValue']
                
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=param_value,
                    Type='String',
                    Overwrite=True,
                    Description=output.get('Description', f"Output from {self.stack_name} stack")
                )
                
                logger.info(f"Stored parameter: {param_name}")
                
        except Exception as e:
            logger.warning(f"Failed to store parameters in SSM: {e}")

    def deploy(self) -> bool:
        """Main deployment method"""
        try:
            logger.info("Starting unified platform deployment...")
            
            # Create S3 bucket for source code
            source_bucket = self.create_s3_bucket_for_source()
            
            # Generate template
            template = self.generate_unified_template(source_bucket)
            
            # Deploy stack
            success = self.deploy_stack(template)
            
            if success:
                # Store parameters in SSM
                self.store_parameters_in_ssm()
                logger.info("Unified platform deployment completed successfully!")
            else:
                logger.error("Unified platform deployment failed!")
            
            return success
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Deploy Unified Cloud Optimization Platform')
    parser.add_argument('--stack-name', default='cloud-optimization-platform',
                        help='CloudFormation stack name')
    parser.add_argument('--region', default='us-east-1',
                        help='AWS region')
    parser.add_argument('--environment', default='prod',
                        choices=['dev', 'staging', 'prod'],
                        help='Environment')
    parser.add_argument('--profile', 
                        help='AWS CLI profile name')
    
    args = parser.parse_args()
    
    # Create deployer
    deployer = UnifiedPlatformCorrectedDeployer(
        stack_name=args.stack_name,
        region=args.region,
        environment=args.environment,
        profile=args.profile
    )
    
    # Deploy
    success = deployer.deploy()
    
    if success:
        print(f"\n✅ Deployment successful!")
        print(f"Stack: {args.stack_name}")
        print(f"Region: {args.region}")
        print(f"Environment: {args.environment}")
        if args.profile:
            print(f"Profile: {args.profile}")
    else:
        print(f"\n❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()