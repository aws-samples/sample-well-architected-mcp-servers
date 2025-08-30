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
Unified Tool Discovery Mechanism
Implements tool discovery across all MCP servers with capabilities mapping
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from agent_config.utils.logging_utils import get_logger
from agent_config.utils.error_handling import ErrorHandler

logger = get_logger(__name__)


class ToolCapability(Enum):
    """Enumeration of tool capabilities"""

    SECURITY_ASSESSMENT = "security_assessment"
    VULNERABILITY_SCANNING = "vulnerability_scanning"
    COMPLIANCE_CHECKING = "compliance_checking"
    DOCUMENTATION_SEARCH = "documentation_search"
    BEST_PRACTICES = "best_practices"
    RESOURCE_ANALYSIS = "resource_analysis"
    AUTOMATED_REMEDIATION = "automated_remediation"
    CONFIGURATION_ANALYSIS = "configuration_analysis"
    MONITORING = "monitoring"
    REPORTING = "reporting"


class ToolCategory(Enum):
    """Enumeration of tool categories"""

    SECURITY = "security"
    KNOWLEDGE = "knowledge"
    API = "api"
    ANALYSIS = "analysis"
    REMEDIATION = "remediation"


@dataclass
class ToolMetadata:
    """Metadata for a discovered tool"""

    name: str
    description: str
    mcp_server: str
    category: ToolCategory
    capabilities: Set[ToolCapability] = field(default_factory=set)
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_permissions: List[str] = field(default_factory=list)
    estimated_execution_time: int = 30  # seconds
    risk_level: str = "low"  # low, medium, high
    last_updated: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    success_rate: float = 1.0
    average_execution_time: float = 0.0


@dataclass
class CapabilityMapping:
    """Mapping of capabilities to tools"""

    capability: ToolCapability
    tools: List[str] = field(default_factory=list)
    primary_tool: Optional[str] = None
    fallback_tools: List[str] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    """Result of tool discovery operation"""

    server_name: str
    tools_discovered: int
    tools_added: int
    tools_updated: int
    tools_removed: int
    discovery_time: float
    success: bool
    error_message: Optional[str] = None


class ToolRegistry:
    """Registry for managing discovered tools and their capabilities"""

    def __init__(self):
        """Initialize the tool registry"""
        self.tools: Dict[str, ToolMetadata] = {}
        self.capabilities: Dict[ToolCapability, CapabilityMapping] = {}
        self.server_tools: Dict[str, Set[str]] = {}
        self.last_discovery: Dict[str, datetime] = {}
        self.error_handler = ErrorHandler()

        # Initialize capability mappings
        self._initialize_capability_mappings()

        logger.info("Tool registry initialized")

    def _initialize_capability_mappings(self) -> None:
        """Initialize capability mappings"""
        for capability in ToolCapability:
            self.capabilities[capability] = CapabilityMapping(capability=capability)

    def register_tool(self, tool_metadata: ToolMetadata) -> bool:
        """Register a tool in the registry"""
        try:
            tool_key = f"{tool_metadata.mcp_server}:{tool_metadata.name}"

            # Check if tool already exists
            if tool_key in self.tools:
                # Update existing tool
                existing_tool = self.tools[tool_key]
                existing_tool.description = tool_metadata.description
                existing_tool.parameters = tool_metadata.parameters
                existing_tool.capabilities = tool_metadata.capabilities
                existing_tool.last_updated = datetime.now()
                logger.debug(f"Updated tool: {tool_key}")
            else:
                # Add new tool
                self.tools[tool_key] = tool_metadata
                logger.debug(f"Registered new tool: {tool_key}")

            # Update server tools mapping
            if tool_metadata.mcp_server not in self.server_tools:
                self.server_tools[tool_metadata.mcp_server] = set()
            self.server_tools[tool_metadata.mcp_server].add(tool_key)

            # Update capability mappings
            self._update_capability_mappings(tool_key, tool_metadata.capabilities)

            return True

        except Exception as e:
            logger.error(f"Failed to register tool {tool_metadata.name}: {e}")
            return False

    def _update_capability_mappings(
        self, tool_key: str, capabilities: Set[ToolCapability]
    ) -> None:
        """Update capability mappings for a tool"""
        for capability in capabilities:
            if capability in self.capabilities:
                capability_mapping = self.capabilities[capability]

                # Add tool to capability mapping if not already present
                if tool_key not in capability_mapping.tools:
                    capability_mapping.tools.append(tool_key)

                # Set primary tool if none exists
                if not capability_mapping.primary_tool:
                    capability_mapping.primary_tool = tool_key
                elif tool_key not in capability_mapping.fallback_tools:
                    capability_mapping.fallback_tools.append(tool_key)

    def get_tools_by_capability(self, capability: ToolCapability) -> List[ToolMetadata]:
        """Get tools that support a specific capability"""
        if capability not in self.capabilities:
            return []

        capability_mapping = self.capabilities[capability]
        tools = []

        for tool_key in capability_mapping.tools:
            if tool_key in self.tools:
                tools.append(self.tools[tool_key])

        # Sort by success rate and usage count
        tools.sort(key=lambda t: (t.success_rate, t.usage_count), reverse=True)
        return tools

    def get_tools_by_server(self, server_name: str) -> List[ToolMetadata]:
        """Get all tools for a specific MCP server"""
        if server_name not in self.server_tools:
            return []

        tools = []
        for tool_key in self.server_tools[server_name]:
            if tool_key in self.tools:
                tools.append(self.tools[tool_key])

        return tools

    def get_tools_by_category(self, category: ToolCategory) -> List[ToolMetadata]:
        """Get tools by category"""
        return [tool for tool in self.tools.values() if tool.category == category]

    def search_tools(self, query: str) -> List[ToolMetadata]:
        """Search tools by name or description"""
        query_lower = query.lower()
        matching_tools = []

        for tool in self.tools.values():
            if (
                query_lower in tool.name.lower()
                or query_lower in tool.description.lower()
            ):
                matching_tools.append(tool)

        return matching_tools

    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get statistics about the tool registry"""
        total_tools = len(self.tools)
        tools_by_server = {
            server: len(tools) for server, tools in self.server_tools.items()
        }
        tools_by_category = {}

        for category in ToolCategory:
            tools_by_category[category.value] = len(
                self.get_tools_by_category(category)
            )

        capabilities_coverage = {}
        for capability in ToolCapability:
            tools_count = len(self.get_tools_by_capability(capability))
            capabilities_coverage[capability.value] = tools_count

        return {
            "total_tools": total_tools,
            "tools_by_server": tools_by_server,
            "tools_by_category": tools_by_category,
            "capabilities_coverage": capabilities_coverage,
            "last_discovery_times": {
                server: time.isoformat() for server, time in self.last_discovery.items()
            },
        }

    def update_tool_usage(
        self, tool_key: str, execution_time: float, success: bool
    ) -> None:
        """Update tool usage statistics"""
        if tool_key in self.tools:
            tool = self.tools[tool_key]
            tool.usage_count += 1

            # Update success rate
            total_executions = tool.usage_count
            current_successes = (tool.success_rate * (total_executions - 1)) + (
                1 if success else 0
            )
            tool.success_rate = current_successes / total_executions

            # Update average execution time
            tool.average_execution_time = (
                tool.average_execution_time * (total_executions - 1) + execution_time
            ) / total_executions

    def remove_server_tools(self, server_name: str) -> int:
        """Remove all tools for a specific server"""
        if server_name not in self.server_tools:
            return 0

        tools_to_remove = list(self.server_tools[server_name])
        removed_count = 0

        for tool_key in tools_to_remove:
            if tool_key in self.tools:
                # Remove from capability mappings
                tool = self.tools[tool_key]
                for capability in tool.capabilities:
                    if capability in self.capabilities:
                        capability_mapping = self.capabilities[capability]
                        if tool_key in capability_mapping.tools:
                            capability_mapping.tools.remove(tool_key)
                        if capability_mapping.primary_tool == tool_key:
                            capability_mapping.primary_tool = (
                                capability_mapping.tools[0]
                                if capability_mapping.tools
                                else None
                            )
                        if tool_key in capability_mapping.fallback_tools:
                            capability_mapping.fallback_tools.remove(tool_key)

                # Remove from tools registry
                del self.tools[tool_key]
                removed_count += 1

        # Clear server tools mapping
        del self.server_tools[server_name]

        logger.info(f"Removed {removed_count} tools for server {server_name}")
        return removed_count


class UnifiedToolDiscovery:
    """Unified tool discovery mechanism for all MCP servers"""

    def __init__(self, orchestrator):
        """Initialize the tool discovery system"""
        self.orchestrator = orchestrator
        self.registry = ToolRegistry()
        self.discovery_interval = 300  # 5 minutes
        self.auto_discovery_enabled = True
        self.discovery_lock = asyncio.Lock()
        self.error_handler = ErrorHandler()

        # Tool capability inference rules
        self.capability_inference_rules = self._initialize_capability_rules()

        logger.info("Unified tool discovery system initialized")

    def _initialize_capability_rules(self) -> Dict[str, Set[ToolCapability]]:
        """Initialize rules for inferring tool capabilities from names/descriptions"""
        return {
            # Security-related keywords
            "security": {
                ToolCapability.SECURITY_ASSESSMENT,
                ToolCapability.VULNERABILITY_SCANNING,
            },
            "vulnerability": {
                ToolCapability.VULNERABILITY_SCANNING,
                ToolCapability.SECURITY_ASSESSMENT,
            },
            "compliance": {
                ToolCapability.COMPLIANCE_CHECKING,
                ToolCapability.SECURITY_ASSESSMENT,
            },
            "scan": {
                ToolCapability.VULNERABILITY_SCANNING,
                ToolCapability.SECURITY_ASSESSMENT,
            },
            "assess": {ToolCapability.SECURITY_ASSESSMENT},
            "check": {
                ToolCapability.COMPLIANCE_CHECKING,
                ToolCapability.SECURITY_ASSESSMENT,
            },
            # Knowledge-related keywords
            "search": {ToolCapability.DOCUMENTATION_SEARCH},
            "documentation": {
                ToolCapability.DOCUMENTATION_SEARCH,
                ToolCapability.BEST_PRACTICES,
            },
            "best_practices": {ToolCapability.BEST_PRACTICES},
            "recommend": {
                ToolCapability.BEST_PRACTICES,
                ToolCapability.DOCUMENTATION_SEARCH,
            },
            "guide": {
                ToolCapability.BEST_PRACTICES,
                ToolCapability.DOCUMENTATION_SEARCH,
            },
            # API-related keywords
            "describe": {
                ToolCapability.RESOURCE_ANALYSIS,
                ToolCapability.CONFIGURATION_ANALYSIS,
            },
            "list": {ToolCapability.RESOURCE_ANALYSIS},
            "get": {
                ToolCapability.RESOURCE_ANALYSIS,
                ToolCapability.CONFIGURATION_ANALYSIS,
            },
            "analyze": {
                ToolCapability.RESOURCE_ANALYSIS,
                ToolCapability.CONFIGURATION_ANALYSIS,
            },
            "remediate": {ToolCapability.AUTOMATED_REMEDIATION},
            "fix": {ToolCapability.AUTOMATED_REMEDIATION},
            "execute": {ToolCapability.AUTOMATED_REMEDIATION},
            # Monitoring and reporting
            "monitor": {ToolCapability.MONITORING},
            "report": {ToolCapability.REPORTING},
            "generate": {ToolCapability.REPORTING},
        }

    async def discover_all_tools(
        self, force_refresh: bool = False
    ) -> Dict[str, DiscoveryResult]:
        """Discover tools from all MCP servers"""
        async with self.discovery_lock:
            logger.info("Starting unified tool discovery across all MCP servers")

            discovery_results = {}

            # Ensure orchestrator is initialized
            if not self.orchestrator._initialized:
                await self.orchestrator.initialize_connections()

            # Discover tools from each connector
            for server_name, connector in self.orchestrator.connectors.items():
                if connector:
                    result = await self._discover_server_tools(
                        server_name, connector, force_refresh
                    )
                    discovery_results[server_name] = result
                else:
                    discovery_results[server_name] = DiscoveryResult(
                        server_name=server_name,
                        tools_discovered=0,
                        tools_added=0,
                        tools_updated=0,
                        tools_removed=0,
                        discovery_time=0.0,
                        success=False,
                        error_message="Connector not available",
                    )

            # Update registry statistics
            total_tools = sum(
                result.tools_discovered for result in discovery_results.values()
            )
            successful_discoveries = sum(
                1 for result in discovery_results.values() if result.success
            )

            logger.info(
                f"Tool discovery completed: {total_tools} tools discovered from "
                f"{successful_discoveries}/{len(discovery_results)} servers"
            )

            return discovery_results

    async def _discover_server_tools(
        self, server_name: str, connector, force_refresh: bool
    ) -> DiscoveryResult:
        """Discover tools from a specific MCP server"""
        start_time = time.time()

        try:
            # Check if discovery is needed
            if not force_refresh and server_name in self.registry.last_discovery:
                last_discovery = self.registry.last_discovery[server_name]
                if datetime.now() - last_discovery < timedelta(
                    seconds=self.discovery_interval
                ):
                    logger.debug(f"Skipping discovery for {server_name} - too recent")
                    existing_tools = len(self.registry.get_tools_by_server(server_name))
                    return DiscoveryResult(
                        server_name=server_name,
                        tools_discovered=existing_tools,
                        tools_added=0,
                        tools_updated=0,
                        tools_removed=0,
                        discovery_time=time.time() - start_time,
                        success=True,
                    )

            logger.info(f"Discovering tools from {server_name} MCP server")

            # Get current tools for comparison
            current_tools = set(
                tool.name for tool in self.registry.get_tools_by_server(server_name)
            )

            # Discover tools from connector
            discovered_tools = await connector.discover_tools()

            tools_added = 0
            tools_updated = 0

            # Process discovered tools
            for tool_data in discovered_tools:
                tool_metadata = self._create_tool_metadata(tool_data, server_name)

                if tool_metadata.name in current_tools:
                    tools_updated += 1
                else:
                    tools_added += 1

                self.registry.register_tool(tool_metadata)

            # Check for removed tools
            discovered_tool_names = set(tool["name"] for tool in discovered_tools)
            removed_tools = current_tools - discovered_tool_names
            tools_removed = len(removed_tools)

            # Remove tools that are no longer available
            for tool_name in removed_tools:
                tool_key = f"{server_name}:{tool_name}"
                if tool_key in self.registry.tools:
                    del self.registry.tools[tool_key]

            # Update last discovery time
            self.registry.last_discovery[server_name] = datetime.now()

            discovery_time = time.time() - start_time

            logger.info(
                f"Discovery completed for {server_name}: {len(discovered_tools)} tools "
                f"({tools_added} added, {tools_updated} updated, {tools_removed} removed) "
                f"in {discovery_time:.2f}s"
            )

            return DiscoveryResult(
                server_name=server_name,
                tools_discovered=len(discovered_tools),
                tools_added=tools_added,
                tools_updated=tools_updated,
                tools_removed=tools_removed,
                discovery_time=discovery_time,
                success=True,
            )

        except Exception as e:
            discovery_time = time.time() - start_time
            logger.error(f"Failed to discover tools from {server_name}: {e}")

            return DiscoveryResult(
                server_name=server_name,
                tools_discovered=0,
                tools_added=0,
                tools_updated=0,
                tools_removed=0,
                discovery_time=discovery_time,
                success=False,
                error_message=str(e),
            )

    def _create_tool_metadata(
        self, tool_data: Dict[str, Any], server_name: str
    ) -> ToolMetadata:
        """Create tool metadata from discovered tool data"""
        tool_name = tool_data.get("name", "unknown")
        tool_description = tool_data.get("description", "")
        tool_parameters = tool_data.get("parameters", {})

        # Infer category from server name
        category = self._infer_category(server_name)

        # Infer capabilities from name and description
        capabilities = self._infer_capabilities(tool_name, tool_description)

        # Infer risk level and execution time
        risk_level = self._infer_risk_level(tool_name, tool_description)
        execution_time = self._infer_execution_time(tool_name, capabilities)

        # Extract required permissions if available
        required_permissions = self._extract_permissions(tool_parameters)

        return ToolMetadata(
            name=tool_name,
            description=tool_description,
            mcp_server=server_name,
            category=category,
            capabilities=capabilities,
            parameters=tool_parameters,
            required_permissions=required_permissions,
            estimated_execution_time=execution_time,
            risk_level=risk_level,
            last_updated=datetime.now(),
        )

    def _infer_category(self, server_name: str) -> ToolCategory:
        """Infer tool category from server name"""
        server_lower = server_name.lower()

        if "security" in server_lower:
            return ToolCategory.SECURITY
        elif "knowledge" in server_lower or "doc" in server_lower:
            return ToolCategory.KNOWLEDGE
        elif "api" in server_lower:
            return ToolCategory.API
        else:
            return ToolCategory.ANALYSIS

    def _infer_capabilities(
        self, tool_name: str, tool_description: str
    ) -> Set[ToolCapability]:
        """Infer tool capabilities from name and description"""
        capabilities = set()
        text_to_analyze = f"{tool_name} {tool_description}".lower()

        for keyword, keyword_capabilities in self.capability_inference_rules.items():
            if keyword in text_to_analyze:
                capabilities.update(keyword_capabilities)

        # Default capability if none inferred
        if not capabilities:
            capabilities.add(ToolCapability.RESOURCE_ANALYSIS)

        return capabilities

    def _infer_risk_level(self, tool_name: str, tool_description: str) -> str:
        """Infer risk level from tool name and description"""
        text_to_analyze = f"{tool_name} {tool_description}".lower()

        high_risk_keywords = [
            "delete",
            "remove",
            "terminate",
            "destroy",
            "execute",
            "remediate",
        ]
        medium_risk_keywords = ["modify", "update", "change", "configure", "set"]

        for keyword in high_risk_keywords:
            if keyword in text_to_analyze:
                return "high"

        for keyword in medium_risk_keywords:
            if keyword in text_to_analyze:
                return "medium"

        return "low"

    def _infer_execution_time(
        self, tool_name: str, capabilities: Set[ToolCapability]
    ) -> int:
        """Infer estimated execution time based on tool characteristics"""
        base_time = 30  # seconds

        # Adjust based on capabilities
        if ToolCapability.VULNERABILITY_SCANNING in capabilities:
            base_time = 120  # Vulnerability scans take longer
        elif ToolCapability.COMPLIANCE_CHECKING in capabilities:
            base_time = 90  # Compliance checks are moderately long
        elif ToolCapability.DOCUMENTATION_SEARCH in capabilities:
            base_time = 15  # Documentation searches are quick
        elif ToolCapability.AUTOMATED_REMEDIATION in capabilities:
            base_time = 180  # Remediation actions take longer

        return base_time

    def _extract_permissions(self, parameters: Dict[str, Any]) -> List[str]:
        """Extract required permissions from tool parameters"""
        permissions = []

        # Look for permission-related parameters
        for param_name, param_info in parameters.items():
            if isinstance(param_info, dict):
                description = param_info.get("description", "").lower()
                if "permission" in description or "role" in description:
                    permissions.append(f"Parameter requires: {param_name}")

        return permissions

    async def get_tools_for_query(
        self, query: str, max_tools: int = 10
    ) -> List[ToolMetadata]:
        """Get the most relevant tools for a given query"""
        # Search tools by name/description
        matching_tools = self.registry.search_tools(query)

        # If no direct matches, try capability-based matching
        if not matching_tools:
            query_lower = query.lower()
            relevant_capabilities = set()

            for keyword, capabilities in self.capability_inference_rules.items():
                if keyword in query_lower:
                    relevant_capabilities.update(capabilities)

            for capability in relevant_capabilities:
                matching_tools.extend(self.registry.get_tools_by_capability(capability))

        # Remove duplicates and sort by relevance
        unique_tools = list({tool.name: tool for tool in matching_tools}.values())

        # Sort by success rate and usage count
        unique_tools.sort(key=lambda t: (t.success_rate, t.usage_count), reverse=True)

        return unique_tools[:max_tools]

    async def start_auto_discovery(self) -> None:
        """Start automatic tool discovery background task"""
        if not self.auto_discovery_enabled:
            return

        logger.info("Starting automatic tool discovery")

        while self.auto_discovery_enabled:
            try:
                await asyncio.sleep(self.discovery_interval)
                await self.discover_all_tools(force_refresh=False)
            except Exception as e:
                logger.error(f"Error in automatic tool discovery: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    def stop_auto_discovery(self) -> None:
        """Stop automatic tool discovery"""
        self.auto_discovery_enabled = False
        logger.info("Automatic tool discovery stopped")

    def get_discovery_status(self) -> Dict[str, Any]:
        """Get current discovery status"""
        return {
            "auto_discovery_enabled": self.auto_discovery_enabled,
            "discovery_interval": self.discovery_interval,
            "registry_statistics": self.registry.get_tool_statistics(),
            "last_discovery_times": self.registry.last_discovery,
        }
