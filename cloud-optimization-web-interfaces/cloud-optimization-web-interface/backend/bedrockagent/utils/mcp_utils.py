"""
MCP (Model Context Protocol) helper functions for BedrockAgent version.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)


def format_mcp_server_name(server_name: str) -> str:
    """
    Format MCP server name for display.
    
    Args:
        server_name: Raw server name
        
    Returns:
        Formatted server name
    """
    return server_name.replace('_', ' ').replace('-', ' ').title()


def validate_mcp_tool_request(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate MCP tool request parameters.
    
    Args:
        tool_name: Name of the MCP tool
        tool_input: Tool input parameters
        
    Returns:
        Validation result dictionary
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Validate tool name
    if not tool_name:
        validation_result["errors"].append("Tool name is required")
        validation_result["valid"] = False
    elif not isinstance(tool_name, str):
        validation_result["errors"].append("Tool name must be a string")
        validation_result["valid"] = False
    
    # Validate tool input
    if not isinstance(tool_input, dict):
        validation_result["errors"].append("Tool input must be a dictionary")
        validation_result["valid"] = False
    
    # Check for potentially large inputs
    if isinstance(tool_input, dict):
        input_str = json.dumps(tool_input)
        if len(input_str) > 10000:
            validation_result["warnings"].append("Tool input is very large and may cause performance issues")
    
    return validation_result


def parse_mcp_tool_response(response_data: Any) -> Dict[str, Any]:
    """
    Parse and normalize MCP tool response.
    
    Args:
        response_data: Raw MCP tool response
        
    Returns:
        Normalized response dictionary
    """
    try:
        if isinstance(response_data, dict):
            return {
                "success": True,
                "result": response_data,
                "error": None,
                "timestamp": datetime.utcnow().isoformat()
            }
        elif isinstance(response_data, str):
            # Try to parse as JSON
            try:
                parsed_data = json.loads(response_data)
                return {
                    "success": True,
                    "result": parsed_data,
                    "error": None,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except json.JSONDecodeError:
                # Return as plain text
                return {
                    "success": True,
                    "result": {"text": response_data},
                    "error": None,
                    "timestamp": datetime.utcnow().isoformat()
                }
        else:
            return {
                "success": True,
                "result": {"data": str(response_data)},
                "error": None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error parsing MCP tool response: {e}")
        return {
            "success": False,
            "result": None,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def format_mcp_error(error: Exception, tool_name: str = "unknown") -> Dict[str, Any]:
    """
    Format MCP tool error for consistent error handling.
    
    Args:
        error: Exception that occurred
        tool_name: Name of the tool that failed
        
    Returns:
        Formatted error dictionary
    """
    return {
        "success": False,
        "tool_name": tool_name,
        "error": {
            "type": type(error).__name__,
            "message": str(error)
        },
        "timestamp": datetime.utcnow().isoformat()
    }


def extract_mcp_capabilities(server_info: Dict[str, Any]) -> List[str]:
    """
    Extract capabilities from MCP server information.
    
    Args:
        server_info: MCP server information dictionary
        
    Returns:
        List of capability strings
    """
    capabilities = []
    
    # Extract from various possible fields
    if "capabilities" in server_info:
        if isinstance(server_info["capabilities"], list):
            capabilities.extend(server_info["capabilities"])
        elif isinstance(server_info["capabilities"], str):
            capabilities.append(server_info["capabilities"])
    
    if "tools" in server_info:
        if isinstance(server_info["tools"], list):
            capabilities.extend([f"Tool: {tool}" for tool in server_info["tools"]])
    
    if "available_tools" in server_info:
        if isinstance(server_info["available_tools"], list):
            capabilities.extend([f"Tool: {tool}" for tool in server_info["available_tools"]])
    
    if "supported_services" in server_info:
        if isinstance(server_info["supported_services"], list):
            capabilities.extend([f"Service: {service}" for service in server_info["supported_services"]])
    
    return capabilities


def categorize_mcp_tool(tool_name: str, tool_description: str = "") -> str:
    """
    Categorize MCP tool based on name and description.
    
    Args:
        tool_name: Name of the MCP tool
        tool_description: Description of the tool
        
    Returns:
        Tool category string
    """
    combined_text = f"{tool_name} {tool_description}".lower()
    
    if any(keyword in combined_text for keyword in ["security", "check", "findings", "encryption", "vulnerability"]):
        return "security"
    elif any(keyword in combined_text for keyword in ["cost", "usage", "billing", "savings", "budget", "pricing"]):
        return "cost_optimization"
    elif any(keyword in combined_text for keyword in ["list", "describe", "get", "discover", "search"]):
        return "discovery"
    elif any(keyword in combined_text for keyword in ["storage", "s3", "ebs", "efs"]):
        return "storage"
    elif any(keyword in combined_text for keyword in ["network", "vpc", "elb", "cloudfront"]):
        return "networking"
    elif any(keyword in combined_text for keyword in ["compute", "ec2", "lambda", "ecs"]):
        return "compute"
    elif any(keyword in combined_text for keyword in ["database", "rds", "dynamodb"]):
        return "database"
    else:
        return "general"


def format_mcp_tool_list(tools: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Format and categorize MCP tools for display.
    
    Args:
        tools: List of MCP tool dictionaries
        
    Returns:
        Dictionary of categorized tools
    """
    categorized_tools = {}
    
    for tool in tools:
        tool_name = tool.get("name", "unknown")
        tool_description = tool.get("description", "")
        category = categorize_mcp_tool(tool_name, tool_description)
        
        if category not in categorized_tools:
            categorized_tools[category] = []
        
        categorized_tools[category].append({
            "name": tool_name,
            "description": tool_description,
            "server": tool.get("server", "unknown"),
            "parameters": tool.get("parameters", {})
        })
    
    # Sort tools within each category
    for category in categorized_tools:
        categorized_tools[category].sort(key=lambda x: x["name"])
    
    return categorized_tools


def create_mcp_tool_summary(tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create summary statistics for MCP tools.
    
    Args:
        tools: List of MCP tool dictionaries
        
    Returns:
        Summary statistics dictionary
    """
    if not tools:
        return {
            "total_tools": 0,
            "categories": {},
            "servers": {},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    categorized = format_mcp_tool_list(tools)
    servers = {}
    
    for tool in tools:
        server_name = tool.get("server", "unknown")
        if server_name not in servers:
            servers[server_name] = 0
        servers[server_name] += 1
    
    return {
        "total_tools": len(tools),
        "categories": {category: len(tools) for category, tools in categorized.items()},
        "servers": servers,
        "categorized_tools": categorized,
        "timestamp": datetime.utcnow().isoformat()
    }


def validate_mcp_server_config(server_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate MCP server configuration.
    
    Args:
        server_config: MCP server configuration dictionary
        
    Returns:
        Validation result dictionary
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    required_fields = ["name", "agent_id"]
    for field in required_fields:
        if field not in server_config:
            validation_result["errors"].append(f"Required field '{field}' is missing")
            validation_result["valid"] = False
    
    # Validate agent_id format if present
    if "agent_id" in server_config:
        agent_id = server_config["agent_id"]
        if not isinstance(agent_id, str) or len(agent_id) != 10:
            validation_result["errors"].append("Agent ID must be a 10-character string")
            validation_result["valid"] = False
    
    # Check for optional but recommended fields
    recommended_fields = ["description", "capabilities", "region"]
    for field in recommended_fields:
        if field not in server_config:
            validation_result["warnings"].append(f"Recommended field '{field}' is missing")
    
    return validation_result


def format_mcp_connection_info(connection_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format MCP connection information for display.
    
    Args:
        connection_info: Raw connection information
        
    Returns:
        Formatted connection information
    """
    formatted = {
        "server_name": connection_info.get("name", "unknown"),
        "display_name": format_mcp_server_name(connection_info.get("name", "unknown")),
        "agent_id": connection_info.get("agent_id", "unknown"),
        "status": "connected" if connection_info.get("agent_id") else "disconnected",
        "capabilities": extract_mcp_capabilities(connection_info),
        "region": connection_info.get("region", "unknown"),
        "deployment_type": connection_info.get("deployment_type", "unknown"),
        "framework": connection_info.get("framework", "mcp"),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add tool information if available
    if "available_tools" in connection_info:
        formatted["tools"] = connection_info["available_tools"]
        formatted["tool_count"] = len(connection_info["available_tools"])
    
    if "supported_services" in connection_info:
        formatted["supported_services"] = connection_info["supported_services"]
    
    return formatted


def create_mcp_health_summary(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create health summary for MCP servers.
    
    Args:
        servers: List of MCP server information
        
    Returns:
        Health summary dictionary
    """
    total_servers = len(servers)
    connected_servers = sum(1 for server in servers if server.get("agent_id"))
    
    health_status = "healthy"
    if connected_servers == 0:
        health_status = "unhealthy"
    elif connected_servers < total_servers:
        health_status = "degraded"
    
    return {
        "status": health_status,
        "total_servers": total_servers,
        "connected_servers": connected_servers,
        "disconnected_servers": total_servers - connected_servers,
        "connection_rate": connected_servers / max(total_servers, 1),
        "timestamp": datetime.utcnow().isoformat()
    }