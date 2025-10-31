"""
Command Manager - Processes command-based interactions and routes requests to appropriate services.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from models.agentcore_models import CommandResponse, CommandType
from models.agentcore_interfaces import (
    CommandManagerInterface, AgentRegistryInterface, AgentDiscoveryInterface
)
from models.exceptions import CommandProcessingError
from utils.parameter_manager import get_parameter_manager, ParameterManagerError

logger = logging.getLogger(__name__)


class CommandManager(CommandManagerInterface):
    """Processes command-based interactions and routes requests to appropriate services."""
    
    def __init__(self, 
                 registry: AgentRegistryInterface, 
                 discovery: AgentDiscoveryInterface):
        """
        Initialize the command manager.
        
        Args:
            registry: Agent registry service
            discovery: Agent discovery service
        """
        self.registry = registry
        self.discovery = discovery
        
        # Command handlers mapping
        self.command_handlers = self._initialize_handlers()
        
        # Command patterns for validation
        self.command_patterns = {
            "list": re.compile(r"^/agentcore\s+list(?:\s+(.*))?$", re.IGNORECASE),
            "discover": re.compile(r"^/agentcore\s+discover(?:\s+(.*))?$", re.IGNORECASE),
            "status": re.compile(r"^/agentcore\s+status(?:\s+(.*))?$", re.IGNORECASE),
            "help": re.compile(r"^/agentcore\s+help(?:\s+(.*))?$", re.IGNORECASE),
            "start": re.compile(r"^/agentcore\s+start(?:\s+(.*))?$", re.IGNORECASE),
            "stop": re.compile(r"^/agentcore\s+stop(?:\s+(.*))?$", re.IGNORECASE),
            "config": re.compile(r"^/agentcore\s+config(?:\s+(.*))?$", re.IGNORECASE),
            "runtime": re.compile(r"^/agentcore\s+runtime(?:\s+(.*))?$", re.IGNORECASE),
            "orchestrator": re.compile(r"^/agentcore\s+orchestrator(?:\s+(.*))?$", re.IGNORECASE),
        }
    
    def _get_agentcore_ssm_prefix(self) -> str:
        """Get the dynamic AgentCore SSM parameter prefix"""
        try:
            parameter_manager = get_parameter_manager()
            return parameter_manager.get_parameter_path('agentcore')
        except ParameterManagerError:
            logger.warning("Parameter manager not available, using fallback prefix")
            return "/coa/agentcore"  # Fallback to legacy prefix
        
        logger.info("Command Manager initialized with registry and discovery services")
    
    def _initialize_handlers(self) -> Dict[str, Callable]:
        """Initialize command handlers mapping."""
        return {
            CommandType.LIST.value: self.handle_list_command,
            CommandType.DISCOVER.value: self.handle_discover_command,
            CommandType.STATUS.value: self.handle_status_command,
            "help": self.handle_help_command,
            "start": self.handle_start_command,
            "stop": self.handle_stop_command,
            "config": self.handle_config_command,
            "runtime": self.handle_runtime_command,
            "orchestrator": self.handle_orchestrator_command,
        }
    
    async def process_command(self, command: str, session_id: str) -> CommandResponse:
        """
        Process an AgentCore command.
        
        Args:
            command: Command string to process
            session_id: Session identifier
            
        Returns:
            Command response
        """
        try:
            logger.info(f"Processing command: {command} for session: {session_id}")
            
            # Validate command format
            if not self.validate_command(command):
                return CommandResponse(
                    command=command,
                    status="error",
                    data={},
                    message="Invalid command format. Use '/agentcore help' for usage information."
                )
            
            # Parse command
            parsed_command = self.parse_command(command)
            command_type = parsed_command["type"]
            args = parsed_command["args"]
            
            # Get handler
            handler = self.command_handlers.get(command_type)
            if not handler:
                return CommandResponse(
                    command=command,
                    status="error",
                    data={},
                    message=f"Unknown command type: {command_type}"
                )
            
            # Execute handler
            result_data = await handler(args)
            
            # Create response
            return CommandResponse(
                command=command,
                status="success",
                data=result_data,
                message=result_data.get("message", f"Command '{command_type}' executed successfully")
            )
            
        except Exception as e:
            logger.error(f"Command processing failed: {e}")
            raise CommandProcessingError(
                f"Command processing failed: {e}",
                command=command,
                details={"error": str(e), "session_id": session_id}
            )
    
    async def handle_list_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore list command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        try:
            logger.info("Handling list command")
            
            # Get all agents from registry
            agents = await self.registry.get_all_agents()
            
            # Format agent information for display
            agent_list = []
            for agent_id, agent_info in agents.items():
                agent_display = {
                    "agent_id": agent_info.agent_id,
                    "agent_name": agent_info.agent_name,
                    "agent_arn": agent_info.agent_arn,
                    "runtime_type": agent_info.runtime_type.value,
                    "status": agent_info.status.value,
                    "deployment_status": "deployed" if agent_info.is_healthy() else "unavailable",
                    "integration_status": "integrated" if agent_info.endpoint_url else "discovered",
                    "capabilities": agent_info.capabilities,
                    "framework": agent_info.framework,
                    "last_updated": agent_info.last_updated.isoformat(),
                    "endpoint_url": agent_info.endpoint_url,
                    "health_check_url": agent_info.health_check_url
                }
                agent_list.append(agent_display)
            
            # Sort by agent name for consistent display
            agent_list.sort(key=lambda x: x["agent_name"])
            
            # Get registry statistics
            registry_stats = self.registry.get_registry_stats()
            
            # Create summary message
            total_agents = len(agent_list)
            healthy_agents = sum(1 for agent in agent_list if agent["deployment_status"] == "deployed")
            integrated_agents = sum(1 for agent in agent_list if agent["integration_status"] == "integrated")
            
            if total_agents == 0:
                message = "No agents found in AgentCore runtime. Use '/agentcore discover' to scan for new agents."
            else:
                message = (f"Found {total_agents} agent(s) in AgentCore runtime: "
                          f"{healthy_agents} deployed, {integrated_agents} integrated")
            
            return {
                "agents": agent_list,
                "summary": {
                    "total_agents": total_agents,
                    "healthy_agents": healthy_agents,
                    "integrated_agents": integrated_agents,
                    "agentcore_agents": registry_stats.agentcore_agents,
                    "bedrock_agents": registry_stats.bedrock_agents
                },
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"List command failed: {e}")
            raise CommandProcessingError(
                f"Failed to list agents: {e}",
                command="list",
                details={"error": str(e)}
            )
    
    async def handle_discover_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore discover command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        try:
            logger.info("Handling discover command")
            
            # Get current agent count
            current_agents = await self.registry.get_all_agents()
            initial_count = len(current_agents)
            
            # Trigger discovery
            discovered_agents = await self.discovery.discover_agents()
            
            # Register discovered agents
            new_agents = []
            updated_agents = []
            
            for agent_info in discovered_agents:
                existing_agent = await self.registry.get_agent(agent_info.agent_id)
                
                if existing_agent:
                    # Update existing agent
                    await self.registry.register_agent(agent_info)
                    updated_agents.append(agent_info)
                    logger.info(f"Updated agent: {agent_info.agent_id}")
                else:
                    # Register new agent
                    await self.registry.register_agent(agent_info)
                    new_agents.append(agent_info)
                    logger.info(f"Registered new agent: {agent_info.agent_id}")
            
            # Get discovery statistics
            discovery_stats = self.discovery.get_discovery_stats()
            
            # Create result summary
            new_count = len(new_agents)
            updated_count = len(updated_agents)
            total_discovered = len(discovered_agents)
            
            if new_count == 0 and updated_count == 0:
                message = "No new agents found. Agent registry is up to date."
            else:
                message = f"Discovery completed: {new_count} new agent(s), {updated_count} updated agent(s)"
            
            # Format discovered agents for display
            discovered_agent_list = []
            for agent_info in discovered_agents:
                agent_display = {
                    "agent_id": agent_info.agent_id,
                    "agent_name": agent_info.agent_name,
                    "runtime_type": agent_info.runtime_type.value,
                    "status": agent_info.status.value,
                    "capabilities": agent_info.capabilities,
                    "is_new": agent_info in new_agents,
                    "is_updated": agent_info in updated_agents
                }
                discovered_agent_list.append(agent_display)
            
            return {
                "discovered_agents": discovered_agent_list,
                "summary": {
                    "total_discovered": total_discovered,
                    "new_agents": new_count,
                    "updated_agents": updated_count,
                    "scan_duration": discovery_stats.scan_duration,
                    "parameters_scanned": discovery_stats.total_scanned,
                    "errors": discovery_stats.errors
                },
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Discover command failed: {e}")
            raise CommandProcessingError(
                f"Failed to discover agents: {e}",
                command="discover",
                details={"error": str(e)}
            )
    
    async def handle_status_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore status command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        try:
            logger.info("Handling status command")
            
            # Get registry status
            registry_health = await self.registry.health_check()
            registry_stats = self.registry.get_registry_stats()
            
            # Get discovery status
            discovery_health = await self.discovery.health_check()
            discovery_stats = self.discovery.get_discovery_stats()
            discovery_status = self.discovery.get_discovery_status()
            
            # Overall system status
            overall_status = "healthy"
            if registry_health == "unhealthy" or discovery_health == "unhealthy":
                overall_status = "unhealthy"
            elif registry_health == "degraded" or discovery_health == "degraded":
                overall_status = "degraded"
            
            return {
                "overall_status": overall_status,
                "registry": {
                    "health": registry_health,
                    "total_agents": registry_stats.total_agents,
                    "healthy_agents": registry_stats.healthy_agents,
                    "agentcore_agents": registry_stats.agentcore_agents,
                    "bedrock_agents": registry_stats.bedrock_agents,
                    "last_updated": registry_stats.last_updated.isoformat() if registry_stats.last_updated else None,
                    "cache_hits": registry_stats.cache_hits,
                    "cache_misses": registry_stats.cache_misses
                },
                "discovery": {
                    "health": discovery_health,
                    "running": discovery_status["running"],
                    "interval": discovery_status["interval"],
                    "last_scan": discovery_stats.last_scan.isoformat() if discovery_stats.last_scan else None,
                    "scan_duration": discovery_stats.scan_duration,
                    "total_scanned": discovery_stats.total_scanned,
                    "agents_found": discovery_stats.agents_found,
                    "errors": len(discovery_stats.errors),
                    "callbacks_count": discovery_status["callbacks_count"]
                },
                "message": f"AgentCore system status: {overall_status}",
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Status command failed: {e}")
            raise CommandProcessingError(
                f"Failed to get status: {e}",
                command="status",
                details={"error": str(e)}
            )
    
    async def handle_help_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore help command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        # Get dynamic SSM prefix for help text
        ssm_prefix = self._get_agentcore_ssm_prefix()
        
        help_text = f"""
AgentCore Commands:

/agentcore list
    Display all available and integrated agents from AgentCore runtime
    Shows agent names, ARNs, deployment status, and integration status

/agentcore discover
    Scan SSM Parameter Store for new available agents
    Reports newly found agents and updates the agent registry

/agentcore status
    Show system status including registry and discovery service health
    Displays statistics and operational metrics

/agentcore runtime
    Show runtime configuration and enabled runtime types
    Displays Bedrock Agent and AgentCore Runtime status

/agentcore orchestrator [status|help]
    Show runtime orchestrator configuration and routing information
    Use 'help' subcommand for detailed orchestrator documentation

/agentcore start
    Start periodic discovery of agents (scans SSM parameters at regular intervals)
    Only affects {ssm_prefix}/* parameters

/agentcore stop
    Stop periodic discovery of agents

/agentcore config [interval=<seconds>]
    Configure periodic discovery settings
    Example: /agentcore config interval=600

/agentcore help
    Show this help message

Examples:
    /agentcore list
    /agentcore discover
    /agentcore status
    /agentcore runtime
    /agentcore orchestrator
    /agentcore start
    /agentcore stop
    /agentcore config interval=300
        """
        
        return {
            "help_text": help_text.strip(),
            "available_commands": ["list", "discover", "status", "runtime", "orchestrator", "start", "stop", "config", "help"],
            "message": "AgentCore command help",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def handle_start_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore start command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        try:
            logger.info("Handling start periodic discovery command")
            
            if self.discovery.is_discovery_running():
                return {
                    "status": "already_running",
                    "message": "Periodic discovery is already running",
                    "discovery_status": self.discovery.get_discovery_status(),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Start periodic discovery
            await self.discovery.start_periodic_discovery()
            
            discovery_status = self.discovery.get_discovery_status()
            
            return {
                "status": "started",
                "message": f"Periodic discovery started with {discovery_status['interval']}s interval",
                "discovery_status": discovery_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Start command failed: {e}")
            raise CommandProcessingError(
                f"Failed to start periodic discovery: {e}",
                command="start",
                details={"error": str(e)}
            )
    
    async def handle_stop_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore stop command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        try:
            logger.info("Handling stop periodic discovery command")
            
            if not self.discovery.is_discovery_running():
                return {
                    "status": "not_running",
                    "message": "Periodic discovery is not currently running",
                    "discovery_status": self.discovery.get_discovery_status(),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Stop periodic discovery
            await self.discovery.stop_periodic_discovery()
            
            discovery_status = self.discovery.get_discovery_status()
            
            return {
                "status": "stopped",
                "message": "Periodic discovery stopped",
                "discovery_status": discovery_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Stop command failed: {e}")
            raise CommandProcessingError(
                f"Failed to stop periodic discovery: {e}",
                command="stop",
                details={"error": str(e)}
            )
    
    async def handle_config_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore config command.
        
        Args:
            args: Command arguments (e.g., ["interval=300"])
            
        Returns:
            Command result data
        """
        try:
            logger.info(f"Handling config command with args: {args}")
            
            changes_made = []
            current_status = self.discovery.get_discovery_status()
            
            # Parse arguments
            for arg in args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    key = key.strip().lower()
                    
                    if key == "interval":
                        try:
                            interval = int(value)
                            if interval < 30:
                                return {
                                    "status": "error",
                                    "message": "Interval must be at least 30 seconds",
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            
                            old_interval = self.discovery.discovery_interval
                            self.discovery.set_discovery_interval(interval)
                            changes_made.append(f"Interval changed from {old_interval}s to {interval}s")
                            
                        except ValueError:
                            return {
                                "status": "error",
                                "message": f"Invalid interval value: {value}. Must be a number.",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                    else:
                        return {
                            "status": "error",
                            "message": f"Unknown configuration key: {key}. Available: interval",
                            "timestamp": datetime.utcnow().isoformat()
                        }
            
            # If no arguments provided, show current configuration
            if not args:
                return {
                    "status": "info",
                    "message": "Current AgentCore configuration",
                    "configuration": {
                        "periodic_discovery_running": current_status["running"],
                        "discovery_interval": current_status["interval"],
                        "ssm_prefix": f"{self._get_agentcore_ssm_prefix()}/",
                        "last_scan": current_status.get("last_scan"),
                        "callbacks_count": current_status["callbacks_count"]
                    },
                    "usage": "Use '/agentcore config interval=<seconds>' to change settings",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Return results
            updated_status = self.discovery.get_discovery_status()
            
            return {
                "status": "success",
                "message": "Configuration updated successfully",
                "changes": changes_made,
                "configuration": {
                    "periodic_discovery_running": updated_status["running"],
                    "discovery_interval": updated_status["interval"],
                    "ssm_prefix": f"{self._get_agentcore_ssm_prefix()}/",
                    "last_scan": updated_status.get("last_scan"),
                    "callbacks_count": updated_status["callbacks_count"]
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Config command failed: {e}")
            raise CommandProcessingError(
                f"Failed to configure periodic discovery: {e}",
                command="config",
                details={"error": str(e), "args": args}
            )
    
    def validate_command(self, command: str) -> bool:
        """
        Validate command syntax.
        
        Args:
            command: Command string to validate
            
        Returns:
            True if command is valid
        """
        try:
            if not isinstance(command, str):
                return False
            
            command = command.strip()
            if not command:
                return False
            
            # Check if it's an agentcore command
            if not command.lower().startswith("/agentcore"):
                return False
            
            # Check against known patterns
            for pattern in self.command_patterns.values():
                if pattern.match(command):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Command validation failed: {e}")
            return False
    
    def parse_command(self, command: str) -> Dict[str, Any]:
        """
        Parse command into components.
        
        Args:
            command: Command string to parse
            
        Returns:
            Parsed command dictionary
        """
        try:
            command = command.strip()
            
            # Check each pattern
            for command_type, pattern in self.command_patterns.items():
                match = pattern.match(command)
                if match:
                    args_string = match.group(1) if match.group(1) else ""
                    args = [arg.strip() for arg in args_string.split()] if args_string else []
                    
                    return {
                        "type": command_type,
                        "args": args,
                        "raw_command": command,
                        "args_string": args_string
                    }
            
            # If no pattern matches, return unknown
            return {
                "type": "unknown",
                "args": [],
                "raw_command": command,
                "args_string": ""
            }
            
        except Exception as e:
            logger.error(f"Command parsing failed: {e}")
            return {
                "type": "error",
                "args": [],
                "raw_command": command,
                "error": str(e)
            }
    
    def is_agentcore_command(self, text: str) -> bool:
        """
        Check if text is an AgentCore command.
        
        Args:
            text: Text to check
            
        Returns:
            True if text is an AgentCore command
        """
        try:
            if not isinstance(text, str):
                return False
            
            text = text.strip().lower()
            return text.startswith("/agentcore")
            
        except Exception as e:
            logger.error(f"AgentCore command check failed: {e}")
            return False
    
    async def health_check(self) -> str:
        """
        Check command manager health status.
        
        Returns:
            Health status string
        """
        try:
            # Check if required services are available
            if not self.registry or not self.discovery:
                return "unhealthy"
            
            # Check service health
            registry_health = await self.registry.health_check()
            discovery_health = await self.discovery.health_check()
            
            if registry_health == "unhealthy" or discovery_health == "unhealthy":
                return "unhealthy"
            elif registry_health == "degraded" or discovery_health == "degraded":
                return "degraded"
            else:
                return "healthy"
                
        except Exception as e:
            logger.error(f"Command manager health check failed: {e}")
            return "unhealthy"
    
    def get_command_stats(self) -> Dict[str, Any]:
        """
        Get command processing statistics.
        
        Returns:
            Command statistics dictionary
        """
        return {
            "available_commands": list(self.command_handlers.keys()),
            "command_patterns": list(self.command_patterns.keys()),
            "handlers_count": len(self.command_handlers),
            "patterns_count": len(self.command_patterns)
        }
    
    def add_command_handler(self, command_type: str, handler: Callable) -> None:
        """
        Add a custom command handler.
        
        Args:
            command_type: Command type identifier
            handler: Handler function
        """
        self.command_handlers[command_type] = handler
        logger.info(f"Added command handler for: {command_type}")
    
    def remove_command_handler(self, command_type: str) -> bool:
        """
        Remove a command handler.
        
        Args:
            command_type: Command type identifier
            
        Returns:
            True if handler was removed
        """
        if command_type in self.command_handlers:
            del self.command_handlers[command_type]
            logger.info(f"Removed command handler for: {command_type}")
            return True
        return False
    
    async def handle_runtime_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore runtime command - show runtime configuration and status.
        
        Args:
            args: Command arguments
            
        Returns:
            Command result data
        """
        try:
            logger.info("Handling runtime command")
            
            # NOTE: Runtime orchestrator service has been deprecated
            # Using environment variables directly for runtime configuration
            import os
            
            # Get runtime configuration from environment variables
            bedrock_agent_enabled = os.getenv("BEDROCK_AGENT_ENABLED", "false").lower() == "true"
            agentcore_enabled = os.getenv("AGENTCORE_ENABLED", "true").lower() == "true"
            
            # Get enabled runtimes
            enabled_runtimes = []
            if bedrock_agent_enabled:
                enabled_runtimes.append("bedrock_agent")
            if agentcore_enabled:
                enabled_runtimes.append("agentcore")
                
                # Format runtime information
                runtime_info = {
                    "bedrock_agent": {
                        "enabled": config.bedrock_agent_enabled,
                        "status": "enabled" if config.bedrock_agent_enabled else "disabled"
                    },
                    "agentcore_runtime": {
                        "enabled": config.agentcore_enabled,
                        "status": "enabled" if config.agentcore_enabled else "disabled"
                    }
                }
                
                # Configuration details
                configuration = {
                    "priority_runtime": config.priority_runtime.value,
                    "fallback_enabled": config.fallback_enabled,
                    "keyword_analysis_enabled": config.keyword_analysis_enabled,
                    "health_check_interval": config.health_check_interval
                }
                
                # Create summary message
                enabled_count = len(enabled_runtimes)
                if enabled_count == 0:
                    message = "⚠️ No runtime types are enabled. Check environment configuration."
                elif enabled_count == 1:
                    runtime_name = enabled_runtimes[0].value.replace('_', ' ').title()
                    message = f"Single runtime mode: {runtime_name}"
                else:
                    priority_name = config.priority_runtime.value.replace('_', ' ').title()
                    message = f"Dual runtime mode with {priority_name} priority"
                
                return {
                    "runtime_info": runtime_info,
                    "configuration": configuration,
                    "enabled_runtimes": [rt.value for rt in enabled_runtimes],
                    "enabled_count": enabled_count,
                    "message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except ImportError as e:
                return {
                    "error": "Runtime orchestrator not available",
                    "message": "Runtime orchestration features are not initialized",
                    "details": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Runtime command failed: {e}")
            raise CommandProcessingError(
                f"Failed to get runtime information: {e}",
                command="runtime",
                details={"error": str(e)}
            )
    
    async def handle_orchestrator_command(self, args: List[str]) -> Dict[str, Any]:
        """
        Handle /agentcore orchestrator command - show orchestrator status and routing stats.
        
        Args:
            args: Command arguments (e.g., ["stats", "health"])
            
        Returns:
            Command result data
        """
        try:
            logger.info(f"Handling orchestrator command with args: {args}")
            
            # NOTE: Runtime orchestrator service has been deprecated
            # Using environment variables directly for orchestrator configuration
            import os
            
            # Get configuration from environment variables
            bedrock_agent_enabled = os.getenv("BEDROCK_AGENT_ENABLED", "false").lower() == "true"
            agentcore_enabled = os.getenv("AGENTCORE_ENABLED", "true").lower() == "true"
            
            # Determine what information to show based on args
            if not args or args[0].lower() == "status":
                # Show orchestrator status
                return {
                    "orchestrator_status": "deprecated - using environment configuration",
                    "configuration": {
                        "bedrock_agent_enabled": bedrock_agent_enabled,
                            "agentcore_enabled": config.agentcore_enabled,
                            "priority_runtime": config.priority_runtime.value,
                            "fallback_enabled": config.fallback_enabled,
                            "keyword_analysis_enabled": config.keyword_analysis_enabled,
                            "health_check_interval": config.health_check_interval
                        },
                        "enabled_runtimes": [rt.value for rt in config.get_enabled_runtimes()],
                        "message": "Runtime orchestrator is configured and ready",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
                elif args[0].lower() == "help":
                    # Show orchestrator help
                    help_text = """
Orchestrator Commands:

/agentcore orchestrator [status]
    Show runtime orchestrator configuration and status
    
/agentcore orchestrator help
    Show this help message

/agentcore runtime
    Show detailed runtime configuration and enabled types

Environment Variables:
    ENABLE_BEDROCK_AGENT=true/false     - Enable/disable Bedrock Agent runtime
    ENABLE_BEDROCK_AGENTCORE=true/false - Enable/disable AgentCore runtime
    ENABLE_KEYWORD_ANALYSIS=true/false  - Enable/disable keyword-based routing
    RUNTIME_HEALTH_CHECK_INTERVAL=30    - Health check cache interval in seconds

Runtime Modes:
    - Bedrock Only: Only ENABLE_BEDROCK_AGENT=true
    - AgentCore Only: Only ENABLE_BEDROCK_AGENTCORE=true  
    - Dual Mode: Both enabled (AgentCore preferred, Bedrock fallback)
                    """
                    
                    return {
                        "help_text": help_text.strip(),
                        "available_subcommands": ["status", "help"],
                        "message": "Runtime orchestrator help",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
                else:
                    return {
                        "error": f"Unknown orchestrator subcommand: {args[0]}",
                        "message": "Use '/agentcore orchestrator help' for available commands",
                        "available_subcommands": ["status", "help"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
            except ImportError as e:
                return {
                    "error": "Runtime orchestrator not available",
                    "message": "Runtime orchestration features are not initialized",
                    "details": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Orchestrator command failed: {e}")
            raise CommandProcessingError(
                f"Failed to get orchestrator information: {e}",
                command="orchestrator",
                details={"error": str(e), "args": args}
            )