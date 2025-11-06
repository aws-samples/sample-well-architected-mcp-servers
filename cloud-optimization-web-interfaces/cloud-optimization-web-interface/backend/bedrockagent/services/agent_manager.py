"""
Agent Manager service for discovering, selecting, and managing agents.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from models.data_models import AgentInfo, AgentFramework, AgentStatus, CommandResponse


logger = logging.getLogger(__name__)


class AgentManager:
    """Manages agent discovery, selection, and metadata."""
    
    def __init__(self, region: str = "us-east-1", cache_ttl_seconds: int = 300):
        """
        Initialize the Agent Manager.
        
        Args:
            region: AWS region for SSM Parameter Store
            cache_ttl_seconds: Cache TTL in seconds (default: 5 minutes)
        """
        self.region = region
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        
        # Initialize AWS clients
        try:
            self.ssm_client = boto3.client('ssm', region_name=region)
        except (NoCredentialsError, ClientError, Exception) as e:
            logger.error(f"Failed to initialize SSM client: {e}")
            self.ssm_client = None
        
        # Cache for agent metadata
        self.agents: Dict[str, AgentInfo] = {}
        self.last_discovery: Optional[datetime] = None
        
        # Session-based agent selection
        self.session_agents: Dict[str, str] = {}  # session_id -> agent_id
        
        # Discovery metrics
        self.discovery_metrics = {
            "total_discoveries": 0,
            "successful_discoveries": 0,
            "failed_discoveries": 0,
            "last_error": None,
            "last_error_time": None,
            "average_discovery_time_ms": 0.0
        }
        
        logger.info(f"AgentManager initialized for region {region} with {cache_ttl_seconds}s cache TTL")

    async def discover_agents(self, force_refresh: bool = False) -> Dict[str, AgentInfo]:
        """
        Discover agents from SSM Parameter Store.
        
        Args:
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            Dictionary of agent_id -> AgentInfo
        """
        # Check if cache is still valid
        if not force_refresh and self._is_cache_valid():
            logger.debug("Using cached agent data")
            return self.agents
        
        if not self.ssm_client:
            logger.error("SSM client not available, cannot discover agents")
            self.discovery_metrics["failed_discoveries"] += 1
            self.discovery_metrics["last_error"] = "SSM client not available"
            self.discovery_metrics["last_error_time"] = datetime.utcnow().isoformat()
            return self.agents
        
        start_time = datetime.utcnow()
        self.discovery_metrics["total_discoveries"] += 1
        
        try:
            logger.info("Discovering agents from SSM Parameter Store")
            
            # Query SSM for agent metadata parameters
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            page_iterator = paginator.paginate(
                Path='/coa/agents/',
                Recursive=True,
                ParameterFilters=[
                    {
                        'Key': 'Name',
                        'Option': 'Contains',
                        'Values': ['metadata']
                    }
                ]
            )
            
            discovered_agents = {}
            parsing_errors = 0
            
            for page in page_iterator:
                for parameter in page.get('Parameters', []):
                    try:
                        agent_info = self._parse_agent_parameter(parameter)
                        if agent_info:
                            discovered_agents[agent_info.agent_id] = agent_info
                            logger.debug(f"Discovered agent: {agent_info.agent_id}")
                    except Exception as e:
                        parsing_errors += 1
                        logger.warning(f"Failed to parse agent parameter {parameter['Name']}: {e}")
            
            # Update cache
            self.agents = discovered_agents
            self.last_discovery = datetime.utcnow()
            
            # Update metrics
            self.discovery_metrics["successful_discoveries"] += 1
            discovery_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Update average discovery time (simple moving average)
            current_avg = self.discovery_metrics["average_discovery_time_ms"]
            total_successful = self.discovery_metrics["successful_discoveries"]
            self.discovery_metrics["average_discovery_time_ms"] = (
                (current_avg * (total_successful - 1) + discovery_time) / total_successful
            )
            
            if parsing_errors > 0:
                logger.warning(f"Discovery completed with {parsing_errors} parsing errors")
            
            logger.info(f"Discovered {len(discovered_agents)} agents in {discovery_time:.1f}ms")
            return discovered_agents
            
        except ClientError as e:
            self.discovery_metrics["failed_discoveries"] += 1
            self.discovery_metrics["last_error"] = str(e)
            self.discovery_metrics["last_error_time"] = datetime.utcnow().isoformat()
            logger.error(f"Failed to discover agents from SSM: {e}")
            return self.agents
        except Exception as e:
            self.discovery_metrics["failed_discoveries"] += 1
            self.discovery_metrics["last_error"] = str(e)
            self.discovery_metrics["last_error_time"] = datetime.utcnow().isoformat()
            logger.error(f"Unexpected error during agent discovery: {e}")
            return self.agents

    def _parse_agent_parameter(self, parameter: Dict) -> Optional[AgentInfo]:
        """
        Parse an SSM parameter into AgentInfo, extracting MCP tool counts and capabilities.
        
        Args:
            parameter: SSM parameter dictionary
            
        Returns:
            AgentInfo object or None if parsing fails
        """
        try:
            # Extract agent_id from parameter name
            # Expected format: /coa/agents/{agent_id}/metadata
            name_parts = parameter['Name'].split('/')
            if len(name_parts) < 4 or name_parts[-1] != 'metadata':
                logger.warning(f"Invalid parameter name format: {parameter['Name']}")
                return None
            
            agent_id = name_parts[3]
            
            # Parse parameter value as JSON
            metadata = json.loads(parameter['Value'])
            
            # Extract required fields
            name = metadata.get('name', agent_id)
            description = metadata.get('description', '')
            capabilities = metadata.get('capabilities', [])
            
            # Extract MCP tool count with enhanced parsing
            tool_count = self._extract_mcp_tool_count(metadata, agent_id)
            
            # Validate capabilities list
            if not isinstance(capabilities, list):
                logger.warning(f"Invalid capabilities format for agent {agent_id}, converting to list")
                capabilities = [str(capabilities)] if capabilities else []
            
            # Determine framework
            framework_str = metadata.get('framework', 'bedrock').lower()
            try:
                framework = AgentFramework(framework_str)
            except ValueError:
                logger.warning(f"Unknown framework '{framework_str}' for agent {agent_id}, defaulting to bedrock")
                framework = AgentFramework.BEDROCK
            
            # Optional fields
            endpoint_url = metadata.get('endpoint_url')
            
            # Determine status
            status_str = metadata.get('status', 'available').lower()
            try:
                status = AgentStatus(status_str)
            except ValueError:
                logger.warning(f"Unknown status '{status_str}' for agent {agent_id}, defaulting to available")
                status = AgentStatus.AVAILABLE
            
            logger.debug(f"Parsed agent {agent_id}: {len(capabilities)} capabilities, {tool_count} MCP tools")
            
            return AgentInfo(
                agent_id=agent_id,
                name=name,
                description=description,
                capabilities=capabilities,
                tool_count=tool_count,
                framework=framework,
                endpoint_url=endpoint_url,
                status=status,
                last_updated=datetime.utcnow()
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in parameter {parameter['Name']}: {e}")
            return None
        except KeyError as e:
            logger.error(f"Missing required field in parameter {parameter['Name']}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing parameter {parameter['Name']}: {e}")
            return None

    def _extract_mcp_tool_count(self, metadata: Dict, agent_id: str) -> int:
        """
        Extract MCP tool count from agent metadata with enhanced parsing.
        
        Args:
            metadata: Agent metadata dictionary
            agent_id: Agent identifier for logging
            
        Returns:
            Number of MCP tools available to the agent
        """
        try:
            # Primary field: tool_count
            if 'tool_count' in metadata:
                tool_count = metadata['tool_count']
                if isinstance(tool_count, int) and tool_count >= 0:
                    return tool_count
                elif isinstance(tool_count, str) and tool_count.isdigit():
                    return int(tool_count)
                else:
                    logger.warning(f"Invalid tool_count format for agent {agent_id}: {tool_count}")
            
            # Alternative field: mcp_tool_count
            if 'mcp_tool_count' in metadata:
                mcp_tool_count = metadata['mcp_tool_count']
                if isinstance(mcp_tool_count, int) and mcp_tool_count >= 0:
                    return mcp_tool_count
                elif isinstance(mcp_tool_count, str) and mcp_tool_count.isdigit():
                    return int(mcp_tool_count)
            
            # Alternative field: tools (array or object)
            if 'tools' in metadata:
                tools = metadata['tools']
                if isinstance(tools, list):
                    return len(tools)
                elif isinstance(tools, dict) and 'count' in tools:
                    count = tools['count']
                    if isinstance(count, int) and count >= 0:
                        return count
            
            # Alternative field: mcp_tools (array or object)
            if 'mcp_tools' in metadata:
                mcp_tools = metadata['mcp_tools']
                if isinstance(mcp_tools, list):
                    return len(mcp_tools)
                elif isinstance(mcp_tools, dict) and 'count' in mcp_tools:
                    count = mcp_tools['count']
                    if isinstance(count, int) and count >= 0:
                        return count
            
            # Default to 0 if no valid tool count found
            logger.debug(f"No valid MCP tool count found for agent {agent_id}, defaulting to 0")
            return 0
            
        except Exception as e:
            logger.error(f"Error extracting MCP tool count for agent {agent_id}: {e}")
            return 0

    def _is_cache_valid(self) -> bool:
        """Check if the agent cache is still valid."""
        if self.last_discovery is None:
            return False
        
        return datetime.utcnow() - self.last_discovery < self.cache_ttl

    async def get_agent_info(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get information about a specific agent.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            AgentInfo object or None if not found
        """
        # Ensure we have fresh agent data
        await self.discover_agents()
        
        return self.agents.get(agent_id)

    async def get_agent_capabilities(self, agent_id: str) -> List[str]:
        """
        Get capabilities for a specific agent.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            List of capability strings
        """
        try:
            agent_info = await self.get_agent_info(agent_id)
            if not agent_info:
                logger.warning(f"Agent {agent_id} not found when retrieving capabilities")
                return []
            
            logger.debug(f"Retrieved {len(agent_info.capabilities)} capabilities for agent {agent_id}")
            return agent_info.capabilities
            
        except Exception as e:
            logger.error(f"Error retrieving capabilities for agent {agent_id}: {e}")
            return []

    async def get_agent_tool_count(self, agent_id: str) -> int:
        """
        Get MCP tool count for a specific agent.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            Number of MCP tools available to the agent
        """
        try:
            agent_info = await self.get_agent_info(agent_id)
            if not agent_info:
                logger.warning(f"Agent {agent_id} not found when retrieving tool count")
                return 0
            
            logger.debug(f"Agent {agent_id} has {agent_info.tool_count} MCP tools available")
            return agent_info.tool_count
            
        except Exception as e:
            logger.error(f"Error retrieving tool count for agent {agent_id}: {e}")
            return 0

    async def get_detailed_agent_capabilities(self, agent_id: str) -> Dict[str, any]:
        """
        Get detailed capability information for a specific agent.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            Dictionary with detailed capability information
        """
        try:
            agent_info = await self.get_agent_info(agent_id)
            if not agent_info:
                return {
                    "agent_id": agent_id,
                    "found": False,
                    "error": "Agent not found"
                }
            
            is_healthy = await self.check_agent_health(agent_id)
            
            return {
                "agent_id": agent_id,
                "found": True,
                "name": agent_info.name,
                "description": agent_info.description,
                "framework": agent_info.framework.value,
                "status": agent_info.status.value,
                "is_healthy": is_healthy,
                "capabilities": {
                    "list": agent_info.capabilities,
                    "count": len(agent_info.capabilities)
                },
                "tools": {
                    "count": agent_info.tool_count,
                    "framework_type": agent_info.framework.value
                },
                "metadata": {
                    "endpoint_url": agent_info.endpoint_url,
                    "last_updated": agent_info.last_updated.isoformat() if agent_info.last_updated else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting detailed capabilities for agent {agent_id}: {e}")
            return {
                "agent_id": agent_id,
                "found": False,
                "error": str(e)
            }

    def select_agent_for_session(self, session_id: str, agent_id: str) -> CommandResponse:
        """
        Select an agent for a specific session.
        
        Args:
            session_id: The session identifier
            agent_id: The agent identifier to select
            
        Returns:
            CommandResponse indicating success or failure
        """
        try:
            # Validate agent exists
            if agent_id not in self.agents:
                return CommandResponse(
                    success=False,
                    message=f"Agent '{agent_id}' not found. Use '/agent list' to see available agents.",
                    command_type="select"
                )
            
            agent_info = self.agents[agent_id]
            
            # Check agent status
            if agent_info.status != AgentStatus.AVAILABLE:
                return CommandResponse(
                    success=False,
                    message=f"Agent '{agent_id}' is currently {agent_info.status.value}.",
                    command_type="select"
                )
            
            # Store selection
            self.session_agents[session_id] = agent_id
            
            logger.info(f"Selected agent '{agent_id}' for session '{session_id}'")
            
            return CommandResponse(
                success=True,
                message=f"Selected agent: {agent_info.name} ({agent_info.tool_count} tools available)",
                data={
                    "agent_id": agent_id,
                    "agent_name": agent_info.name,
                    "tool_count": agent_info.tool_count,
                    "capabilities": agent_info.capabilities
                },
                command_type="select"
            )
            
        except Exception as e:
            logger.error(f"Error selecting agent for session {session_id}: {e}")
            return CommandResponse(
                success=False,
                message="An error occurred while selecting the agent.",
                command_type="select"
            )

    def get_selected_agent(self, session_id: str) -> Optional[str]:
        """
        Get the selected agent for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Agent ID if selected, None otherwise
        """
        return self.session_agents.get(session_id)

    def clear_agent_selection(self, session_id: str) -> CommandResponse:
        """
        Clear agent selection for a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            CommandResponse indicating the result
        """
        try:
            if session_id in self.session_agents:
                agent_id = self.session_agents.pop(session_id)
                logger.info(f"Cleared agent selection for session '{session_id}' (was '{agent_id}')")
                return CommandResponse(
                    success=True,
                    message="Agent selection cleared. Queries will use intelligent routing.",
                    command_type="clear"
                )
            else:
                return CommandResponse(
                    success=True,
                    message="No agent was selected for this session.",
                    command_type="clear"
                )
                
        except Exception as e:
            logger.error(f"Error clearing agent selection for session {session_id}: {e}")
            return CommandResponse(
                success=False,
                message="An error occurred while clearing agent selection.",
                command_type="clear"
            )

    async def list_agents(self, session_id: Optional[str] = None) -> CommandResponse:
        """
        List all available agents.
        
        Args:
            session_id: Optional session ID to include current selection
            
        Returns:
            CommandResponse with agent list data
        """
        try:
            # Ensure we have fresh agent data
            agents = await self.discover_agents()
            
            if not agents:
                return CommandResponse(
                    success=True,
                    message="No agents are currently available.",
                    data={"agents": [], "selected_agent": None},
                    command_type="list"
                )
            
            # Format agent list
            agent_list = []
            for agent_id, agent_info in agents.items():
                agent_list.append({
                    "agent_id": agent_id,
                    "name": agent_info.name,
                    "description": agent_info.description,
                    "tool_count": agent_info.tool_count,
                    "capabilities": agent_info.capabilities,
                    "framework": agent_info.framework.value,
                    "status": agent_info.status.value
                })
            
            # Sort by name for consistent ordering
            agent_list.sort(key=lambda x: x["name"])
            
            # Get current selection
            selected_agent = self.get_selected_agent(session_id) if session_id else None
            
            # Create message
            message_lines = ["Available agents:"]
            for agent in agent_list:
                status_indicator = "✓" if agent["agent_id"] == selected_agent else " "
                message_lines.append(
                    f"{status_indicator} {agent['name']} ({agent['tool_count']} tools) - {agent['description']}"
                )
            
            if selected_agent:
                message_lines.append(f"\nCurrently selected: {agents[selected_agent].name}")
            else:
                message_lines.append("\nNo agent selected (using intelligent routing)")
            
            return CommandResponse(
                success=True,
                message="\n".join(message_lines),
                data={
                    "agents": agent_list,
                    "selected_agent": selected_agent,
                    "total_count": len(agent_list)
                },
                command_type="list"
            )
            
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return CommandResponse(
                success=False,
                message="An error occurred while listing agents.",
                command_type="list"
            )

    async def check_agent_health(self, agent_id: str) -> bool:
        """
        Check if an agent is healthy and available with comprehensive status monitoring.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            True if agent is healthy, False otherwise
        """
        try:
            agent_info = await self.get_agent_info(agent_id)
            if not agent_info:
                logger.warning(f"Agent {agent_id} not found during health check")
                return False
            
            # Check basic availability
            if agent_info.status != AgentStatus.AVAILABLE:
                logger.debug(f"Agent {agent_id} is not available (status: {agent_info.status})")
                return False
            
            # Check if agent has valid tool count
            if agent_info.tool_count < 0:
                logger.warning(f"Agent {agent_id} has invalid tool count: {agent_info.tool_count}")
                return False
            
            # Check if agent has capabilities defined
            if not agent_info.capabilities:
                logger.debug(f"Agent {agent_id} has no capabilities defined")
                # This is a warning but not a failure condition
            
            # Check if agent metadata is recent (within last 2 hours for health check)
            if agent_info.last_updated:
                age = datetime.utcnow() - agent_info.last_updated
                if age.total_seconds() > 7200:  # 2 hours
                    logger.warning(f"Agent {agent_id} metadata is stale (last updated: {agent_info.last_updated})")
                    # Still consider healthy, but log warning
            
            # Framework-specific health checks
            if agent_info.framework == AgentFramework.BEDROCK:
                # For Bedrock agents, check if they have a valid agent_id format
                if not agent_id or len(agent_id) < 3:
                    logger.warning(f"Bedrock agent {agent_id} has invalid ID format")
                    return False
                logger.debug(f"Bedrock agent {agent_id} health check passed")
                
            elif agent_info.framework == AgentFramework.AGENTCORE:
                # For AgentCore agents, check endpoint URL if provided
                if agent_info.endpoint_url:
                    if not agent_info.endpoint_url.startswith(('http://', 'https://')):
                        logger.warning(f"AgentCore agent {agent_id} has invalid endpoint URL: {agent_info.endpoint_url}")
                        return False
                    logger.debug(f"AgentCore agent {agent_id} endpoint: {agent_info.endpoint_url}")
                else:
                    logger.debug(f"AgentCore agent {agent_id} has no endpoint URL defined")
            
            logger.debug(f"Agent {agent_id} health check passed (framework: {agent_info.framework.value}, tools: {agent_info.tool_count})")
            return True
            
        except Exception as e:
            logger.error(f"Error checking health for agent {agent_id}: {e}")
            return False

    async def get_agent_health_details(self, agent_id: str) -> Dict[str, any]:
        """
        Get detailed health information for a specific agent.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            Dictionary with detailed health information
        """
        try:
            agent_info = await self.get_agent_info(agent_id)
            if not agent_info:
                return {
                    "agent_id": agent_id,
                    "healthy": False,
                    "status": "not_found",
                    "checks": {
                        "agent_exists": False,
                        "status_available": False,
                        "valid_tool_count": False,
                        "metadata_fresh": False,
                        "framework_valid": False
                    },
                    "details": {
                        "error": "Agent not found"
                    }
                }
            
            # Perform individual health checks
            checks = {
                "agent_exists": True,
                "status_available": agent_info.status == AgentStatus.AVAILABLE,
                "valid_tool_count": agent_info.tool_count >= 0,
                "has_capabilities": len(agent_info.capabilities) > 0,
                "metadata_fresh": True,
                "framework_valid": True
            }
            
            details = {
                "agent_name": agent_info.name,
                "framework": agent_info.framework.value,
                "status": agent_info.status.value,
                "tool_count": agent_info.tool_count,
                "capabilities_count": len(agent_info.capabilities),
                "last_updated": agent_info.last_updated.isoformat() if agent_info.last_updated else None
            }
            
            # Check metadata freshness
            if agent_info.last_updated:
                age_seconds = (datetime.utcnow() - agent_info.last_updated).total_seconds()
                details["metadata_age_seconds"] = age_seconds
                checks["metadata_fresh"] = age_seconds < 7200  # 2 hours
            
            # Framework-specific checks
            if agent_info.framework == AgentFramework.AGENTCORE:
                if agent_info.endpoint_url:
                    checks["valid_endpoint"] = agent_info.endpoint_url.startswith(('http://', 'https://'))
                    details["endpoint_url"] = agent_info.endpoint_url
                else:
                    checks["valid_endpoint"] = False
                    details["endpoint_url"] = None
            
            # Overall health status
            is_healthy = all([
                checks["agent_exists"],
                checks["status_available"],
                checks["valid_tool_count"],
                checks["framework_valid"]
            ])
            
            return {
                "agent_id": agent_id,
                "healthy": is_healthy,
                "status": "healthy" if is_healthy else "unhealthy",
                "checks": checks,
                "details": details
            }
            
        except Exception as e:
            logger.error(f"Error getting health details for agent {agent_id}: {e}")
            return {
                "agent_id": agent_id,
                "healthy": False,
                "status": "error",
                "checks": {},
                "details": {
                    "error": str(e)
                }
            }

    def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up agent selections for old sessions.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        # For now, we don't track session timestamps
        # This would need to be enhanced with session timestamp tracking
        # For simplicity, we'll just clean up all sessions older than max_age
        
        # This is a placeholder implementation
        # In a real implementation, we'd track session timestamps
        cleaned_count = 0
        
        logger.info(f"Session cleanup completed, removed {cleaned_count} inactive sessions")
        return cleaned_count

    async def get_agent_status_summary(self) -> Dict[str, any]:
        """
        Get comprehensive status summary for all agents.
        
        Returns:
            Dictionary with agent status information
        """
        try:
            # Ensure we have fresh agent data
            agents = await self.discover_agents()
            
            status_counts = {
                AgentStatus.AVAILABLE.value: 0,
                AgentStatus.UNAVAILABLE.value: 0,
                AgentStatus.ERROR.value: 0
            }
            
            framework_counts = {
                AgentFramework.BEDROCK.value: 0,
                AgentFramework.AGENTCORE.value: 0
            }
            
            total_tools = 0
            agent_details = []
            
            for agent_id, agent_info in agents.items():
                # Count by status
                status_counts[agent_info.status.value] += 1
                
                # Count by framework
                framework_counts[agent_info.framework.value] += 1
                
                # Sum total tools
                total_tools += agent_info.tool_count
                
                # Check health
                is_healthy = await self.check_agent_health(agent_id)
                
                agent_details.append({
                    "agent_id": agent_id,
                    "name": agent_info.name,
                    "status": agent_info.status.value,
                    "framework": agent_info.framework.value,
                    "tool_count": agent_info.tool_count,
                    "capabilities_count": len(agent_info.capabilities),
                    "is_healthy": is_healthy,
                    "last_updated": agent_info.last_updated.isoformat() if agent_info.last_updated else None
                })
            
            return {
                "total_agents": len(agents),
                "status_breakdown": status_counts,
                "framework_breakdown": framework_counts,
                "total_tools_available": total_tools,
                "healthy_agents": sum(1 for detail in agent_details if detail["is_healthy"]),
                "agent_details": agent_details,
                "cache_info": self.get_cache_info()
            }
            
        except Exception as e:
            logger.error(f"Error getting agent status summary: {e}")
            return {
                "total_agents": 0,
                "status_breakdown": {},
                "framework_breakdown": {},
                "total_tools_available": 0,
                "healthy_agents": 0,
                "agent_details": [],
                "cache_info": self.get_cache_info(),
                "error": str(e)
            }

    def get_discovery_metrics(self) -> Dict[str, any]:
        """
        Get agent discovery performance metrics.
        
        Returns:
            Dictionary with discovery metrics
        """
        success_rate = 0.0
        if self.discovery_metrics["total_discoveries"] > 0:
            success_rate = (
                self.discovery_metrics["successful_discoveries"] / 
                self.discovery_metrics["total_discoveries"]
            ) * 100
        
        return {
            **self.discovery_metrics,
            "success_rate_percent": round(success_rate, 2)
        }

    async def monitor_agent_status_changes(self) -> Dict[str, any]:
        """
        Monitor and detect changes in agent status and capabilities.
        
        Returns:
            Dictionary with status change information
        """
        try:
            # Store current agent state for comparison
            previous_agents = self.agents.copy()
            
            # Discover fresh agent data
            current_agents = await self.discover_agents(force_refresh=True)
            
            changes = {
                "timestamp": datetime.utcnow().isoformat(),
                "new_agents": [],
                "removed_agents": [],
                "status_changes": [],
                "capability_changes": [],
                "tool_count_changes": []
            }
            
            # Find new agents
            for agent_id in current_agents:
                if agent_id not in previous_agents:
                    changes["new_agents"].append({
                        "agent_id": agent_id,
                        "name": current_agents[agent_id].name,
                        "tool_count": current_agents[agent_id].tool_count
                    })
            
            # Find removed agents
            for agent_id in previous_agents:
                if agent_id not in current_agents:
                    changes["removed_agents"].append({
                        "agent_id": agent_id,
                        "name": previous_agents[agent_id].name
                    })
            
            # Find changes in existing agents
            for agent_id in current_agents:
                if agent_id in previous_agents:
                    current = current_agents[agent_id]
                    previous = previous_agents[agent_id]
                    
                    # Status changes
                    if current.status != previous.status:
                        changes["status_changes"].append({
                            "agent_id": agent_id,
                            "name": current.name,
                            "old_status": previous.status.value,
                            "new_status": current.status.value
                        })
                    
                    # Capability changes
                    if set(current.capabilities) != set(previous.capabilities):
                        changes["capability_changes"].append({
                            "agent_id": agent_id,
                            "name": current.name,
                            "added_capabilities": list(set(current.capabilities) - set(previous.capabilities)),
                            "removed_capabilities": list(set(previous.capabilities) - set(current.capabilities))
                        })
                    
                    # Tool count changes
                    if current.tool_count != previous.tool_count:
                        changes["tool_count_changes"].append({
                            "agent_id": agent_id,
                            "name": current.name,
                            "old_count": previous.tool_count,
                            "new_count": current.tool_count,
                            "change": current.tool_count - previous.tool_count
                        })
            
            # Log significant changes
            total_changes = (
                len(changes["new_agents"]) + 
                len(changes["removed_agents"]) + 
                len(changes["status_changes"]) + 
                len(changes["capability_changes"]) + 
                len(changes["tool_count_changes"])
            )
            
            if total_changes > 0:
                logger.info(f"Detected {total_changes} agent changes during status monitoring")
            else:
                logger.debug("No agent changes detected during status monitoring")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error monitoring agent status changes: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "new_agents": [],
                "removed_agents": [],
                "status_changes": [],
                "capability_changes": [],
                "tool_count_changes": []
            }

    def get_cache_info(self) -> Dict[str, any]:
        """
        Get information about the current cache state.
        
        Returns:
            Dictionary with cache information
        """
        return {
            "agent_count": len(self.agents),
            "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None,
            "cache_valid": self._is_cache_valid(),
            "cache_ttl_seconds": self.cache_ttl.total_seconds(),
            "active_sessions": len(self.session_agents)
        }