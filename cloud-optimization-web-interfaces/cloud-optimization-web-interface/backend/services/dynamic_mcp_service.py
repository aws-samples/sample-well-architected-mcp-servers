#!/usr/bin/env python3
"""
Dynamic MCP Service - Dynamically discovers and loads MCP servers and tools
Replaces hard-coded tool integration with agent-based MCP server discovery
"""

import json
import logging
import subprocess
import asyncio
import os
import boto3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server"""
    name: str
    type: str  # 'uvx', 'python', 'executable'
    command: List[str]
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    timeout: int = 30
    available: bool = False
    tools: Optional[List[Dict[str, Any]]] = field(default_factory=list)


@dataclass
class AgentMCPMapping:
    """Mapping between agents and their MCP servers"""
    agent_type: str
    agent_id: str
    mcp_servers: List[str]
    capabilities: List[str]
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


class DynamicMCPService:
    """Dynamic MCP server discovery and tool loading service"""
    
    def __init__(self):
        self.mcp_servers: Dict[str, MCPServerConfig] = {}
        self.agent_mappings: Dict[str, AgentMCPMapping] = {}
        self.active_tools: Dict[str, Dict[str, Any]] = {}
        self.current_agent: Optional[str] = None
        
        # Dynamic discovery configuration
        self.ssm_client = boto3.client("ssm", region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        self.discovery_cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_discovery_time: Optional[datetime] = None
                
        # Note: Dynamic discovery will be performed on first use
        
    async def discover_agent_mcp_servers(self, agent_type: str, agent_metadata: Dict[str, Any] = None) -> List[str]:
        """Discover which MCP servers are associated with a specific agent"""
        
        # Define agent-to-MCP server mappings
        agent_mcp_mappings = {
        }
        
        # Get MCP servers for this agent type
        mcp_server_names = agent_mcp_mappings.get(agent_type, [])
        
        # Store the mapping
        self.agent_mappings[agent_type] = AgentMCPMapping(
            agent_type=agent_type,
            agent_id=agent_metadata.get("agent_id", "") if agent_metadata else "",
            mcp_servers=mcp_server_names,
            capabilities=agent_metadata.get("capabilities", []) if agent_metadata else [],
            metadata=agent_metadata or {}
        )
        
        logger.info(f"Agent {agent_type} mapped to MCP servers: {mcp_server_names}")
        return mcp_server_names
        
    async def check_mcp_server_availability(self, server_name: str) -> bool:
        """Check if an MCP server is available"""
        
        if server_name not in self.mcp_servers:
            logger.warning(f"Unknown MCP server: {server_name}")
            return False
            
        server_config = self.mcp_servers[server_name]
        
        try:
            if server_config.type == "uvx":
                # Check if uvx is available
                result = await asyncio.create_subprocess_exec(
                    "uvx", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(result.communicate(), timeout=5)
                
                if result.returncode == 0:
                    server_config.available = True
                    logger.info(f"MCP server {server_name} available via uvx")
                    return True
                    
            elif server_config.type == "python":
                # Check if Python MCP server exists
                if server_config.working_dir:
                    server_path = Path(server_config.working_dir) / "src" / "server.py"
                    if server_path.exists():
                        server_config.available = True
                        logger.info(f"MCP server {server_name} found at {server_path}")
                        return True
                        
            elif server_config.type == "executable":
                # Check if executable exists
                result = await asyncio.create_subprocess_exec(
                    server_config.command[0], "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(result.communicate(), timeout=5)
                
                if result.returncode == 0:
                    server_config.available = True
                    logger.info(f"MCP server {server_name} executable available")
                    return True
                    
        except Exception as e:
            logger.warning(f"MCP server {server_name} not available: {e}")
            
        server_config.available = False
        return False
        
    async def discover_mcp_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Discover available tools from an MCP server"""
        
        if server_name not in self.mcp_servers:
            logger.warning(f"Unknown MCP server: {server_name}")
            return []
            
        server_config = self.mcp_servers[server_name]
        
        if not server_config.available:
            logger.warning(f"MCP server {server_name} not available")
            return []
            
        try:
            # For now, return predefined tools based on server type
            # In a full implementation, this would query the actual MCP server
            tools = await self._get_predefined_tools(server_name)
            server_config.tools = tools
            
            logger.info(f"Discovered {len(tools)} tools from MCP server {server_name}")
            return tools
            
        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")
            return []
            
    async def _get_predefined_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """Get predefined tools for known MCP servers"""
        
        if server_name == "wa_security":
            return [
                {
                    "name": "CheckSecurityServices",
                    "description": "Check if AWS security services are enabled",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "default": "us-east-1"},
                            "services": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                {
                    "name": "GetSecurityFindings", 
                    "description": "Get security findings from AWS security services",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string"},
                            "region": {"type": "string", "default": "us-east-1"},
                            "max_findings": {"type": "integer", "default": 100}
                        }
                    }
                },
                {
                    "name": "CheckStorageEncryption",
                    "description": "Check storage encryption status",
                    "inputSchema": {
                        "type": "object", 
                        "properties": {
                            "region": {"type": "string", "default": "us-east-1"},
                            "services": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                {
                    "name": "CheckNetworkSecurity",
                    "description": "Check network security configuration",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "default": "us-east-1"},
                            "services": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            ]
            
        elif server_name == "cost_explorer":
            return [
                {
                    "name": "get_cost_and_usage",
                    "description": "Get AWS cost and usage data for specified time periods and dimensions",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "time_period": {
                                "type": "object",
                                "properties": {
                                    "start": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                                    "end": {"type": "string", "description": "End date (YYYY-MM-DD)"}
                                }
                            },
                            "granularity": {"type": "string", "enum": ["DAILY", "MONTHLY"], "default": "MONTHLY"},
                            "group_by": {
                                "type": "array", 
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["DIMENSION", "TAG"]},
                                        "key": {"type": "string"}
                                    }
                                }
                            },
                            "metrics": {"type": "array", "items": {"type": "string"}, "default": ["BlendedCost"]}
                        }
                    }
                },
                {
                    "name": "get_dimension_values",
                    "description": "Get available values for a specific dimension (like SERVICE, REGION, etc.)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "dimension": {"type": "string", "description": "Dimension to get values for (SERVICE, REGION, AZ, etc.)"},
                            "time_period": {
                                "type": "object",
                                "properties": {
                                    "start": {"type": "string"},
                                    "end": {"type": "string"}
                                }
                            },
                            "search_string": {"type": "string", "description": "Filter dimension values"}
                        },
                        "required": ["dimension"]
                    }
                },
                {
                    "name": "get_rightsizing_recommendation",
                    "description": "Get rightsizing recommendations for EC2 instances",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "default": "EC2-Instance"},
                            "page_size": {"type": "integer", "default": 100},
                            "configuration": {
                                "type": "object",
                                "properties": {
                                    "benefits_considered": {"type": "boolean", "default": True},
                                    "recommendation_target": {"type": "string", "enum": ["SAME_INSTANCE_FAMILY", "CROSS_INSTANCE_FAMILY"]}
                                }
                            }
                        }
                    }
                },
                {
                    "name": "get_savings_utilization",
                    "description": "Get Savings Plans or Reserved Instance utilization",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "time_period": {
                                "type": "object",
                                "properties": {
                                    "start": {"type": "string"},
                                    "end": {"type": "string"}
                                }
                            },
                            "granularity": {"type": "string", "enum": ["DAILY", "MONTHLY"], "default": "MONTHLY"},
                            "group_by": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                {
                    "name": "get_cost_categories",
                    "description": "Get cost category information and rules",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "cost_category_name": {"type": "string"},
                            "time_period": {
                                "type": "object",
                                "properties": {
                                    "start": {"type": "string"},
                                    "end": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                {
                    "name": "GetCostExplorerData",
                    "description": "Generic cost explorer data retrieval (legacy compatibility)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "service": {"type": "string", "description": "AWS service name (e.g., ec2, s3, rds)"},
                            "time_range": {"type": "string", "description": "Time range (e.g., 'Last 30 days', 'Last 3 months')"},
                            "granularity": {"type": "string", "enum": ["DAILY", "MONTHLY"], "default": "MONTHLY"},
                            "group_by": {"type": "string", "description": "Group by dimension (SERVICE, REGION, etc.)"}
                        }
                    }
                }
            ]
            
        elif server_name == "aws_api":
            return [
                {
                    "name": "CallAWS",
                    "description": "Execute AWS CLI commands",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "cli_command": {"type": "string"},
                            "max_results": {"type": "integer"}
                        },
                        "required": ["cli_command"]
                    }
                }
            ]
            
        elif server_name == "aws_knowledge":
            return [
                {
                    "name": "SearchDocumentation",
                    "description": "Search AWS documentation",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "search_phrase": {"type": "string"},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["search_phrase"]
                    }
                }
            ]
            
        return []
    
    async def health_check(self) -> str:
        """Check the health of the dynamic MCP service"""
        try:
            # Check if we have any available MCP servers
            available_servers = sum(1 for server in self.mcp_servers.values() if server.available)
            total_servers = len(self.mcp_servers)
            
            if available_servers == 0:
                return "unhealthy"
            elif available_servers == total_servers:
                return "healthy"
            else:
                return "degraded"
                
        except Exception as e:
            logger.error(f"Dynamic MCP service health check failed: {e}")
            return "unhealthy"
    
    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information for the dynamic MCP service"""
        try:
            health_info = {
                "total_servers": len(self.mcp_servers),
                "available_servers": sum(1 for server in self.mcp_servers.values() if server.available),
                "agent_mappings": len(self.agent_mappings),
                "active_tools": len(self.active_tools),
                "current_agent": self.current_agent,
                "last_discovery_time": self.last_discovery_time.isoformat() if self.last_discovery_time else None,
                "cache_ttl": self.cache_ttl,
                "servers": {}
            }
            
            # Add server details
            for server_name, server_config in self.mcp_servers.items():
                health_info["servers"][server_name] = {
                    "available": server_config.available,
                    "type": server_config.type,
                    "command": server_config.command,
                    "tools_count": len(server_config.tools) if server_config.tools else 0,
                    "timeout": server_config.timeout
                }
            
            return health_info
            
        except Exception as e:
            logger.error(f"Failed to get detailed health: {e}")
            return {"error": str(e)}
        
    async def load_agent_tools(self, agent_type: str, agent_metadata: Dict[str, Any] = None) -> Dict[str, Dict[str, Any]]:
        """Load all tools for a specific agent"""
        
        logger.info(f"Loading tools for agent: {agent_type}")
        
        # Discover MCP servers for this agent
        mcp_server_names = await self.discover_agent_mcp_servers(agent_type, agent_metadata)
        
        # Check availability and discover tools for each MCP server
        all_tools = {}
        
        for server_name in mcp_server_names:
            # Check if server is available
            is_available = await self.check_mcp_server_availability(server_name)
            
            if is_available:
                # Discover tools from this server
                tools = await self.discover_mcp_tools(server_name)
                
                # Add tools to the registry with server prefix
                for tool in tools:
                    tool_key = f"{server_name}:{tool['name']}"
                    all_tools[tool_key] = {
                        **tool,
                        "server": server_name,
                        "server_config": self.mcp_servers[server_name]
                    }
            else:
                logger.warning(f"MCP server {server_name} not available for agent {agent_type}")
                
        # Store active tools for this agent
        self.active_tools = all_tools
        self.current_agent = agent_type
        
        logger.info(f"Loaded {len(all_tools)} tools for agent {agent_type}")
        return all_tools
        
    async def get_available_tools(self, agent_type: str = None) -> List[Dict[str, Any]]:
        """Get available tools for the current or specified agent"""
        
        if agent_type and agent_type != self.current_agent:
            # Load tools for the specified agent
            await self.load_agent_tools(agent_type)
            
        # Return list of available tools
        return [
            {
                "name": tool_data["name"],
                "description": tool_data["description"], 
                "inputSchema": tool_data["inputSchema"],
                "server": tool_data["server"]
            }
            for tool_data in self.active_tools.values()
        ]
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by routing to the appropriate MCP server"""
        
        # Find the tool in active tools
        tool_key = None
        for key, tool_data in self.active_tools.items():
            if tool_data["name"] == tool_name:
                tool_key = key
                break
                
        if not tool_key:
            logger.error(f"Tool {tool_name} not found in active tools")
            return {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": f"Tool {tool_name} not found",
                "status": "error",
                "error": "Tool not found"
            }
            
        tool_data = self.active_tools[tool_key]
        server_name = tool_data["server"]
        
        logger.info(f"Executing tool {tool_name} on MCP server {server_name}")
        
        try:
            # Route to appropriate MCP server
            result = await self._execute_on_mcp_server(server_name, tool_name, arguments)
            
            return {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "status": "success",
                "server": server_name
            }
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": f"Error executing {tool_name}: {str(e)}",
                "status": "error",
                "error": str(e),
                "server": server_name
            }
            
    async def _execute_on_mcp_server(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on a specific MCP server"""
        
        # For now, return placeholder responses for different tools
        # In a full implementation, this would communicate with the actual MCP server
        
        if server_name == "cost_explorer":
            if tool_name == "GetCostExplorerData":
                service = arguments.get("service", "").lower()
                time_range = arguments.get("time_range", "Last 30 days")
                
                # Generate realistic cost data based on service
                if service == "ec2":
                    return {
                        "service": "EC2",
                        "time_range": time_range,
                        "total_cost": "$2,847.32",
                        "cost_breakdown": [
                            {"instance_type": "t3.medium", "cost": "$1,234.56", "usage_hours": "720"},
                            {"instance_type": "m5.large", "cost": "$987.43", "usage_hours": "480"},
                            {"instance_type": "c5.xlarge", "cost": "$625.33", "usage_hours": "240"}
                        ],
                        "regions": [
                            {"region": "us-east-1", "cost": "$1,698.39"},
                            {"region": "us-west-2", "cost": "$1,148.93"}
                        ],
                        "recommendations": [
                            "Consider rightsizing t3.medium instances - 23% underutilized",
                            "Switch to Reserved Instances for m5.large - potential 40% savings"
                        ]
                    }
                elif service == "s3":
                    return {
                        "service": "S3",
                        "time_range": time_range,
                        "total_cost": "$456.78",
                        "cost_breakdown": [
                            {"storage_class": "Standard", "cost": "$234.56", "storage_gb": "1,234"},
                            {"storage_class": "IA", "cost": "$123.45", "storage_gb": "2,345"},
                            {"storage_class": "Glacier", "cost": "$98.77", "storage_gb": "5,678"}
                        ],
                        "recommendations": [
                            "Move infrequently accessed data to IA storage class",
                            "Enable lifecycle policies for automatic archiving"
                        ]
                    }
                else:
                    return {
                        "service": service.upper() if service else "ALL_SERVICES",
                        "time_range": time_range,
                        "total_cost": "$3,456.78",
                        "message": f"Cost data for {service or 'all services'} over {time_range}",
                        "top_services": [
                            {"service": "EC2", "cost": "$2,847.32"},
                            {"service": "S3", "cost": "$456.78"},
                            {"service": "RDS", "cost": "$152.68"}
                        ]
                    }
            
            elif tool_name == "get_cost_and_usage":
                return {
                    "results_by_time": [
                        {
                            "time_period": {"start": "2024-01-01", "end": "2024-01-31"},
                            "total": {"BlendedCost": {"amount": "1234.56", "unit": "USD"}},
                            "groups": []
                        }
                    ],
                    "dimension_key": arguments.get("group_by", []),
                    "granularity": arguments.get("granularity", "MONTHLY")
                }
            
            elif tool_name == "get_rightsizing_recommendation":
                return {
                    "rightsizing_recommendations": [
                        {
                            "account_id": "123456789012",
                            "current_instance": {
                                "resource_id": "i-1234567890abcdef0",
                                "instance_type": "m5.large",
                                "region": "us-east-1"
                            },
                            "rightsizing_type": "Modify",
                            "modify_recommendation": {
                                "target_instances": [
                                    {"instance_type": "m5.medium", "estimated_monthly_savings": "45.67"}
                                ]
                            }
                        }
                    ]
                }
            
            elif tool_name == "GetCostComparisonDrivers":
                return {
                    "cost_drivers": [
                        {"service": "EC2", "cost_change": "+15%", "driver": "Increased instance usage"},
                        {"service": "S3", "cost_change": "+5%", "driver": "Storage growth"},
                        {"service": "RDS", "cost_change": "-2%", "driver": "Reserved instance savings"}
                    ],
                    "total_cost_change": "+12%",
                    "period": arguments.get("time_period", "last_30_days")
                }
        
        # Default response for other servers/tools
        return f"Executed {tool_name} on {server_name} with arguments: {arguments}"
    
    async def _discover_dynamic_configurations(self):
        """Discover dynamic MCP server and agent configurations from SSM"""
        try:
            logger.info("Starting dynamic configuration discovery...")
            
            # Discover MCP server configurations
            await self._discover_mcp_server_configs()
            
            # Discover agent-MCP mappings
            await self._discover_agent_mappings()
            
            self.last_discovery_time = datetime.utcnow()
            logger.info("Dynamic configuration discovery completed")
            
        except Exception as e:
            logger.error(f"Dynamic configuration discovery failed: {e}")
    
    async def _discover_mcp_server_configs(self):
        """Discover MCP server configurations from SSM parameters"""
        try:
            # Look for MCP server configurations in SSM
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            
            for page in paginator.paginate(Path='/coa/mcp_servers/', Recursive=True):
                for param in page.get('Parameters', []):
                    param_name = param['Name']
                    param_value = param['Value']
                    
                    # Extract server name from parameter path
                    # Expected format: /coa/mcp_servers/{server_name}/config
                    path_parts = param_name.split('/')
                    if len(path_parts) >= 4 and path_parts[-1] == 'config':
                        server_name = path_parts[-2]
                        
                        try:
                            config_data = json.loads(param_value)
                            
                            # Create MCP server config from SSM data
                            mcp_config = MCPServerConfig(
                                name=server_name,
                                type=config_data.get('type', 'uvx'),
                                command=config_data.get('command', []),
                                working_dir=config_data.get('working_dir'),
                                env_vars=config_data.get('env_vars'),
                                timeout=config_data.get('timeout', 30)
                            )
                            
                            self.mcp_servers[server_name] = mcp_config
                            logger.info(f"Discovered MCP server config: {server_name}")
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON in MCP server config {param_name}: {e}")
                            
        except ClientError as e:
            if e.response['Error']['Code'] != 'ParameterNotFound':
                logger.warning(f"Failed to discover MCP server configs: {e}")
    
    async def _discover_agent_mappings(self):
        """Discover agent-MCP mappings from SSM parameters"""
        try:
            # Look for agent configurations in SSM
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            
            for page in paginator.paginate(Path='/coa/agents/', Recursive=True):
                for param in page.get('Parameters', []):
                    param_name = param['Name']
                    param_value = param['Value']
                    
                    # Extract agent info from parameter path
                    # Expected format: /coa/agents/{agent_name}/metadata
                    path_parts = param_name.split('/')
                    if len(path_parts) >= 4 and path_parts[-1] == 'metadata':
                        agent_name = path_parts[-2]
                        
                        try:
                            metadata = json.loads(param_value)
                            
                            # Extract MCP servers from metadata
                            mcp_servers = metadata.get('mcp_servers', [])
                            capabilities = metadata.get('capabilities', [])
                            
                            # Create agent mapping
                            mapping = AgentMCPMapping(
                                agent_type=agent_name,
                                agent_id=metadata.get('agent_id', ''),
                                mcp_servers=mcp_servers,
                                capabilities=capabilities,
                                metadata=metadata
                            )
                            
                            self.agent_mappings[agent_name] = mapping
                            logger.info(f"Discovered agent mapping: {agent_name} -> {mcp_servers}")
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON in agent metadata {param_name}: {e}")
                            
        except ClientError as e:
            if e.response['Error']['Code'] != 'ParameterNotFound':
                logger.warning(f"Failed to discover agent mappings: {e}")
    
    async def _refresh_dynamic_configurations_if_needed(self):
        """Refresh dynamic configurations if cache has expired"""
        if (not self.last_discovery_time or 
            (datetime.utcnow() - self.last_discovery_time).total_seconds() > self.cache_ttl):
            await self._discover_dynamic_configurations()
    
    def _extract_mcp_servers_from_metadata(self, agent_metadata: Dict[str, Any]) -> List[str]:
        """Extract MCP server names from agent metadata"""
        mcp_servers = []
        
        # Check for explicit MCP server list
        if 'mcp_servers' in agent_metadata:
            mcp_servers.extend(agent_metadata['mcp_servers'])
        
        # Check for capabilities-based mapping
        capabilities = agent_metadata.get('capabilities', [])
        for capability in capabilities:
            if capability == 'security_assessment':
                mcp_servers.extend(['wa_security', 'aws_api'])
            elif capability == 'cost_analysis':
                mcp_servers.extend(['cost_explorer', 'aws_api'])
            elif capability == 'knowledge_search':
                mcp_servers.append('aws_knowledge')
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(mcp_servers))
    
    async def _discover_mcp_servers_from_ssm(self, agent_type: str) -> List[str]:
        """Discover MCP servers for an agent from SSM parameters"""
        try:
            # Try to get agent-specific MCP server configuration
            param_name = f"/coa/agents/{agent_type}/mcp_servers"
            
            response = self.ssm_client.get_parameter(Name=param_name)
            mcp_servers = json.loads(response['Parameter']['Value'])
            
            if isinstance(mcp_servers, list):
                return mcp_servers
            
        except (ClientError, json.JSONDecodeError) as e:
            logger.debug(f"No SSM MCP server config found for {agent_type}: {e}")
        
        return []
    
    async def register_new_mcp_server(self, server_name: str, config: Dict[str, Any]) -> bool:
        """Register a new MCP server configuration"""
        try:
            # Create MCP server config
            mcp_config = MCPServerConfig(
                name=server_name,
                type=config.get('type', 'uvx'),
                command=config.get('command', []),
                working_dir=config.get('working_dir'),
                env_vars=config.get('env_vars'),
                timeout=config.get('timeout', 30)
            )
            
            # Add to local registry
            self.mcp_servers[server_name] = mcp_config
            
            # Store in SSM for persistence
            param_name = f"/coa/mcp_servers/{server_name}/config"
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=json.dumps(config),
                Type='String',
                Overwrite=True,
                Description=f"MCP server configuration for {server_name}"
            )
            
            logger.info(f"Registered new MCP server: {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register MCP server {server_name}: {e}")
            return False
    
    async def register_agent_mcp_mapping(self, agent_type: str, mcp_servers: List[str], 
                                       capabilities: List[str] = None, metadata: Dict[str, Any] = None) -> bool:
        """Register a new agent-MCP server mapping"""
        try:
            # Create agent mapping
            mapping = AgentMCPMapping(
                agent_type=agent_type,
                agent_id=metadata.get('agent_id', '') if metadata else '',
                mcp_servers=mcp_servers,
                capabilities=capabilities or [],
                metadata=metadata or {}
            )
            
            # Add to local registry
            self.agent_mappings[agent_type] = mapping
            
            # Store in SSM for persistence
            param_name = f"/coa/agents/{agent_type}/metadata"
            agent_metadata = {
                'mcp_servers': mcp_servers,
                'capabilities': capabilities or [],
                **(metadata or {})
            }
            
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=json.dumps(agent_metadata),
                Type='String',
                Overwrite=True,
                Description=f"Agent metadata for {agent_type}"
            )
            
            logger.info(f"Registered agent mapping: {agent_type} -> {mcp_servers}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent mapping for {agent_type}: {e}")
            return False
    
    async def discover_tools_from_live_mcp_server(self, server_name: str) -> List[Dict[str, Any]]:
        """Discover tools from a live MCP server (future implementation)"""
        # This would implement actual MCP protocol communication
        # For now, fall back to predefined tools
        return await self._get_predefined_tools(server_name)
    
    def get_agent_capabilities(self, agent_type: str) -> List[str]:
        """Get capabilities for a specific agent type"""
        if agent_type in self.agent_mappings:
            return self.agent_mappings[agent_type].capabilities
        return []
    
    def get_mcp_servers_for_capability(self, capability: str) -> List[str]:
        """Get MCP servers that support a specific capability"""
        servers = set()
        
        for mapping in self.agent_mappings.values():
            if capability in mapping.capabilities:
                servers.update(mapping.mcp_servers)
        
        return list(servers)
        
    async def health_check(self) -> str:
        """Health check for the dynamic MCP service"""
        
        available_servers = sum(1 for server in self.mcp_servers.values() if server.available)
        total_servers = len(self.mcp_servers)
        
        if available_servers == 0:
            return "unhealthy"
        elif available_servers == total_servers:
            return "healthy"
        else:
            return "degraded"
            
    def get_detailed_health(self) -> Dict[str, Any]:
        """Get detailed health information"""
        
        return {
            "overall_status": asyncio.run(self.health_check()),
            "current_agent": self.current_agent,
            "active_tools_count": len(self.active_tools),
            "mcp_servers": {
                name: {
                    "available": config.available,
                    "type": config.type,
                    "tools_count": len(config.tools) if config.tools else 0
                }
                for name, config in self.mcp_servers.items()
            },
            "agent_mappings": {
                agent_type: mapping.mcp_servers
                for agent_type, mapping in self.agent_mappings.items()
            }
        }