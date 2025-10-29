#!/usr/bin/env python3
"""
Agent Unregistration Service

This service handles the unregistration of agents from the COA system by:
1. Removing SSM parameters associated with the agent
2. Clearing agent from local registries
3. Providing safe unregistration with validation
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class UnregistrationResult:
    """Result of agent unregistration process"""
    agent_name: str
    agent_type: str
    status: str  # success, failed, not_found, partial
    parameters_deleted: List[str]
    parameters_failed: List[str]
    error_message: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "status": self.status,
            "parameters_deleted": self.parameters_deleted,
            "parameters_failed": self.parameters_failed,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "summary": {
                "total_parameters": len(self.parameters_deleted) + len(self.parameters_failed),
                "deleted_count": len(self.parameters_deleted),
                "failed_count": len(self.parameters_failed),
                "success_rate": len(self.parameters_deleted) / max(1, len(self.parameters_deleted) + len(self.parameters_failed))
            }
        }


class AgentUnregistrationService:
    """Service for unregistering agents from the COA system"""
    
    def __init__(self, region: str = "us-east-1", param_prefix: str = "coa"):
        """
        Initialize the unregistration service
        
        Args:
            region: AWS region for SSM operations
            param_prefix: Parameter prefix for dynamic parameter paths
        """
        self.region = region
        self.param_prefix = param_prefix
        self.ssm_client = boto3.client("ssm", region_name=region)
        
        # SSM parameter prefixes to search (using dynamic prefix)
        self.ssm_prefixes = [
            f"/{param_prefix}/agents/",      # Current Strands agents
            f"/{param_prefix}/agentcore/",   # AgentCore agents
            f"/{param_prefix}/agent/",       # Legacy Bedrock agents
            f"/{param_prefix}/components/"   # MCP server components
        ]
        
        logger.info(f"Agent Unregistration Service initialized for region: {region}")
    
    async def list_registered_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        List all registered agents across all SSM prefixes
        
        Returns:
            Dictionary mapping agent names to their information
        """
        agents = {}
        
        for prefix in self.ssm_prefixes:
            try:
                # Get all parameters under this prefix
                paginator = self.ssm_client.get_paginator('get_parameters_by_path')
                
                for page in paginator.paginate(Path=prefix, Recursive=True):
                    for param in page.get('Parameters', []):
                        param_name = param['Name']
                        
                        # Extract agent name from parameter path
                        # Format: /{param_prefix}/{prefix}/{agent_name}/{param_key}
                        path_parts = param_name.split('/')
                        if len(path_parts) >= 4:
                            agent_name = path_parts[3]
                            
                            if agent_name not in agents:
                                agents[agent_name] = {
                                    "agent_name": agent_name,
                                    "parameters": [],
                                    "prefixes": set(),
                                    "metadata": {},
                                    "connection_info": {}
                                }
                            
                            agents[agent_name]["parameters"].append(param_name)
                            agents[agent_name]["prefixes"].add(prefix)
                            
                            # Extract metadata if this is a metadata parameter
                            if param_name.endswith('/metadata'):
                                try:
                                    metadata = json.loads(param['Value'])
                                    agents[agent_name]["metadata"] = metadata
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse metadata for {param_name}")
                            
                            # Extract connection info if this is a connection_info parameter
                            elif param_name.endswith('/connection_info'):
                                try:
                                    connection_info = json.loads(param['Value'])
                                    agents[agent_name]["connection_info"] = connection_info
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse connection_info for {param_name}")
                
            except ClientError as e:
                logger.warning(f"Failed to list parameters for prefix {prefix}: {e}")
                continue
        
        # Convert sets to lists for JSON serialization
        for agent_info in agents.values():
            agent_info["prefixes"] = list(agent_info["prefixes"])
        
        logger.info(f"Found {len(agents)} registered agents")
        return agents
    
    async def get_agent_parameters(self, agent_name: str) -> List[str]:
        """
        Get all SSM parameters associated with an agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            List of parameter paths
        """
        parameters = []
        
        for prefix in self.ssm_prefixes:
            agent_prefix = f"{prefix}{agent_name}/"
            
            try:
                # Get all parameters under this agent's prefix
                paginator = self.ssm_client.get_paginator('get_parameters_by_path')
                
                for page in paginator.paginate(Path=agent_prefix, Recursive=True):
                    for param in page.get('Parameters', []):
                        parameters.append(param['Name'])
                        
            except ClientError as e:
                logger.debug(f"No parameters found for {agent_prefix}: {e}")
                continue
        
        logger.info(f"Found {len(parameters)} parameters for agent {agent_name}")
        return parameters
    
    async def validate_agent_exists(self, agent_name: str) -> bool:
        """
        Validate that an agent exists in the system
        
        Args:
            agent_name: Name of the agent to validate
            
        Returns:
            True if agent exists, False otherwise
        """
        parameters = await self.get_agent_parameters(agent_name)
        return len(parameters) > 0
    
    async def unregister_agent(
        self, 
        agent_name: str, 
        dry_run: bool = False,
        force: bool = False
    ) -> UnregistrationResult:
        """
        Unregister an agent from the COA system
        
        Args:
            agent_name: Name of the agent to unregister
            dry_run: If True, only simulate the unregistration
            force: If True, continue even if some parameters fail to delete
            
        Returns:
            UnregistrationResult with details of the operation
        """
        logger.info(f"Starting unregistration for agent: {agent_name} (dry_run={dry_run})")
        
        # Get all parameters for this agent
        parameters = await self.get_agent_parameters(agent_name)
        
        if not parameters:
            return UnregistrationResult(
                agent_name=agent_name,
                agent_type="unknown",
                status="not_found",
                parameters_deleted=[],
                parameters_failed=[],
                error_message=f"Agent '{agent_name}' not found in system"
            )
        
        # Determine agent type from parameters
        agent_type = self._determine_agent_type(parameters)
        
        deleted_parameters = []
        failed_parameters = []
        
        if dry_run:
            logger.info(f"DRY RUN: Would delete {len(parameters)} parameters for {agent_name}")
            return UnregistrationResult(
                agent_name=agent_name,
                agent_type=agent_type,
                status="dry_run_success",
                parameters_deleted=parameters,  # In dry run, show what would be deleted
                parameters_failed=[],
                error_message=None
            )
        
        # Delete each parameter
        for param_name in parameters:
            try:
                logger.debug(f"Deleting parameter: {param_name}")
                self.ssm_client.delete_parameter(Name=param_name)
                deleted_parameters.append(param_name)
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                if error_code == 'ParameterNotFound':
                    # Parameter already deleted, consider it a success
                    logger.warning(f"Parameter {param_name} already deleted")
                    deleted_parameters.append(param_name)
                else:
                    logger.error(f"Failed to delete parameter {param_name}: {e}")
                    failed_parameters.append(param_name)
                    
                    if not force:
                        # Stop on first failure if not forcing
                        break
            
            except Exception as e:
                logger.error(f"Unexpected error deleting parameter {param_name}: {e}")
                failed_parameters.append(param_name)
                
                if not force:
                    break
        
        # Determine final status
        if failed_parameters and not deleted_parameters:
            status = "failed"
        elif failed_parameters and deleted_parameters:
            status = "partial"
        else:
            status = "success"
        
        error_message = None
        if failed_parameters:
            error_message = f"Failed to delete {len(failed_parameters)} parameters"
            if not force:
                error_message += " (stopped on first failure, use force=True to continue)"
        
        result = UnregistrationResult(
            agent_name=agent_name,
            agent_type=agent_type,
            status=status,
            parameters_deleted=deleted_parameters,
            parameters_failed=failed_parameters,
            error_message=error_message
        )
        
        logger.info(f"Unregistration completed for {agent_name}: {status}")
        return result
    
    def _determine_agent_type(self, parameters: List[str]) -> str:
        """
        Determine agent type from parameter paths
        
        Args:
            parameters: List of parameter paths
            
        Returns:
            Agent type string
        """
        # Look for patterns in parameter paths to determine type
        for param in parameters:
            if f'/{self.param_prefix}/agents/' in param:
                return 'strands_agent'
            elif f'/{self.param_prefix}/agentcore/' in param:
                return 'agentcore_agent'
            elif f'/{self.param_prefix}/agent/' in param:
                return 'bedrock_agent'
            elif f'/{self.param_prefix}/components/' in param:
                return 'mcp_server'
        
        return 'unknown'
    
    async def bulk_unregister_agents(
        self, 
        agent_names: List[str], 
        dry_run: bool = False,
        force: bool = False
    ) -> Dict[str, UnregistrationResult]:
        """
        Unregister multiple agents in bulk
        
        Args:
            agent_names: List of agent names to unregister
            dry_run: If True, only simulate the unregistration
            force: If True, continue even if some parameters fail to delete
            
        Returns:
            Dictionary mapping agent names to their unregistration results
        """
        logger.info(f"Starting bulk unregistration for {len(agent_names)} agents")
        
        results = {}
        
        for agent_name in agent_names:
            try:
                result = await self.unregister_agent(agent_name, dry_run=dry_run, force=force)
                results[agent_name] = result
                
            except Exception as e:
                logger.error(f"Failed to unregister agent {agent_name}: {e}")
                results[agent_name] = UnregistrationResult(
                    agent_name=agent_name,
                    agent_type="unknown",
                    status="failed",
                    parameters_deleted=[],
                    parameters_failed=[],
                    error_message=str(e)
                )
        
        logger.info(f"Bulk unregistration completed for {len(agent_names)} agents")
        return results
    
    async def cleanup_orphaned_parameters(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up orphaned parameters that don't belong to any complete agent
        
        Args:
            dry_run: If True, only simulate the cleanup
            
        Returns:
            Dictionary with cleanup results
        """
        logger.info("Starting cleanup of orphaned parameters")
        
        # Get all agents and their parameters
        agents = await self.list_registered_agents()
        
        # Find agents with incomplete parameter sets
        orphaned_params = []
        incomplete_agents = []
        
        for agent_name, agent_info in agents.items():
            parameters = agent_info["parameters"]
            
            # Check if agent has essential parameters
            has_metadata = any(p.endswith('/metadata') for p in parameters)
            has_arn = any(p.endswith('/agent_arn') for p in parameters)
            has_id = any(p.endswith('/agent_id') for p in parameters)
            
            # If agent is missing essential parameters, consider it orphaned
            if not (has_metadata or (has_arn and has_id)):
                incomplete_agents.append(agent_name)
                orphaned_params.extend(parameters)
        
        if dry_run:
            return {
                "status": "dry_run",
                "orphaned_parameters": orphaned_params,
                "incomplete_agents": incomplete_agents,
                "total_orphaned": len(orphaned_params),
                "message": f"Would clean up {len(orphaned_params)} orphaned parameters from {len(incomplete_agents)} incomplete agents"
            }
        
        # Delete orphaned parameters
        deleted_params = []
        failed_params = []
        
        for param_name in orphaned_params:
            try:
                self.ssm_client.delete_parameter(Name=param_name)
                deleted_params.append(param_name)
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ParameterNotFound':
                    deleted_params.append(param_name)  # Already deleted
                else:
                    failed_params.append(param_name)
                    logger.error(f"Failed to delete orphaned parameter {param_name}: {e}")
        
        return {
            "status": "completed",
            "orphaned_parameters": orphaned_params,
            "incomplete_agents": incomplete_agents,
            "deleted_parameters": deleted_params,
            "failed_parameters": failed_params,
            "total_orphaned": len(orphaned_params),
            "deleted_count": len(deleted_params),
            "failed_count": len(failed_params),
            "message": f"Cleaned up {len(deleted_params)} orphaned parameters from {len(incomplete_agents)} incomplete agents"
        }
    
    async def health_check(self) -> str:
        """
        Check health of the unregistration service
        
        Returns:
            Health status string
        """
        try:
            # Test SSM connectivity
            self.ssm_client.describe_parameters(MaxResults=1)
            return "healthy"
            
        except Exception as e:
            logger.error(f"Unregistration service health check failed: {e}")
            return "unhealthy"