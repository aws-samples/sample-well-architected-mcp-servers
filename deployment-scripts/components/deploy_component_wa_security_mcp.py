#!/usr/bin/env python3
"""
Deploy Well-Architected Security MCP Server to Amazon Bedrock AgentCore Runtime
REFACTORED VERSION - Uses shared Cognito user pool
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
    """Prepare the deployment files for the WA Security MCP Server"""
    print("Preparing deployment files...")
    
    # Source directory
    source_dir = Path("mcp-servers/well-architected-security-mcp-server")
    if not source_dir.exists():
        print(f"❌ Source directory {source_dir} not found")
        return False
    
    # Create deployment directory
    deploy_dir = Path("wa-security-mcp-deploy")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.mkdir()
    
    # Copy the src package
    shutil.copytree(source_dir / "src", deploy_dir / "src")
    
    # Copy pyproject.toml
    shutil.copy2(source_dir / "pyproject.toml", deploy_dir / "pyproject.toml")
    
    # Create AgentCore-compatible server entrypoint
    server_py_content = '''#!/usr/bin/env python3
"""
Entrypoint for Well-Architected Security MCP Server - AgentCore Compatible
"""
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set default AWS region if not set
if not os.environ.get("AWS_REGION"):
    os.environ["AWS_REGION"] = "us-east-1"

# Create a new FastMCP instance with AgentCore-compatible settings
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "security-assessment-mcp-server",
    host="0.0.0.0",
    stateless_http=True,
    dependencies=[
        "boto3",
        "requests",
        "beautifulsoup4", 
        "pydantic",
        "loguru",
    ],
)

# Import and register all the tools manually
from src.util.network_security import check_network_security
from src.util.resource_utils import list_services_in_region
from src.util.security_services import (
    check_access_analyzer, check_guard_duty, check_inspector, check_macie, 
    check_security_hub, check_trusted_advisor, get_access_analyzer_findings,
    get_guardduty_findings, get_inspector_findings, get_macie_findings,
    get_securityhub_findings, get_trusted_advisor_findings,
)
from src.util.storage_security import check_storage_encryption

# Register the tools with the MCP server
mcp.tool()(check_network_security)
mcp.tool()(list_services_in_region)
mcp.tool()(check_access_analyzer)
mcp.tool()(check_guard_duty)
mcp.tool()(check_inspector)
mcp.tool()(check_macie)
mcp.tool()(check_security_hub)
mcp.tool()(check_trusted_advisor)
mcp.tool()(get_access_analyzer_findings)
mcp.tool()(get_guardduty_findings)
mcp.tool()(get_inspector_findings)
mcp.tool()(get_macie_findings)
mcp.tool()(get_securityhub_findings)
mcp.tool()(get_trusted_advisor_findings)
mcp.tool()(check_storage_encryption)

if __name__ == "__main__":
    # Run the MCP server with stateless HTTP for AgentCore compatibility
    mcp.run(transport="streamable-http")
'''
    
    with open(deploy_dir / "server.py", "w") as f:
        f.write(server_py_content)
    
    # Create requirements.txt from pyproject.toml dependencies
    requirements_content = '''mcp[server]>=1.7.1
boto3>=1.28.0
loguru>=0.7.0
pydantic>=2.0.0
fastapi>=0.100.0
'''
    
    with open(deploy_dir / "requirements.txt", "w") as f:
        f.write(requirements_content)
    
    print(f"✓ Deployment files prepared in {deploy_dir}")
    return True

def main():
    print("🚀 Starting Well-Architected Security MCP Server Deployment")
    print("Using Shared Cognito User Pool")
    print("=" * 60)
    
    # Prepare deployment files
    if not prepare_deployment_files():
        sys.exit(1)
    
    # Change to deployment directory
    os.chdir("wa-security-mcp-deploy")
    
    # Check required files
    required_files = ['server.py', 'requirements.txt', 'src']
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
            agent_name="wa_security_mcp_server"
        )
        print("✓ Configuration completed")
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        sys.exit(1)
    
    # Launch to AgentCore Runtime
    print("\n🚀 Launching WA Security MCP server to AgentCore Runtime...")
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
    
    # Store component-specific configuration
    print("\n💾 Storing component configuration...")
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        
        # Store Agent ARN in component-specific path
        ssm_client.put_parameter(
            Name='/coa/components/wa_security_mcp/agent_arn',
            Value=launch_result.agent_arn,
            Type='String',
            Description='Agent ARN for WA Security MCP server',
            Overwrite=True
        )
        
        ssm_client.put_parameter(
            Name='/coa/components/wa_security_mcp/agent_id',
            Value=launch_result.agent_id,
            Type='String',
            Description='Agent ID for WA Security MCP server',
            Overwrite=True
        )
        
        # Store additional metadata
        ssm_client.put_parameter(
            Name='/coa/components/wa_security_mcp/deployment_type',
            Value='custom_build',
            Type='String',
            Description='Deployment type for WA Security MCP server',
            Overwrite=True
        )
        
        ssm_client.put_parameter(
            Name='/coa/components/wa_security_mcp/region',
            Value=region,
            Type='String',
            Description='AWS region for WA Security MCP server',
            Overwrite=True
        )
        
        # Store connection information as JSON
        connection_info = {
            'agent_arn': launch_result.agent_arn,
            'agent_id': launch_result.agent_id,
            'user_pool_id': cognito_client.get_user_pool_id(),
            'mcp_client_id': cognito_client.get_mcp_server_client_id(),
            'region': region,
            'deployment_type': 'custom_build',
            'source_directory': 'well-architected-security-mcp-server'
        }
        
        ssm_client.put_parameter(
            Name='/coa/components/wa_security_mcp/connection_info',
            Value=json.dumps(connection_info, indent=2),
            Type='String',
            Description='Complete connection information for WA Security MCP server',
            Overwrite=True
        )
        
        print("✓ Component configuration stored in Parameter Store")
        print(f"  Agent ARN: /coa/components/wa_security_mcp/agent_arn")
        print(f"  Agent ID: /coa/components/wa_security_mcp/agent_id")
        print(f"  Connection Info: /coa/components/wa_security_mcp/connection_info")
        
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
    print(f"Deployment Type: custom_build")
    print("\nThe Well-Architected Security MCP Server is now deployed and ready!")
    print("It uses the shared Cognito user pool for authentication.")
    print("Configuration stored in Parameter Store under /coa/components/wa_security_mcp/*")

if __name__ == "__main__":
    main()