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
Deploy AWS API MCP Server to Amazon Bedrock AgentCore Runtime
REFACTORED VERSION - Uses shared Cognito user pool and stores output in SSM
"""
import os
import sys
import time
import json
import boto3
import shutil
from pathlib import Path
from boto3.session import Session
from bedrock_agentcore_starter_toolkit import Runtime

# Import our shared Cognito utilities
from cognito_utils import get_shared_cognito_client

def prepare_deployment_files():
    """Prepare the deployment files for the AWS API MCP Server"""
    print("Preparing deployment files...")
    
    # Create deployment directory
    deploy_dir = Path("aws-api-mcp-deploy")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.mkdir()
    
    # Create AgentCore-compatible server entrypoint using the public package
    server_py_content = '''#!/usr/bin/env python3
"""
Entrypoint for AWS API MCP Server - AgentCore Compatible
Uses the official awslabs.aws-api-mcp-server package
"""
import os
import sys
import subprocess
from pathlib import Path

# Set default AWS region if not set
if not os.environ.get("AWS_REGION"):
    os.environ["AWS_REGION"] = "us-east-1"

def main():
    """Main entrypoint that runs the official AWS API MCP server"""
    try:
        # Run the official AWS API MCP server using uvx
        cmd = ["uvx", "awslabs.aws-api-mcp-server@latest"]
        
        # Set environment variables for the server
        env = os.environ.copy()
        env.update({
            "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
            "MCP_LOG_LEVEL": os.environ.get("MCP_LOG_LEVEL", "INFO")
        })
        
        # Execute the server
        subprocess.run(cmd, env=env, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to start AWS API MCP server: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    with open(deploy_dir / "server.py", "w") as f:
        f.write(server_py_content)
    
    # Create requirements.txt with minimal dependencies
    requirements_content = '''mcp[server]>=1.7.1
boto3>=1.28.0
'''
    
    with open(deploy_dir / "requirements.txt", "w") as f:
        f.write(requirements_content)
    
    # Create a simple Dockerfile for uvx compatibility
    dockerfile_content = '''FROM python:3.11-slim

# Install uv and uvx
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy server script
COPY server.py .

# Make server script executable
RUN chmod +x server.py

# Expose port for MCP server
EXPOSE 8000

# Run the server
CMD ["python", "server.py"]
'''
    
    with open(deploy_dir / "Dockerfile", "w") as f:
        f.write(dockerfile_content)
    
    print(f"✓ Deployment files prepared in {deploy_dir}")
    return True

def main():
    print("🚀 Starting AWS API MCP Server Deployment")
    print("Using Shared Cognito User Pool")
    print("=" * 60)
    
    # Prepare deployment files
    if not prepare_deployment_files():
        sys.exit(1)
    
    # Change to deployment directory
    os.chdir("aws-api-mcp-deploy")
    
    # Check required files
    required_files = ['server.py', 'requirements.txt', 'Dockerfile']
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file {file} not found")
            sys.exit(1)
    print("✓ All required files found")
    
    # Get AWS region
    boto_session = Session()
    region = boto_session.region_name
    print(f"✓ Using AWS region: {region}")
    
    # Get shared Cognito configuration from Parameter Store
    print("\n📋 Getting shared Cognito configuration from Parameter Store...")
    try:
        cognito_client = get_shared_cognito_client(region=region, use_parameter_store=True)
        
        # Get authentication configuration for AgentCore
        auth_config = cognito_client.get_auth_config_for_agentcore()
        
        print("✓ Shared Cognito configuration retrieved from Parameter Store")
        print(f"  User Pool ID: {cognito_client.get_user_pool_id()}")
        print(f"  MCP Client ID: {cognito_client.get_mcp_server_client_id()}")
        
    except Exception as e:
        print(f"❌ Failed to get shared Cognito configuration: {e}")
        print("Make sure the shared Cognito infrastructure is deployed first:")
        print("  python deployment-scripts/deploy_shared_cognito.py --create-test-user")
        print("This will create the required parameters in Parameter Store at /coa/cognito/*")
        sys.exit(1)
    
    # Configure AgentCore Runtime
    print("\n🔧 Configuring AgentCore Runtime...")
    agentcore_runtime = Runtime()
    
    try:
        response = agentcore_runtime.configure(
            entrypoint="server.py",
            auto_create_execution_role=True,
            auto_create_ecr=True,
            requirements_file="requirements.txt",
            region=region,
            authorizer_configuration=auth_config,
            protocol="MCP",
            agent_name="aws_api_mcp_server"
        )
        print("✓ Configuration completed")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        sys.exit(1)
    
    # Launch to AgentCore Runtime
    print("\n🚀 Launching AWS API MCP server to AgentCore Runtime...")
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
    
    # Store component-specific configuration in SSM
    print("\n💾 Storing component configuration...")
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        
        # Store Agent ARN in component-specific path
        ssm_client.put_parameter(
            Name='/coa/components/aws_api_mcp/agent_arn',
            Value=launch_result.agent_arn,
            Type='String',
            Description='Agent ARN for AWS API MCP server',
            Overwrite=True
        )
        
        ssm_client.put_parameter(
            Name='/coa/components/aws_api_mcp/agent_id',
            Value=launch_result.agent_id,
            Type='String',
            Description='Agent ID for AWS API MCP server',
            Overwrite=True
        )
        
        # Store additional metadata
        # ssm_client.put_parameter(
        #     Name='/coa/components/aws_api_mcp/package_name',
        #     Value='awslabs.aws-api-mcp-server',
        #     Type='String',
        #     Description='Package name for AWS API MCP server',
        #     Overwrite=True
        # )
        
        # ssm_client.put_parameter(
        #     Name='/coa/components/aws_api_mcp/deployment_type',
        #     Value='public_package',
        #     Type='String',
        #     Description='Deployment type for AWS API MCP server',
        #     Overwrite=True
        # )
        
        # ssm_client.put_parameter(
        #     Name='/coa/components/aws_api_mcp/region',
        #     Value=region,
        #     Type='String',
        #     Description='AWS region for AWS API MCP server',
        #     Overwrite=True
        # )
        
        # Store connection information as JSON
        connection_info = {
            'agent_arn': launch_result.agent_arn,
            'agent_id': launch_result.agent_id,
            'user_pool_id': cognito_client.get_user_pool_id(),
            'mcp_client_id': cognito_client.get_mcp_server_client_id(),
            'region': region,
            'package_name': 'awslabs.aws-api-mcp-server',
            'deployment_type': 'public_package'
        }
        
        ssm_client.put_parameter(
            Name='/coa/components/aws_api_mcp/connection_info',
            Value=json.dumps(connection_info, indent=2),
            Type='String',
            Description='Complete connection information for AWS API MCP server',
            Overwrite=True
        )
        
        print("✓ Component configuration stored in Parameter Store")
        print(f"  Agent ARN: /coa/components/aws_api_mcp/agent_arn")
        print(f"  Agent ID: /coa/components/aws_api_mcp/agent_id")
        print(f"  Connection Info: /coa/components/aws_api_mcp/connection_info")
        
    except Exception as e:
        print(f"❌ Failed to store configuration: {e}")
        # Don't fail deployment for parameter storage issues
        print("⚠️ Continuing despite parameter storage failure...")
    
    print("\n🎉 Deployment completed successfully!")
    print("=" * 60)
    print(f"Agent ARN: {launch_result.agent_arn}")
    print(f"Agent ID: {launch_result.agent_id}")
    print(f"Shared User Pool ID: {cognito_client.get_user_pool_id()}")
    print(f"MCP Client ID: {cognito_client.get_mcp_server_client_id()}")
    print(f"Package: awslabs.aws-api-mcp-server")
    print(f"Deployment Type: public_package")
    print("\nThe AWS API MCP Server is now deployed and ready!")
    print("It uses the shared Cognito user pool for authentication.")
    print("Configuration stored in Parameter Store under /coa/components/aws_api_mcp/*")

if __name__ == "__main__":
    main()