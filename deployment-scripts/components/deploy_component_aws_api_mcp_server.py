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
REFACTORED VERSION - Uses shared Cognito user pool, BedrockAgentCoreRuntimeRole from COA stack, and stores output in SSM
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path

import boto3
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session



build_dir = "build/aws-api-mcp-deploy"

def get_coa_stack_role_arn(region, stack_name_prefix="cloud-optimization-assistant"):
    """Get the BedrockAgentCoreRuntimeRole ARN from the COA CloudFormation stack"""
    print(f"🔍 Looking for BedrockAgentCoreRuntimeRole in COA stack...")
    
    cf_client = boto3.client("cloudformation", region_name=region)
    
    try:
        # List stacks to find the COA stack
        paginator = cf_client.get_paginator('list_stacks')
        
        coa_stack_name = None
        for page in paginator.paginate(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']):
            for stack in page['StackSummaries']:
                if stack['StackName'].startswith(stack_name_prefix):
                    coa_stack_name = stack['StackName']
                    break
            if coa_stack_name:
                break
        
        if not coa_stack_name:
            raise Exception(f"No CloudFormation stack found with prefix '{stack_name_prefix}'")
        
        print(f"✓ Found COA stack: {coa_stack_name}")
        
        # Get stack resources to find the BedrockAgentCoreRuntimeRole
        paginator = cf_client.get_paginator('list_stack_resources')
        
        for page in paginator.paginate(StackName=coa_stack_name):
            for resource in page['StackResourceSummaries']:
                if resource['LogicalResourceId'] == 'BedrockAgentCoreRuntimeRole':
                    role_arn = f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/{resource['PhysicalResourceId']}"
                    print(f"✓ Found BedrockAgentCoreRuntimeRole: {role_arn}")
                    return role_arn
        
        raise Exception("BedrockAgentCoreRuntimeRole not found in COA stack. Make sure you're using CloudFormation template v0.1.1 or later.")
        
    except Exception as e:
        print(f"❌ Failed to get BedrockAgentCoreRuntimeRole from COA stack: {e}")
        raise


def prepare_deployment_files():
    """Prepare the deployment files for the AWS API MCP Server"""
    print("Preparing deployment files...")

    source_dir = Path("agents/strands-agents/aws-api-mcp-runtime")

    # Create deployment directory
    deploy_dir = Path(build_dir)
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.mkdir()

    # Copy server.py to deployment directory
    shutil.copy(source_dir / "server.py", deploy_dir)
    # Copy requirements.txt to deployment directory
    shutil.copy(source_dir / "requirements.txt", deploy_dir)
    # Create empty __init__.py in deployment directory
    shutil.copy(source_dir / "Dockerfile", deploy_dir)
    (deploy_dir / "__init__.py").touch()
    print("✓ Deployment files prepared")
    return True


def main():
    print("🚀 Starting AWS API MCP Server Deployment")
    print("Using Shared Cognito User Pool and COA Stack BedrockAgentCoreRuntimeRole")
    print("=" * 80)

    # Prepare deployment files
    if not prepare_deployment_files():
        sys.exit(1)

    # Change to deployment directory
    os.chdir(build_dir)

    # Check required files
    required_files = ["server.py", "requirements.txt"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file {file} not found")
            sys.exit(1)
    print("✓ All required files found")

    # Get AWS region
    boto_session = Session()
    region = boto_session.region_name
    print(f"✓ Using AWS region: {region}")

    # Get BedrockAgentCoreRuntimeRole from COA stack
    print("\n🔍 Getting BedrockAgentCoreRuntimeRole from COA stack...")
    try:
        execution_role_arn = get_coa_stack_role_arn(region)
    except Exception as e:
        print(f"❌ Failed to get execution role: {e}")
        print("Make sure the COA stack is deployed with CloudFormation template v0.1.1 or later")
        sys.exit(1)

    # Get shared Cognito configuration from Parameter Store
    # Not using this for demo site because we are leveraging SigV4(IAM) for permission control
    # print("\n📋 Getting shared Cognito configuration from Parameter Store...")
    # try:
    #     cognito_client = get_shared_cognito_client(
    #         region=region, use_parameter_store=True
    #     )

    #     # Get authentication configuration for AgentCore
    #     auth_config = cognito_client.get_auth_config_for_agentcore()

    #     print("✓ Shared Cognito configuration retrieved from Parameter Store")
    #     print(f"  User Pool ID: {cognito_client.get_user_pool_id()}")
    #     print(f"  MCP Client ID: {cognito_client.get_mcp_server_client_id()}")

    # except Exception as e:
    #     print(f"❌ Failed to get shared Cognito configuration: {e}")
    #     print("Make sure the shared Cognito infrastructure is deployed first:")
    #     print("  python deployment-scripts/deploy_shared_cognito.py --create-test-user")
    #     print(
    #         "This will create the required parameters in Parameter Store at /coa/cognito/*"
    #     )
    #     sys.exit(1)

    # Configure AgentCore Runtime
    print("\n🔧 Configuring AgentCore Runtime...")
    agentcore_runtime = Runtime()

    try:
        response = agentcore_runtime.configure(
            entrypoint="server.py",
            execution_role=execution_role_arn,  # Use BedrockAgentCoreRuntimeRole
            auto_create_ecr=True,
            requirements_file="requirements.txt",
            region=region,
            protocol="MCP",
            agent_name="aws_api_mcp_server",
        )
        
        # Handle response properly (no .body attribute)
        print(f"Configuration response: {response}")
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
        status = status_response.endpoint["status"]
        print(f"Initial status: {status}")

        end_status = ["READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"]
        while status not in end_status:
            print(f"Status: {status} - waiting...")
            time.sleep(10)
            status_response = agentcore_runtime.status()
            status = status_response.endpoint["status"]

        if status == "READY":
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
        ssm_client = boto3.client("ssm", region_name=region)

        # Store Agent ARN in component-specific path
        ssm_client.put_parameter(
            Name="/coa/components/aws_api_mcp/agent_arn",
            Value=launch_result.agent_arn,
            Type="String",
            Description="Agent ARN for AWS API MCP server",
            Overwrite=True,
        )

        ssm_client.put_parameter(
            Name="/coa/components/aws_api_mcp/agent_id",
            Value=launch_result.agent_id,
            Type="String",
            Description="Agent ID for AWS API MCP server",
            Overwrite=True,
        )

        # Store additional metadata
        ssm_client.put_parameter(
            Name="/coa/components/aws_api_mcp/deployment_type",
            Value="public_package",
            Type="String",
            Description="Deployment type for AWS API MCP server",
            Overwrite=True,
        )

        ssm_client.put_parameter(
            Name="/coa/components/aws_api_mcp/region",
            Value=region,
            Type="String",
            Description="AWS region for AWS API MCP server",
            Overwrite=True,
        )

        ssm_client.put_parameter(
            Name="/coa/components/aws_api_mcp/execution_role_arn",
            Value=execution_role_arn,
            Type="String",
            Description="Execution role ARN used by AWS API MCP server",
            Overwrite=True,
        )

        # Store connection information as JSON
        connection_info = {
            "agent_arn": launch_result.agent_arn,
            "agent_id": launch_result.agent_id,
            "region": region,
            "package_name": "awslabs.aws-api-mcp-server",
            "deployment_type": "public_package",
            "execution_role_arn": execution_role_arn,
        }

        ssm_client.put_parameter(
            Name="/coa/components/aws_api_mcp/connection_info",
            Value=json.dumps(connection_info, indent=2),
            Type="String",
            Description="Complete connection information for AWS API MCP server",
            Overwrite=True,
        )

        print("✓ Component configuration stored in Parameter Store")
        print("  Agent ARN: /coa/components/aws_api_mcp/agent_arn")
        print("  Agent ID: /coa/components/aws_api_mcp/agent_id")
        print("  Execution Role: /coa/components/aws_api_mcp/execution_role_arn")
        print("  Connection Info: /coa/components/aws_api_mcp/connection_info")

    except Exception as e:
        print(f"❌ Failed to store configuration: {e}")
        # Don't fail deployment for parameter storage issues
        print("⚠️ Continuing despite parameter storage failure...")

    print("\n🎉 Deployment completed successfully!")
    print("=" * 80)
    print(f"Agent ARN: {launch_result.agent_arn}")
    print(f"Agent ID: {launch_result.agent_id}")
    print(f"Execution Role: {execution_role_arn}")
    print("Package: awslabs.aws-api-mcp-server")
    print("Deployment Type: public_package")
    print("\nThe AWS API MCP Server is now deployed and ready!")
    print("It uses the shared Cognito user pool for authentication.")
    print("It uses the BedrockAgentCoreRuntimeRole from the COA CloudFormation stack.")
    print("Configuration stored in Parameter Store under /coa/components/aws_api_mcp/*")


if __name__ == "__main__":
    main()