"""
AgentCore Discovery Service - Discovers and monitors AgentCore agents through SSM Parameter Store.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from agentcore.models.strands_models import (
    StrandsAgent, StrandsDiscoveryStats, StrandsAgentStatus
)
from agentcore.models.agentcore_interfaces import AgentDiscoveryInterface
from shared.models.exceptions import AgentDiscoveryError, SSMParameterError

logger = logging.getLogger(__name__)


class AgentCoreDiscoveryService(AgentDiscoveryInterface):
    """Discovers and monitors AgentCore agents through SSM Parameter Store scanning."""
    
    def __init__(self, ssm_prefix: Optional[str] = None, region: str = "us-east-1", 
                 discovery_interval: int = 300, parameter_manager=None):
        """
        Initialize the discovery service.
        
        Args:
            ssm_prefix: SSM parameter prefix for agent configurations
            region: AWS region for SSM client
            discovery_interval: Automatic discovery interval in seconds (default: 5 minutes)
            parameter_manager: Parameter manager instance for dynamic prefix
        """
        # Use dynamic parameter prefix
        if ssm_prefix:
            self.ssm_prefix = ssm_prefix
        elif parameter_manager:
            self.ssm_prefix = f"/{parameter_manager.param_prefix}/agents/"
        else:
            from shared.utils.parameter_manager import get_dynamic_parameter_prefix
            param_prefix = get_dynamic_parameter_prefix()
            self.ssm_prefix = f"/{param_prefix}/agents/"
        
        self.region = region
        self.discovery_interval = discovery_interval
        self.ssm_client = None
        self.last_scan: Optional[datetime] = None
        
        # Statistics tracking
        self._stats = DiscoveryStats()
        
        # Periodic discovery management
        self._discovery_task: Optional[asyncio.Task] = None
        self._discovery_running = False
        self._discovery_callbacks: List[Callable[[List[AgentInfo]], None]] = []
        
        # Change detection
        self._last_parameter_hash: Optional[str] = None
        
        # Initialize SSM client
        self._initialize_ssm_client()
        
        logger.info(f"AgentCore Discovery Service initialized - prefix: {ssm_prefix}, region: {region}, interval: {discovery_interval}s")
    
    def _initialize_ssm_client(self) -> None:
        """Initialize SSM client with proper error handling."""
        try:
            self.ssm_client = boto3.client("ssm", region_name=self.region)
            
            # Test connectivity
            self.ssm_client.describe_parameters(MaxResults=1)
            logger.info("✓ SSM client initialized successfully")
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to initialize SSM client: {e}")
            self.ssm_client = None
            raise AgentDiscoveryError(
                f"Failed to initialize SSM client: {e}",
                details={"region": self.region, "error": str(e)}
            )
        except Exception as e:
            logger.error(f"Unexpected error initializing SSM client: {e}")
            self.ssm_client = None
            raise AgentDiscoveryError(
                f"Unexpected error initializing SSM client: {e}",
                details={"region": self.region, "error": str(e)}
            )
    
    async def discover_agents(self) -> List[AgentInfo]:
        """
        Discover agents from SSM Parameter Store.
        
        Returns:
            List of discovered agent information
        """
        start_time = time.time()
        discovered_agents = []
        
        try:
            logger.info("Starting agent discovery from SSM Parameter Store")
            
            # Reset statistics for this discovery run
            self._stats = DiscoveryStats()
            self._stats.last_scan = datetime.utcnow()
            
            # Scan SSM parameters
            param_data_list = await self.scan_ssm_parameters()
            self._stats.total_scanned = len(param_data_list)
            
            # Parse each parameter set into agent configuration
            for param_data in param_data_list:
                try:
                    agent_info = await self.parse_agent_config(param_data)
                    if agent_info:
                        # Validate agent configuration
                        if await self.validate_agent_config(agent_info.to_dict()):
                            discovered_agents.append(agent_info)
                            self._stats.agents_found += 1
                            logger.info(f"Discovered agent: {agent_info.agent_id}")
                        else:
                            logger.warning(f"Invalid agent configuration: {param_data.get('agent_name', 'unknown')}")
                            self._stats.errors.append(f"Invalid configuration for {param_data.get('agent_name', 'unknown')}")
                    
                except Exception as e:
                    logger.error(f"Failed to parse agent config: {e}")
                    self._stats.errors.append(f"Parse error: {str(e)}")
                    continue
            
            # Update statistics
            self._stats.scan_duration = time.time() - start_time
            self.last_scan = datetime.utcnow()
            
            logger.info(f"Discovery completed - found {len(discovered_agents)} agents in {self._stats.scan_duration:.2f}s")
            return discovered_agents
            
        except Exception as e:
            self._stats.scan_duration = time.time() - start_time
            self._stats.errors.append(f"Discovery failed: {str(e)}")
            logger.error(f"Agent discovery failed: {e}")
            raise AgentDiscoveryError(
                f"Agent discovery failed: {e}",
                details={"scan_duration": self._stats.scan_duration, "error": str(e)}
            )
    
    async def scan_ssm_parameters(self) -> List[Dict[str, Any]]:
        """
        Scan SSM parameters for agent configurations.
        
        Returns:
            List of parameter data dictionaries
        """
        if not self.ssm_client:
            raise AgentDiscoveryError("SSM client not initialized")
        
        try:
            logger.info(f"Scanning SSM parameters with prefix: {self.ssm_prefix}")
            
            # Get all parameters under the prefix with pagination
            all_parameters = []
            next_token = None
            
            while True:
                params = {
                    "Path": self.ssm_prefix,
                    "Recursive": True,
                    "WithDecryption": True,
                }
                if next_token:
                    params["NextToken"] = next_token
                
                try:
                    response = self.ssm_client.get_parameters_by_path(**params)
                    all_parameters.extend(response.get("Parameters", []))
                    
                    next_token = response.get("NextToken")
                    if not next_token:
                        break
                        
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ParameterNotFound":
                        logger.info("No parameters found with the specified prefix")
                        break
                    else:
                        raise
            
            logger.info(f"Found {len(all_parameters)} parameters")
            
            # Group parameters by agent
            agent_params = self._group_parameters_by_agent(all_parameters)
            
            return list(agent_params.values())
            
        except Exception as e:
            logger.error(f"Failed to scan SSM parameters: {e}")
            raise SSMParameterError(
                f"Failed to scan SSM parameters: {e}",
                parameter_name=self.ssm_prefix,
                details={"error": str(e)}
            )
    
    def _group_parameters_by_agent(self, parameters: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """
        Group SSM parameters by agent name.
        
        Args:
            parameters: List of SSM parameters
            
        Returns:
            Dictionary of agent configurations
        """
        agent_configs = {}
        
        # Extract the expected path component from the configured prefix
        # e.g., "/coa/agentcore/" -> "agentcore", "/coa/agents/" -> "agents"
        prefix_parts = self.ssm_prefix.strip("/").split("/")
        expected_path_component = prefix_parts[-1] if prefix_parts else "agents"
        
        for param in parameters:
            param_name = param["Name"]
            param_value = param["Value"]
            
            # Parse parameter path: /coa/{prefix_component}/{agent_name}/{param_key}
            path_parts = param_name.split("/")
            if len(path_parts) >= 4:
                # Check if this parameter matches our configured prefix
                if len(path_parts) >= 3 and path_parts[2] == expected_path_component:
                    agent_name = path_parts[3]
                    param_key = path_parts[4] if len(path_parts) > 4 else "root"
                    
                    if agent_name not in agent_configs:
                        agent_configs[agent_name] = {"agent_name": agent_name}
                    
                    # Handle JSON parameters
                    if param_key in ["metadata", "capabilities", "connection_info"]:
                        try:
                            agent_configs[agent_name][param_key] = json.loads(param_value)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON parameter {param_name}")
                            agent_configs[agent_name][param_key] = param_value
                    else:
                        agent_configs[agent_name][param_key] = param_value
                else:
                    logger.debug(f"Skipping parameter {param_name} - doesn't match expected prefix component '{expected_path_component}'")
        
        logger.info(f"Grouped {len(agent_configs)} agent configurations from {len(parameters)} parameters")
        return agent_configs
    
    async def parse_agent_config(self, param_data: Dict) -> Optional[AgentInfo]:
        """
        Parse agent configuration from SSM parameter data.
        
        Args:
            param_data: Parameter data dictionary
            
        Returns:
            AgentInfo object if parsing successful, None otherwise
        """
        try:
            # Extract required fields
            agent_name = param_data.get("agent_name")
            agent_id = param_data.get("agent_id")
            agent_arn = param_data.get("agent_arn")
            
            # Fault tolerance: Use agent_name as agent_id if agent_id is missing
            if not agent_id and agent_name:
                agent_id = agent_name
                logger.info(f"Using agent_name '{agent_name}' as agent_id (fault tolerance)")
            
            # Check for minimum required fields
            if not agent_name:
                logger.warning("Missing agent_name - cannot create agent configuration")
                return None
            
            if not agent_id:
                logger.warning(f"Missing both agent_id and agent_name for agent configuration")
                return None
            
            # Generate a default ARN if missing (fault tolerance)
            if not agent_arn:
                # Create a default ARN based on agent type and name
                runtime_type = self._determine_runtime_type(param_data)
                if runtime_type == AgentRuntimeType.BEDROCK_AGENTCORE:
                    agent_arn = f"arn:aws:bedrock-agentcore:{self.region}:unknown:agent/{agent_id}"
                else:
                    agent_arn = f"arn:aws:bedrock:{self.region}:unknown:agent/{agent_id}"
                logger.info(f"Generated default ARN for agent '{agent_name}': {agent_arn}")
            
            # Determine runtime type
            runtime_type = self._determine_runtime_type(param_data)
            
            # Parse metadata
            metadata = param_data.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            
            # Parse capabilities
            capabilities = param_data.get("capabilities", [])
            if isinstance(capabilities, str):
                try:
                    capabilities = json.loads(capabilities)
                except json.JSONDecodeError:
                    capabilities = []
            
            # Determine status
            status = self._determine_agent_status(param_data, metadata)
            
            # Create AgentInfo object
            agent_info = AgentInfo(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_arn=agent_arn,
                runtime_type=runtime_type,
                status=status,
                capabilities=capabilities,
                metadata=metadata,
                endpoint_url=param_data.get("endpoint_url"),
                health_check_url=param_data.get("health_check_url"),
                framework=metadata.get("framework", "agentcore"),
                model_id=metadata.get("model_id", "unknown")
            )
            
            return agent_info
            
        except Exception as e:
            logger.error(f"Failed to parse agent config: {e}")
            return None
    
    def _determine_runtime_type(self, param_data: Dict) -> AgentRuntimeType:
        """
        Determine agent runtime type from parameter data.
        
        Args:
            param_data: Parameter data dictionary
            
        Returns:
            Agent runtime type
        """
        # Check for AgentCore specific indicators
        if any(key in param_data for key in ["endpoint_url", "health_check_url"]):
            return AgentRuntimeType.BEDROCK_AGENTCORE
        
        # Check metadata for framework indicators
        metadata = param_data.get("metadata", {})
        if isinstance(metadata, dict):
            framework = metadata.get("framework", "").lower()
            if framework in ["strands", "agentcore"]:
                return AgentRuntimeType.BEDROCK_AGENTCORE
        
        # Check for ARN pattern
        agent_arn = param_data.get("agent_arn", "")
        if "bedrock-agentcore" in agent_arn:
            return AgentRuntimeType.BEDROCK_AGENTCORE
        
        # Default to standard Bedrock Agent
        return AgentRuntimeType.BEDROCK_AGENT
    
    def _determine_agent_status(self, param_data: Dict, metadata: Dict) -> AgentDiscoveryStatus:
        """
        Determine agent status from parameter data and metadata.
        
        Args:
            param_data: Parameter data dictionary
            metadata: Agent metadata
            
        Returns:
            Agent discovery status
        """
        # Check explicit status in metadata
        if "status" in metadata:
            status_str = metadata["status"].upper()
            try:
                return AgentDiscoveryStatus(status_str.lower())
            except ValueError:
                pass
        
        # Check if agent has endpoint (indicates deployment)
        if param_data.get("endpoint_url"):
            return AgentDiscoveryStatus.DEPLOYED
        
        # Default to discovered
        return AgentDiscoveryStatus.DISCOVERED
    
    async def validate_agent_config(self, config: Dict) -> bool:
        """
        Validate agent configuration data.
        
        Args:
            config: Agent configuration dictionary
            
        Returns:
            True if configuration is valid
        """
        try:
            # Essential fields (agent_name is the minimum requirement)
            if not config.get("agent_name"):
                logger.warning("Missing essential field: agent_name")
                return False
            
            # agent_id should exist (either original or fallback from agent_name)
            if not config.get("agent_id"):
                logger.warning("Missing agent_id field")
                return False
            
            # Validate agent_id format
            agent_id = config["agent_id"]
            if not isinstance(agent_id, str) or len(agent_id) < 3:
                logger.warning(f"Invalid agent_id format: {agent_id}")
                return False
            
            # Validate agent_arn format
            agent_arn = config["agent_arn"]
            if not isinstance(agent_arn, str) or not agent_arn.startswith("arn:aws:"):
                logger.warning(f"Invalid agent_arn format: {agent_arn}")
                return False
            
            # Validate capabilities if present
            capabilities = config.get("capabilities", [])
            if capabilities and not isinstance(capabilities, list):
                logger.warning("Capabilities must be a list")
                return False
            
            # Validate metadata if present
            metadata = config.get("metadata", {})
            if metadata and not isinstance(metadata, dict):
                logger.warning("Metadata must be a dictionary")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_discovery_stats(self) -> DiscoveryStats:
        """
        Get discovery statistics.
        
        Returns:
            Discovery statistics
        """
        return self._stats
    
    async def start_periodic_discovery(self) -> None:
        """Start periodic agent discovery."""
        if self._discovery_running:
            logger.warning("Periodic discovery is already running")
            return
        
        self._discovery_running = True
        self._discovery_task = asyncio.create_task(self._periodic_discovery_loop())
        logger.info(f"Started periodic agent discovery with {self.discovery_interval}s interval")
    
    async def stop_periodic_discovery(self) -> None:
        """Stop periodic agent discovery."""
        if not self._discovery_running:
            logger.warning("Periodic discovery is not running")
            return
        
        self._discovery_running = False
        
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
            self._discovery_task = None
        
        logger.info("Stopped periodic agent discovery")
    
    async def _periodic_discovery_loop(self) -> None:
        """Main loop for periodic agent discovery."""
        logger.info("Starting periodic discovery loop")
        
        while self._discovery_running:
            try:
                # Perform discovery
                discovered_agents = await self.discover_agents()
                
                # Check for changes
                if await self._detect_changes():
                    logger.info(f"Changes detected - notifying {len(self._discovery_callbacks)} callbacks")
                    
                    # Notify callbacks about discovered agents
                    for callback in self._discovery_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(discovered_agents)
                            else:
                                callback(discovered_agents)
                        except Exception as e:
                            logger.error(f"Discovery callback failed: {e}")
                
                # Wait for next discovery cycle
                await asyncio.sleep(self.discovery_interval)
                
            except asyncio.CancelledError:
                logger.info("Periodic discovery cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic discovery loop: {e}")
                # Wait before retrying
                await asyncio.sleep(min(self.discovery_interval, 60))
        
        logger.info("Periodic discovery loop ended")
    
    def add_discovery_callback(self, callback: Callable[[List[AgentInfo]], None]) -> None:
        """
        Add a callback to be notified when agents are discovered.
        
        Args:
            callback: Function to call with discovered agents
        """
        self._discovery_callbacks.append(callback)
        logger.info(f"Added discovery callback - total callbacks: {len(self._discovery_callbacks)}")
    
    def remove_discovery_callback(self, callback: Callable[[List[AgentInfo]], None]) -> None:
        """
        Remove a discovery callback.
        
        Args:
            callback: Function to remove
        """
        if callback in self._discovery_callbacks:
            self._discovery_callbacks.remove(callback)
            logger.info(f"Removed discovery callback - total callbacks: {len(self._discovery_callbacks)}")
    
    async def _detect_changes(self) -> bool:
        """
        Detect if there have been changes in SSM parameters since last scan.
        
        Returns:
            True if changes detected
        """
        try:
            # Get current parameter hash
            current_hash = await self._get_parameters_hash()
            
            if self._last_parameter_hash is None:
                # First scan
                self._last_parameter_hash = current_hash
                return True
            
            if current_hash != self._last_parameter_hash:
                logger.info("Parameter changes detected")
                self._last_parameter_hash = current_hash
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to detect changes: {e}")
            return True  # Assume changes on error
    
    async def _get_parameters_hash(self) -> str:
        """
        Get a hash of all parameters for change detection.
        
        Returns:
            Hash string representing current parameter state
        """
        try:
            if not self.ssm_client:
                return ""
            
            # Get parameter metadata (names and last modified dates)
            response = self.ssm_client.describe_parameters(
                ParameterFilters=[
                    {
                        "Key": "Name",
                        "Option": "BeginsWith",
                        "Values": [self.ssm_prefix]
                    }
                ]
            )
            
            # Create hash from parameter names and modification dates
            param_info = []
            for param in response.get("Parameters", []):
                param_info.append(f"{param['Name']}:{param.get('LastModifiedDate', '')}")
            
            # Simple hash of concatenated parameter info
            import hashlib
            param_string = "|".join(sorted(param_info))
            return hashlib.md5(param_string.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Failed to get parameters hash: {e}")
            return ""
    
    async def trigger_discovery(self) -> List[AgentInfo]:
        """
        Manually trigger agent discovery.
        
        Returns:
            List of discovered agents
        """
        logger.info("Manually triggering agent discovery")
        return await self.discover_agents()
    
    def set_discovery_interval(self, interval: int) -> None:
        """
        Set the discovery interval.
        
        Args:
            interval: New interval in seconds
        """
        old_interval = self.discovery_interval
        self.discovery_interval = interval
        logger.info(f"Discovery interval updated: {old_interval}s -> {interval}s")
    
    def is_discovery_running(self) -> bool:
        """
        Check if periodic discovery is running.
        
        Returns:
            True if discovery is running
        """
        return self._discovery_running
    
    def get_discovery_status(self) -> Dict[str, Any]:
        """
        Get detailed discovery status.
        
        Returns:
            Discovery status dictionary
        """
        return {
            "running": self._discovery_running,
            "interval": self.discovery_interval,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "callbacks_count": len(self._discovery_callbacks),
            "task_status": "running" if self._discovery_task and not self._discovery_task.done() else "stopped"
        }
    
    async def health_check(self) -> str:
        """
        Check discovery service health status.
        
        Returns:
            Health status string
        """
        try:
            if not self.ssm_client:
                return "unhealthy"
            
            # Test SSM connectivity
            self.ssm_client.describe_parameters(MaxResults=1)
            
            # Check if recent discovery was successful
            if self.last_scan:
                time_since_scan = datetime.utcnow() - self.last_scan
                if time_since_scan.total_seconds() > 3600:  # 1 hour
                    return "degraded"  # No recent scan
            
            # Check error rate
            if len(self._stats.errors) > 0:
                error_rate = len(self._stats.errors) / max(self._stats.total_scanned, 1)
                if error_rate > 0.5:  # More than 50% errors
                    return "degraded"
            
            return "healthy"
            
        except Exception as e:
            logger.error(f"Discovery service health check failed: {e}")
            return "unhealthy"
    
    def get_ssm_client_status(self) -> Dict[str, Any]:
        """
        Get SSM client status information.
        
        Returns:
            SSM client status dictionary
        """
        return {
            "initialized": self.ssm_client is not None,
            "region": self.region,
            "prefix": self.ssm_prefix,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "discovery_status": self.get_discovery_status()
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_periodic_discovery()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_periodic_discovery()