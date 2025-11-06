import os
import re
import subprocess
import boto3
import logging
from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Set up logging
logger = logging.getLogger(__name__)


def validate_role_arn(role_arn: str) -> bool:
    """
    Validate that the role ARN has the correct format.
    
    Args:
        role_arn: The role ARN to validate
        
    Returns:
        True if the ARN format is valid, False otherwise
    """
    if not role_arn:
        return False
        
    # AWS IAM role ARN pattern: arn:aws:iam::account-id:role/role-name
    pattern = r'^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@_-]+$'
    return bool(re.match(pattern, role_arn))

def get_environment_config(role_arn=None, external_id=None, session_name=None, custom_env=None):
    """
    Get environment configuration for MCP server with AWS credentials and cross-account setup.
    
    Args:
        role_arn: Optional ARN of the role to assume for cross-account access
        external_id: Optional external ID for enhanced security when assuming roles
        session_name: Optional session name for the assumed role
        custom_env: Optional custom environment variables to merge
        
    Returns:
        Dictionary of environment variables for MCP server
    """
    env = {}
    
    # Start with custom environment if provided
    if custom_env:
        env.update(custom_env)
    
    # Configure AssumeRole environment variables for the MCP server
    if role_arn is not None:
        if not validate_role_arn(role_arn):
            raise ValueError(f"Invalid role ARN format: {role_arn}. Expected format: arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME")
            
        print(f"Configuring cross-account access to: {role_arn}")
        env["AWS_ASSUME_ROLE_ARN"] = role_arn
        env["AWS_ASSUME_ROLE_SESSION_NAME"] = session_name or "aws-api-agent"
        
        if external_id is not None:
            env["AWS_ASSUME_ROLE_EXTERNAL_ID"] = external_id
            print(f"Using external ID for enhanced security")
            
        # Extract account ID from ARN for logging
        account_id = role_arn.split(':')[4]
        print(f"Target account ID: {account_id}")
    else:
        # Ensure AssumeRole environment variables are not set if not using cross-account
        env.pop("AWS_ASSUME_ROLE_ARN", None)
        env.pop("AWS_ASSUME_ROLE_SESSION_NAME", None)
        env.pop("AWS_ASSUME_ROLE_EXTERNAL_ID", None)
        print("Using same-account operations (no AssumeRole configured)")

    # Ensure AWS credentials are passed to the subprocess
    # This is critical for cross-account functionality to work
    aws_credential_vars = [
        'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
        'AWS_PROFILE', 'AWS_DEFAULT_PROFILE', 'AWS_REGION', 'AWS_DEFAULT_REGION',
        'AWS_CONFIG_FILE', 'AWS_SHARED_CREDENTIALS_FILE'
    ]
    
    for var in aws_credential_vars:
        if os.getenv(var) is not None:
            env[var] = os.getenv(var)
            print(f"Passing {var} to MCP server subprocess")
    
    # If no explicit credentials are set, try to extract from current session
    if not any(os.getenv(var) for var in ['AWS_ACCESS_KEY_ID', 'AWS_PROFILE']):
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials:
                env['AWS_ACCESS_KEY_ID'] = credentials.access_key
                env['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
                if credentials.token:
                    env['AWS_SESSION_TOKEN'] = credentials.token
                print("✅ Extracted credentials from current boto3 session")
            else:
                print("⚠️  No credentials found in current session")
        except Exception as cred_error:
            print(f"⚠️  Failed to extract credentials from session: {cred_error}")
    
    # Set standard AWS environment variables
    if not env.get("AWS_REGION"):
        env["AWS_REGION"] = os.getenv("AWS_REGION", "us-east-1")
        
    if os.getenv("BEDROCK_LOG_GROUP_NAME") is not None:
        env["BEDROCK_LOG_GROUP_NAME"] = os.getenv("BEDROCK_LOG_GROUP_NAME")
    
    # Set AWS API MCP server specific environment variables
    env["AWS_API_MCP_WORKING_DIR"] = "/tmp/aws-api-mcp/workdir"
    env["FASTMCP_LOG_LEVEL"] = os.getenv("FASTMCP_LOG_LEVEL", "INFO")
    
    # Ensure Python path includes the MCP server source
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(current_dir, "src")
    python_path = env.get("PYTHONPATH", "")
    if python_path:
        env["PYTHONPATH"] = f"{src_path}:{current_dir}:{python_path}"
    else:
        env["PYTHONPATH"] = f"{src_path}:{current_dir}"
    
    print("MCP server environment:", {k: v for k, v in env.items() if not k.startswith("AWS_SECRET")})
    
    return env


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
    print("debug", query, env, role_arn, account_id, external_id, session_name)
    
    # Basic validation before proceeding
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_server_script = os.path.join(current_dir, "src", "server.py")
    
    if not os.path.exists(mcp_server_script):
        return f"Local MCP server not found at: {mcp_server_script}\n\nPlease ensure the AWS API MCP server files are properly installed in the src/ directory."
    
    # Handle account_id parameter - construct role ARN if needed
    if account_id is not None and role_arn is None:
        # Validate account_id format (12-digit number)
        if not account_id.isdigit() or len(account_id) != 12:
            raise ValueError(f"Invalid account ID format: {account_id}. Expected 12-digit number.")
        
        role_arn = f"arn:aws:iam::{account_id}:role/COAReadOnlyRole"
        print(f"Constructed role ARN from account ID: {role_arn}")
    elif account_id is not None and role_arn is not None:
        print(f"Both role_arn and account_id provided. Using role_arn: {role_arn}")
        print(f"Ignoring account_id: {account_id}")
    
    # Get current identity for debugging
    sts_client = boto3.client('sts')
    current_identity = sts_client.get_caller_identity()
    print("Current identity:", current_identity)

    try:
        # Get environment configuration using the centralized function
        env_config = get_environment_config(
            role_arn=role_arn,
            external_id=external_id,
            session_name=session_name,
            custom_env=env
        )
        
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
                        args=["-m", "src"],  # Run as module
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
            # Log successful completion
            if role_arn:
                print(f"Successfully completed cross-account AWS operations for: {role_arn}")
            else:
                print("Successfully completed same-account AWS operations")
            return response

        return "I apologize, but I couldn't properly analyze your AWS request. Could you please rephrase or provide more context about what AWS operation you'd like to perform?"

    except Exception as e:
        error_msg = str(e)
        print(f"Error in AWS operations: {error_msg}")
        
        # Provide more specific error guidance
        if "AssumeRole" in error_msg:
            return f"Cross-account access error: {error_msg}\n\nPlease verify:\n1. The target role ARN is correct\n2. The role trusts your current identity\n3. External ID matches (if required)\n4. Your current role has sts:AssumeRole permissions"
        elif "AccessDenied" in error_msg or "NoCredentialsError" in error_msg:
            return f"AWS credentials error: {error_msg}\n\nPlease ensure:\n1. AWS credentials are properly configured (run 'aws configure' or set environment variables)\n2. Your IAM user/role has the necessary permissions for AWS operations\n3. If using cross-account access, verify the AssumeRole configuration\n\nYou can use the 'validate_credential_configuration' tool to diagnose credential issues."
        elif "FileNotFoundError" in error_msg and "server.py" in error_msg:
            return f"Local MCP server error: {error_msg}\n\nThe local AWS API MCP server could not be found. Please ensure:\n1. The src/server.py file exists in the agent directory\n2. All required dependencies are installed\n3. The Python environment is properly configured"
        elif "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
            return f"Dependency error: {error_msg}\n\nMissing required dependencies. Please:\n1. Install dependencies: pip install -r requirements.txt\n2. Ensure FastMCP and other required packages are available\n3. Check that the Python environment is properly configured"
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