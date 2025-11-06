"""
BedrockAgent-specific validation utilities.
"""

import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from shared.utils.validation_utils import (
    validate_aws_region,
    validate_aws_account_id,
    validate_agent_id,
    validate_session_id,
    ValidationResult
)


def validate_bedrock_agent_config(config: Dict[str, Any]) -> ValidationResult:
    """
    Validate BedrockAgent-specific configuration.
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    # Check required BedrockAgent fields
    required_fields = ["agent_id", "agent_alias_id"]
    for field in required_fields:
        if field not in config or not config[field]:
            result.add_error(f"Required field '{field}' is missing or empty")
    
    # Validate agent ID format
    if "agent_id" in config and config["agent_id"]:
        if not validate_agent_id(config["agent_id"]):
            result.add_error("Invalid agent ID format")
    
    # Validate region if provided
    if "region" in config and config["region"]:
        if not validate_aws_region(config["region"]):
            result.add_error("Invalid AWS region format")
    
    # Check for AgentCore-specific fields that shouldn't be present
    agentcore_fields = ["param_prefix", "strands_discovery", "agentcore_runtime"]
    for field in agentcore_fields:
        if field in config:
            result.add_warning(f"AgentCore-specific field '{field}' found in BedrockAgent configuration")
    
    return result


def validate_mcp_server_connection(connection_info: Dict[str, Any]) -> ValidationResult:
    """
    Validate MCP server connection information.
    
    Args:
        connection_info: MCP server connection information
        
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    # Check required fields
    required_fields = ["name", "agent_id"]
    for field in required_fields:
        if field not in connection_info or not connection_info[field]:
            result.add_error(f"Required field '{field}' is missing or empty")
    
    # Validate agent ID
    if "agent_id" in connection_info and connection_info["agent_id"]:
        if not validate_agent_id(connection_info["agent_id"]):
            result.add_error("Invalid MCP server agent ID format")
    
    # Validate optional fields
    if "region" in connection_info and connection_info["region"]:
        if not validate_aws_region(connection_info["region"]):
            result.add_warning("Invalid region format in MCP server configuration")
    
    # Check capabilities format
    if "capabilities" in connection_info:
        capabilities = connection_info["capabilities"]
        if not isinstance(capabilities, list):
            result.add_warning("Capabilities should be a list")
        elif not capabilities:
            result.add_warning("No capabilities specified for MCP server")
    
    return result


def validate_agent_invocation_params(
    agent_id: str,
    agent_alias_id: str,
    session_id: str,
    input_text: str
) -> ValidationResult:
    """
    Validate parameters for agent invocation.
    
    Args:
        agent_id: Bedrock agent ID
        agent_alias_id: Agent alias ID
        session_id: Session ID
        input_text: User input text
        
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    # Validate agent ID
    if not agent_id:
        result.add_error("Agent ID is required")
    elif not validate_agent_id(agent_id):
        result.add_error("Invalid agent ID format")
    
    # Validate agent alias ID
    if not agent_alias_id:
        result.add_error("Agent alias ID is required")
    elif not isinstance(agent_alias_id, str) or not agent_alias_id.strip():
        result.add_error("Agent alias ID must be a non-empty string")
    
    # Validate session ID
    if not session_id:
        result.add_error("Session ID is required")
    elif not validate_session_id(session_id):
        result.add_error("Invalid session ID format")
    
    # Validate input text
    if not input_text:
        result.add_error("Input text is required")
    elif not isinstance(input_text, str):
        result.add_error("Input text must be a string")
    elif len(input_text.strip()) == 0:
        result.add_error("Input text cannot be empty")
    elif len(input_text) > 25000:  # Bedrock agent input limit
        result.add_warning("Input text exceeds recommended length and may be truncated")
    
    return result


def validate_tool_execution_request(tool_name: str, tool_input: Dict[str, Any]) -> ValidationResult:
    """
    Validate tool execution request parameters.
    
    Args:
        tool_name: Name of the tool to execute
        tool_input: Tool input parameters
        
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    # Validate tool name
    if not tool_name:
        result.add_error("Tool name is required")
    elif not isinstance(tool_name, str):
        result.add_error("Tool name must be a string")
    elif not re.match(r'^[a-zA-Z0-9_\-\.]+$', tool_name):
        result.add_error("Tool name contains invalid characters")
    
    # Validate tool input
    if not isinstance(tool_input, dict):
        result.add_error("Tool input must be a dictionary")
    else:
        # Check for potentially problematic input
        try:
            import json
            input_json = json.dumps(tool_input)
            if len(input_json) > 50000:
                result.add_warning("Tool input is very large and may cause performance issues")
        except (TypeError, ValueError):
            result.add_error("Tool input contains non-serializable data")
    
    return result


def validate_chat_session_config(session_config: Dict[str, Any]) -> ValidationResult:
    """
    Validate chat session configuration.
    
    Args:
        session_config: Session configuration dictionary
        
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    # Validate session ID
    if "session_id" in session_config:
        if not validate_session_id(session_config["session_id"]):
            result.add_error("Invalid session ID format")
    
    # Validate agent configuration
    if "agent_config" in session_config:
        agent_config = session_config["agent_config"]
        if not isinstance(agent_config, dict):
            result.add_error("Agent configuration must be a dictionary")
        else:
            agent_validation = validate_bedrock_agent_config(agent_config)
            result.errors.extend(agent_validation.errors)
            result.warnings.extend(agent_validation.warnings)
    
    # Validate context settings
    if "context" in session_config:
        context = session_config["context"]
        if not isinstance(context, dict):
            result.add_warning("Session context should be a dictionary")
    
    # Validate streaming settings
    if "streaming" in session_config:
        streaming = session_config["streaming"]
        if not isinstance(streaming, bool):
            result.add_warning("Streaming setting should be a boolean")
    
    return result


def validate_bedrock_response(response: Dict[str, Any]) -> ValidationResult:
    """
    Validate Bedrock agent response structure.
    
    Args:
        response: Agent response dictionary
        
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    # Check required response fields
    required_fields = ["content", "agent_id", "session_id"]
    for field in required_fields:
        if field not in response:
            result.add_error(f"Required response field '{field}' is missing")
    
    # Validate content
    if "content" in response:
        content = response["content"]
        if not isinstance(content, str):
            result.add_error("Response content must be a string")
        elif len(content) == 0:
            result.add_warning("Response content is empty")
    
    # Validate tool executions
    if "tool_executions" in response:
        tool_executions = response["tool_executions"]
        if not isinstance(tool_executions, list):
            result.add_error("Tool executions must be a list")
        else:
            for i, tool in enumerate(tool_executions):
                if not isinstance(tool, dict):
                    result.add_error(f"Tool execution {i} must be a dictionary")
                else:
                    # Check required tool fields
                    tool_required_fields = ["tool_name", "success"]
                    for field in tool_required_fields:
                        if field not in tool:
                            result.add_warning(f"Tool execution {i} missing field '{field}'")
    
    # Validate metadata
    if "response_time_ms" in response:
        response_time = response["response_time_ms"]
        if not isinstance(response_time, (int, float)) or response_time < 0:
            result.add_warning("Invalid response time format")
    
    return result


def validate_environment_for_bedrockagent() -> ValidationResult:
    """
    Validate environment configuration for BedrockAgent version.
    
    Returns:
        ValidationResult object
    """
    result = ValidationResult()
    
    import os
    
    # Check for required environment variables
    required_env_vars = ["AWS_DEFAULT_REGION"]
    for var in required_env_vars:
        if not os.getenv(var):
            result.add_warning(f"Environment variable '{var}' is not set")
    
    # Check for conflicting AgentCore variables
    agentcore_vars = ["PARAM_PREFIX", "AGENTCORE_PERIODIC_DISCOVERY_ENABLED"]
    for var in agentcore_vars:
        if os.getenv(var):
            result.add_warning(f"AgentCore environment variable '{var}' is set in BedrockAgent mode")
    
    # Validate AWS region format
    aws_region = os.getenv("AWS_DEFAULT_REGION")
    if aws_region and not validate_aws_region(aws_region):
        result.add_error("Invalid AWS_DEFAULT_REGION format")
    
    # Check for recommended BedrockAgent variables
    recommended_vars = ["ENHANCED_SECURITY_AGENT_ID", "ENHANCED_SECURITY_AGENT_ALIAS_ID"]
    for var in recommended_vars:
        if not os.getenv(var):
            result.add_warning(f"Recommended environment variable '{var}' is not set")
    
    return result


def create_bedrockagent_validator() -> callable:
    """
    Create a comprehensive validator for BedrockAgent configurations.
    
    Returns:
        Validator function
    """
    def validator(data: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        # Validate based on data type
        if "agent_id" in data and "agent_alias_id" in data:
            # This looks like agent configuration
            agent_validation = validate_bedrock_agent_config(data)
            result.errors.extend(agent_validation.errors)
            result.warnings.extend(agent_validation.warnings)
        
        if "name" in data and "agent_id" in data and "capabilities" in data:
            # This looks like MCP server configuration
            mcp_validation = validate_mcp_server_connection(data)
            result.errors.extend(mcp_validation.errors)
            result.warnings.extend(mcp_validation.warnings)
        
        if "session_id" in data:
            # This looks like session configuration
            session_validation = validate_chat_session_config(data)
            result.errors.extend(session_validation.errors)
            result.warnings.extend(session_validation.warnings)
        
        return result
    
    return validator