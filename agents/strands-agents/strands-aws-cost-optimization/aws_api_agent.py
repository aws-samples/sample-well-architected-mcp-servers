import os
import subprocess
import boto3
import logging
from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Import shared utilities
from aws_cross_account_utils import (
    validate_role_arn,
    get_environment_config,
    handle_cross_account_parameters,
    format_cross_account_error,
    log_cross_account_success
)

# Set up logging
logger = logging.getLogger(__name__)


@tool
def aws_api_agent(query: str, env=None, role_arn=None, account_id=None, external_id=None, session_name=None) -> str:
    """
    Process and respond to AWS API and CLI related queries with comprehensive AWS service integration and cross-account support.

    Args:
        query: The user's question about AWS operations, CLI commands, or service management
        env: Optional environment variables dictionary
        role_arn: Optional ARN of the role to assume for cross-account access
        account_id: Optional AWS account ID (will construct role ARN as arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole)
        external_id: Optional external ID for enhanced security when assuming roles
        session_name: Optional session name for the assumed role (defaults to 'aws-api-agent')

    Returns:
        A helpful response addressing user query with specific AWS CLI commands and guidance
        
    Note:
        If both role_arn and account_id are provided, role_arn takes precedence.
        If only account_id is provided, the role ARN will be constructed as:
        arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole
    """

    bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")

    response = str()
    logger.debug(f"AWS API agent called with: query={query[:100]}..., role_arn={role_arn}, account_id={account_id}")
    
    # Basic validation before proceeding
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_server_script = os.path.join(current_dir, "api_src", "server.py")
    
    if not os.path.exists(mcp_server_script):
        return f"Local MCP server not found at: {mcp_server_script}\n\nPlease ensure the AWS API MCP server files are properly installed in the src/ directory."
    
    # Handle cross-account parameters using shared utilities
    cross_account_config = handle_cross_account_parameters(
        role_arn=role_arn,
        account_id=account_id,
        external_id=external_id,
        session_name=session_name,
        default_session_name="aws-api-agent"
    )
    
    resolved_role_arn = cross_account_config["role_arn"]

    try:
        # Get environment configuration using the shared utility
        env_config = get_environment_config(
            role_arn=resolved_role_arn,
            external_id=external_id,
            session_name=cross_account_config["session_name"],
            custom_env=env,
            default_session_name="aws-api-agent",
            working_dir="/tmp/aws-api-mcp/workdir"
        )
        
        # Ensure Python path includes the MCP server source
        src_path = os.path.join(current_dir, "api_src")
        python_path = env_config.get("PYTHONPATH", "")
        if python_path:
            env_config["PYTHONPATH"] = f"{src_path}:{current_dir}:{python_path}"
        else:
            env_config["PYTHONPATH"] = f"{src_path}:{current_dir}"
        
        # Define MCP server command
        current_dir = os.path.dirname(os.path.abspath(__file__))
        import sys
        MCP_SERVER_COMMAND = sys.executable  # Use current Python interpreter
        
        # Initialize MCP client with cleaner pattern
        try:
            mcp_server = MCPClient(
                lambda: stdio_client(
                    StdioServerParameters(
                        command=MCP_SERVER_COMMAND,
                        args=["-m", "api_src"],  # Run as module
                        env=env_config,
                        cwd=current_dir,  # Set working directory to agent root
                    )
                )
            )
            print("✅ MCP client created successfully")
        except Exception as e:
            logger.error(f"MCP client error: {e}")
            raise Exception(f"Failed to create MCP client: {e}")

        try:
            with mcp_server:
                tools = mcp_server.list_tools_sync()
                # Create the AWS API agent with comprehensive AWS CLI capabilities and cross-account support
                mcp_agent = Agent(
                    model=bedrock_model,
                    system_prompt="""You are an AWS Operations Assistant with access to AWS CLI functionality through two specialized tools:

1. **call_aws**: Execute specific AWS CLI commands when you know the exact syntax
2. **suggest_aws_commands**: Get command suggestions when requests are unclear or you need options

Use call_aws for specific operations (list, describe, create, delete) with clear parameters.
Use suggest_aws_commands for ambiguous requests or when exploring multiple approaches.

Always verify account context, explain business impact, and provide actionable recommendations.""",
                tools=tools,
                )
                response = str(mcp_agent(query))
                print("\n\n")
        
        except Exception as mcp_error:
            print(f"MCP server connection or execution error: {mcp_error}")
            raise Exception(f"MCP server error: {mcp_error}")

        if len(response) > 0:
            # Log successful completion using shared utility
            log_cross_account_success(resolved_role_arn, "AWS operations")
            return response

        return "I apologize, but I couldn't properly analyze your AWS request. Could you please rephrase or provide more context about what AWS operation you'd like to perform?"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in AWS operations: {error_msg}")
        
        # Use shared utility for cross-account error formatting
        formatted_error = format_cross_account_error(error_msg)
        
        # Add specific error guidance for API agent
        if "FileNotFoundError" in error_msg and "server.py" in error_msg:
            return f"Local MCP server error: {error_msg}\n\nThe local AWS API MCP server could not be found. Please ensure:\n1. The src/server.py file exists in the agent directory\n2. All required dependencies are installed\n3. The Python environment is properly configured"
        elif "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
            return f"Dependency error: {error_msg}\n\nMissing required dependencies. Please:\n1. Install dependencies: pip install -r requirements.txt\n2. Ensure FastMCP and other required packages are available\n3. Check that the Python environment is properly configured"
        elif "AssumeRole" in error_msg or "AccessDenied" in error_msg or "NoCredentialsError" in error_msg:
            return formatted_error
        else:
            return f"Error processing your AWS query: {error_msg}\n\nPlease check:\n1. AWS credentials and network connectivity\n2. Local MCP server configuration\n3. Required dependencies are installed\n\nFor detailed diagnostics, try using the 'validate_credential_configuration' tool."


if __name__ == "__main__":
    # Example 1: Same-account AWS operations
    print("=== Same-Account AWS Operations ===")
    result1 = aws_api_agent(
        "List all EC2 instances in us-east-1 region and show their current status."
    )
    print(result1)
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: Cross-account AWS operations using role_arn
    print("=== Cross-Account AWS Operations (using role_arn) ===")
    result2 = aws_api_agent(
        "List all S3 buckets in the target account and check their encryption status.",
        role_arn="arn:aws:iam::256358067059:role/COAReadOnlyRole",
        external_id="your-external-id-here",  # Replace with actual external ID if required
        session_name="aws-api-cross-account-operations"
    )
    print(result2)
    
    print("\n" + "="*50 + "\n")
    
    # Example 3: Cross-account AWS operations using account_id
    print("=== Cross-Account AWS Operations (using account_id) ===")
    result3 = aws_api_agent(
        "Get the current caller identity and list all IAM roles in the target account.",
        account_id="123456789012",  # Will construct arn:aws:iam::123456789012:role/COAReadOnlyRole
        external_id="your-external-id-here",  # Replace with actual external ID if required
        session_name="aws-api-cross-account-operations"
    )
    print(result3)