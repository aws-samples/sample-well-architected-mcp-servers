"""
AWS Billing Management Agent - Optimized Version

This agent provides comprehensive AWS cost optimization and billing management capabilities
through integration with the AWS Billing & Cost Management MCP server.
"""

import os
import sys
import logging
import boto3
from typing import Optional, Dict, Any
from functools import lru_cache
# Removed contextmanager import as it's no longer needed

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
DEFAULT_AWS_REGION = "us-east-1"
MCP_SERVER_COMMAND = "awslabs.billing-cost-management-mcp-server"
WORKING_DIR = "/tmp/aws-billing-mcp/workdir"

# System prompt optimized for cost management and billing
SYSTEM_PROMPT = """You are an AWS Cost Optimization and Billing Management Expert. Use the available MCP tools to provide data-driven cost analysis and optimization recommendations.

## Available MCP Tools

### Cost Explorer
- cost_explorer: Retrieve cost and usage data with filtering and grouping options
- cost_comparison: Compare costs between two time periods to identify changes
- cost_anomaly: Detect and analyze cost anomalies in your AWS spending

### Reservations & Savings Plans
- ri_performance: Analyze Reserved Instance coverage and utilization
- sp_performance: Monitor Savings Plans utilization and coverage
- rec_details: Get detailed cost optimization recommendations with savings estimates

### Budget & Free Tier
- budgets: List and analyze AWS budgets with actual vs forecasted spending
- free_tier_usage: Monitor Free Tier usage limits and remaining allowances

### Cost Optimization
- cost_optimization: Get cost optimization recommendations from Cost Optimization Hub
- compute_optimizer: Retrieve rightsizing recommendations for EC2, EBS, Lambda, RDS

### Pricing & Analysis
- aws_pricing: Get AWS service pricing information and cost calculations
- bcm_pricing_calc: Access Pricing Calculator workload estimates
- storage_lens: Run advanced S3 storage analytics queries

### Session Data
- session_sql: Query cost data stored in session database for complex analysis

Always quantify savings opportunities with specific dollar amounts and provide actionable implementation steps.
"""


class AWSBillingAgentError(Exception):
    """Custom exception for AWS Billing Agent errors."""
    pass


# Removed duplicate functions - now using shared utilities from aws_cross_account_utils


@lru_cache(maxsize=1)
def get_bedrock_model(model_id: str = DEFAULT_MODEL_ID) -> BedrockModel:
    """Get cached Bedrock model instance."""
    return BedrockModel(model_id=model_id)


def create_mcp_client(role_arn=None, external_id=None, session_name=None, custom_env=None):
    """Create MCP client with proper configuration and cross-account support."""
    try:
        env = get_environment_config(
            role_arn=role_arn,
            external_id=external_id,
            session_name=session_name,
            custom_env=custom_env,
            default_session_name="aws-billing-agent",
            working_dir=WORKING_DIR
        )
        return MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command=MCP_SERVER_COMMAND,
                    args=[],
                    env=env,
                )
            )
        )
    except Exception as e:
        logger.error(f"MCP client error: {e}")
        raise AWSBillingAgentError(f"Failed to initialize MCP client: {e}")


def validate_query(query: str) -> str:
    """Validate and sanitize the input query."""
    if not query or not query.strip():
        raise AWSBillingAgentError("Query cannot be empty")
    
    # Basic sanitization
    query = query.strip()
    
    # Length validation
    if len(query) > 10000:  # Reasonable limit
        raise AWSBillingAgentError("Query too long. Please provide a more concise request.")
    
    return query


@tool
def aws_billing_management_agent(query: str, env=None, role_arn=None, account_id=None, external_id=None, session_name=None) -> str:
    """
    Advanced AWS Cost Optimization and Billing Management Agent with cross-account support.
    
    This agent provides comprehensive AWS cost analysis, optimization recommendations,
    and billing management capabilities through integration with AWS Cost Explorer,
    Budgets, Compute Optimizer, and other cost management services.

    Args:
        query: User's question about AWS costs, billing, optimization, or financial management
        env: Optional environment variables dictionary
        role_arn: Optional ARN of the role to assume for cross-account access
        account_id: Optional AWS account ID (will construct role ARN as arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole)
        external_id: Optional external ID for enhanced security when assuming roles
        session_name: Optional session name for the assumed role (defaults to 'aws-billing-agent')

    Returns:
        Detailed analysis and actionable recommendations for AWS cost optimization

    Raises:
        AWSBillingAgentError: For agent-specific errors
        
    Note:
        If both role_arn and account_id are provided, role_arn takes precedence.
        If only account_id is provided, the role ARN will be constructed as:
        arn:aws:iam::ACCOUNT_ID:role/COAReadOnlyRole
    """
    try:
        # Validate input
        validated_query = validate_query(query)
        logger.info(f"Processing billing query: {validated_query[:100]}...")
        
        # Handle cross-account parameters using shared utilities
        cross_account_config = handle_cross_account_parameters(
            role_arn=role_arn,
            account_id=account_id,
            external_id=external_id,
            session_name=session_name,
            default_session_name="aws-billing-agent"
        )
        
        resolved_role_arn = cross_account_config["role_arn"]
        
        # Get cached model
        bedrock_model = get_bedrock_model()
        
        # Create MCP client with cross-account support
        mcp_server = create_mcp_client(
            role_arn=resolved_role_arn,
            external_id=external_id,
            session_name=cross_account_config["session_name"],
            custom_env=env
        )
        
        with mcp_server:
            # Get available tools
            tools = mcp_server.list_tools_sync()
            logger.info(f"Available MCP tools: {len(tools)}")
            
            # Create optimized agent
            mcp_agent = Agent(
                model=bedrock_model,
                system_prompt=SYSTEM_PROMPT,
                tools=tools,
            )
            
            # Process query
            response = mcp_agent(validated_query)
            
            # Extract response content
            if hasattr(response, 'message') and response.message:
                if isinstance(response.message, dict):
                    content = response.message.get('content', [])
                    if content and isinstance(content, list) and len(content) > 0:
                        return content[0].get('text', str(response))
                return str(response.message)
            
            # Log successful completion using shared utility
            log_cross_account_success(resolved_role_arn, "billing operations")
            
            return str(response)
                
    except AWSBillingAgentError:
        # Re-raise custom errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error in billing agent: {e}")
        error_msg = str(e)
        
        # Use shared utility for cross-account error formatting
        if "AssumeRole" in error_msg or "AccessDenied" in error_msg or "NoCredentialsError" in error_msg:
            return format_cross_account_error(error_msg)
        else:
            return (
                f"I encountered an error while processing your AWS billing query: {str(e)}\n\n"
                "Please try:\n"
                "1. Rephrasing your question more specifically\n"
                "2. Breaking complex requests into smaller parts\n"
                "3. Checking if you have the necessary AWS permissions\n"
                "4. Verifying your AWS credentials are properly configured"
            )


def get_agent_info() -> Dict[str, Any]:
    """Get information about the agent's capabilities."""
    return {
        "name": "AWS Billing Management Agent",
        "version": "2.0.0",
        "description": "Advanced AWS cost optimization and billing management",
        "capabilities": [
            "Cost analysis and forecasting",
            "Reservation and Savings Plans optimization",
            "Budget management and monitoring",
            "Cost anomaly detection",
            "Service-specific optimization recommendations",
            "Compute Optimizer integration",
            "Storage analytics and optimization"
        ],
        "supported_services": [
            "Cost Explorer", "AWS Budgets", "Compute Optimizer",
            "Cost Optimization Hub", "AWS Pricing", "S3 Storage Lens"
        ]
    }


# Command-line interface and testing
if __name__ == "__main__":
    import argparse
    import signal
    import sys
    from threading import Timer
    
    def setup_argument_parser():
        """Set up command-line argument parser."""
        parser = argparse.ArgumentParser(
            description="AWS Billing Management Agent - Cost Optimization and Billing Analysis",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Test with a simple cost query
  python3 aws_billing_management_agent.py --prompt "Show me my EC2 costs for last month"
  
  # Test EBS optimization
  python3 aws_billing_management_agent.py --prompt "Analyze my EBS volumes for cost optimization opportunities"
  
  # Test Reserved Instance recommendations
  python3 aws_billing_management_agent.py --prompt "Provide Reserved Instance purchase recommendations"
  
  # Interactive mode (default)
  python3 aws_billing_management_agent.py
            """
        )
        
        parser.add_argument(
            "--prompt", "-p",
            type=str,
            help="Cost optimization or billing query to test with the agent"
        )
        
        parser.add_argument(
            "--timeout", "-t",
            type=int,
            default=60,
            help="Timeout in seconds for agent execution (default: 60)"
        )
        
        parser.add_argument(
            "--info", "-i",
            action="store_true",
            help="Show agent information and capabilities"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output with detailed logging"
        )
        
        return parser
    
    def run_agent_with_prompt(prompt: str, timeout: int = 60, verbose: bool = False):
        """Run the agent with a specific prompt."""
        
        print("=" * 60)
        print("AWS BILLING MANAGEMENT AGENT - PROMPT TEST")
        print("=" * 60)
        
        if verbose:
            print(f"Prompt: {prompt}")
            print(f"Timeout: {timeout} seconds")
            print(f"Verbose mode: {verbose}")
            print()
        
        # Set up timeout handler
        timeout_occurred = False
        
        def timeout_handler():
            nonlocal timeout_occurred
            timeout_occurred = True
            print(f"\n⚠️  Execution timed out after {timeout} seconds!")
            print("This may be due to:")
            print("1. MCP server taking longer than expected")
            print("2. Complex query requiring more processing time")
            print("3. Network connectivity issues")
            print("4. AWS API rate limiting")
            os._exit(1)
        
        timer = Timer(timeout, timeout_handler)
        timer.start()
        
        try:
            print("🚀 Executing agent with your prompt...")
            print()
            
            # Execute the agent
            result = aws_billing_management_agent(prompt)
            
            # Cancel timeout if successful
            timer.cancel()
            
            print("✅ AGENT EXECUTION SUCCESSFUL!")
            print("=" * 60)
            print("RESULT:")
            print("=" * 60)
            print(result)
            print("=" * 60)
            
            return True
            
        except KeyboardInterrupt:
            timer.cancel()
            print("\n⚠️  Interrupted by user (Ctrl+C)")
            return False
            
        except AWSBillingAgentError as e:
            timer.cancel()
            print(f"\n❌ Agent Error: {e}")
            return False
            
        except Exception as e:
            timer.cancel()
            print(f"\n❌ Unexpected Error: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def run_interactive_mode():
        """Run the agent in interactive mode."""
        
        print("AWS Billing Management Agent - Interactive Mode")
        print("=" * 50)
        print(f"Agent Info: {get_agent_info()}")
        print("\n⚠️  Note: MCP server communication may take time on first run.")
        print("Press Ctrl+C to exit at any time.\n")
        
        # Default test queries
        test_queries = [
            "What are the main AWS cost optimization strategies?",
            "Show me information about AWS cost management tools",
            "How can I optimize my EBS volume costs?",
            "Provide Reserved Instance recommendations for EC2"
        ]
        
        print("Available test queries:")
        for i, query in enumerate(test_queries, 1):
            print(f"  {i}. {query}")
        
        print("\nEnter a number (1-4) to use a test query, or type your own prompt:")
        
        try:
            user_input = input("> ").strip()
            
            if user_input.isdigit():
                query_num = int(user_input)
                if 1 <= query_num <= len(test_queries):
                    prompt = test_queries[query_num - 1]
                    print(f"\nUsing test query: {prompt}")
                else:
                    print("Invalid query number. Using default query.")
                    prompt = test_queries[0]
            elif user_input:
                prompt = user_input
            else:
                print("Using default query.")
                prompt = test_queries[0]
            
            return run_agent_with_prompt(prompt, timeout=60, verbose=True)
            
        except KeyboardInterrupt:
            print("\n\nExiting interactive mode.")
            return False
    
    def main():
        """Main entry point."""
        parser = setup_argument_parser()
        args = parser.parse_args()
        
        # Configure logging level
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Show agent info if requested
        if args.info:
            print("AWS Billing Management Agent Information")
            print("=" * 40)
            info = get_agent_info()
            for key, value in info.items():
                if isinstance(value, list):
                    print(f"{key.title()}:")
                    for item in value:
                        print(f"  - {item}")
                else:
                    print(f"{key.title()}: {value}")
            print()
            return
        
        # Run with prompt if provided
        if args.prompt:
            success = run_agent_with_prompt(args.prompt, args.timeout, args.verbose)
            sys.exit(0 if success else 1)
        
        # Otherwise run in interactive mode
        success = run_interactive_mode()
        sys.exit(0 if success else 1)
    
    # Run the main function
    main()


# Example usage for cross-account scenarios
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--examples":
    # Example 1: Same-account billing operations
    print("=== Same-Account Billing Operations ===")
    result1 = aws_billing_management_agent(
        "Show me my EC2 costs for the last month and identify optimization opportunities."
    )
    print(result1)
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: Cross-account billing operations using role_arn
    print("=== Cross-Account Billing Operations (using role_arn) ===")
    result2 = aws_billing_management_agent(
        "Analyze cost optimization opportunities across all services in the target account.",
        role_arn="arn:aws:iam::256358067059:role/COAReadOnlyRole",
        external_id="your-external-id-here",  # Replace with actual external ID if required
        session_name="aws-billing-cross-account-operations"
    )
    print(result2)
    
    print("\n" + "="*50 + "\n")
    
    # Example 3: Cross-account billing operations using account_id
    print("=== Cross-Account Billing Operations (using account_id) ===")
    result3 = aws_billing_management_agent(
        "Get Reserved Instance recommendations and analyze Savings Plans utilization.",
        account_id="123456789012",  # Will construct arn:aws:iam::123456789012:role/COAReadOnlyRole
        external_id="your-external-id-here",  # Replace with actual external ID if required
        session_name="aws-billing-cross-account-operations"
    )
    print(result3)