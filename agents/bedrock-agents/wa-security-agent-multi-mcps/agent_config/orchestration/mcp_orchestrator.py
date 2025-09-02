# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
MCP Orchestrator Implementation
Manages connections and interactions with multiple MCP servers
"""

import asyncio
from typing import Any, Dict, List, Optional

from agent_config.interfaces import (
    MCPOrchestrator,
    MCPServerConfig,
    MCPServerType,
    ToolCall,
    ToolResult,
)
from agent_config.orchestration.connection_pool import ConnectionPoolManager
from agent_config.orchestration.connectors import (
    APIMCPConnector,
    KnowledgeMCPConnector,
    SecurityMCPConnector,
)
from agent_config.orchestration.parallel_executor import (
    CircuitBreakerConfig,
    ParallelExecutionEngine,
)
from agent_config.orchestration.tool_discovery import UnifiedToolDiscovery
from agent_config.utils.error_handling import ErrorHandler
from agent_config.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MCPOrchestratorImpl(MCPOrchestrator):
    """
    Implementation of MCP Orchestrator for managing multiple MCP server connections
    """

    def __init__(self, region: str = "us-east-1", max_concurrent_requests: int = 10):
        """Initialize the MCP Orchestrator"""
        self.region = region
        self.connectors: Dict[str, Any] = {}
        self.connection_pool = ConnectionPoolManager()
        self.error_handler = ErrorHandler()
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = {}
        self._initialization_lock = asyncio.Lock()
        self._initialized = False

        # Initialize unified tool discovery
        self.tool_discovery = UnifiedToolDiscovery(self)

        # Initialize parallel execution engine
        circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60,
            success_threshold=3,
            timeout_threshold=30,
        )
        self.parallel_executor = ParallelExecutionEngine(
            max_concurrent_requests=max_concurrent_requests,
            max_queue_size=1000,
            circuit_breaker_config=circuit_breaker_config,
        )

        logger.info(
            f"MCP Orchestrator initialized for region: {region} with max_concurrent={max_concurrent_requests}"
        )

    async def initialize_connections(self) -> None:
        """Initialize all MCP server connections with connection pooling"""
        async with self._initialization_lock:
            if self._initialized:
                logger.info("MCP connections already initialized")
                return

            try:
                logger.info("Initializing MCP server connections...")

                # Initialize Security MCP Connector
                await self._initialize_security_connector()

                # Initialize Knowledge MCP Connector
                await self._initialize_knowledge_connector()

                # Initialize API MCP Connector
                await self._initialize_api_connector()

                # Discover tools from all connectors using unified discovery
                await self.tool_discovery.discover_all_tools(force_refresh=True)

                # Start automatic tool discovery
                asyncio.create_task(self.tool_discovery.start_auto_discovery())

                # Start health monitoring
                asyncio.create_task(self._start_health_monitoring())

                # Start parallel execution engine
                await self.parallel_executor.start()

                # Set the executor function for the parallel engine
                self.parallel_executor.set_executor_function(
                    self._create_execution_task
                )

                self._initialized = True
                logger.info(
                    f"✅ MCP Orchestrator initialized with {len(self.connectors)} connectors"
                )

            except Exception as e:
                logger.error(f"Failed to initialize MCP connections: {e}")
                self.error_handler.handle_initialization_error(e)
                raise

    async def _initialize_security_connector(self) -> None:
        """Initialize Security MCP Server connector"""
        try:
            config = MCPServerConfig(
                name="security",
                server_type=MCPServerType.SECURITY,
                connection_type="agentcore",
                timeout=120,
                retry_attempts=3,
                health_check_interval=300,
            )

            connector = SecurityMCPConnector(config, self.region, self.connection_pool)

            if await connector.initialize():
                self.connectors["security"] = connector
                logger.info("✅ Security MCP connector initialized")
            else:
                logger.warning("⚠️ Security MCP connector failed to initialize")

        except Exception as e:
            logger.error(f"Failed to initialize Security MCP connector: {e}")
            # Create a placeholder to prevent errors
            self.connectors["security"] = None

    async def _initialize_knowledge_connector(self) -> None:
        """Initialize Knowledge MCP Server connector"""
        try:
            config = MCPServerConfig(
                name="knowledge",
                server_type=MCPServerType.KNOWLEDGE,
                connection_type="direct",
                timeout=60,
                retry_attempts=3,
                health_check_interval=300,
            )

            connector = KnowledgeMCPConnector(config, self.region, self.connection_pool)

            if await connector.initialize():
                self.connectors["knowledge"] = connector
                logger.info("✅ Knowledge MCP connector initialized")
            else:
                logger.warning("⚠️ Knowledge MCP connector failed to initialize")

        except Exception as e:
            logger.error(f"Failed to initialize Knowledge MCP connector: {e}")
            # Create a placeholder to prevent errors
            self.connectors["knowledge"] = None

    async def _initialize_api_connector(self) -> None:
        """Initialize API MCP Server connector"""
        try:
            config = MCPServerConfig(
                name="api",
                server_type=MCPServerType.API,
                connection_type="agentcore",  # Changed to agentcore for Bedrock Core Runtime
                timeout=120,
                retry_attempts=3,
                health_check_interval=300,
            )

            connector = APIMCPConnector(config, self.region, self.connection_pool)

            if await connector.initialize():
                self.connectors["api"] = connector
                logger.info("✅ API MCP connector initialized via Bedrock Core Runtime")
            else:
                logger.warning("⚠️ API MCP connector failed to initialize")

        except Exception as e:
            logger.error(f"Failed to initialize API MCP connector: {e}")
            # Create a placeholder to prevent errors
            self.connectors["api"] = None

    async def execute_parallel_calls(
        self, tool_calls: List[ToolCall]
    ) -> List[ToolResult]:
        """Execute multiple tool calls in parallel with advanced features"""
        if not tool_calls:
            return []

        logger.info(
            f"Executing {len(tool_calls)} tool calls using parallel execution engine"
        )

        # Use the parallel execution engine with all its advanced features
        return await self.parallel_executor.execute_parallel_calls(
            tool_calls, self._create_execution_task
        )

    async def _create_execution_task(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call and return the result"""
        return await self._execute_single_call(tool_call)

    async def _execute_single_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call through the appropriate connector"""
        connector = self.connectors.get(tool_call.mcp_server)

        if not connector:
            raise ValueError(
                f"No connector available for MCP server: {tool_call.mcp_server}"
            )

        result = await connector.call_tool(tool_call.tool_name, tool_call.arguments)

        # Update tool usage statistics
        self.update_tool_usage_stats(
            tool_call.tool_name,
            tool_call.mcp_server,
            result.execution_time,
            result.success,
        )

        return result

    async def call_security_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Call a tool on the Security MCP server"""
        connector = self.connectors.get("security")
        if not connector:
            logger.warning("Security MCP connector not available")
            return None

        try:
            return await connector.call_tool(tool_name, args)
        except Exception as e:
            logger.error(f"Error calling security tool {tool_name}: {e}")
            return ToolResult(
                tool_name=tool_name,
                mcp_server="security",
                success=False,
                data=None,
                error_message=str(e),
            )

    async def call_knowledge_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Call a tool on the Knowledge MCP server"""
        connector = self.connectors.get("knowledge")
        if not connector:
            logger.warning("Knowledge MCP connector not available")
            return None

        try:
            return await connector.call_tool(tool_name, args)
        except Exception as e:
            logger.error(f"Error calling knowledge tool {tool_name}: {e}")
            return ToolResult(
                tool_name=tool_name,
                mcp_server="knowledge",
                success=False,
                data=None,
                error_message=str(e),
            )

    async def call_api_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Call a tool on the API MCP server"""
        connector = self.connectors.get("api")
        if not connector:
            logger.warning("API MCP connector not available")
            return None

        try:
            return await connector.call_tool(tool_name, args)
        except Exception as e:
            logger.error(f"Error calling API tool {tool_name}: {e}")
            return ToolResult(
                tool_name=tool_name,
                mcp_server="api",
                success=False,
                data=None,
                error_message=str(e),
            )

    async def discover_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover tools across all MCP servers using unified discovery"""
        if not self._initialized:
            await self.initialize_connections()

        # Use unified tool discovery
        discovery_results = await self.tool_discovery.discover_all_tools(
            force_refresh=True
        )

        # Convert to legacy format for compatibility
        tool_registry = {}
        for server_name in self.connectors.keys():
            tools = self.tool_discovery.registry.get_tools_by_server(server_name)
            tool_registry[server_name] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "mcp_server": tool.mcp_server,
                    "category": tool.category.value,
                    "capabilities": [cap.value for cap in tool.capabilities],
                    "risk_level": tool.risk_level,
                    "estimated_execution_time": tool.estimated_execution_time,
                }
                for tool in tools
            ]

        return tool_registry

    async def health_check_all(self) -> Dict[str, bool]:
        """Health check all MCP servers"""
        health_status = {}

        for server_name, connector in self.connectors.items():
            if connector:
                try:
                    is_healthy = await connector.health_check()
                    health_status[server_name] = is_healthy

                    if not is_healthy:
                        logger.warning(
                            f"Health check failed for {server_name} MCP server"
                        )
                        # Attempt reconnection
                        await self._attempt_reconnection(server_name, connector)

                except Exception as e:
                    logger.error(f"Health check error for {server_name}: {e}")
                    health_status[server_name] = False
            else:
                health_status[server_name] = False

        return health_status

    async def _attempt_reconnection(self, server_name: str, connector) -> None:
        """Attempt to reconnect to a failed MCP server"""
        try:
            logger.info(f"Attempting to reconnect to {server_name} MCP server...")

            # Close existing connection
            await connector.close()

            # Reinitialize connection
            if await connector.initialize():
                logger.info(f"✅ Successfully reconnected to {server_name} MCP server")
                # Rediscover tools using unified discovery
                await self.tool_discovery._discover_server_tools(
                    server_name, connector, force_refresh=True
                )
            else:
                logger.error(f"❌ Failed to reconnect to {server_name} MCP server")

        except Exception as e:
            logger.error(f"Error during reconnection attempt for {server_name}: {e}")

    async def _start_health_monitoring(self) -> None:
        """Start background health monitoring for all MCP servers"""
        logger.info("Starting health monitoring for MCP servers")

        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                logger.debug("Performing scheduled health check")
                health_status = await self.health_check_all()

                # Log health status
                healthy_servers = [
                    name for name, status in health_status.items() if status
                ]
                unhealthy_servers = [
                    name for name, status in health_status.items() if not status
                ]

                if unhealthy_servers:
                    logger.warning(f"Unhealthy MCP servers: {unhealthy_servers}")

                logger.info(
                    f"Health check completed - Healthy: {len(healthy_servers)}, Unhealthy: {len(unhealthy_servers)}"
                )

            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")

    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics for monitoring"""
        stats = {
            "initialized": self._initialized,
            "total_connectors": len(self.connectors),
            "active_connectors": len(
                [c for c in self.connectors.values() if c is not None]
            ),
            "total_tools": len(self.tool_discovery.registry.tools),
            "tools_by_server": {
                name: len(self.tool_discovery.registry.get_tools_by_server(name))
                for name in self.connectors.keys()
            },
            "tool_discovery_stats": self.tool_discovery.get_discovery_status(),
            "connection_pool_stats": await self.connection_pool.get_stats(),
            "parallel_execution_stats": await self.parallel_executor.get_execution_stats(),
        }

        return stats

    async def close_all_connections(self) -> None:
        """Close all MCP server connections"""
        logger.info("Closing all MCP connections...")

        # Stop parallel execution engine
        await self.parallel_executor.stop()

        # Stop tool discovery
        self.tool_discovery.stop_auto_discovery()

        for server_name, connector in self.connectors.items():
            if connector:
                try:
                    await connector.close()
                    logger.info(f"Closed connection to {server_name} MCP server")
                except Exception as e:
                    logger.error(f"Error closing connection to {server_name}: {e}")

        await self.connection_pool.close_all()
        self._initialized = False
        logger.info("All MCP connections closed")

    async def get_tools_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Get tools that support a specific capability"""
        from agent_config.orchestration.tool_discovery import ToolCapability

        try:
            capability_enum = ToolCapability(capability)
            tools = self.tool_discovery.registry.get_tools_by_capability(
                capability_enum
            )

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "mcp_server": tool.mcp_server,
                    "category": tool.category.value,
                    "capabilities": [cap.value for cap in tool.capabilities],
                    "risk_level": tool.risk_level,
                    "success_rate": tool.success_rate,
                    "usage_count": tool.usage_count,
                    "estimated_execution_time": tool.estimated_execution_time,
                }
                for tool in tools
            ]
        except ValueError:
            logger.warning(f"Unknown capability: {capability}")
            return []

    async def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get tools by category"""
        from agent_config.orchestration.tool_discovery import ToolCategory

        try:
            category_enum = ToolCategory(category)
            tools = self.tool_discovery.registry.get_tools_by_category(category_enum)

            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "mcp_server": tool.mcp_server,
                    "category": tool.category.value,
                    "capabilities": [cap.value for cap in tool.capabilities],
                    "risk_level": tool.risk_level,
                    "success_rate": tool.success_rate,
                    "usage_count": tool.usage_count,
                    "estimated_execution_time": tool.estimated_execution_time,
                }
                for tool in tools
            ]
        except ValueError:
            logger.warning(f"Unknown category: {category}")
            return []

    async def search_tools(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for tools by query"""
        tools = await self.tool_discovery.get_tools_for_query(query, max_results)

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "mcp_server": tool.mcp_server,
                "category": tool.category.value,
                "capabilities": [cap.value for cap in tool.capabilities],
                "risk_level": tool.risk_level,
                "success_rate": tool.success_rate,
                "usage_count": tool.usage_count,
                "estimated_execution_time": tool.estimated_execution_time,
            }
            for tool in tools
        ]

    async def get_tool_capabilities(self) -> Dict[str, List[str]]:
        """Get all available capabilities and their associated tools"""
        from agent_config.orchestration.tool_discovery import ToolCapability

        capabilities = {}
        for capability in ToolCapability:
            tools = self.tool_discovery.registry.get_tools_by_capability(capability)
            capabilities[capability.value] = [
                f"{tool.mcp_server}:{tool.name}" for tool in tools
            ]

        return capabilities

    def update_tool_usage_stats(
        self, tool_name: str, mcp_server: str, execution_time: float, success: bool
    ) -> None:
        """Update tool usage statistics"""
        tool_key = f"{mcp_server}:{tool_name}"
        self.tool_discovery.registry.update_tool_usage(
            tool_key, execution_time, success
        )

    async def refresh_tool_discovery(
        self, server_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Refresh tool discovery for all servers or a specific server"""
        if server_name:
            # Refresh specific server
            connector = self.connectors.get(server_name)
            if connector:
                result = await self.tool_discovery._discover_server_tools(
                    server_name, connector, force_refresh=True
                )
                return {server_name: result}
            else:
                return {server_name: {"error": "Connector not available"}}
        else:
            # Refresh all servers
            return await self.tool_discovery.discover_all_tools(force_refresh=True)
