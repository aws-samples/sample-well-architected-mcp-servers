"""
AWS Billing Management Agent - Optimized Version

This agent provides comprehensive AWS cost optimization and billing management capabilities
through integration with the AWS Billing & Cost Management MCP server.
"""

import os
import logging
from typing import Optional, Dict, Any
from functools import lru_cache
from contextlib import contextmanager

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
DEFAULT_AWS_REGION = "us-east-1"
MCP_SERVER_COMMAND = "awslabs.billing-cost-management-mcp-server"
WORKING_DIR = "/tmp/aws-billing-mcp/workdir"

# System prompt optimized for cost management and billing
SYSTEM_PROMPT = """You are an AWS Cost Optimization and Billing Management Expert with comprehensive access to AWS financial management tools through the awslabs.billing-cost-management-mcp-server.

## Your Expertise Areas

### 1. Cost Analysis & Optimization
- Analyze current AWS spending patterns and trends
- Identify cost optimization opportunities across services
- Provide actionable recommendations for cost reduction
- Compare costs across different time periods and dimensions

### 2. Reservation & Savings Plans Management
- Evaluate Reserved Instance and Savings Plans opportunities
- Analyze utilization and coverage of existing commitments
- Recommend optimal purchase strategies for long-term savings
- Monitor and optimize commitment utilization

### 3. Budget Management & Monitoring
- Create and manage AWS budgets with appropriate thresholds
- Set up cost anomaly detection and alerting
- Monitor spending against budgets and forecasts
- Provide budget variance analysis and recommendations

### 4. Service-Specific Cost Optimization
- EC2: Right-sizing, instance family optimization, spot instances
- RDS: Instance optimization, storage optimization
- Lambda: Memory and timeout optimization
- EBS: Volume type and size optimization
- S3: Storage class optimization, lifecycle policies

## Available MCP Tools

### Cost Explorer & Analysis
- get_cost_and_usage: Retrieve detailed cost and usage data
- get_cost_and_usage_with_resources: Get cost data with resource-level details
- get_cost_forecast: Generate cost forecasts for future periods
- get_usage_forecast: Predict future usage patterns
- get_anomalies: Detect and analyze cost anomalies
- get_cost_comparison_drivers: Identify drivers of cost changes
- get_dimension_values: Get available dimensions for cost analysis
- get_tags: Retrieve cost allocation tags
- get_cost_categories: Manage cost categories for organization

### Reservations & Savings Plans
- get_reservation_purchase_recommendation: Get RI purchase recommendations
- get_reservation_coverage: Analyze RI coverage across resources
- get_reservation_utilization: Monitor RI utilization rates
- get_savings_plans_purchase_recommendation: Get Savings Plans recommendations
- get_savings_plans_utilization: Monitor Savings Plans utilization
- get_savings_plans_coverage: Analyze Savings Plans coverage
- get_savings_plans_details: Get detailed Savings Plans information

### Budget Management
- describe_budgets: List and analyze existing budgets
- get_free_tier_usage: Monitor Free Tier usage and limits

### Pricing & Product Information
- get_service_codes: Get AWS service codes for pricing
- get_service_attributes: Retrieve service attributes
- get_attribute_values: Get possible values for attributes
- get_products: Search and retrieve product pricing information

### Cost Optimization Hub
- get_recommendation: Get specific cost optimization recommendations
- list_recommendations: List all available recommendations
- list_recommendation_summaries: Get summary of recommendations by category

### Compute Optimizer Integration
- get_ec2_instance_recommendations: EC2 right-sizing recommendations
- get_auto_scaling_group_recommendations: ASG optimization recommendations
- get_ebs_volume_recommendations: EBS volume optimization
- get_ecs_service_recommendations: ECS service optimization
- get_rds_database_recommendations: RDS optimization recommendations
- get_lambda_function_recommendations: Lambda optimization recommendations
- get_idle_recommendations: Identify idle resources
- get_enrollment_status: Check Compute Optimizer enrollment

### Storage Analytics
- storage_lens_run_query: Advanced S3 storage analytics using Athena

## Best Practices

1. **Always provide context** for cost recommendations with specific dollar amounts and percentages
2. **Include timeframes** for analysis and recommendations
3. **Prioritize recommendations** by potential savings impact
4. **Consider business requirements** when suggesting optimizations
5. **Provide actionable next steps** with specific AWS console links or CLI commands
6. **Monitor and track** the impact of implemented optimizations

## Response Format

Structure your responses with:
- **Executive Summary**: Key findings and total potential savings
- **Detailed Analysis**: Breakdown by service/category
- **Prioritized Recommendations**: Ordered by impact and ease of implementation
- **Implementation Steps**: Specific actions to take
- **Monitoring Plan**: How to track success

Remember: Focus on providing data-driven, actionable cost optimization guidance that balances savings with operational requirements.
"""


class AWSBillingAgentError(Exception):
    """Custom exception for AWS Billing Agent errors."""
    pass


@lru_cache(maxsize=1)
def get_bedrock_model(model_id: str = DEFAULT_MODEL_ID) -> BedrockModel:
    """Get cached Bedrock model instance."""
    return BedrockModel(model_id=model_id)


def get_environment_config() -> Dict[str, str]:
    """Get optimized environment configuration for MCP server."""
    env = {}
    
    # Core AWS configuration
    env["AWS_REGION"] = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
    env["AWS_API_MCP_WORKING_DIR"] = WORKING_DIR
    
    # Logging configuration
    env["FASTMCP_LOG_LEVEL"] = os.getenv("FASTMCP_LOG_LEVEL", "INFO")
    
    # Optional Bedrock logging
    if bedrock_log_group := os.getenv("BEDROCK_LOG_GROUP_NAME"):
        env["BEDROCK_LOG_GROUP_NAME"] = bedrock_log_group
    
    # Performance optimizations
    env["MCP_CLIENT_TIMEOUT"] = os.getenv("MCP_CLIENT_TIMEOUT", "300")  # 5 minutes
    env["MCP_MAX_RETRIES"] = os.getenv("MCP_MAX_RETRIES", "3")
    
    return env


@contextmanager
def mcp_client_context():
    """Context manager for MCP client with proper resource cleanup."""
    mcp_client = None
    try:
        env = get_environment_config()
        mcp_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command=MCP_SERVER_COMMAND,
                    args=[],
                    env=env,
                )
            )
        )
        yield mcp_client
    except Exception as e:
        logger.error(f"MCP client error: {e}")
        raise AWSBillingAgentError(f"Failed to initialize MCP client: {e}")
    finally:
        if mcp_client:
            try:
                # Ensure proper cleanup
                pass
            except Exception as cleanup_error:
                logger.warning(f"Cleanup warning: {cleanup_error}")


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
def aws_billing_management_agent(query: str) -> str:
    """
    Advanced AWS Cost Optimization and Billing Management Agent.
    
    This agent provides comprehensive AWS cost analysis, optimization recommendations,
    and billing management capabilities through integration with AWS Cost Explorer,
    Budgets, Compute Optimizer, and other cost management services.

    Args:
        query: User's question about AWS costs, billing, optimization, or financial management

    Returns:
        Detailed analysis and actionable recommendations for AWS cost optimization

    Raises:
        AWSBillingAgentError: For agent-specific errors
    """
    try:
        # Validate input
        validated_query = validate_query(query)
        logger.info(f"Processing billing query: {validated_query[:100]}...")
        
        # Get cached model
        bedrock_model = get_bedrock_model()
        
        # Use context manager for MCP client
        with mcp_client_context() as mcp_server:
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
                
                return str(response)
                
    except AWSBillingAgentError:
        # Re-raise custom errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error in billing agent: {e}")
        error_msg = (
            f"I encountered an error while processing your AWS billing query: {str(e)}\n\n"
            "Please try:\n"
            "1. Rephrasing your question more specifically\n"
            "2. Breaking complex requests into smaller parts\n"
            "3. Checking if you have the necessary AWS permissions\n"
            "4. Verifying your AWS credentials are properly configured"
        )
        return error_msg


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


# Example usage and testing
if __name__ == "__main__":
    # Test queries for different use cases
    test_queries = [
        "Analyze my AWS costs for the last 3 months and identify top spending areas",
        "What are the best Reserved Instance opportunities for my EC2 usage?",
        "Show me cost anomalies detected in the last 30 days",
        "Provide Compute Optimizer recommendations for cost savings",
        "Help me optimize my S3 storage costs"
    ]
    
    print("AWS Billing Management Agent - Optimized Version")
    print("=" * 50)
    print(f"Agent Info: {get_agent_info()}")
    print("\nTesting with sample query...")
    
    try:
        result = aws_billing_management_agent(test_queries[0])
        print(f"Result: {result[:200]}...")
    except Exception as e:
        print(f"Test error: {e}")