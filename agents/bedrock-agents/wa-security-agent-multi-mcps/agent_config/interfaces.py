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
Core interfaces for Enhanced Security Agent with Multi-MCP Integration
Defines base interfaces for MCP orchestration and multi-source data handling
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, AsyncGenerator
from enum import Enum


class MCPServerType(Enum):
    """Types of MCP servers supported"""

    SECURITY = "security"
    KNOWLEDGE = "knowledge"
    API = "api"


class ToolPriority(Enum):
    """Priority levels for tool execution"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class ToolCall:
    """Represents a tool call to an MCP server"""

    tool_name: str
    mcp_server: str
    arguments: Dict[str, Any]
    priority: ToolPriority = ToolPriority.NORMAL
    timeout: int = 120


@dataclass
class ToolResult:
    """Result from an MCP tool call"""

    tool_name: str
    mcp_server: str
    success: bool
    data: Any
    error_message: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = None


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection"""

    name: str
    server_type: MCPServerType
    connection_type: str  # 'agentcore', 'direct', 'api'
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: int = 120
    retry_attempts: int = 3
    health_check_interval: int = 300


@dataclass
class Finding:
    """Security finding from assessment"""

    id: str
    severity: str
    title: str
    description: str
    affected_resources: List[str]
    remediation_steps: List[str]
    documentation_links: List[str]
    api_remediation_available: bool = False


@dataclass
class Recommendation:
    """Security recommendation"""

    id: str
    priority: str
    category: str
    title: str
    description: str
    implementation_steps: List[str]
    documentation_references: List[str]
    estimated_effort: str
    business_impact: str


@dataclass
class SynthesizedResult:
    """Result from multi-source data synthesis"""

    primary_findings: List[Finding]
    supporting_documentation: List[Dict[str, Any]]
    api_insights: List[Dict[str, Any]]
    recommendations: List[Recommendation]
    executive_summary: str
    confidence_score: float


class MCPConnector(ABC):
    """Abstract base class for MCP server connectors"""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize connection to MCP server"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if MCP server is healthy"""
        pass

    @abstractmethod
    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools on the MCP server"""
        pass

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call a tool on the MCP server"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection to MCP server"""
        pass


class MCPOrchestrator(ABC):
    """Abstract base class for MCP orchestration"""

    @abstractmethod
    async def initialize_connections(self) -> None:
        """Initialize all MCP server connections"""
        pass

    @abstractmethod
    async def execute_parallel_calls(
        self, tool_calls: List[ToolCall]
    ) -> List[ToolResult]:
        """Execute multiple tool calls in parallel"""
        pass

    @abstractmethod
    async def call_security_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Call a tool on the Security MCP server"""
        pass

    @abstractmethod
    async def call_knowledge_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Call a tool on the Knowledge MCP server"""
        pass

    @abstractmethod
    async def call_api_tool(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[ToolResult]:
        """Call a tool on the API MCP server"""
        pass

    @abstractmethod
    async def discover_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover tools across all MCP servers"""
        pass

    @abstractmethod
    async def health_check_all(self) -> Dict[str, bool]:
        """Health check all MCP servers"""
        pass

    @abstractmethod
    async def get_tools_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Get tools that support a specific capability"""
        pass

    @abstractmethod
    async def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get tools by category"""
        pass

    @abstractmethod
    async def search_tools(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for tools by query"""
        pass

    @abstractmethod
    async def get_tool_capabilities(self) -> Dict[str, List[str]]:
        """Get all available capabilities and their associated tools"""
        pass

    @abstractmethod
    def update_tool_usage_stats(
        self, tool_name: str, mcp_server: str, execution_time: float, success: bool
    ) -> None:
        """Update tool usage statistics"""
        pass

    @abstractmethod
    async def refresh_tool_discovery(
        self, server_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Refresh tool discovery for all servers or a specific server"""
        pass


class DataSynthesizer(ABC):
    """Abstract base class for multi-source data synthesis"""

    @abstractmethod
    def synthesize_security_assessment(
        self,
        security_data: Dict[str, Any],
        knowledge_data: Dict[str, Any],
        api_data: Dict[str, Any],
    ) -> SynthesizedResult:
        """Synthesize data from multiple sources into coherent insights"""
        pass

    @abstractmethod
    def resolve_conflicts(
        self, conflicting_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Resolve conflicts between different data sources"""
        pass

    @abstractmethod
    def prioritize_recommendations(
        self, recommendations: List[Recommendation]
    ) -> List[Recommendation]:
        """Prioritize recommendations based on risk and impact"""
        pass

    @abstractmethod
    def generate_executive_summary(self, all_data: Dict[str, Any]) -> str:
        """Generate executive summary from all data sources"""
        pass


class ResponseEngine(ABC):
    """Abstract base class for enhanced response generation"""

    @abstractmethod
    def transform_multi_source_response(
        self, tool_results: List[ToolResult], user_query: str
    ) -> str:
        """Transform raw MCP data into intelligent responses"""
        pass

    @abstractmethod
    def create_contextual_analysis(
        self, current_data: Dict[str, Any], session_context: Dict[str, Any]
    ) -> str:
        """Create contextual analysis based on session history"""
        pass

    @abstractmethod
    def generate_action_plan(self, findings: List[Finding]) -> Dict[str, Any]:
        """Generate actionable plan from findings"""
        pass

    @abstractmethod
    def format_with_documentation_links(
        self, response: str, docs: List[Dict[str, Any]]
    ) -> str:
        """Format response with documentation links"""
        pass


class SessionContextManager(ABC):
    """Abstract base class for session context management"""

    @abstractmethod
    def add_assessment_result(self, result: Dict[str, Any]) -> None:
        """Add assessment result to session context"""
        pass

    @abstractmethod
    def get_session_insights(self) -> Dict[str, Any]:
        """Get insights from current session"""
        pass

    @abstractmethod
    def build_contextual_recommendations(
        self, current_query: str
    ) -> List[Recommendation]:
        """Build recommendations based on session context"""
        pass

    @abstractmethod
    def track_remediation_progress(
        self, actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Track remediation progress across sessions"""
        pass


class AWSKnowledgeIntegration(ABC):
    """Abstract base class for AWS Knowledge MCP integration"""

    @abstractmethod
    async def search_relevant_documentation(
        self, security_topic: str
    ) -> List[Dict[str, Any]]:
        """Search AWS documentation for relevant security guidance"""
        pass

    @abstractmethod
    async def get_best_practices_for_service(self, aws_service: str) -> Dict[str, Any]:
        """Get best practices for specific AWS service"""
        pass

    @abstractmethod
    async def find_compliance_guidance(
        self, compliance_framework: str
    ) -> Dict[str, Any]:
        """Find compliance and regulatory guidance"""
        pass

    @abstractmethod
    def format_documentation_results(self, docs: List[Dict[str, Any]]) -> str:
        """Format documentation results for integration"""
        pass


class AWSAPIIntegration(ABC):
    """Abstract base class for AWS API MCP integration"""

    @abstractmethod
    async def get_detailed_resource_config(self, resource_arn: str) -> Dict[str, Any]:
        """Get detailed resource configuration through AWS APIs"""
        pass

    @abstractmethod
    async def analyze_service_configuration(
        self, service_name: str, region: str
    ) -> Dict[str, Any]:
        """Analyze service configuration using AWS APIs"""
        pass

    @abstractmethod
    async def execute_remediation_action(
        self, action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute automated remediation action"""
        pass

    @abstractmethod
    async def validate_permissions(
        self, required_permissions: List[str]
    ) -> Dict[str, Any]:
        """Validate required permissions for API operations"""
        pass


class EnhancedSecurityAgentInterface(ABC):
    """Interface for the Enhanced Security Agent"""

    @abstractmethod
    async def stream(self, user_query: str) -> AsyncGenerator[str, None]:
        """Stream enhanced response with multi-MCP integration"""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        pass

    @abstractmethod
    def get_available_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all available tools across MCP servers"""
        pass

    @abstractmethod
    async def generate_comprehensive_report(self) -> str:
        """Generate comprehensive security report"""
        pass

    @abstractmethod
    async def execute_enhanced_workflow(
        self, workflow_type: str, parameters: Dict[str, Any]
    ) -> str:
        """Execute enhanced security assessment workflow"""
        pass
