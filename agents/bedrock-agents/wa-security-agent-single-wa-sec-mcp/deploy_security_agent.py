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
#!/usr/bin/env python3
"""
Deploy Well-Architected Security Agent to Amazon Bedrock AgentCore Runtime
This agent combines Claude 3.5 Sonnet with the Well-Architected Security MCP Server
"""
import os
import sys
import time
import json
import boto3
from pathlib import Path
from boto3.session import Session
from bedrock_agentcore_starter_toolkit import Runtime

def setup_cognito_user_pool():
    """Set up Amazon Cognito user pool for authentication"""
    print("Setting up Amazon Cognito user pool for Security Agent...")
    
    cognito_client = boto3.client('cognito-idp')
    
    try:
        # Create user pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName='security-agent-user-pool',
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': False,
                    'RequireLowercase': False,
                    'RequireNumbers': False,
                    'RequireSymbols': False
                }
            },
            AutoVerifiedAttributes=['email'],
            UsernameAttributes=['email']
        )
        user_pool_id = user_pool_response['UserPool']['Id']
        
        # Create user pool client
        client_response = cognito_client.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName='security-agent-client',
            GenerateSecret=False,
            ExplicitAuthFlows=['ALLOW_USER_PASSWORD_AUTH', 'ALLOW_REFRESH_TOKEN_AUTH']
        )
        client_id = client_response['UserPoolClient']['ClientId']
        
        # Create a test user
        test_email = 'security-user@example.com'
        cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=test_email,
            TemporaryPassword='TempPass123!',
            MessageAction='SUPPRESS'
        )
        
        # Set permanent password
        cognito_client.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=test_email,
            Password='SecurityPass123!',
            Permanent=True
        )
        
        # Get JWT token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': test_email,
                'PASSWORD': 'SecurityPass123!'
            }
        )
        
        bearer_token = auth_response['AuthenticationResult']['AccessToken']
        region = boto3.Session().region_name
        discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
        
        return {
            'user_pool_id': user_pool_id,
            'client_id': client_id,
            'bearer_token': bearer_token,
            'discovery_url': discovery_url
        }
        
    except Exception as e:
        print(f"Error setting up Cognito: {e}")
        return None

def main():
    print("🚀 Deploying Well-Architected Security Agent")
    print("🤖 Model: Claude 3.5 Sonnet")
    print("🔒 Integration: Well-Architected Security MCP Server")
    print("=" * 60)
    
    # Check required files
    required_files = ['agent_config/agent_task.py', 'requirements.txt']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file {file} not found")
            sys.exit(1)
    print("✓ All required files found")
    
    # Get AWS region
    boto_session = Session()
    region = boto_session.region_name
    print(f"✓ Using AWS region: {region}")
    
    # Setup Cognito
    print("\n📋 Setting up authentication...")
    cognito_config = setup_cognito_user_pool()
    if not cognito_config:
        print("❌ Failed to setup Cognito")
        sys.exit(1)
    print("✓ Cognito setup completed")
    
    # Configure AgentCore Runtime
    print("\n🔧 Configuring AgentCore Runtime...")
    agentcore_runtime = Runtime()
    
    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [cognito_config['client_id']],
            "discoveryUrl": cognito_config['discovery_url'],
        }
    }
    
    try:
        response = agentcore_runtime.configure(
            entrypoint="agent_config/agent_task.py",
            auto_create_execution_role=True,
            auto_create_ecr=True,
            requirements_file="requirements.txt",
            region=region,
            authorizer_configuration=auth_config,
            protocol="AGENT",  # This is an Agent, not MCP
            agent_name="security_agent_claude"
        )
        print("✓ Configuration completed")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        sys.exit(1)
    
    # Launch to AgentCore Runtime
    print("\n🚀 Launching Security Agent to AgentCore Runtime...")
    print("This may take several minutes...")
    try:
        launch_result = agentcore_runtime.launch(auto_update_on_conflict=True)
        print("✓ Launch completed")
        print(f"Agent ARN: {launch_result.agent_arn}")
        print(f"Agent ID: {launch_result.agent_id}")
    except Exception as e:
        print(f"❌ Launch failed: {e}")
        sys.exit(1)
    
    # Check status
    print("\n⏳ Checking AgentCore Runtime status...")
    try:
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']
        print(f"Initial status: {status}")
        
        end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        while status not in end_status:
            print(f"Status: {status} - waiting...")
            time.sleep(10)
            status_response = agentcore_runtime.status()
            status = status_response.endpoint['status']
        
        if status == 'READY':
            print("✅ AgentCore Runtime is READY!")
        else:
            print(f"⚠️ AgentCore Runtime status: {status}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        sys.exit(1)
    
    # Store configuration
    print("\n💾 Storing configuration...")
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        secrets_client = boto3.client('secretsmanager', region_name=region)
        
        # Store Cognito credentials
        try:
            secrets_client.create_secret(
                Name='security_agent/cognito/credentials',
                Description='Cognito credentials for Security Agent',
                SecretString=json.dumps(cognito_config)
            )
            print("✓ Cognito credentials stored in Secrets Manager")
        except secrets_client.exceptions.ResourceExistsException:
            secrets_client.update_secret(
                SecretId='security_agent/cognito/credentials',
                SecretString=json.dumps(cognito_config)
            )
            print("✓ Cognito credentials updated in Secrets Manager")
        
        # Store Agent ARN
        ssm_client.put_parameter(
            Name='/security_agent/runtime/agent_arn',
            Value=launch_result.agent_arn,
            Type='String',
            Description='Agent ARN for Security Agent',
            Overwrite=True
        )
        print("✓ Agent ARN stored in Parameter Store")
        
        # Store Memory ID (for conversation context)
        memory_id = f"security_agent_memory_{launch_result.agent_id}"
        ssm_client.put_parameter(
            Name='/app/security/agentcore/memory_id',
            Value=memory_id,
            Type='String',
            Description='Memory ID for Security Agent',
            Overwrite=True
        )
        print("✓ Memory ID stored in Parameter Store")
        
    except Exception as e:
        print(f"❌ Failed to store configuration: {e}")
        sys.exit(1)
    
    print("\n🎉 Security Agent Deployment Completed Successfully!")
    print("=" * 60)
    print(f"🤖 Agent: Claude 3.5 Sonnet + Well-Architected Security MCP")
    print(f"🔗 Agent ARN: {launch_result.agent_arn}")
    print(f"🆔 Agent ID: {launch_result.agent_id}")
    print(f"👤 User Pool ID: {cognito_config['user_pool_id']}")
    print(f"🔑 Client ID: {cognito_config['client_id']}")
    print(f"🧠 Memory ID: {memory_id}")
    print("\n✅ Your Security Agent is ready to use!")
    print("💬 It can now answer security questions using real-time AWS data")
    print("🔒 Powered by Claude 3.5 Sonnet + Well-Architected Security MCP Server")

if __name__ == "__main__":
    main()