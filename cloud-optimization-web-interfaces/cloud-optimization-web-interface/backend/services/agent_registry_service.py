"""
Agent Registry Service - Manages discovered AgentCore agents with caching and state management.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from models.agentcore_models import AgentInfo, RegistryStats, AgentDiscoveryStatus
from models.agentcore_interfaces import AgentRegistryInterface
from models.exceptions import AgentRegistryError

logger = logging.getLogger(__name__)


class AgentRegistryService(AgentRegistryInterface):
    """Central registry for managing discovered AgentCore agents."""
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialize the agent registry.
        
        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.agents: Dict[str, AgentInfo] = {}
        self.last_discovery: Optional[datetime] = None
        self.discovery_lock = asyncio.Lock()
        self.cache_ttl = cache_ttl
        
        # Statistics tracking
        self._stats = RegistryStats()
        self._cache_hits = 0
        self._cache_misses = 0
        
        logger.info(f"Agent Registry Service initialized with cache TTL: {cache_ttl}s")
    
    async def register_agent(self, agent_info: AgentInfo) -> bool:
        """
        Register a new agent in the registry.
        
        Args:
            agent_info: Agent information to register
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            async with self.discovery_lock:
                agent_id = agent_info.agent_id
                
                # Check if agent already exists
                existing_agent = self.agents.get(agent_id)
                if existing_agent:
                    # Update existing agent
                    logger.info(f"Updating existing agent: {agent_id}")
                    self.agents[agent_id] = agent_info
                    self._stats.agents_updated += 1
                else:
                    # Register new agent
                    logger.info(f"Registering new agent: {agent_id}")
                    self.agents[agent_id] = agent_info
                    self._stats.agents_found += 1
                
                # Update statistics
                self._update_stats()
                
                logger.info(f"Agent {agent_id} registered successfully")
                return True
                
        except Exception as e:
            logger.error(f"Failed to register agent {agent_info.agent_id}: {e}")
            raise AgentRegistryError(
                f"Failed to register agent: {e}",
                agent_id=agent_info.agent_id,
                details={"error": str(e)}
            )
    
    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get agent information by ID.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent information if found, None otherwise
        """
        try:
            agent = self.agents.get(agent_id)
            
            if agent:
                self._cache_hits += 1
                logger.debug(f"Agent {agent_id} found in registry")
                
                # Check if agent data is stale
                if self._is_agent_stale(agent):
                    logger.warning(f"Agent {agent_id} data is stale")
                    agent.status = AgentDiscoveryStatus.UNAVAILABLE
                
                return agent
            else:
                self._cache_misses += 1
                logger.debug(f"Agent {agent_id} not found in registry")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            raise AgentRegistryError(
                f"Failed to get agent: {e}",
                agent_id=agent_id,
                details={"error": str(e)}
            )
    
    async def get_all_agents(self) -> Dict[str, AgentInfo]:
        """
        Get all registered agents.
        
        Returns:
            Dictionary of all registered agents
        """
        try:
            logger.debug(f"Returning {len(self.agents)} registered agents")
            return self.agents.copy()
            
        except Exception as e:
            logger.error(f"Failed to get all agents: {e}")
            raise AgentRegistryError(
                f"Failed to get all agents: {e}",
                details={"error": str(e)}
            )
    
    async def remove_agent(self, agent_id: str) -> bool:
        """
        Remove an agent from the registry.
        
        Args:
            agent_id: Agent identifier to remove
            
        Returns:
            True if removal successful, False if agent not found
        """
        try:
            async with self.discovery_lock:
                if agent_id in self.agents:
                    del self.agents[agent_id]
                    self._stats.agents_removed += 1
                    self._update_stats()
                    logger.info(f"Agent {agent_id} removed from registry")
                    return True
                else:
                    logger.warning(f"Agent {agent_id} not found for removal")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to remove agent {agent_id}: {e}")
            raise AgentRegistryError(
                f"Failed to remove agent: {e}",
                agent_id=agent_id,
                details={"error": str(e)}
            )
    
    async def update_agent_status(self, agent_id: str, status: str) -> bool:
        """
        Update agent status.
        
        Args:
            agent_id: Agent identifier
            status: New status
            
        Returns:
            True if update successful, False if agent not found
        """
        try:
            async with self.discovery_lock:
                agent = self.agents.get(agent_id)
                if agent:
                    old_status = agent.status
                    agent.status = AgentDiscoveryStatus(status)
                    agent.last_updated = datetime.utcnow()
                    
                    logger.info(f"Agent {agent_id} status updated: {old_status} -> {status}")
                    self._update_stats()
                    return True
                else:
                    logger.warning(f"Agent {agent_id} not found for status update")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to update agent {agent_id} status: {e}")
            raise AgentRegistryError(
                f"Failed to update agent status: {e}",
                agent_id=agent_id,
                details={"error": str(e), "status": status}
            )
    
    async def clear_registry(self) -> None:
        """Clear all agents from the registry."""
        try:
            async with self.discovery_lock:
                agent_count = len(self.agents)
                self.agents.clear()
                self.last_discovery = None
                
                # Reset statistics
                self._stats = RegistryStats()
                self._cache_hits = 0
                self._cache_misses = 0
                
                logger.info(f"Registry cleared - removed {agent_count} agents")
                
        except Exception as e:
            logger.error(f"Failed to clear registry: {e}")
            raise AgentRegistryError(
                f"Failed to clear registry: {e}",
                details={"error": str(e)}
            )
    
    def get_registry_stats(self) -> RegistryStats:
        """
        Get registry statistics.
        
        Returns:
            Registry statistics
        """
        try:
            # Update current statistics
            self._update_stats()
            
            # Include cache statistics
            self._stats.cache_hits = self._cache_hits
            self._stats.cache_misses = self._cache_misses
            
            return self._stats
            
        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            raise AgentRegistryError(
                f"Failed to get registry stats: {e}",
                details={"error": str(e)}
            )
    
    async def health_check(self) -> str:
        """
        Check registry health status.
        
        Returns:
            Health status string
        """
        try:
            total_agents = len(self.agents)
            healthy_agents = sum(1 for agent in self.agents.values() if agent.is_healthy())
            
            if total_agents == 0:
                return "degraded"  # No agents registered
            elif healthy_agents == total_agents:
                return "healthy"   # All agents healthy
            elif healthy_agents > 0:
                return "degraded"  # Some agents healthy
            else:
                return "unhealthy" # No healthy agents
                
        except Exception as e:
            logger.error(f"Registry health check failed: {e}")
            return "unhealthy"
    
    def _update_stats(self) -> None:
        """Update internal statistics."""
        try:
            self._stats.total_agents = len(self.agents)
            self._stats.healthy_agents = sum(1 for agent in self.agents.values() if agent.is_healthy())
            self._stats.agentcore_agents = sum(1 for agent in self.agents.values() if agent.is_agentcore())
            self._stats.bedrock_agents = sum(1 for agent in self.agents.values() if agent.is_bedrock_agent())
            self._stats.last_updated = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to update stats: {e}")
    
    def _is_agent_stale(self, agent: AgentInfo) -> bool:
        """
        Check if agent data is stale based on cache TTL.
        
        Args:
            agent: Agent to check
            
        Returns:
            True if agent data is stale
        """
        try:
            if not agent.last_updated:
                return True
                
            age = datetime.utcnow() - agent.last_updated
            return age.total_seconds() > self.cache_ttl
            
        except Exception as e:
            logger.error(f"Failed to check agent staleness: {e}")
            return True  # Assume stale on error
    
    def set_cache_ttl(self, ttl: int) -> None:
        """
        Set cache time-to-live.
        
        Args:
            ttl: Time-to-live in seconds
        """
        self.cache_ttl = ttl
        logger.info(f"Cache TTL updated to {ttl}s")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Cache statistics dictionary
        """
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0.0
        }