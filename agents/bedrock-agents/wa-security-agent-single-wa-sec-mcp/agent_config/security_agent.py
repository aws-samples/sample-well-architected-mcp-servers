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
Enhanced Well-Architected Security Agent for Amazon Bedrock
Integrates Claude 3.5 Sonnet with the Well-Architected Security MCP Server
Includes comprehensive response transformation for human readability
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

import boto3
from bedrock_agentcore.agent import Agent
from bedrock_agentcore.memory import MemoryHook
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .response_transformer import SecurityResponseTransformer

logger = logging.getLogger(__name__)


class SecurityAgent(Agent):
    """
    Well-Architected Security Agent that combines Claude 3.5 Sonnet with MCP Security Tools
    """

    def __init__(
        self,
        bearer_token: str,
        memory_hook: MemoryHook,
        model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        region: str = "us-east-1",
        **kwargs,
    ):
        """Initialize the Enhanced Security Agent with Response Transformation"""
        super().__init__(
            bearer_token=bearer_token,
            memory_hook=memory_hook,
            model_id=model_id,
            **kwargs,
        )

        self.region = region
        self.mcp_session = None
        self.mcp_tools = []
        self.mcp_url = None
        self.mcp_headers = None

        # Initialize response transformer
        self.response_transformer = SecurityResponseTransformer()

        # Store responses for comprehensive analysis
        self.session_responses = []

        # Initialize MCP connection
        asyncio.create_task(self._initialize_mcp_connection())

    async def _initialize_mcp_connection(self):
        """Initialize connection to the Well-Architected Security MCP Server"""
        try:
            logger.info(
                "Initializing MCP connection to Well-Architected Security Server..."
            )

            # Get MCP server credentials
            ssm_client = boto3.client("ssm", region_name=self.region)
            secrets_client = boto3.client("secretsmanager", region_name=self.region)

            # Get Agent ARN
            agent_arn_response = ssm_client.get_parameter(
                Name="/wa_security_direct_mcp/runtime/agent_arn"
            )
            agent_arn = agent_arn_response["Parameter"]["Value"]

            # Get bearer token
            response = secrets_client.get_secret_value(
                SecretId="wa_security_direct_mcp/cognito/credentials"
            )
            secret_value = response["SecretString"]
            parsed_secret = json.loads(secret_value)
            bearer_token = parsed_secret["bearer_token"]

            # Build MCP connection details
            encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
            self.mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            self.mcp_headers = {
                "authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            }

            # Test connection and get available tools
            await self._discover_mcp_tools()

            logger.info(
                f"✅ MCP connection initialized with {len(self.mcp_tools)} security tools"
            )

        except Exception as e:
            logger.error(f"Failed to initialize MCP connection: {e}")
            self.mcp_tools = []

    async def _discover_mcp_tools(self):
        """Discover available MCP tools"""
        try:
            async with streamablehttp_client(
                self.mcp_url, self.mcp_headers, timeout=timedelta(seconds=60)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tool_result = await session.list_tools()
                    self.mcp_tools = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema.get("properties", {})
                            if hasattr(tool, "inputSchema") and tool.inputSchema
                            else {},
                        }
                        for tool in tool_result.tools
                    ]
        except Exception as e:
            logger.error(f"Failed to discover MCP tools: {e}")
            self.mcp_tools = []

    async def _call_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any], user_query: str = ""
    ) -> Optional[str]:
        """Call an MCP tool, transform the response, and return human-readable result"""
        try:
            logger.info(f"Calling MCP tool: {tool_name} with args: {arguments}")

            async with streamablehttp_client(
                self.mcp_url, self.mcp_headers, timeout=timedelta(seconds=120)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        name=tool_name, arguments=arguments
                    )
                    raw_response = result.content[0].text

                    logger.info(f"Raw MCP response received for {tool_name}")

                    # Transform the response for human readability
                    transformed_response = self.response_transformer.transform_response(
                        tool_name=tool_name,
                        raw_response=raw_response,
                        user_query=user_query,
                    )

                    # Store response for session analysis
                    self.session_responses.append(
                        {
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "raw_response": raw_response,
                            "transformed_response": transformed_response,
                            "timestamp": asyncio.get_event_loop().time(),
                        }
                    )

                    logger.info(f"Response transformed for {tool_name}")
                    return transformed_response

        except Exception as e:
            logger.error(f"Failed to call MCP tool {tool_name}: {e}")
            error_response = self.response_transformer._format_error_response(
                tool_name=tool_name, error=str(e), raw_response=""
            )
            return error_response

    def _get_system_prompt(self) -> str:
        """Get the enhanced system prompt for the security agent with response transformation"""
        tools_description = "\n".join(
            [f"- {tool['name']}: {tool['description']}" for tool in self.mcp_tools]
        )

        return f"""You are an Enhanced Well-Architected Security Expert Assistant with advanced response transformation capabilities.

Your role is to help users assess, understand, and improve their AWS security posture according to the AWS Well-Architected Framework Security Pillar. You have access to real-time AWS security data through MCP tools and provide comprehensive, human-readable analysis.

## Available Security Assessment Tools:
{tools_description}

## Enhanced Capabilities:
1. **Intelligent Response Transformation**: All MCP tool responses are automatically transformed into comprehensive, human-readable formats
2. **Risk-Based Analysis**: Automatic risk scoring and prioritization of security issues
3. **Visual Formatting**: Rich formatting with emojis, colors, and structured layouts for better readability
4. **Executive Summaries**: Generate high-level summaries for management and stakeholders
5. **Actionable Recommendations**: Specific, prioritized remediation steps with business impact analysis
6. **Contextual Analysis**: Build session context to provide increasingly intelligent recommendations

## Response Transformation Features:
- **Security Services**: Visual status indicators, service-by-service breakdown, security scores
- **Storage Encryption**: Encryption compliance rates, unencrypted resource identification, remediation priorities
- **Network Security**: Security posture analysis, insecure resource identification, configuration recommendations
- **Security Findings**: Severity-based grouping, risk prioritization, immediate action items
- **Service Inventory**: Categorized service listings, security-relevant service identification

## How You Help Users:
1. **Real-Time Assessment**: Use MCP tools to get current AWS security data
2. **Intelligent Analysis**: Transform raw data into actionable insights
3. **Risk Prioritization**: Focus on critical and high-severity issues first
4. **Business Context**: Explain security issues in business terms and impact
5. **Remediation Guidance**: Provide specific, step-by-step remediation instructions
6. **Continuous Improvement**: Build on previous assessments for better recommendations

## Response Style Guidelines:
- **Comprehensive but Digestible**: Detailed analysis presented in clear, structured format
- **Visual Enhancement**: Use emojis, formatting, and visual indicators for better readability
- **Action-Oriented**: Always include specific next steps and recommendations
- **Risk-Focused**: Prioritize critical and high-risk issues
- **Business-Aware**: Explain technical issues in business impact terms
- **Well-Architected Aligned**: Reference AWS Well-Architected Framework principles

## Example Enhanced Interactions:
- "Check my security services" → Comprehensive service status with visual indicators and security score
- "Are my S3 buckets encrypted?" → Detailed encryption analysis with compliance rates and specific remediation steps
- "Show me security findings" → Severity-grouped findings with risk prioritization and immediate action items
- "What's my security posture?" → Multi-dimensional assessment with executive summary and improvement roadmap
- "Generate executive summary" → High-level security overview for management presentation

## Key Enhancement: Response Transformation
Every MCP tool response is automatically enhanced with:
- 📊 Visual formatting and status indicators
- 🎯 Risk-based prioritization and scoring
- 📋 Structured, scannable layouts
- 🚀 Specific, actionable recommendations
- 💼 Business impact explanations
- 🔄 Continuous context building

Remember: You don't just provide data - you provide intelligence. Transform every response into actionable insights that help users improve their security posture effectively."""

    async def _process_security_query(self, user_message: str) -> str:
        """Process user query and determine which security tools to use with enhanced response transformation"""
        user_message_lower = user_message.lower()

        # Determine which tools to call based on user intent
        tool_calls = []

        # Security services queries
        if any(
            word in user_message_lower
            for word in [
                "security services",
                "guardduty",
                "security hub",
                "inspector",
                "enabled",
                "disabled",
            ]
        ):
            tool_calls.append(
                {
                    "tool": "CheckSecurityServices",
                    "args": {
                        "region": self.region,
                        "services": [
                            "guardduty",
                            "securityhub",
                            "inspector",
                            "accessanalyzer",
                            "macie",
                        ],
                        "debug": True,
                        "store_in_context": True,
                    },
                }
            )

        # Storage encryption queries
        if any(
            word in user_message_lower
            for word in [
                "s3",
                "encryption",
                "encrypted",
                "storage",
                "buckets",
                "ebs",
                "rds",
            ]
        ):
            tool_calls.append(
                {
                    "tool": "CheckStorageEncryption",
                    "args": {
                        "region": self.region,
                        "services": ["s3", "ebs", "rds", "dynamodb"],
                        "store_in_context": True,
                    },
                }
            )

        # Network security queries
        if any(
            word in user_message_lower
            for word in ["network", "https", "ssl", "tls", "load balancer", "transit"]
        ):
            tool_calls.append(
                {
                    "tool": "CheckNetworkSecurity",
                    "args": {
                        "region": self.region,
                        "services": ["elb", "apigateway", "cloudfront"],
                        "store_in_context": True,
                    },
                }
            )

        # Service discovery queries
        if any(
            word in user_message_lower
            for word in ["services", "resources", "inventory", "what am i using"]
        ):
            tool_calls.append(
                {
                    "tool": "ListServicesInRegion",
                    "args": {"region": self.region, "store_in_context": True},
                }
            )

        # Security findings queries
        if any(
            word in user_message_lower
            for word in ["findings", "alerts", "vulnerabilities", "issues"]
        ):
            tool_calls.append(
                {
                    "tool": "GetSecurityFindings",
                    "args": {
                        "region": self.region,
                        "service": "guardduty",
                        "max_findings": 10,
                    },
                }
            )

        # Comprehensive assessment queries
        if any(
            word in user_message_lower
            for word in [
                "security posture",
                "overall security",
                "comprehensive",
                "assessment",
                "audit",
            ]
        ):
            tool_calls = [
                {
                    "tool": "CheckSecurityServices",
                    "args": {
                        "region": self.region,
                        "services": [
                            "guardduty",
                            "securityhub",
                            "inspector",
                            "accessanalyzer",
                        ],
                        "store_in_context": True,
                    },
                },
                {
                    "tool": "CheckStorageEncryption",
                    "args": {
                        "region": self.region,
                        "services": ["s3", "ebs"],
                        "store_in_context": True,
                    },
                },
                {
                    "tool": "CheckNetworkSecurity",
                    "args": {
                        "region": self.region,
                        "services": ["elb", "apigateway"],
                        "store_in_context": True,
                    },
                },
            ]

        # Executive summary queries
        if any(
            word in user_message_lower
            for word in ["summary", "executive summary", "overview", "report"]
        ):
            # Generate executive summary from session responses
            if self.session_responses:
                return self.response_transformer.create_executive_summary(
                    [
                        {
                            "tool_name": resp["tool_name"],
                            "data": resp.get("raw_response", {}),
                        }
                        for resp in self.session_responses
                    ]
                )

        # Execute tool calls and collect transformed results
        tool_results = []
        for tool_call in tool_calls:
            logger.info(f"Processing tool call: {tool_call['tool']}")
            result = await self._call_mcp_tool(
                tool_name=tool_call["tool"],
                arguments=tool_call["args"],
                user_query=user_message,
            )
            if result:
                # The result is already transformed by _call_mcp_tool
                tool_results.append(result)

        # If multiple tools were called, add a separator
        if len(tool_results) > 1:
            separator = "\n" + "=" * 50 + "\n\n"
            return separator.join(tool_results)
        elif tool_results:
            return tool_results[0]
        else:
            return ""

    async def stream(self, user_query: str) -> AsyncGenerator[str, None]:
        """Stream enhanced response to user query with comprehensive security analysis"""
        try:
            logger.info(f"Processing enhanced security query: {user_query}")

            # First, get transformed security data using MCP tools
            security_data = await self._process_security_query(user_query)

            # Prepare the enhanced prompt with transformed security data
            if security_data:
                # If we have security data, provide it directly as it's already transformed
                enhanced_query = f"""User Query: {user_query}

## Comprehensive Security Assessment Results

{security_data}

Based on this detailed security assessment, please provide additional context, insights, and recommendations that would help the user understand and act on these findings. Focus on:

1. **Strategic Insights**: What do these findings mean for their overall security posture?
2. **Business Impact**: How do these security issues affect business operations and risk?
3. **Implementation Guidance**: Practical steps for implementing the recommendations
4. **Best Practices**: Additional Well-Architected Framework security best practices
5. **Monitoring & Maintenance**: How to maintain and monitor these security improvements

Keep your response concise and actionable, as the detailed technical assessment is already provided above."""

                # Stream the transformed security data first
                yield security_data + "\n\n"
                yield "---\n\n"
                yield "## 🧠 Strategic Analysis & Recommendations\n\n"

                # Then get Claude's strategic analysis
                async for chunk in super().stream(user_query=enhanced_query):
                    yield chunk
            else:
                # No specific security tools triggered, use general security knowledge
                enhanced_query = f"""User Query: {user_query}

As a Well-Architected Security Expert, please provide comprehensive guidance on this security-related query. Include:

1. **Direct Answer**: Address the specific question asked
2. **Security Best Practices**: Relevant AWS Well-Architected Framework security principles
3. **Implementation Guidance**: Practical steps and recommendations
4. **Risk Considerations**: Potential security risks and mitigation strategies
5. **Monitoring & Compliance**: How to maintain security posture over time

Use clear formatting with emojis and structured sections for better readability."""

                async for chunk in super().stream(user_query=enhanced_query):
                    yield chunk

        except Exception as e:
            logger.error(f"Error in enhanced security agent stream: {e}")
            error_message = f"""❌ **Error Processing Security Query**

**Error Details**: {str(e)}

**Troubleshooting Steps**:
1. Check AWS credentials and permissions
2. Verify MCP server connectivity
3. Ensure target AWS region is accessible
4. Review CloudWatch logs for detailed error information

**Alternative Actions**:
- Try a simpler security query to test connectivity
- Check the AWS console for manual security service status
- Contact your AWS administrator for permission verification
"""
            yield error_message

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available MCP security tools"""
        return self.mcp_tools

    def get_session_insights(self) -> Dict[str, Any]:
        """Get insights from the current session's security assessments"""
        if not self.session_responses:
            return {"message": "No security assessments performed in this session"}

        insights = {
            "total_assessments": len(self.session_responses),
            "tools_used": list(
                set(resp["tool_name"] for resp in self.session_responses)
            ),
            "assessment_timeline": [
                {
                    "tool": resp["tool_name"],
                    "timestamp": resp["timestamp"],
                    "summary": resp["transformed_response"][:100] + "..."
                    if len(resp["transformed_response"]) > 100
                    else resp["transformed_response"],
                }
                for resp in self.session_responses
            ],
        }

        return insights

    async def generate_comprehensive_report(self) -> str:
        """Generate a comprehensive security report from all session assessments"""
        if not self.session_responses:
            return "📋 **No Security Assessments Available**\n\nPerform security assessments to generate a comprehensive report."

        # Create executive summary
        executive_summary = self.response_transformer.create_executive_summary(
            [
                {"tool_name": resp["tool_name"], "data": resp.get("raw_response", {})}
                for resp in self.session_responses
            ]
        )

        # Add detailed findings
        detailed_report = executive_summary + "\n\n"
        detailed_report += "# 📋 Detailed Security Assessment Results\n\n"

        for i, response in enumerate(self.session_responses, 1):
            detailed_report += f"## Assessment {i}: {response['tool_name']}\n\n"
            detailed_report += response["transformed_response"] + "\n\n"
            detailed_report += "---\n\n"

        # Add recommendations summary
        detailed_report += "# 🎯 Consolidated Recommendations\n\n"
        detailed_report += "Based on all security assessments performed:\n\n"
        detailed_report += "## Immediate Actions (Critical Priority)\n"
        detailed_report += "- Review and address any critical security findings\n"
        detailed_report += "- Enable missing security services\n"
        detailed_report += "- Fix unencrypted storage resources\n\n"

        detailed_report += "## Short-term Improvements (High Priority)\n"
        detailed_report += "- Implement comprehensive monitoring and alerting\n"
        detailed_report += "- Establish security incident response procedures\n"
        detailed_report += "- Regular security assessment scheduling\n\n"

        detailed_report += "## Long-term Strategy (Medium Priority)\n"
        detailed_report += "- Implement Infrastructure as Code for security controls\n"
        detailed_report += "- Establish security governance and compliance frameworks\n"
        detailed_report += "- Regular Well-Architected Framework reviews\n\n"

        return detailed_report

    def clear_session_data(self):
        """Clear session response data"""
        self.session_responses = []
        logger.info("Session response data cleared")

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the security agent and MCP connection"""
        health_status = {
            "agent_status": "healthy",
            "mcp_connection": "unknown",
            "available_tools": len(self.mcp_tools),
            "session_responses": len(self.session_responses),
            "region": self.region,
        }

        try:
            # Test MCP connection
            if self.mcp_url and self.mcp_headers:
                # Try to list tools as a connectivity test
                await self._discover_mcp_tools()
                health_status["mcp_connection"] = "healthy"
            else:
                health_status["mcp_connection"] = "not_initialized"
        except Exception as e:
            health_status["mcp_connection"] = f"error: {str(e)}"
            health_status["agent_status"] = "degraded"

        return health_status
