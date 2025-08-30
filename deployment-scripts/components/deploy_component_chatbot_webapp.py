#!/usr/bin/env python3
"""
Deployment script for Cloud Optimization Chatbot Web Application
REFACTORED VERSION - Uses shared Cognito user pool
"""

import boto3
import json
import time
import os
import sys
import argparse
from typing import Dict, Any, Optional
import logging
from pathlib import Path

# Import our shared Cognito utilities
from cognito_utils import get_shared_cognito_client, get_cognito_config_for_cloudformation

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ChatbotWebAppDeployer:
    def __init__(self, 
                 stack_name: str = "cloud-optimization-chatbot",
                 region: str = "us-east-1",
                 domain_name: Optional[str] = None,
                 certificate_arn: Optional[str] = None,
                 shared_cognito_stack: str = "cloud-optimization-agentflow-cognito"):
        """
        Initialize the deployer
        
        Args:
            stack_name: CloudFormation stack name
            region: AWS region
            domain_name: Custom domain name (optional)
            certificate_arn: ACM certificate ARN for custom domain (optional)
            shared_cognito_stack: Name of the shared Cognito stack
        """
        self.stack_name = stack_name
        self.region = region
        self.domain_name = domain_name
        self.certificate_arn = certificate_arn
        self.shared_cognito_stack = shared_cognito_stack
        
        # Initialize AWS clients
        self.cf_client = boto3.client('cloudformation', region_name=region)
        self.ecr_client = boto3.client('ecr', region_name=region)
        self.sts_client = boto3.client('sts', region_name=region)
        
        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        # Initialize shared Cognito client
        self.cognito_client = get_shared_cognito_client(region=region, 
                                                      shared_stack_name=shared_cognito_stack)
        
        logger.info(f"Initialized deployer for account {self.account_id} in region {region}")

    def create_ecr_repository(self) -> str:
        """Create ECR repository for the application"""
        repo_name = f"{self.stack_name}-backend"
        
        try:
            response = self.ecr_client.create_repository(
                repositoryName=repo_name,
                imageScanningConfiguration={'scanOnPush': True},
                encryptionConfiguration={'encryptionType': 'AES256'}
            )
            logger.info(f"Created ECR repository: {repo_name}")
            return response['repository']['repositoryUri']
        except self.ecr_client.exceptions.RepositoryAlreadyExistsException:
            response = self.ecr_client.describe_repositories(repositoryNames=[repo_name])
            logger.info(f"ECR repository already exists: {repo_name}")
            return response['repositories'][0]['repositoryUri']

    def update_cognito_callback_urls(self):
        """Update callback URLs in the shared Cognito user pool"""
        logger.info("Updating Cognito callback URLs...")
        
        # Determine the callback URLs based on domain configuration
        if self.domain_name:
            callback_urls = [
                f"https://{self.domain_name}/callback",
                "http://localhost:3000/callback"
            ]
            logout_urls = [
                f"https://{self.domain_name}/logout",
                "http://localhost:3000/logout"
            ]
        else:
            # We'll update these after CloudFront is created
            callback_urls = [
                "http://localhost:3000/callback"
            ]
            logout_urls = [
                "http://localhost:3000/logout"
            ]
        
        try:
            self.cognito_client.update_client_callback_urls(
                client_id=self.cognito_client.get_web_app_client_id(),
                callback_urls=callback_urls,
                logout_urls=logout_urls
            )
            logger.info("✓ Cognito callback URLs updated")
        except Exception as e:
            logger.warning(f"Failed to update callback URLs: {e}")

    def generate_cloudformation_template(self, ecr_uri: str) -> Dict[str, Any]:
        """Generate CloudFormation template for the infrastructure"""
        
        # Get Cognito configuration for CloudFormation
        cognito_config = get_cognito_config_for_cloudformation(
            region=self.region,
            shared_stack_name=self.shared_cognito_stack
        )
        
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Cloud Optimization Chatbot Web Application Infrastructure (Using Shared Cognito)",
            "Parameters": {
                "ECRImageURI": {
                    "Type": "String",
                    "Default": f"{ecr_uri}:latest",
                    "Description": "ECR image URI for the backend application"
                },
                "DomainName": {
                    "Type": "String",
                    "Default": self.domain_name or "",
                    "Description": "Custom domain name (optional)"
                },
                "CertificateArn": {
                    "Type": "String",
                    "Default": self.certificate_arn or "",
                    "Description": "ACM certificate ARN for custom domain (optional)"
                }
            },
            "Conditions": {
                "HasCustomDomain": {
                    "Fn::Not": [{"Fn::Equals": [{"Ref": "DomainName"}, ""]}]
                }
            },
            "Resources": {
                # VPC and Networking (same as before)
                "VPC": {
                    "Type": "AWS::EC2::VPC",
                    "Properties": {
                        "CidrBlock": "10.0.0.0/16",
                        "EnableDnsHostnames": True,
                        "EnableDnsSupport": True,
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-vpc"}]
                    }
                },
                "PublicSubnet1": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "CidrBlock": "10.0.1.0/24",
                        "AvailabilityZone": {"Fn::Select": [0, {"Fn::GetAZs": ""}]},
                        "MapPublicIpOnLaunch": True,
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-public-subnet-1"}]
                    }
                },
                "PublicSubnet2": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "CidrBlock": "10.0.2.0/24",
                        "AvailabilityZone": {"Fn::Select": [1, {"Fn::GetAZs": ""}]},
                        "MapPublicIpOnLaunch": True,
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-public-subnet-2"}]
                    }
                },
                "PrivateSubnet1": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "CidrBlock": "10.0.3.0/24",
                        "AvailabilityZone": {"Fn::Select": [0, {"Fn::GetAZs": ""}]},
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-private-subnet-1"}]
                    }
                },
                "PrivateSubnet2": {
                    "Type": "AWS::EC2::Subnet",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "CidrBlock": "10.0.4.0/24",
                        "AvailabilityZone": {"Fn::Select": [1, {"Fn::GetAZs": ""}]},
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-private-subnet-2"}]
                    }
                },
                "InternetGateway": {
                    "Type": "AWS::EC2::InternetGateway",
                    "Properties": {
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-igw"}]
                    }
                },
                "AttachGateway": {
                    "Type": "AWS::EC2::VPCGatewayAttachment",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "InternetGatewayId": {"Ref": "InternetGateway"}
                    }
                },
                "NATGateway1": {
                    "Type": "AWS::EC2::NatGateway",
                    "Properties": {
                        "AllocationId": {"Fn::GetAtt": ["NATGateway1EIP", "AllocationId"]},
                        "SubnetId": {"Ref": "PublicSubnet1"},
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-nat-1"}]
                    }
                },
                "NATGateway1EIP": {
                    "Type": "AWS::EC2::EIP",
                    "DependsOn": "AttachGateway",
                    "Properties": {"Domain": "vpc"}
                },
                "PublicRouteTable": {
                    "Type": "AWS::EC2::RouteTable",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-public-rt"}]
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
                "PrivateRouteTable": {
                    "Type": "AWS::EC2::RouteTable",
                    "Properties": {
                        "VpcId": {"Ref": "VPC"},
                        "Tags": [{"Key": "Name", "Value": f"{self.stack_name}-private-rt"}]
                    }
                },
                "PrivateRoute": {
                    "Type": "AWS::EC2::Route",
                    "Properties": {
                        "RouteTableId": {"Ref": "PrivateRouteTable"},
                        "DestinationCidrBlock": "0.0.0.0/0",
                        "NatGatewayId": {"Ref": "NATGateway1"}
                    }
                },
                "PrivateSubnetRouteTableAssociation1": {
                    "Type": "AWS::EC2::SubnetRouteTableAssociation",
                    "Properties": {
                        "SubnetId": {"Ref": "PrivateSubnet1"},
                        "RouteTableId": {"Ref": "PrivateRouteTable"}
                    }
                },
                "PrivateSubnetRouteTableAssociation2": {
                    "Type": "AWS::EC2::SubnetRouteTableAssociation",
                    "Properties": {
                        "SubnetId": {"Ref": "PrivateSubnet2"},
                        "RouteTableId": {"Ref": "PrivateRouteTable"}
                    }
                },
                
                # ECS Task Definition (updated to use shared Cognito)
                "TaskDefinition": {
                    "Type": "AWS::ECS::TaskDefinition",
                    "Properties": {
                        "Family": f"{self.stack_name}-backend",
                        "NetworkMode": "awsvpc",
                        "RequiresCompatibilities": ["FARGATE"],
                        "Cpu": "512",
                        "Memory": "1024",
                        "ExecutionRoleArn": {"Ref": "TaskExecutionRole"},
                        "TaskRoleArn": {"Ref": "TaskRole"},
                        "ContainerDefinitions": [
                            {
                                "Name": "backend",
                                "Image": {"Ref": "ECRImageURI"},
                                "PortMappings": [{"ContainerPort": 8000}],
                                "Environment": [
                                    {"Name": "AWS_DEFAULT_REGION", "Value": self.region},
                                    {"Name": "COGNITO_USER_POOL_ID", "Value": cognito_config["UserPoolId"]},
                                    {"Name": "COGNITO_CLIENT_ID", "Value": cognito_config["WebAppClientId"]},
                                    {"Name": "COGNITO_DOMAIN", "Value": cognito_config["UserPoolDomain"]},
                                    {"Name": "COGNITO_IDENTITY_POOL_ID", "Value": cognito_config["IdentityPoolId"]}
                                ],
                                "LogConfiguration": {
                                    "LogDriver": "awslogs",
                                    "Options": {
                                        "awslogs-group": {"Ref": "LogGroup"},
                                        "awslogs-region": self.region,
                                        "awslogs-stream-prefix": "ecs"
                                    }
                                },
                                "Essential": True
                            }
                        ]
                    }
                },
                
                # ECS Cluster and Service (same as before)
                "ECSCluster": {
                    "Type": "AWS::ECS::Cluster",
                    "Properties": {
                        "ClusterName": f"{self.stack_name}-cluster",
                        "CapacityProviders": ["FARGATE"],
                        "DefaultCapacityProviderStrategy": [
                            {"CapacityProvider": "FARGATE", "Weight": 1}
                        ]
                    }
                },
                "TaskExecutionRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                                    "Action": "sts:AssumeRole"
                                }
                            ]
                        },
                        "ManagedPolicyArns": [
                            "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
                        ]
                    }
                },
                "TaskRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                                    "Action": "sts:AssumeRole"
                                }
                            ]
                        },
                        "Policies": [
                            {
                                "PolicyName": "BedrockAccess",
                                "PolicyDocument": {
                                    "Version": "2012-10-17",
                                    "Statement": [
                                        {
                                            "Effect": "Allow",
                                            "Action": [
                                                "bedrock:*",
                                                "bedrock-agent:*",
                                                "bedrock-runtime:*"
                                            ],
                                            "Resource": "*"
                                        },
                                        {
                                            "Effect": "Allow",
                                            "Action": [
                                                "cognito-idp:*"
                                            ],
                                            "Resource": "*"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
                "LogGroup": {
                    "Type": "AWS::Logs::LogGroup",
                    "Properties": {
                        "LogGroupName": f"/ecs/{self.stack_name}",
                        "RetentionInDays": 7
                    }
                },
                "ECSService": {
                    "Type": "AWS::ECS::Service",
                    "DependsOn": "ALBListener",
                    "Properties": {
                        "ServiceName": f"{self.stack_name}-service",
                        "Cluster": {"Ref": "ECSCluster"},
                        "TaskDefinition": {"Ref": "TaskDefinition"},
                        "DesiredCount": 2,
                        "LaunchType": "FARGATE",
                        "NetworkConfiguration": {
                            "AwsvpcConfiguration": {
                                "SecurityGroups": [{"Ref": "ECSSecurityGroup"}],
                                "Subnets": [{"Ref": "PrivateSubnet1"}, {"Ref": "PrivateSubnet2"}]
                            }
                        },
                        "LoadBalancers": [
                            {
                                "ContainerName": "backend",
                                "ContainerPort": 8000,
                                "TargetGroupArn": {"Ref": "TargetGroup"}
                            }
                        ]
                    }
                },
                
                # Application Load Balancer (same as before)
                "ApplicationLoadBalancer": {
                    "Type": "AWS::ElasticLoadBalancingV2::LoadBalancer",
                    "Properties": {
                        "Name": f"{self.stack_name}-alb",
                        "Scheme": "internal",
                        "Type": "application",
                        "Subnets": [{"Ref": "PrivateSubnet1"}, {"Ref": "PrivateSubnet2"}],
                        "SecurityGroups": [{"Ref": "ALBSecurityGroup"}]
                    }
                },
                "TargetGroup": {
                    "Type": "AWS::ElasticLoadBalancingV2::TargetGroup",
                    "Properties": {
                        "Name": f"{self.stack_name}-tg",
                        "Port": 8000,
                        "Protocol": "HTTP",
                        "VpcId": {"Ref": "VPC"},
                        "TargetType": "ip",
                        "HealthCheckPath": "/health",
                        "HealthCheckProtocol": "HTTP",
                        "HealthCheckIntervalSeconds": 30,
                        "HealthyThresholdCount": 2,
                        "UnhealthyThresholdCount": 5
                    }
                },
                "ALBListener": {
                    "Type": "AWS::ElasticLoadBalancingV2::Listener",
                    "Properties": {
                        "DefaultActions": [
                            {
                                "Type": "forward",
                                "TargetGroupArn": {"Ref": "TargetGroup"}
                            }
                        ],
                        "LoadBalancerArn": {"Ref": "ApplicationLoadBalancer"},
                        "Port": 80,
                        "Protocol": "HTTP"
                    }
                },
                
                # Security Groups (same as before)
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
                                "SourceSecurityGroupId": {"Ref": "ALBSecurityGroup"}
                            }
                        ],
                        "SecurityGroupEgress": [
                            {
                                "IpProtocol": "-1",
                                "CidrIp": "0.0.0.0/0"
                            }
                        ]
                    }
                },
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
                                "CidrIp": "10.0.0.0/16"
                            }
                        ]
                    }
                },
                
                # S3 and CloudFront (same as before)
                "StaticAssetsBucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {
                        "BucketName": f"{self.stack_name}-static-assets-{self.account_id}",
                        "PublicAccessBlockConfiguration": {
                            "BlockPublicAcls": True,
                            "BlockPublicPolicy": True,
                            "IgnorePublicAcls": True,
                            "RestrictPublicBuckets": True
                        }
                    }
                },
                
                "CloudFrontDistribution": {
                    "Type": "AWS::CloudFront::Distribution",
                    "Properties": {
                        "DistributionConfig": {
                            "Aliases": {"Fn::If": ["HasCustomDomain", [{"Ref": "DomainName"}], {"Ref": "AWS::NoValue"}]},
                            "ViewerCertificate": {
                                "Fn::If": [
                                    "HasCustomDomain",
                                    {
                                        "AcmCertificateArn": {"Ref": "CertificateArn"},
                                        "SslSupportMethod": "sni-only",
                                        "MinimumProtocolVersion": "TLSv1.2_2021"
                                    },
                                    {
                                        "CloudFrontDefaultCertificate": True
                                    }
                                ]
                            },
                            "DefaultCacheBehavior": {
                                "TargetOriginId": "static-assets",
                                "ViewerProtocolPolicy": "redirect-to-https",
                                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                                "OriginRequestPolicyId": "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"
                            },
                            "CacheBehaviors": [
                                {
                                    "PathPattern": "/api/*",
                                    "TargetOriginId": "backend-api",
                                    "ViewerProtocolPolicy": "redirect-to-https",
                                    "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                                    "OriginRequestPolicyId": "b689b0a8-53d0-40ab-baf2-68738e2966ac",
                                    "AllowedMethods": ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
                                }
                            ],
                            "Origins": [
                                {
                                    "Id": "static-assets",
                                    "DomainName": {"Fn::GetAtt": ["StaticAssetsBucket", "RegionalDomainName"]},
                                    "S3OriginConfig": {
                                        "OriginAccessIdentity": {"Fn::Sub": "origin-access-identity/cloudfront/${OriginAccessIdentity}"}
                                    }
                                },
                                {
                                    "Id": "backend-api",
                                    "DomainName": {"Fn::GetAtt": ["ApplicationLoadBalancer", "DNSName"]},
                                    "CustomOriginConfig": {
                                        "HTTPPort": 80,
                                        "OriginProtocolPolicy": "http-only"
                                    }
                                }
                            ],
                            "Enabled": True,
                            "DefaultRootObject": "index.html",
                            "CustomErrorResponses": [
                                {
                                    "ErrorCode": 404,
                                    "ResponseCode": 200,
                                    "ResponsePagePath": "/index.html"
                                }
                            ]
                        }
                    }
                },
                "OriginAccessIdentity": {
                    "Type": "AWS::CloudFront::CloudFrontOriginAccessIdentity",
                    "Properties": {
                        "CloudFrontOriginAccessIdentityConfig": {
                            "Comment": f"OAI for {self.stack_name}"
                        }
                    }
                },
                "BucketPolicy": {
                    "Type": "AWS::S3::BucketPolicy",
                    "Properties": {
                        "Bucket": {"Ref": "StaticAssetsBucket"},
                        "PolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {
                                        "AWS": {"Fn::Sub": "arn:aws:iam::cloudfront:user/CloudFront Origin Access Identity ${OriginAccessIdentity}"}
                                    },
                                    "Action": "s3:GetObject",
                                    "Resource": {"Fn::Join": ["", [{"Fn::GetAtt": ["StaticAssetsBucket", "Arn"]}, "/*"]]}
                                }
                            ]
                        }
                    }
                }
            },
            "Outputs": {
                "CloudFrontURL": {
                    "Description": "CloudFront distribution URL",
                    "Value": {"Fn::Sub": "https://${CloudFrontDistribution.DomainName}"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-CloudFrontURL"}}
                },
                "CustomDomainURL": {
                    "Condition": "HasCustomDomain",
                    "Description": "Custom domain URL",
                    "Value": {"Fn::Sub": "https://${DomainName}"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-CustomDomainURL"}}
                },
                "SharedUserPoolId": {
                    "Description": "Shared Cognito User Pool ID",
                    "Value": cognito_config["UserPoolId"],
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-SharedUserPoolId"}}
                },
                "WebAppClientId": {
                    "Description": "Web App Client ID",
                    "Value": cognito_config["WebAppClientId"],
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-WebAppClientId"}}
                },
                "S3BucketName": {
                    "Description": "S3 bucket for static assets",
                    "Value": {"Ref": "StaticAssetsBucket"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-S3BucketName"}}
                }
            }
        }
        
        return template

    def deploy_stack(self) -> Dict[str, str]:
        """Deploy the CloudFormation stack"""
        logger.info(f"Deploying stack: {self.stack_name}")
        
        # Create ECR repository
        ecr_uri = self.create_ecr_repository()
        
        # Update Cognito callback URLs
        self.update_cognito_callback_urls()
        
        # Generate template
        template = self.generate_cloudformation_template(ecr_uri)
        
        try:
            # Check if stack exists
            try:
                self.cf_client.describe_stacks(StackName=self.stack_name)
                stack_exists = True
            except self.cf_client.exceptions.ClientError:
                stack_exists = False
            
            parameters = [
                {"ParameterKey": "ECRImageURI", "ParameterValue": f"{ecr_uri}:latest"}
            ]
            
            if self.domain_name:
                parameters.append({"ParameterKey": "DomainName", "ParameterValue": self.domain_name})
            if self.certificate_arn:
                parameters.append({"ParameterKey": "CertificateArn", "ParameterValue": self.certificate_arn})
            
            if stack_exists:
                logger.info("Stack exists, updating...")
                response = self.cf_client.update_stack(
                    StackName=self.stack_name,
                    TemplateBody=json.dumps(template),
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM']
                )
            else:
                logger.info("Creating new stack...")
                response = self.cf_client.create_stack(
                    StackName=self.stack_name,
                    TemplateBody=json.dumps(template),
                    Parameters=parameters,
                    Capabilities=['CAPABILITY_IAM']
                )
            
            # Wait for completion
            logger.info("Waiting for stack operation to complete...")
            waiter_name = 'stack_update_complete' if stack_exists else 'stack_create_complete'
            waiter = self.cf_client.get_waiter(waiter_name)
            waiter.wait(StackName=self.stack_name)
            
            # Get outputs
            stack_info = self.cf_client.describe_stacks(StackName=self.stack_name)
            outputs = {}
            if 'Outputs' in stack_info['Stacks'][0]:
                for output in stack_info['Stacks'][0]['Outputs']:
                    outputs[output['OutputKey']] = output['OutputValue']
            
            # Update callback URLs with CloudFront domain if no custom domain
            if not self.domain_name and 'CloudFrontURL' in outputs:
                cloudfront_url = outputs['CloudFrontURL']
                callback_urls = [
                    f"{cloudfront_url}/callback",
                    "http://localhost:3000/callback"
                ]
                logout_urls = [
                    f"{cloudfront_url}/logout",
                    "http://localhost:3000/logout"
                ]
                
                self.cognito_client.update_client_callback_urls(
                    client_id=self.cognito_client.get_web_app_client_id(),
                    callback_urls=callback_urls,
                    logout_urls=logout_urls
                )
                logger.info("✓ Updated Cognito callback URLs with CloudFront domain")
            
            logger.info("✅ Stack deployed successfully!")
            return outputs
            
        except Exception as e:
            logger.error(f"❌ Failed to deploy stack: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Deploy Cloud Optimization Chatbot Web Application')
    parser.add_argument('--stack-name', default='cloud-optimization-chatbot',
                       help='CloudFormation stack name')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--domain-name',
                       help='Custom domain name (optional)')
    parser.add_argument('--certificate-arn',
                       help='ACM certificate ARN for custom domain (optional)')
    parser.add_argument('--shared-cognito-stack', default='cloud-optimization-agentflow-cognito',
                       help='Name of the shared Cognito stack')
    
    args = parser.parse_args()
    
    print("🚀 Deploying Cloud Optimization Chatbot Web Application")
    print("Using Shared Cognito User Pool")
    print("=" * 60)
    
    deployer = ChatbotWebAppDeployer(
        stack_name=args.stack_name,
        region=args.region,
        domain_name=args.domain_name,
        certificate_arn=args.certificate_arn,
        shared_cognito_stack=args.shared_cognito_stack
    )
    
    try:
        outputs = deployer.deploy_stack()
        
        print("\n🎉 Deployment completed successfully!")
        print("=" * 60)
        
        if args.domain_name:
            print(f"Application URL: https://{args.domain_name}")
        else:
            print(f"Application URL: {outputs.get('CloudFrontURL', 'Not available')}")
        
        print(f"Shared User Pool ID: {outputs.get('SharedUserPoolId', 'Not available')}")
        print(f"Web App Client ID: {outputs.get('WebAppClientId', 'Not available')}")
        print(f"S3 Bucket: {outputs.get('S3BucketName', 'Not available')}")
        
        print("\n📝 Next steps:")
        print("1. Build and push your Docker image to the ECR repository")
        print("2. Update the ECS service to use the new image")
        print("3. Upload your frontend assets to the S3 bucket")
        
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()