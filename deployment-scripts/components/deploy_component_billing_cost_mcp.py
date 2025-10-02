#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Deploy Billing and Cost Management MCP Server to Amazon Bedrock AgentCore Runtime
Uses shared Cognito user pool for authentication
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

# Import our shared Cognito utilities
from cognito_utils import get_shared_cognito_client


def prepare_deployment_files():
    """Prepare the deployment files for the Billing Cost Management MCP Server"""
    print("Preparing deployment files...")

    # Source directory
    source_dir = Path("mcp-servers/billing-cost-management-mcp-server")
    if not source_dir.exists():
        print(f"❌ Source directory {source_dir} not found")
        return False

    # Create deployment directory
    deploy_dir = Path("build/billing-cost-mcp-deploy")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.mkdir()

    # Copy the awslabs package
    shutil.copytree(source_dir / "awslabs", deploy_dir / "awslabs")

    # Copy pyproject.toml and fastmcp.json
    shutil.copy2(source_dir / "pyproject.toml", deploy_dir / "pyproject.toml")
    shutil.copy2(source_dir / "fastmcp.json", deploy_dir / "fastmcp.json")

    # Create AgentCore-compatible server entrypoint
    server_py_content = '''#!/usr/bin/env python3
"""
Entrypoint for Billing and Cost Management MCP Server - AgentCore Compatible
"""
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set default AWS region if not set
if not os.environ.get("AWS_REGION"):
    os.environ["AWS_REGION"] = "us-east-1"

# Import the main server module
from awslabs.billing_cost_management_mcp_server.server import mcp, setup
import asyncio

async def initialize_server():
    """Initialize the MCP server with all tools and prompts."""
    await setup()

if __name__ == "__main__":
    # Initialize the server
    asyncio.run(initialize_server())
    
    # Run the MCP server with streamable HTTP for AgentCore compatibility
    mcp.run(transport="streamable-http", host="0.0.0.0", stateless_http=True)
'''

    with open(deploy_dir / "server.py", "w") as f:
        f.write(server_py_content)

    # Create requirements.txt from pyproject.toml dependencies
    requirements_content = """loguru>=0.7.0
mcp[cli]>=1.11.0
pydantic>=2.10.6
fastmcp>=2.0.0
boto3>=1.34.0
python-dotenv>=1.0.0
"""

    with open(deploy_dir / "requirements.txt", "w") as f:
        f.write(requirements_content)

    print(f"✓ Deployment files prepared in {deploy_dir}")
    return True


def main():
    print("🚀 Starting Billing and Cost Management MCP Server Deployment")
    print("Using Shared Cognito User Pool")
    print("=" * 70)

    # Prepare deployment files
    if not prepare_deployment_files():
        sys.exit(1)

    # Change to deployment directory
    os.chdir("build/billing-cost-mcp-deploy")

    # Check required files
    required_files = ["server.py", "requirements.txt", "awslabs"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file/directory {file} not found")
            sys.exit(1)
    print("✓ All required files found")

    # Get AWS region
    boto_session = Session()
    region = boto_session.region_name
    print(f"✓ Using AWS region: {region}")

    # Get shared Cognito configuration from Parameter Store
    print("\n📋 Getting shared Cognito configuration from Parameter Store...")
    try:
        cognito_client = get_shared_cognito_client(
            region=region, use_parameter_store=True
        )

        # Get authentication configuration for AgentCore
        auth_config = cognito_client.get_auth_config_for_agentcore()

        print("✓ Shared Cognito configuration retrieved from Parameter Store")
        print(f"  User Pool ID: {cognito_client.get_user_pool_id()}")
        print(f"  MCP Client ID: {cognito_client.get_mcp_server_client_id()}")

    except Exception as e:
        print(f"❌ Failed to get shared Cognito configuration: {e}")
        print("Make sure the shared Cognito infrastructure is deployed first:")
        print("  python deployment-scripts/deploy_shared_cognito.py --create-test-user")
        print(
            "This will create the required parameters in Parameter Store at /coa/cognito/*"
        )
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
            agent_name="billing_cost_mcp_server",
        )
        
        # Debug: Check what attributes the response has
        print(f"Response type: {type(response)}")
        print(f"Response attributes: {dir(response)}")
        
        # Try to access the response content properly
        if hasattr(response, 'message'):
            print(f"Configuration message: {response.message}")
        elif hasattr(response, 'status'):
            print(f"Configuration status: {response.status}")
        else:
            print(f"Configuration response: {response}")
        
        print("✓ Configuration completed")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        sys.exit(1)

    # Launch to AgentCore Runtime
    print("\n🚀 Launching Billing Cost Management MCP server to AgentCore Runtime...")
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

    # Store component-specific configuration
    print("\n💾 Storing component configuration...")
    try:
        ssm_client = boto3.client("ssm", region_name=region)

        # Store Agent ARN in component-specific path
        ssm_client.put_parameter(
            Name="/coa/components/billing_cost_mcp/agent_arn",
            Value=launch_result.agent_arn,
            Type="String",
            Description="Agent ARN for Billing Cost Management MCP server",
            Overwrite=True,
        )

        ssm_client.put_parameter(
            Name="/coa/components/billing_cost_mcp/agent_id",
            Value=launch_result.agent_id,
            Type="String",
            Description="Agent ID for Billing Cost Management MCP server",
            Overwrite=True,
        )

        # Store additional metadata
        ssm_client.put_parameter(
            Name="/coa/components/billing_cost_mcp/deployment_type",
            Value="custom_build",
            Type="String",
            Description="Deployment type for Billing Cost Management MCP server",
            Overwrite=True,
        )

        ssm_client.put_parameter(
            Name="/coa/components/billing_cost_mcp/region",
            Value=region,
            Type="String",
            Description="AWS region for Billing Cost Management MCP server",
            Overwrite=True,
        )

        # Store connection information as JSON
        connection_info = {
            "agent_arn": launch_result.agent_arn,
            "agent_id": launch_result.agent_id,
            "user_pool_id": cognito_client.get_user_pool_id(),
            "mcp_client_id": cognito_client.get_mcp_server_client_id(),
            "region": region,
            "deployment_type": "custom_build",
            "source_directory": "billing-cost-management-mcp-server",
        }

        ssm_client.put_parameter(
            Name="/coa/components/billing_cost_mcp/connection_info",
            Value=json.dumps(connection_info, indent=2),
            Type="String",
            Description="Complete connection information for Billing Cost Management MCP server",
            Overwrite=True,
        )

        print("✓ Component configuration stored in Parameter Store")
        print("  Agent ARN: /coa/components/billing_cost_mcp/agent_arn")
        print("  Agent ID: /coa/components/billing_cost_mcp/agent_id")
        print("  Connection Info: /coa/components/billing_cost_mcp/connection_info")

    except Exception as e:
        print(f"❌ Failed to store configuration: {e}")
        # Don't fail deployment for parameter storage issues
        print("⚠️ Continuing despite parameter storage failure...")

    print("\n🎉 Deployment completed successfully!")
    print("=" * 70)
    print(f"Agent ARN: {launch_result.agent_arn}")
    print(f"Agent ID: {launch_result.agent_id}")
    print(f"Shared User Pool ID: {cognito_client.get_user_pool_id()}")
    print(f"MCP Client ID: {cognito_client.get_mcp_server_client_id()}")
    print("Deployment Type: custom_build")
    print("\nThe Billing and Cost Management MCP Server is now deployed and ready!")
    print("It uses the shared Cognito user pool for authentication.")
    print(
        "Configuration stored in Parameter Store under /coa/components/billing_cost_mcp/*"
    )
    print("\nAvailable tools:")
    print("  - cost-explorer: Historical cost and usage data")
    print("  - compute-optimizer: Performance optimization recommendations")
    print("  - cost-optimization: Cost optimization recommendations")
    print("  - storage-lens: S3 Storage Lens metrics")
    print("  - pricing: AWS service pricing information")
    print("  - budget: AWS budget information")
    print("  - cost-anomaly: Cost anomaly detection")
    print("  - And many more cost management tools...")


if __name__ == "__main__":
    main()