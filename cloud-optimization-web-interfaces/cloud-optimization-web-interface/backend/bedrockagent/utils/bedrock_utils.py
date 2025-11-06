"""
Bedrock-specific utilities for BedrockAgent version.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from shared.models.chat_models import ChatMessage, ToolExecution
from shared.utils.validation_utils import validate_agent_id, validate_session_id

logger = logging.getLogger(__name__)


def format_agent_name(agent_type: str) -> str:
    """
    Convert agent type to human-readable name.
    
    Args:
        agent_type: Agent type identifier
        
    Returns:
        Human-readable agent name
    """
    return agent_type.replace('_', ' ').replace('-', ' ').title().replace('Wa ', 'WA ').replace('Mcp', 'MCP')


def get_agent_description(agent_type: str) -> str:
    """
    Get description for an agent type.
    
    Args:
        agent_type: Agent type identifier
        
    Returns:
        Agent description string
    """
    descriptions = {
        'wa-security-agent': 'AWS security analysis and Well-Architected security pillar assessments',
        'enhanced-security-agent': 'Enhanced AWS security analysis with multi-MCP integration',
        'wa_cost_agent': 'Cost optimization and financial analysis',
        'wa_reliability_agent': 'Reliability assessments and resilience analysis',
        'multi_agent_supervisor': 'Coordinating multiple specialized agents for comprehensive analysis'
    }
    return descriptions.get(agent_type, 'Cloud optimization and analysis specialist')


def validate_agent_request(
    agent_id: str,
    agent_alias_id: str,
    session_id: str,
    input_text: str
) -> Dict[str, Any]:
    """
    Validate agent invocation request parameters.
    
    Args:
        agent_id: Bedrock agent ID
        agent_alias_id: Agent alias ID
        session_id: Session ID
        input_text: User input text
        
    Returns:
        Validation result dictionary
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Validate agent ID
    if not agent_id:
        validation_result["errors"].append("Agent ID is required")
        validation_result["valid"] = False
    elif not validate_agent_id(agent_id):
        validation_result["errors"].append("Invalid agent ID format")
        validation_result["valid"] = False
    
    # Validate agent alias ID
    if not agent_alias_id:
        validation_result["errors"].append("Agent alias ID is required")
        validation_result["valid"] = False
    
    # Validate session ID
    if not session_id:
        validation_result["errors"].append("Session ID is required")
        validation_result["valid"] = False
    elif not validate_session_id(session_id):
        validation_result["errors"].append("Invalid session ID format")
        validation_result["valid"] = False
    
    # Validate input text
    if not input_text or not input_text.strip():
        validation_result["errors"].append("Input text is required")
        validation_result["valid"] = False
    elif len(input_text) > 25000:  # Bedrock agent input limit
        validation_result["warnings"].append("Input text is very long and may be truncated")
    
    return validation_result


def parse_agent_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and normalize agent response data.
    
    Args:
        response_data: Raw agent response data
        
    Returns:
        Normalized response dictionary
    """
    try:
        parsed_response = {
            "content": response_data.get("content", ""),
            "agent_id": response_data.get("agent_id", "unknown"),
            "session_id": response_data.get("session_id", "unknown"),
            "tool_executions": response_data.get("tool_executions", []),
            "response_time_ms": response_data.get("response_time_ms", 0),
            "streaming": response_data.get("streaming", False),
            "timestamp": response_data.get("timestamp", datetime.utcnow().isoformat()),
            "success": True
        }
        
        # Validate tool executions
        if parsed_response["tool_executions"]:
            parsed_response["tool_executions"] = [
                tool for tool in parsed_response["tool_executions"]
                if isinstance(tool, (dict, ToolExecution))
            ]
        
        return parsed_response
        
    except Exception as e:
        logger.error(f"Error parsing agent response: {e}")
        return {
            "content": "",
            "agent_id": "unknown",
            "session_id": "unknown",
            "tool_executions": [],
            "response_time_ms": 0,
            "streaming": False,
            "timestamp": datetime.utcnow().isoformat(),
            "success": False,
            "error": str(e)
        }


def format_tool_execution_summary(tool_executions: List[ToolExecution]) -> str:
    """
    Format tool execution summary for display.
    
    Args:
        tool_executions: List of tool executions
        
    Returns:
        Formatted summary string
    """
    if not tool_executions:
        return "No tools executed"
    
    summary_parts = []
    successful_tools = 0
    failed_tools = 0
    
    for tool in tool_executions:
        if isinstance(tool, dict):
            tool_name = tool.get("tool_name", "unknown")
            success = tool.get("success", False)
        else:
            tool_name = tool.tool_name
            success = tool.success
        
        if success:
            successful_tools += 1
        else:
            failed_tools += 1
    
    summary_parts.append(f"Executed {len(tool_executions)} tools")
    
    if successful_tools > 0:
        summary_parts.append(f"{successful_tools} successful")
    
    if failed_tools > 0:
        summary_parts.append(f"{failed_tools} failed")
    
    return " - ".join(summary_parts)


def extract_agent_metadata(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract metadata from agent response.
    
    Args:
        response: Agent response dictionary
        
    Returns:
        Metadata dictionary
    """
    metadata = {
        "agent_id": response.get("agent_id", "unknown"),
        "session_id": response.get("session_id", "unknown"),
        "response_time_ms": response.get("response_time_ms", 0),
        "streaming": response.get("streaming", False),
        "timestamp": response.get("timestamp", datetime.utcnow().isoformat()),
        "content_length": len(response.get("content", "")),
        "tool_count": len(response.get("tool_executions", [])),
        "success": response.get("success", True)
    }
    
    # Add tool execution summary
    tool_executions = response.get("tool_executions", [])
    if tool_executions:
        successful_tools = sum(1 for tool in tool_executions 
                             if (tool.success if hasattr(tool, 'success') else tool.get("success", False)))
        metadata["successful_tools"] = successful_tools
        metadata["failed_tools"] = len(tool_executions) - successful_tools
        metadata["tool_summary"] = format_tool_execution_summary(tool_executions)
    
    return metadata


def create_agent_error_response(
    error: Exception,
    agent_id: str = "unknown",
    session_id: str = "unknown"
) -> Dict[str, Any]:
    """
    Create standardized error response for agent failures.
    
    Args:
        error: Exception that occurred
        agent_id: Agent ID (if known)
        session_id: Session ID (if known)
        
    Returns:
        Error response dictionary
    """
    return {
        "content": f"Agent invocation failed: {str(error)}",
        "agent_id": agent_id,
        "session_id": session_id,
        "tool_executions": [],
        "response_time_ms": 0,
        "streaming": False,
        "timestamp": datetime.utcnow().isoformat(),
        "success": False,
        "error": {
            "type": type(error).__name__,
            "message": str(error)
        }
    }


def prepare_chat_context(messages: List[ChatMessage], max_context_length: int = 20000) -> str:
    """
    Prepare chat context from message history for agent input.
    
    Args:
        messages: List of chat messages
        max_context_length: Maximum context length in characters
        
    Returns:
        Formatted context string
    """
    if not messages:
        return ""
    
    context_parts = []
    current_length = 0
    
    # Process messages in reverse order (most recent first)
    for message in reversed(messages[:-1]):  # Exclude the last message (current user input)
        message_text = f"{message.role.upper()}: {message.content}\n"
        
        if current_length + len(message_text) > max_context_length:
            break
        
        context_parts.insert(0, message_text)
        current_length += len(message_text)
    
    if context_parts:
        context = "Previous conversation:\n" + "".join(context_parts) + "\n"
        return context
    
    return ""


def categorize_tool_by_name(tool_name: str) -> str:
    """
    Categorize tools based on their name and functionality.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Tool category string
    """
    tool_name_lower = tool_name.lower()
    
    if any(keyword in tool_name_lower for keyword in ["security", "check", "findings", "encryption", "network"]):
        return "security"
    elif any(keyword in tool_name_lower for keyword in ["cost", "usage", "rightsizing", "savings", "budget"]):
        return "cost_optimization"
    elif any(keyword in tool_name_lower for keyword in ["service", "region", "list", "discover"]):
        return "discovery"
    elif any(keyword in tool_name_lower for keyword in ["storage", "encryption"]):
        return "storage"
    elif any(keyword in tool_name_lower for keyword in ["network", "vpc", "elb"]):
        return "networking"
    else:
        return "general"


def format_agent_capabilities(capabilities: List[str]) -> str:
    """
    Format agent capabilities for display.
    
    Args:
        capabilities: List of capability strings
        
    Returns:
        Formatted capabilities string
    """
    if not capabilities:
        return "No specific capabilities listed"
    
    # Group capabilities by category
    categorized = {}
    for capability in capabilities:
        category = categorize_tool_by_name(capability)
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(capability)
    
    # Format by category
    formatted_parts = []
    for category, items in categorized.items():
        category_title = category.replace('_', ' ').title()
        formatted_parts.append(f"{category_title}: {', '.join(items)}")
    
    return " | ".join(formatted_parts)


def calculate_response_metrics(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate response metrics for monitoring and analysis.
    
    Args:
        response: Agent response dictionary
        
    Returns:
        Metrics dictionary
    """
    metrics = {
        "response_time_ms": response.get("response_time_ms", 0),
        "content_length": len(response.get("content", "")),
        "tool_count": len(response.get("tool_executions", [])),
        "success": response.get("success", True),
        "streaming": response.get("streaming", False)
    }
    
    # Calculate tool success rate
    tool_executions = response.get("tool_executions", [])
    if tool_executions:
        successful_tools = sum(1 for tool in tool_executions 
                             if (tool.success if hasattr(tool, 'success') else tool.get("success", False)))
        metrics["tool_success_rate"] = successful_tools / len(tool_executions)
    else:
        metrics["tool_success_rate"] = 1.0
    
    # Categorize response time
    response_time = metrics["response_time_ms"]
    if response_time < 1000:
        metrics["response_speed"] = "fast"
    elif response_time < 5000:
        metrics["response_speed"] = "normal"
    else:
        metrics["response_speed"] = "slow"
    
    return metrics