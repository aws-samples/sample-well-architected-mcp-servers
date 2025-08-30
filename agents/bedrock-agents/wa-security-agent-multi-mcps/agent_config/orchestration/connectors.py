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
MCP Server Connectors
Individual connector classes for different types of MCP servers
"""

import asyncio
import json
import time
import boto3
from datetime import timedelta
from typing import Dict, List, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from agent_config.interfaces import MCPConnector, ToolResult, MCPServerConfig
from agent_config.orchestration.connection_pool import ConnectionPoolManager
from agent_config.utils.logging_utils import get_logger
from agent_config.utils.error_handling import ErrorHandler

logger = get_logger(__name__)


class BaseMCPConnector(MCPConnector):
    """Base class for MCP server connectors with common functionality"""

    def __init__(
        self,
        config: MCPServerConfig,
        region: str,
        connection_pool: ConnectionPoolManager,
    ):
        """Initialize base connector"""
        self.config = config
        self.region = region
        self.connection_pool = connection_pool
        self.error_handler = ErrorHandler()
        self.is_initialized = False
        self.last_health_check = 0
        self.health_check_cache_duration = 30  # seconds

        logger.info(f"Initialized {config.name} MCP connector for region {region}")

    async def health_check(self) -> bool:
        """Check if MCP server is healthy with caching"""
        current_time = time.time()

        # Use cached result if recent
        if current_time - self.last_health_check < self.health_check_cache_duration:
            return self.is_initialized

        try:
            # Perform actual health check
            health_result = await self._perform_health_check()
            self.last_health_check = current_time
            return health_result

        except Exception as e:
            logger.error(f"Health check failed for {self.config.name}: {e}")
            return False

    async def _perform_health_check(self) -> bool:
        """Override in subclasses to implement specific health check logic"""
        return self.is_initialized

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute an operation with retry logic"""
        last_exception = None

        for attempt in range(self.config.retry_attempts):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.config.retry_attempts - 1:
                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {self.config.name}, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"All {self.config.retry_attempts} attempts failed for {self.config.name}"
                    )

        raise last_exception


class SecurityMCPConnector(BaseMCPConnector):
    """Connector for Well-Architected Security MCP Server (AgentCore runtime)"""

    def __init__(
        self,
        config: MCPServerConfig,
        region: str,
        connection_pool: ConnectionPoolManager,
    ):
        super().__init__(config, region, connection_pool)
        self.mcp_url = None
        self.mcp_headers = None
        self.connection_info = None

    async def initialize(self) -> bool:
        """Initialize connection to Well-Architected Security MCP Server"""
        try:
            logger.info(
                "Initializing Well-Architected Security MCP Server connection..."
            )

            # Get connection info from SSM parameter
            ssm_client = boto3.client("ssm", region_name=self.region)

            try:
                # Get connection info from SSM
                response = ssm_client.get_parameter(
                    Name="/coa/components/wa_security_mcp/connection_info"
                )
                self.connection_info = json.loads(response["Parameter"]["Value"])

                agent_arn = self.connection_info["agent_arn"]

                # Get bearer token from Cognito (if needed)
                # For now, we'll use the agent ARN directly
                encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
                self.mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
                self.mcp_headers = {"Content-Type": "application/json"}

                # Test connection
                await self._test_connection()

                self.is_initialized = True
                logger.info(
                    f"✅ Well-Architected Security MCP Server connection initialized (Agent: {self.connection_info['agent_id']})"
                )
                return True

            except Exception as e:
                logger.warning(
                    f"Well-Architected Security MCP Server not available: {e}"
                )
                self.is_initialized = False
                return False

        except Exception as e:
            logger.error(
                f"Failed to initialize Well-Architected Security MCP Server: {e}"
            )
            self.is_initialized = False
            return False

    async def _test_connection(self) -> None:
        """Test the connection to Security MCP Server"""
        if not self.mcp_url or not self.mcp_headers:
            raise ValueError("MCP connection not configured")

        async with streamablehttp_client(
            self.mcp_url, self.mcp_headers, timeout=timedelta(seconds=30)
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                # Test with a simple tool list call
                await session.list_tools()

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools on Security MCP Server"""
        if not self.is_initialized:
            return []

        try:
            return await self._execute_with_retry(self._discover_tools_internal)
        except Exception as e:
            logger.error(f"Failed to discover Security MCP tools: {e}")
            return []

    async def _discover_tools_internal(self) -> List[Dict[str, Any]]:
        """Internal method to discover tools"""
        async with streamablehttp_client(
            self.mcp_url,
            self.mcp_headers,
            timeout=timedelta(seconds=self.config.timeout),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()

                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema.get("properties", {})
                        if hasattr(tool, "inputSchema") and tool.inputSchema
                        else {},
                        "mcp_server": self.config.name,
                    }
                    for tool in tool_result.tools
                ]

                logger.info(f"Discovered {len(tools)} tools from Security MCP Server")
                return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call a tool on Security MCP Server"""
        start_time = time.time()

        if not self.is_initialized:
            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=False,
                data=None,
                error_message="Security MCP Server not initialized",
                execution_time=0.0,
            )

        try:
            result = await self._execute_with_retry(
                self._call_tool_internal, tool_name, arguments
            )
            execution_time = time.time() - start_time

            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error calling Security MCP tool {tool_name}: {e}")

            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=False,
                data=None,
                error_message=str(e),
                execution_time=execution_time,
            )

    async def _call_tool_internal(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """Internal method to call tool"""
        async with streamablehttp_client(
            self.mcp_url,
            self.mcp_headers,
            timeout=timedelta(seconds=self.config.timeout),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name=tool_name, arguments=arguments)
                return result.content[0].text

    async def _perform_health_check(self) -> bool:
        """Perform health check for Security MCP Server"""
        if not self.mcp_url or not self.mcp_headers:
            return False

        try:
            await self._test_connection()
            return True
        except Exception as e:
            logger.warning(f"Security MCP Server health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close Security MCP Server connection"""
        self.is_initialized = False
        self.mcp_url = None
        self.mcp_headers = None
        logger.info("Security MCP Server connection closed")


class KnowledgeMCPConnector(BaseMCPConnector):
    """Connector for AWS Knowledge MCP Server (public endpoint)"""

    def __init__(
        self,
        config: MCPServerConfig,
        region: str,
        connection_pool: ConnectionPoolManager,
    ):
        super().__init__(config, region, connection_pool)
        self.available_tools = []
        self.public_endpoint = "https://knowledge-mcp.global.api.aws"

    async def initialize(self) -> bool:
        """Initialize connection to AWS Knowledge MCP Server"""
        try:
            logger.info("Initializing AWS Knowledge MCP Server connection...")

            # AWS Knowledge MCP Server tools available through public endpoint
            self.available_tools = [
                {
                    "name": "aws___search_documentation",
                    "description": "Search AWS documentation for relevant information",
                    "parameters": {
                        "search_phrase": {
                            "type": "string",
                            "description": "Search phrase",
                        },
                        "limit": {"type": "integer", "description": "Maximum results"},
                    },
                    "mcp_server": self.config.name,
                },
                {
                    "name": "aws___read_documentation",
                    "description": "Read specific AWS documentation pages",
                    "parameters": {
                        "url": {"type": "string", "description": "Documentation URL"},
                        "max_length": {
                            "type": "integer",
                            "description": "Maximum content length",
                        },
                    },
                    "mcp_server": self.config.name,
                },
                {
                    "name": "aws___recommend",
                    "description": "Get content recommendations for AWS documentation",
                    "parameters": {
                        "url": {
                            "type": "string",
                            "description": "Base URL for recommendations",
                        }
                    },
                    "mcp_server": self.config.name,
                },
            ]

            self.is_initialized = True
            logger.info("✅ AWS Knowledge MCP Server connection initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize AWS Knowledge MCP Server: {e}")
            self.is_initialized = False
            return False

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools on AWS Knowledge MCP Server"""
        if not self.is_initialized:
            return []

        logger.info(
            f"Discovered {len(self.available_tools)} tools from AWS Knowledge MCP Server"
        )
        return self.available_tools.copy()

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call a tool on AWS Knowledge MCP Server"""
        start_time = time.time()

        if not self.is_initialized:
            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=False,
                data=None,
                error_message="AWS Knowledge MCP Server not initialized",
                execution_time=0.0,
            )

        try:
            result = await self._execute_with_retry(
                self._call_tool_internal, tool_name, arguments
            )
            execution_time = time.time() - start_time

            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error calling AWS Knowledge MCP tool {tool_name}: {e}")

            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=False,
                data=None,
                error_message=str(e),
                execution_time=execution_time,
            )

    async def _call_tool_internal(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """Internal method to call AWS Knowledge MCP tools via public endpoint"""
        logger.info(
            f"Calling AWS Knowledge tool: {tool_name} via {self.public_endpoint}"
        )

        # Make HTTP request to the public AWS Knowledge MCP endpoint
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Prepare MCP request payload
            mcp_request = {
                "jsonrpc": "2.0",
                "id": f"{tool_name}_{int(time.time())}",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }

            # Make request to public endpoint
            response = await client.post(
                f"{self.public_endpoint}/mcp",
                json=mcp_request,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "AWS-Enhanced-Security-Agent/1.0",
                },
            )

            if response.status_code == 200:
                result_data = response.json()

                # Extract results from MCP response
                if "result" in result_data and "content" in result_data["result"]:
                    content = result_data["result"]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # Parse the text content which should contain JSON results
                        text_content = content[0].get("text", "")
                        if text_content:
                            try:
                                # Try to parse as JSON
                                parsed_results = json.loads(text_content)
                                return parsed_results
                            except json.JSONDecodeError:
                                # If not JSON, return as text
                                return text_content

                logger.warning(
                    f"No results from AWS Knowledge MCP server for tool: {tool_name}"
                )
                return {}
            else:
                raise Exception(
                    f"HTTP error from AWS Knowledge MCP server: {response.status_code}"
                )

    def _format_search_result(self, search_phrase: str) -> str:
        """Format search results for AWS documentation"""
        return f"""📚 **AWS Documentation Search Results for: "{search_phrase}"**

**1. AWS Security Best Practices**
🔗 https://docs.aws.amazon.com/security/
📝 Comprehensive guide to AWS security best practices and recommendations

**2. AWS Well-Architected Security Pillar**
🔗 https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/
📝 Security pillar of the AWS Well-Architected Framework

**3. AWS Security Services Overview**
🔗 https://aws.amazon.com/security/
📝 Overview of AWS security services and capabilities
"""

    def _format_documentation_content(self, url: str) -> str:
        """Format documentation content"""
        return f"""📖 **AWS Documentation Content**

**Source**: {url}

This documentation provides comprehensive guidance on AWS security best practices, including:

- Identity and Access Management (IAM) configuration
- Network security and VPC setup
- Data encryption at rest and in transit
- Monitoring and logging with CloudTrail and CloudWatch
- Incident response and security automation

For detailed implementation steps, refer to the full documentation at the provided URL.
"""

    def _format_recommendations(self, url: str) -> str:
        """Format documentation recommendations"""
        return """💡 **Related AWS Documentation Recommendations**

Based on your current context, here are recommended resources:

**Security-Related Documentation:**
- AWS Security Best Practices Guide
- IAM User Guide
- VPC Security Best Practices
- AWS Config Rules for Security
- AWS Security Hub User Guide

**Implementation Guides:**
- Security Pillar - AWS Well-Architected Framework
- AWS Security Incident Response Guide
- Automated Security Response on AWS
"""

    async def _perform_health_check(self) -> bool:
        """Perform health check for AWS Knowledge MCP Server"""
        # Since this is a direct integration, we just check if it's initialized
        return self.is_initialized

    async def close(self) -> None:
        """Close AWS Knowledge MCP Server connection"""
        self.is_initialized = False
        self.available_tools.clear()
        logger.info("AWS Knowledge MCP Server connection closed")


class APIMCPConnector(BaseMCPConnector):
    """Connector for AWS API MCP Server using awslabs.aws-api-mcp-server package"""

    def __init__(
        self,
        config: MCPServerConfig,
        region: str,
        connection_pool: ConnectionPoolManager,
    ):
        super().__init__(config, region, connection_pool)
        self.mcp_url = None
        self.mcp_headers = None
        self.connection_info = None

    async def initialize(self) -> bool:
        """Initialize connection to AWS API MCP Server via Bedrock Core Runtime"""
        try:
            logger.info("Initializing AWS API MCP Server connection...")

            # Get connection info from SSM parameter
            ssm_client = boto3.client("ssm", region_name=self.region)

            try:
                # Get connection info from SSM
                response = ssm_client.get_parameter(
                    Name="/coa/components/aws_api_mcp/connection_info"
                )
                self.connection_info = json.loads(response["Parameter"]["Value"])

                agent_arn = self.connection_info["agent_arn"]

                # Build MCP connection details
                encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
                self.mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
                self.mcp_headers = {"Content-Type": "application/json"}

                # Test connection
                await self._test_connection()

                self.is_initialized = True
                logger.info(
                    f"✅ AWS API MCP Server connection initialized (Agent: {self.connection_info['agent_id']}, Package: {self.connection_info['package_name']})"
                )
                return True

            except Exception as e:
                logger.warning(f"AWS API MCP Server not available: {e}")
                self.is_initialized = False
                return False

        except Exception as e:
            logger.error(f"Failed to initialize AWS API MCP Server: {e}")
            self.is_initialized = False
            return False

    async def _test_connection(self) -> None:
        """Test the connection to AWS API MCP Server"""
        if not self.mcp_url or not self.mcp_headers:
            raise ValueError("MCP connection not configured")

        async with streamablehttp_client(
            self.mcp_url, self.mcp_headers, timeout=timedelta(seconds=30)
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                # Test with a simple tool list call
                await session.list_tools()

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools on AWS API MCP Server"""
        if not self.is_initialized:
            return []

        try:
            return await self._execute_with_retry(self._discover_tools_internal)
        except Exception as e:
            logger.error(f"Failed to discover AWS API MCP tools: {e}")
            return []

    async def _discover_tools_internal(self) -> List[Dict[str, Any]]:
        """Internal method to discover tools"""
        async with streamablehttp_client(
            self.mcp_url,
            self.mcp_headers,
            timeout=timedelta(seconds=self.config.timeout),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.list_tools()

                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema.get("properties", {})
                        if hasattr(tool, "inputSchema") and tool.inputSchema
                        else {},
                        "mcp_server": self.config.name,
                    }
                    for tool in tool_result.tools
                ]

                logger.info(f"Discovered {len(tools)} tools from AWS API MCP Server")
                return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Call a tool on AWS API MCP Server"""
        start_time = time.time()

        if not self.is_initialized:
            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=False,
                data=None,
                error_message="AWS API MCP Server not initialized",
                execution_time=0.0,
            )

        try:
            result = await self._execute_with_retry(
                self._call_tool_internal, tool_name, arguments
            )
            execution_time = time.time() - start_time

            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error calling AWS API MCP tool {tool_name}: {e}")

            return ToolResult(
                tool_name=tool_name,
                mcp_server=self.config.name,
                success=False,
                data=None,
                error_message=str(e),
                execution_time=execution_time,
            )

    async def _call_tool_internal(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """Internal method to call AWS API MCP tools via Bedrock Core Runtime"""
        logger.info(f"Calling AWS API tool via Bedrock Core Runtime: {tool_name}")

        async with streamablehttp_client(
            self.mcp_url,
            self.mcp_headers,
            timeout=timedelta(seconds=self.config.timeout),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

                if result.content and len(result.content) > 0:
                    return result.content[0].text
                else:
                    return f"Tool {tool_name} executed successfully but returned no content"

    def _format_instance_description(self, arguments: Dict[str, Any]) -> str:
        """Format EC2 instance description results"""
        region = arguments.get("region", self.region)
        return f"""🖥️ **EC2 Instances in {region}**

**Instance Details:**
- Instance ID: i-1234567890abcdef0
- Instance Type: t3.medium
- State: running
- Security Groups: sg-12345678
- VPC: vpc-12345678
- Subnet: subnet-12345678

**Security Assessment:**
- ✅ Instance is in private subnet
- ⚠️ Security group allows SSH from 0.0.0.0/0
- ✅ EBS volumes are encrypted
"""

    def _format_s3_bucket_list(self, arguments: Dict[str, Any]) -> str:
        """Format S3 bucket list results"""
        include_encryption = arguments.get("include_encryption", True)

        result = "🪣 **S3 Buckets Configuration**\n\n"

        if include_encryption:
            result += """**Bucket: example-bucket-1**
- Region: us-east-1
- Encryption: AES256 (Server-side)
- Public Access: Blocked
- Versioning: Enabled

**Bucket: example-bucket-2**
- Region: us-west-2
- Encryption: ❌ Not Encrypted
- Public Access: Blocked
- Versioning: Disabled
"""
        else:
            result += """**Bucket: example-bucket-1**
- Region: us-east-1
- Public Access: Blocked

**Bucket: example-bucket-2**
- Region: us-west-2
- Public Access: Blocked
"""

        return result

    def _format_security_groups(self, arguments: Dict[str, Any]) -> str:
        """Format security group results"""
        region = arguments.get("region", self.region)
        return f"""🛡️ **Security Groups in {region}**

**Security Group: sg-12345678**
- Name: web-server-sg
- VPC: vpc-12345678
- Inbound Rules:
  - HTTP (80) from 0.0.0.0/0
  - HTTPS (443) from 0.0.0.0/0
  - SSH (22) from 10.0.0.0/8
- Outbound Rules:
  - All traffic to 0.0.0.0/0

**Security Assessment:**
- ✅ HTTPS traffic allowed
- ✅ SSH restricted to private networks
- ✅ No unnecessary ports open
"""

    def _format_remediation_result(self, arguments: Dict[str, Any]) -> str:
        """Format remediation execution results"""
        action_type = arguments.get("action_type", "unknown")
        resource_arn = arguments.get("resource_arn", "unknown")

        return f"""🔧 **Remediation Action Executed**

**Action Type:** {action_type}
**Resource:** {resource_arn}
**Status:** ✅ Completed Successfully

**Changes Made:**
- Applied security best practices configuration
- Updated resource policies
- Enabled required security features

**Next Steps:**
- Monitor resource for compliance
- Verify functionality after changes
- Update documentation
"""

    async def _perform_health_check(self) -> bool:
        """Perform health check for AWS API MCP Server"""
        if not self.is_initialized or not self.mcp_url or not self.mcp_headers:
            return False

        try:
            async with streamablehttp_client(
                self.mcp_url, self.mcp_headers, timeout=timedelta(seconds=10)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    # Simple health check by listing tools
                    await session.list_tools()
                    return True
        except Exception as e:
            logger.warning(f"AWS API MCP Server health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close AWS API MCP Server connection"""
        self.is_initialized = False
        self.mcp_url = None
        self.mcp_headers = None
        logger.info("AWS API MCP Server connection closed")
