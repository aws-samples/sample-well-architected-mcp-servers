import os
import re
import boto3
from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient


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

@tool
def well_architected_security_agent(query: str, env=None, role_arn=None, account_id=None, external_id=None, session_name=None) -> str:
    """
    Process and respond to AWS security assessment queries using the Well-Architected Security MCP Server.

    Args:
        query: The user's security assessment question
        env: Optional environment variables dictionary
        role_arn: Optional ARN of the role to assume for cross-account access
        account_id: Optional AWS account ID (will construct role ARN as arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole)
        external_id: Optional external ID for enhanced security when assuming roles
        session_name: Optional session name for the assumed role (defaults to 'wa-security-agent')

    Returns:
        A comprehensive security assessment response addressing the user's query
        
    Note:
        If both role_arn and account_id are provided, role_arn takes precedence.
        If only account_id is provided, the role ARN will be constructed as:
        arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole
    """

    bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")

    response = str()
    print("debug", query, env, role_arn, account_id, external_id, session_name)
    
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
        if env is None:
            env = {}
            
        # Configure AssumeRole environment variables for the MCP server
        if role_arn is not None:
            # Validate role ARN format
            if not validate_role_arn(role_arn):
                raise ValueError(f"Invalid role ARN format: {role_arn}. Expected format: arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME")
                
            print(f"Configuring cross-account access to: {role_arn}")
            env["AWS_ASSUME_ROLE_ARN"] = role_arn
            env["AWS_ASSUME_ROLE_SESSION_NAME"] = session_name or "wa-security-agent"
            
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
            print("Using same-account assessment (no AssumeRole configured)")

        # Set standard AWS environment variables
        if os.getenv("AWS_REGION") is not None:
            env["AWS_REGION"] = os.getenv("AWS_REGION")
        else:
            env["AWS_REGION"] = "us-east-1"  # Default region
            
        if os.getenv("BEDROCK_LOG_GROUP_NAME") is not None:
            env["BEDROCK_LOG_GROUP_NAME"] = os.getenv("BEDROCK_LOG_GROUP_NAME")
            
        # Set MCP server log level for debugging
        env["FASTMCP_LOG_LEVEL"] = os.getenv("FASTMCP_LOG_LEVEL", "INFO")
        
        # Use local MCP server from the src directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # The MCP server is now located in the same directory under src/
        mcp_server_path = current_dir
        mcp_server_script = os.path.join(current_dir, "src", "server.py")
        
        # Ensure Python path includes the MCP server source
        src_path = os.path.join(mcp_server_path, "src")
        python_path = env.get("PYTHONPATH", "")
        if python_path:
            env["PYTHONPATH"] = f"{src_path}:{mcp_server_path}:{python_path}"
        else:
            env["PYTHONPATH"] = f"{src_path}:{mcp_server_path}"
        
        print("MCP server environment:", {k: v for k, v in env.items() if not k.startswith("AWS_SECRET")})
        
        if not os.path.exists(mcp_server_script):
            raise FileNotFoundError(
                f"Local MCP server not found at: {mcp_server_script}\n"
                f"Current working directory: {os.getcwd()}\n"
                f"Agent file location: {current_dir}\n"
                f"Expected MCP server at: {mcp_server_script}"
            )
            
        print(f"Using local MCP server: {mcp_server_script}")
        print(f"MCP server working directory: {mcp_server_path}")
        
        # Determine the Python command to use
        python_cmd = "python"
        
        # Check if there's a virtual environment in the MCP server directory
        venv_python = os.path.join(mcp_server_path, ".venv", "bin", "python")
        if os.path.exists(venv_python):
            python_cmd = venv_python
            print(f"Using virtual environment Python: {venv_python}")
        else:
            print(f"Using system Python: {python_cmd}")
        
        mcp_server = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command=python_cmd,
                    args=[mcp_server_script],
                    env=env,
                    cwd=mcp_server_path,  # Set working directory to MCP server root
                )
            )
        )

        with mcp_server:

            tools = mcp_server.list_tools_sync()
            # Create the security assessment agent with comprehensive capabilities
            mcp_agent = Agent(
                model=bedrock_model,
                system_prompt="""You are an AWS Security Assessment Assistant with access to comprehensive security analysis tools through the Well-Architected Security MCP Server.

## Core Capabilities
- **Cross-Account Security Assessment**: Analyze security posture across multiple AWS accounts using AssumeRole
- **Multi-Service Security Analysis**: Evaluate GuardDuty, Security Hub, Inspector, Access Analyzer, Trusted Advisor, and Macie
- **Compliance Framework Assessment**: Check against AWS Foundational Security Best Practices and CIS benchmarks
- **Data Protection Analysis**: Assess encryption at rest and in transit across all storage and network services
- **Security Finding Prioritization**: Retrieve and analyze findings by severity and business impact
- **Well-Architected Framework Alignment**: Provide recommendations based on Security Pillar best practices

## Enhanced Tool Usage Guidelines

### 1. Credential Validation
- **Always start** with `ValidateCredentialConfiguration` to verify access and identify the target account
- This confirms whether cross-account AssumeRole is configured and working properly

### 2. Security Service Assessment
- Use `CheckSecurityServices` to evaluate which security services are enabled
- Check multiple services in one call: `["guardduty", "securityhub", "inspector", "accessanalyzer", "trustedadvisor", "macie"]`
- Store results in context with `store_in_context: true` for efficient subsequent calls

### 3. Data Protection Analysis
- **Storage Security**: Use `CheckStorageEncryption` for S3, EBS, RDS, DynamoDB, EFS, ElastiCache
- **Network Security**: Use `CheckNetworkSecurity` for ELB, VPC, API Gateway, CloudFront
- Focus on non-compliant resources with `include_unencrypted_only` or `include_non_compliant_only`

### 4. Security Findings Analysis
- Use `GetSecurityFindings` for each enabled security service
- Filter by severity: `"HIGH"`, `"CRITICAL"`, `"MEDIUM"`, `"LOW"`
- Limit results with `max_findings` for focused analysis

### 5. Resource Discovery
- Use `ListServicesInRegion` to identify all AWS services in use
- This helps scope the security assessment to actual resources

## Cross-Account Assessment Workflow
1. **Validate Access**: Confirm AssumeRole configuration and target account access
2. **Service Discovery**: Identify which AWS services are deployed in the target account
3. **Security Service Status**: Check which security services are enabled
4. **Data Protection Assessment**: Analyze encryption and network security configurations
5. **Finding Analysis**: Retrieve and prioritize security findings by severity
6. **Compliance Mapping**: Map findings to compliance frameworks (CIS, AWS Foundational)

## Response Format Guidelines
- **Executive Summary**: Lead with overall security risk level and account identification
- **Account Context**: Clearly identify which account(s) were assessed
- **Service Status**: Summarize enabled/disabled security services
- **Critical Findings**: Highlight HIGH and CRITICAL severity issues first
- **Compliance Gaps**: Identify specific control failures and standards affected
- **Remediation Plan**: Provide prioritized action items with effort estimates
- **Resource Details**: Include specific ARNs, resource names, and configuration details

## Security Assessment Focus Areas
1. **Identity and Access Management**: IAM policies, roles, and access patterns
2. **Data Protection**: Encryption at rest and in transit across all services
3. **Infrastructure Protection**: Network security, VPC configuration, security groups
4. **Detective Controls**: Logging, monitoring, alerting, and security service enablement
5. **Incident Response**: Security finding management and response capabilities
6. **Compliance Posture**: Alignment with security frameworks and standards

## Cross-Account Considerations
- Always verify you're analyzing the correct account by checking account IDs in responses
- Be aware that different accounts may have different security service configurations
- Consider organizational security policies that may apply across multiple accounts
- Highlight any cross-account trust relationships or shared resources

When users request AWS security assessments, start with credential validation, then provide comprehensive analysis using all available tools. Focus on actionable insights with clear remediation guidance prioritized by risk and business impact.

""",
                tools=tools,
            )
            response = str(mcp_agent(query))
            print("\n\n")

        if len(response) > 0:
            # Log successful completion
            if role_arn:
                print(f"Successfully completed cross-account security assessment for: {role_arn}")
            else:
                print("Successfully completed same-account security assessment")
            return response

        return "I apologize, but I couldn't properly analyze your security question. Could you please rephrase or provide more specific details about what security aspects you'd like me to assess?"

    except Exception as e:
        error_msg = str(e)
        print(f"Error in security assessment: {error_msg}")
        
        # Provide more specific error guidance
        if "AssumeRole" in error_msg:
            return f"Cross-account access error: {error_msg}\n\nPlease verify:\n1. The target role ARN is correct\n2. The role trusts your current identity\n3. External ID matches (if required)\n4. Your current role has sts:AssumeRole permissions"
        elif "AccessDenied" in error_msg:
            return f"Permission error: {error_msg}\n\nPlease ensure your role has the necessary permissions for AWS security services (GuardDuty, Security Hub, Inspector, etc.)"
        else:
            return f"Error processing your security assessment query: {error_msg}\n\nPlease check your AWS credentials and network connectivity."



if __name__ == "__main__":
    # Example 1: Same-account security assessment
    print("=== Same-Account Security Assessment ===")
    result1 = well_architected_security_agent(
        "Perform a comprehensive security assessment of my AWS account, focusing on Security Hub findings and data encryption status."
    )
    print(result1)
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: Cross-account security assessment using role_arn
    print("=== Cross-Account Security Assessment (using role_arn) ===")
    result2 = well_architected_security_agent(
        "Assess the security posture of the target account, including all enabled security services and high-severity findings.",
        role_arn="arn:aws:iam::123456789012:role/COAReadOnlyRole",
        external_id="your-external-id-here",  # Replace with actual external ID if required
        session_name="wa-security-cross-account-assessment"
    )
    print(result2)
    
    print("\n" + "="*50 + "\n")
    
    # Example 3: Cross-account security assessment using account_id
    print("=== Cross-Account Security Assessment (using account_id) ===")
    result3 = well_architected_security_agent(
        "Assess the security posture of the target account, including all enabled security services and high-severity findings.",
        account_id="123456789012",  # Will construct arn:aws:iam::123456789012:role/COAReadOnlyRole
        external_id="your-external-id-here",  # Replace with actual external ID if required
        session_name="wa-security-cross-account-assessment"
    )
    print(result3)