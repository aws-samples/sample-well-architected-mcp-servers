"""
AWS API Agent with Intelligent Prompt Preprocessing

This module provides an AWS operations agent that can intelligently preprocess
complex user inputs and split them into multiple targeted AWS API operations.
"""

import re
import json
from typing import List, Dict, Any, Optional
from aws_api_agent import aws_api_agent
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import think
from bedrock_agentcore.runtime import BedrockAgentCoreApp


app = BedrockAgentCoreApp()

bedrock_model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")


@tool
def preprocess_complex_prompt(user_input: str) -> str:
    """
    Analyze user input and determine if it needs to be split into multiple AWS operations.
    
    Args:
        user_input: The raw user input that may contain multiple AWS operations
        
    Returns:
        JSON string containing analysis and recommended operations breakdown
    """
    
    # Create a preprocessing agent to analyze the input
    preprocessing_agent = Agent(
        model=bedrock_model,
        system_prompt="""You are an AWS Operations Preprocessor. Your job is to analyze user inputs and determine if they contain multiple AWS operations that should be executed separately.

## Analysis Framework

### Single Operation Indicators:
- One clear AWS service mentioned (EC2, S3, RDS, etc.)
- One specific action verb (list, describe, create, delete, modify)
- Focused scope (single region, single resource type)
- Simple query structure

### Multi-Operation Indicators:
- Multiple AWS services mentioned
- Multiple action verbs or complex workflows
- Cross-service dependencies (e.g., "list EC2 instances and their security groups")
- Comparative analysis requests (e.g., "compare costs across regions")
- Sequential operations (e.g., "create a bucket then upload files")
- Comprehensive assessments (e.g., "analyze my entire security posture")

### Cross-Account Parameter Detection:
Extract these parameters when present:
- **account_id**: 12-digit AWS account numbers
- **role_arn**: Complete IAM role ARNs (arn:aws:iam::ACCOUNT:role/ROLE-NAME)
- **external_id**: External IDs for cross-account access
- **region**: AWS regions mentioned

## Response Format

Return a JSON object with this structure:
```json
{
    "analysis": {
        "complexity": "single|multi",
        "reasoning": "Brief explanation of why single or multi",
        "detected_services": ["service1", "service2"],
        "detected_actions": ["action1", "action2"],
        "cross_account_params": {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/RoleName",
            "external_id": "external-id-value",
            "region": "us-east-1"
        }
    },
    "operations": [
        {
            "sequence": 1,
            "description": "What this operation does",
            "query": "Specific query for aws_api_agent",
            "dependencies": ["operation_2_output"],
            "estimated_complexity": "low|medium|high"
        }
    ],
    "execution_strategy": "sequential|parallel|conditional"
}
```

## Examples

### Single Operation:
Input: "List all EC2 instances in us-east-1"
Output: Single operation with complexity="single"

### Multi Operation:
Input: "Analyze my security posture across all services"
Output: Multiple operations covering security groups, IAM, S3 encryption, etc.

### Cross-Account:
Input: "Check S3 buckets in account 123456789012 using role ReadOnlyRole"
Output: Single operation with cross-account parameters extracted

Focus on creating actionable, specific queries that the aws_api_agent can execute effectively."""
    )
    
    try:
        analysis_result = preprocessing_agent(f"Analyze this AWS request: {user_input}")
        return analysis_result.message['content'][0]['text']
    except Exception as e:
        # Fallback to simple analysis if preprocessing fails
        return json.dumps({
            "analysis": {
                "complexity": "single",
                "reasoning": f"Preprocessing failed: {str(e)}, treating as single operation",
                "detected_services": [],
                "detected_actions": [],
                "cross_account_params": {}
            },
            "operations": [{
                "sequence": 1,
                "description": "Direct execution of user request",
                "query": user_input,
                "dependencies": [],
                "estimated_complexity": "medium"
            }],
            "execution_strategy": "sequential"
        })


@tool
def execute_aws_operations_workflow(preprocessed_analysis: str) -> str:
    """
    Execute a workflow of AWS operations based on preprocessed analysis.
    
    Args:
        preprocessed_analysis: JSON string from preprocess_complex_prompt
        
    Returns:
        Comprehensive results from all executed operations
    """
    
    try:
        analysis = json.loads(preprocessed_analysis)
    except json.JSONDecodeError as e:
        return f"Error parsing preprocessed analysis: {e}"
    
    operations = analysis.get("operations", [])
    cross_account_params = analysis.get("analysis", {}).get("cross_account_params", {})
    execution_strategy = analysis.get("execution_strategy", "sequential")
    
    results = []
    operation_outputs = {}  # Store outputs for dependency resolution
    
    print(f"Executing {len(operations)} operations using {execution_strategy} strategy")
    
    for operation in operations:
        sequence = operation.get("sequence", 1)
        description = operation.get("description", "AWS Operation")
        query = operation.get("query", "")
        dependencies = operation.get("dependencies", [])
        
        print(f"\n--- Operation {sequence}: {description} ---")
        
        # Check dependencies
        missing_deps = [dep for dep in dependencies if dep not in operation_outputs]
        if missing_deps:
            error_msg = f"Missing dependencies for operation {sequence}: {missing_deps}"
            print(error_msg)
            results.append({
                "sequence": sequence,
                "description": description,
                "status": "failed",
                "error": error_msg
            })
            continue
        
        # Substitute dependency outputs in query if needed
        enhanced_query = query
        for dep in dependencies:
            if dep in operation_outputs:
                enhanced_query += f"\n\nContext from previous operation: {operation_outputs[dep]}"
        
        try:
            # Execute the AWS operation with cross-account parameters
            operation_result = aws_api_agent(
                query=enhanced_query,
                role_arn=cross_account_params.get("role_arn"),
                account_id=cross_account_params.get("account_id"),
                external_id=cross_account_params.get("external_id"),
                session_name=f"workflow-op-{sequence}"
            )
            
            # Store result for potential dependencies
            operation_outputs[f"operation_{sequence}_output"] = operation_result
            
            results.append({
                "sequence": sequence,
                "description": description,
                "status": "success",
                "result": operation_result
            })
            
            print(f"✅ Operation {sequence} completed successfully")
            
        except Exception as e:
            error_msg = f"Operation {sequence} failed: {str(e)}"
            print(f"❌ {error_msg}")
            results.append({
                "sequence": sequence,
                "description": description,
                "status": "failed",
                "error": error_msg
            })
            
            # For sequential execution, stop on first failure
            if execution_strategy == "sequential":
                print("Sequential execution stopped due to failure")
                break
    
    # Compile final response
    successful_ops = [r for r in results if r["status"] == "success"]
    failed_ops = [r for r in results if r["status"] == "failed"]
    
    response = f"## AWS Operations Workflow Results\n\n"
    response += f"**Executed:** {len(results)} operations\n"
    response += f"**Successful:** {len(successful_ops)}\n"
    response += f"**Failed:** {len(failed_ops)}\n\n"
    
    for result in results:
        response += f"### Operation {result['sequence']}: {result['description']}\n"
        response += f"**Status:** {result['status']}\n"
        
        if result["status"] == "success":
            response += f"**Result:**\n{result['result']}\n\n"
        else:
            response += f"**Error:** {result['error']}\n\n"
    
    return response

SUPERVISOR_AGENT_PROMPT = """You are an AWS Operations Router Agent with intelligent prompt preprocessing capabilities, designed to coordinate AWS operations with comprehensive tool selection logic and cross-account capabilities.

## Your Role
Analyze incoming queries, determine their complexity, and route them through the appropriate execution path with intelligent parameter extraction and workflow coordination.

## Available Tools

### 1. preprocess_complex_prompt - Intelligent Query Analysis
Use this FIRST for any AWS request to analyze complexity and determine execution strategy:
- Detects single vs multi-operation requests
- Extracts cross-account parameters (account_id, role_arn, external_id)
- Identifies AWS services and actions involved
- Creates structured execution plan

### 2. execute_aws_operations_workflow - Multi-Operation Orchestrator
Use this for complex requests that need multiple AWS operations:
- Executes sequential or parallel operation workflows
- Handles dependencies between operations
- Manages cross-account parameters across operations
- Provides comprehensive workflow results

### 3. aws_api_agent - Direct AWS Operations Expert
Use this for simple, single AWS operations:
- Direct AWS CLI command execution via call_aws
- Command discovery via suggest_aws_commands
- Cross-account parameter support

### 4. think - General Analysis
Use for non-AWS queries or strategic planning that doesn't require AWS API calls.

## Execution Flow Decision Logic

### Step 1: Always Preprocess First
For ANY AWS-related request, start with preprocess_complex_prompt to:
- Analyze query complexity
- Extract cross-account parameters
- Determine optimal execution strategy
- Create structured operation plan

### Step 2: Route Based on Complexity

#### Simple Requests → Direct aws_api_agent
Use aws_api_agent directly when preprocessing indicates:
- Single AWS service and action
- Clear, specific parameters
- No dependencies or complex workflows
- Complexity marked as "single"

Examples:
- "List all EC2 instances in us-east-1"
- "Describe security group sg-12345"
- "Get S3 bucket encryption status for my-bucket"

#### Complex Requests → execute_aws_operations_workflow
Use execute_aws_operations_workflow when preprocessing indicates:
- Multiple AWS services or actions
- Cross-service dependencies
- Sequential operations required
- Comprehensive analysis requests
- Complexity marked as "multi"

Examples:
- "Analyze my complete security posture"
- "Compare costs across all regions and services"
- "Set up monitoring for my entire application stack"
- "Audit all resources for compliance violations"

## Cross-Account Parameter Handling

The preprocessing step automatically extracts:
- **account_id**: 12-digit AWS account numbers
- **role_arn**: Complete IAM role ARNs (arn:aws:iam::ACCOUNT:role/ROLE-NAME)
- **external_id**: External IDs for cross-account access
- **region**: AWS regions mentioned

These parameters are automatically passed to the execution tools.

## Workflow Examples

### Example 1: Simple Request
Input: "List EC2 instances in account 123456789012"
1. preprocess_complex_prompt → Analysis shows single operation
2. aws_api_agent → Direct execution with account_id="123456789012"

### Example 2: Complex Request
Input: "Analyze security across all my AWS services and provide recommendations"
1. preprocess_complex_prompt → Analysis shows multi-operation workflow
2. execute_aws_operations_workflow → Executes security checks for IAM, EC2, S3, etc.

### Example 3: Cross-Account Complex Request
Input: "Audit account 123456789012 for cost optimization opportunities across all services"
1. preprocess_complex_prompt → Multi-operation with cross-account parameters
2. execute_aws_operations_workflow → Sequential cost analysis operations with account_id

## Response Guidelines

1. **Always preprocess first**: Never skip the preprocessing step for AWS requests
2. **Follow complexity routing**: Use the preprocessing results to determine execution path
3. **Preserve parameters**: Ensure cross-account parameters flow through the entire workflow
4. **Provide context**: Explain the execution strategy chosen and why
5. **Handle failures gracefully**: If preprocessing fails, fall back to direct aws_api_agent

## Service-Specific Routing Examples:
- "List my Bedrock spending" → Preprocess → aws_api_agent (single operation)
- "Complete security audit" → Preprocess → execute_aws_operations_workflow (multi-operation)
- "Cost optimization analysis" → Preprocess → execute_aws_operations_workflow (multi-operation)
- "Check specific S3 bucket policy" → Preprocess → aws_api_agent (single operation)

Your goal is to ensure optimal execution path selection through intelligent preprocessing and provide comprehensive AWS operations support with proper workflow orchestration."""

supervisor_agent = Agent(
    system_prompt=SUPERVISOR_AGENT_PROMPT,
    model=bedrock_model,
    # stream_handler=None,
    tools=[preprocess_complex_prompt, execute_aws_operations_workflow, aws_api_agent, think],
)


@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    print("User input:", user_input)
    response = supervisor_agent(user_input)
    return response.message['content'][0]['text']


# Example usage
if __name__ == "__main__":
    app.run()