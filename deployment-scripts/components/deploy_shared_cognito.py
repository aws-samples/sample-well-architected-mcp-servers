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
Deploy Shared Cognito User Pool Infrastructure
This creates a centralized Cognito user pool that can be used by all components
"""

import boto3
import json
import time
import os
import sys
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SharedCognitoDeployer:
    def __init__(self, 
                 stack_name: str = "cloud-optimization-agentflow-cognito",
                 region: str = "us-east-1"):
        """
        Initialize the shared Cognito deployer
        
        Args:
            stack_name: CloudFormation stack name for shared Cognito
            region: AWS region
        """
        self.stack_name = stack_name
        self.region = region
        
        # Initialize AWS clients
        self.cf_client = boto3.client('cloudformation', region_name=region)
        self.sts_client = boto3.client('sts', region_name=region)
        
        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()['Account']
        
        logger.info(f"Initialized shared Cognito deployer for account {self.account_id} in region {region}")

    def generate_cloudformation_template(self) -> Dict[str, Any]:
        """Generate CloudFormation template for shared Cognito infrastructure"""
        
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Shared Cognito User Pool Infrastructure for Cloud Optimization Platform",
            "Parameters": {
                "Environment": {
                    "Type": "String",
                    "Default": "prod",
                    "AllowedValues": ["dev", "staging", "prod"],
                    "Description": "Environment name"
                }
            },
            "Resources": {
                # Main User Pool
                "SharedUserPool": {
                    "Type": "AWS::Cognito::UserPool",
                    "Properties": {
                        "UserPoolName": {"Fn::Sub": "cloud-optimization-shared-${Environment}"},
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
                            },
                            {
                                "Name": "given_name",
                                "AttributeDataType": "String",
                                "Required": False,
                                "Mutable": True
                            },
                            {
                                "Name": "family_name",
                                "AttributeDataType": "String",
                                "Required": False,
                                "Mutable": True
                            }
                        ],
                        "UsernameAttributes": ["email"],
                        "UserPoolTags": {
                            "Environment": {"Ref": "Environment"},
                            "Project": "CloudOptimization",
                            "Purpose": "SharedAuthentication"
                        }
                    }
                },
                
                # User Pool Domain
                "SharedUserPoolDomain": {
                    "Type": "AWS::Cognito::UserPoolDomain",
                    "Properties": {
                        "Domain": {"Fn::Sub": "cloud-optimization-${Environment}-${AWS::AccountId}"},
                        "UserPoolId": {"Ref": "SharedUserPool"}
                    }
                },
                
                # Web Application Client (for frontend apps)
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
                
                # API Client (for backend services)
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
                
                # MCP Server Client (for AgentCore Runtime)
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
                
                # Identity Pool for AWS resource access
                "IdentityPool": {
                    "Type": "AWS::Cognito::IdentityPool",
                    "Properties": {
                        "IdentityPoolName": {"Fn::Sub": "cloud_optimization_identity_pool_${Environment}"},
                        "AllowUnauthenticatedIdentities": False,
                        "CognitoIdentityProviders": [
                            {
                                "ClientId": {"Ref": "WebAppClient"},
                                "ProviderName": {"Fn::GetAtt": ["SharedUserPool", "ProviderName"]}
                            },
                            {
                                "ClientId": {"Ref": "APIClient"},
                                "ProviderName": {"Fn::GetAtt": ["SharedUserPool", "ProviderName"]}
                            }
                        ]
                    }
                },
                
                # IAM Role for authenticated users
                "AuthenticatedRole": {
                    "Type": "AWS::IAM::Role",
                    "Properties": {
                        "AssumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Effect": "Allow",
                                    "Principal": {
                                        "Federated": "cognito-identity.amazonaws.com"
                                    },
                                    "Action": "sts:AssumeRoleWithWebIdentity",
                                    "Condition": {
                                        "StringEquals": {
                                            "cognito-identity.amazonaws.com:aud": {"Ref": "IdentityPool"}
                                        },
                                        "ForAnyValue:StringLike": {
                                            "cognito-identity.amazonaws.com:amr": "authenticated"
                                        }
                                    }
                                }
                            ]
                        },
                        "Policies": [
                            {
                                "PolicyName": "AuthenticatedUserPolicy",
                                "PolicyDocument": {
                                    "Version": "2012-10-17",
                                    "Statement": [
                                        {
                                            "Effect": "Allow",
                                            "Action": [
                                                "cognito-sync:*",
                                                "cognito-identity:*"
                                            ],
                                            "Resource": "*"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                },
                
                # Identity Pool Role Attachment
                "IdentityPoolRoleAttachment": {
                    "Type": "AWS::Cognito::IdentityPoolRoleAttachment",
                    "Properties": {
                        "IdentityPoolId": {"Ref": "IdentityPool"},
                        "Roles": {
                            "authenticated": {"Fn::GetAtt": ["AuthenticatedRole", "Arn"]}
                        }
                    }
                }
            },
            "Outputs": {
                "UserPoolId": {
                    "Description": "Shared Cognito User Pool ID",
                    "Value": {"Ref": "SharedUserPool"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-UserPoolId"}}
                },
                "UserPoolArn": {
                    "Description": "Shared Cognito User Pool ARN",
                    "Value": {"Fn::GetAtt": ["SharedUserPool", "Arn"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-UserPoolArn"}}
                },
                "UserPoolDomain": {
                    "Description": "Cognito User Pool Domain",
                    "Value": {"Ref": "SharedUserPoolDomain"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-UserPoolDomain"}}
                },
                "WebAppClientId": {
                    "Description": "Web Application Client ID",
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
                "IdentityPoolId": {
                    "Description": "Cognito Identity Pool ID",
                    "Value": {"Ref": "IdentityPool"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-IdentityPoolId"}}
                },
                "AuthenticatedRoleArn": {
                    "Description": "IAM Role ARN for authenticated users",
                    "Value": {"Fn::GetAtt": ["AuthenticatedRole", "Arn"]},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-AuthenticatedRoleArn"}}
                },
                "DiscoveryUrl": {
                    "Description": "OIDC Discovery URL for JWT validation",
                    "Value": {"Fn::Sub": "https://cognito-idp.${AWS::Region}.amazonaws.com/${SharedUserPool}/.well-known/openid-configuration"},
                    "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-DiscoveryUrl"}}
                }
            }
        }
        
        return template

    def deploy_stack(self, environment: str = "prod") -> Dict[str, str]:
        """Deploy the shared Cognito stack"""
        logger.info(f"Deploying shared Cognito stack: {self.stack_name}")
        
        template = self.generate_cloudformation_template()
        
        try:
            # Check if stack exists
            try:
                self.cf_client.describe_stacks(StackName=self.stack_name)
                stack_exists = True
            except self.cf_client.exceptions.ClientError:
                stack_exists = False
            
            if stack_exists:
                logger.info("Stack exists, updating...")
                response = self.cf_client.update_stack(
                    StackName=self.stack_name,
                    TemplateBody=json.dumps(template),
                    Parameters=[
                        {"ParameterKey": "Environment", "ParameterValue": environment}
                    ],
                    Capabilities=['CAPABILITY_IAM']
                )
            else:
                logger.info("Creating new stack...")
                response = self.cf_client.create_stack(
                    StackName=self.stack_name,
                    TemplateBody=json.dumps(template),
                    Parameters=[
                        {"ParameterKey": "Environment", "ParameterValue": environment}
                    ],
                    Capabilities=['CAPABILITY_IAM']
                )
            
            # Wait for stack completion
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
            
            # Store configuration in standardized parameter paths
            self._store_parameters(outputs)
            
            logger.info("✅ Shared Cognito stack deployed successfully!")
            return outputs
            
        except Exception as e:
            logger.error(f"❌ Failed to deploy stack: {e}")
            raise

    def _store_parameters(self, outputs: Dict[str, str]) -> None:
        """Store Cognito configuration in standardized Parameter Store paths"""
        logger.info("Storing configuration in Parameter Store...")
        
        ssm_client = boto3.client('ssm', region_name=self.region)
        
        # Define standardized parameter mappings
        parameters = [
            {
                'Name': '/coa/cognito/user_pool_id',
                'Value': outputs['UserPoolId'],
                'Type': 'String',
                'Description': 'Shared Cognito User Pool ID for Cloud Optimization Platform'
            },
            {
                'Name': '/coa/cognito/web_app_client_id',
                'Value': outputs['WebAppClientId'],
                'Type': 'String',
                'Description': 'Web Application Client ID for frontend apps'
            },
            {
                'Name': '/coa/cognito/api_client_id',
                'Value': outputs['APIClientId'],
                'Type': 'String',
                'Description': 'API Client ID for backend services'
            },
            {
                'Name': '/coa/cognito/mcp_server_client_id',
                'Value': outputs['MCPServerClientId'],
                'Type': 'String',
                'Description': 'MCP Server Client ID for AgentCore Runtime'
            },
            {
                'Name': '/coa/cognito/identity_pool_id',
                'Value': outputs['IdentityPoolId'],
                'Type': 'String',
                'Description': 'Cognito Identity Pool ID for AWS resource access'
            },
            {
                'Name': '/coa/cognito/user_pool_domain',
                'Value': outputs['UserPoolDomain'],
                'Type': 'String',
                'Description': 'Cognito User Pool Domain for OAuth flows'
            },
            {
                'Name': '/coa/cognito/discovery_url',
                'Value': outputs['DiscoveryUrl'],
                'Type': 'String',
                'Description': 'OIDC Discovery URL for JWT validation'
            },
            {
                'Name': '/coa/cognito/region',
                'Value': self.region,
                'Type': 'String',
                'Description': 'AWS Region where Cognito is deployed'
            },
            {
                'Name': '/coa/cognito/user_pool_arn',
                'Value': outputs['UserPoolArn'],
                'Type': 'String',
                'Description': 'Cognito User Pool ARN'
            }
        ]
        
        try:
            for param in parameters:
                ssm_client.put_parameter(
                    Name=param['Name'],
                    Value=param['Value'],
                    Type=param['Type'],
                    Description=param['Description'],
                    Overwrite=True
                )
                logger.info(f"✓ Stored {param['Name']}")
            
            logger.info("✅ All Cognito configuration stored in Parameter Store")
            
        except Exception as e:
            logger.error(f"❌ Failed to store parameters: {e}")
            # Don't fail the deployment if parameter storage fails
            logger.warning("Continuing despite parameter storage failure...")

    def create_test_user(self, user_pool_id: str, email: str = "testuser@example.com", 
                        password: str = "TestPass123!") -> Dict[str, str]:
        """Create a test user in the shared user pool"""
        logger.info(f"Creating test user: {email}")
        
        cognito_client = boto3.client('cognito-idp', region_name=self.region)
        
        try:
            # Create user
            cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=email,
                TemporaryPassword='TempPass123!',
                MessageAction='SUPPRESS',
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ]
            )
            
            # Set permanent password
            cognito_client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=email,
                Password=password,
                Permanent=True
            )
            
            logger.info(f"✅ Test user created: {email}")
            return {"email": email, "password": password}
            
        except cognito_client.exceptions.UsernameExistsException:
            logger.info(f"User {email} already exists")
            return {"email": email, "password": password}
        except Exception as e:
            logger.error(f"❌ Failed to create test user: {e}")
            raise

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy shared Cognito infrastructure')
    parser.add_argument('--stack-name', default='cloud-optimization-shared-cognito',
                       help='CloudFormation stack name')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--environment', default='prod',
                       choices=['dev', 'staging', 'prod'],
                       help='Environment name')
    parser.add_argument('--create-test-user', action='store_true',
                       help='Create a test user after deployment')
    
    args = parser.parse_args()
    
    print("🚀 Deploying Shared Cognito Infrastructure")
    print("=" * 50)
    
    deployer = SharedCognitoDeployer(
        stack_name=args.stack_name,
        region=args.region
    )
    
    # Deploy the stack
    outputs = deployer.deploy_stack(environment=args.environment)
    
    # Create test user if requested
    if args.create_test_user:
        deployer.create_test_user(outputs['UserPoolId'])
    
    print("\n🎉 Deployment completed successfully!")
    print("=" * 50)
    print(f"User Pool ID: {outputs['UserPoolId']}")
    print(f"Web App Client ID: {outputs['WebAppClientId']}")
    print(f"API Client ID: {outputs['APIClientId']}")
    print(f"MCP Server Client ID: {outputs['MCPServerClientId']}")
    print(f"Identity Pool ID: {outputs['IdentityPoolId']}")
    print(f"Discovery URL: {outputs['DiscoveryUrl']}")
    
    print("\n📝 Next steps:")
    print("1. Update your component deployment scripts to reference these shared resources")
    print("2. Update callback URLs in the Web App Client for your actual domains")
    print("3. Configure your applications to use the appropriate client IDs")

if __name__ == "__main__":
    main()