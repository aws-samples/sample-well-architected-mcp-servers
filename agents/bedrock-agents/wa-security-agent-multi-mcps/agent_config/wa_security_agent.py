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
Enhanced Security Agent with AWS Knowledge Integration
Combines Claude 3.7 Sonnet with:
- Well-Architected Security MCP Server (real-time AWS security data)
- AWS Knowledge MCP Server (AWS documentation and best practices)
- AWS API MCP Server (awslabs.aws-api-mcp-server)
"""

import asyncio
import json
import boto3
from datetime import timedelta
from typing import AsyncGenerator, List, Dict, Any, Optional
from bedrock_agentcore.agent import Agent
from bedrock_agentcore.memory import MemoryHook
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import logging

from .response_transformer import SecurityResponseTransformer

logger = logging.getLogger(__name__)


# AWS API MCP Server Configuration
# AWS_API_MCP_CONFIG = {
#     "agent_arn": "arn:aws:bedrock-agentcore:us-east-1:384612698411:runtime/aws_api_mcp_server-TOJa8h9Ywj",
#     "region": "us-east-1",
#     "bearer_token": "eyJraWQiOiI1MFBlMDVkaW0rcEdnYmJLcmhadlwvdzdhaEdiaW9uRlVXVVVtKzBNa2IzWT0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJiNDA4NjQ1OC0xMDExLTcwNTAtMDM2Ni0yMTdlYWNjOTgwNjciLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAudXMtZWFzdC0xLmFtYXpvbmF3cy5jb21cL3VzLWVhc3QtMV8yTDJ5MG9mNGMiLCJjbGllbnRfaWQiOiI0NW50OGVxNnJsbHRnN2Fjb3VpYjltNzllaiIsIm9yaWdpbl9qdGkiOiJiMGMwYTY2Ni1mOTAxLTRkNjAtODc1My04M2ExNGQ1ZTJmZWMiLCJldmVudF9pZCI6IjkxMDgyNWVhLTYwODktNGM4ZC1iNmJiLWJmYTRhM2E5NTIzNCIsInRva2VuX3VzZSI6ImFjY2VzcyIsInNjb3BlIjoiYXdzLmNvZ25pdG8uc2lnbmluLnVzZXIuYWRtaW4iLCJhdXRoX3RpbWUiOjE3NTYyNzcxNTcsImV4cCI6MTc1NjI4MDc1NywiaWF0IjoxNzU2Mjc3MTU3LCJqdGkiOiIwODM3YTcxNi1jZWZhLTRjYmItYTY2MC1lMGU3ODZkZDYyM2YiLCJ1c2VybmFtZSI6ImI0MDg2NDU4LTEwMTEtNzA1MC0wMzY2LTIxN2VhY2M5ODA2NyJ9.zMOIbmis90g6R4OY3PLZmgAyPUx-2GqwHUE1Zzbt0pc3m4PW5WLUNa37bHv5esbLWiBVBuj_XV4WUeG8BOzKF3HLAnGwleaPSaR5b0qsP5_Jb_9WhF10u8z_6Sr-QEi6Fr2b8L6XcA7SV4nO_dHr2gqOIMluLXn-rM79Tz0yIO4fJ3q8xL1HQ4exrL3eE9SovxH9whZdz9Dkgh5pUfbj7N34YYyEbnCsoMV1P5r-zM1QYq8KD6tGo8HJcihrS_y3PzmQXbJ1NWfAvs1XyBTmThJNpt_2Gl3yOQ7QkKLEaafdBUJFscoAyjeSFm0Pv9ZC2_qL7XlWyF0VEG3kfoQD6w",
#     "user_pool_id": "us-east-1_2L2y0of4c",
#     "client_id": "45nt8eq6rlltg7acouib9m79ej"
# }


class EnhancedSecurityAgent(Agent):
    """
    Enhanced Security Agent with AWS Knowledge Integration
    Combines real-time security assessments with AWS documentation and best practices
    """

    def __init__(
        self,
        bearer_token: str,
        memory_hook: MemoryHook,
        model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        region: str = "us-east-1",
        **kwargs,
    ):
        """Initialize the Enhanced Security Agent with AWS Knowledge integration"""
        super().__init__(
            bearer_token=bearer_token,
            memory_hook=memory_hook,
            model_id=model_id,
            **kwargs,
        )

        self.region = region
        self.mcp_connections = {}
        self.all_tools = []

        # Initialize response transformer
        self.response_transformer = SecurityResponseTransformer()

        # Store responses for comprehensive analysis
        self.session_responses = []

        # Initialize MCP connections
        asyncio.create_task(self._initialize_all_mcp_connections())

    async def _initialize_all_mcp_connections(self):
        """Initialize connections to all MCP servers"""
        try:
            logger.info("Initializing connections to all MCP servers...")

            # Initialize Security MCP Server (AgentCore runtime)
            await self._initialize_security_mcp()

            # Initialize AWS Knowledge MCP Server (direct connection)
            await self._initialize_aws_knowledge_mcp()

            logger.info(
                f"✅ All MCP connections initialized with {len(self.all_tools)} total tools"
            )

        except Exception as e:
            logger.error(f"Failed to initialize MCP connections: {e}")

    async def _initialize_security_mcp(self):
        """Initialize connection to the Well-Architected Security MCP Server"""
        try:
            logger.info("Initializing Security MCP connection...")

            # Get MCP server credentials from AgentCore deployment
            ssm_client = boto3.client("ssm", region_name=self.region)
            secrets_client = boto3.client("secretsmanager", region_name=self.region)

            # Get AgentCore Runtime (WA SEC MCP Server)
            agent_arn_response = ssm_client.get_parameter(
                Name="/coa/mcp/wa_security_mcp/runtime/agent_arn"
            )
            agent_arn = agent_arn_response["Parameter"]["Value"]

            # Get bearer token
            response = secrets_client.get_secret_value(
                SecretId="/coa/mcp/wa_security_mcp/cognito/credentials"
            )
            secret_value = response["SecretString"]
            parsed_secret = json.loads(secret_value)
            bearer_token = parsed_secret["bearer_token"]

            # Build MCP connection details
            encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
            mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            mcp_headers = {
                "authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            }

            # Store connection details
            self.mcp_connections["security"] = {
                "url": mcp_url,
                "headers": mcp_headers,
                "tools": [],
                "type": "agentcore",
            }

            # Discover tools
            await self._discover_mcp_tools("security")

            logger.info(
                f"✅ Security MCP initialized with {len(self.mcp_connections['security']['tools'])} tools"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Security MCP: {e}")
            # Create empty connection to prevent errors
            self.mcp_connections["security"] = {
                "url": None,
                "headers": None,
                "tools": [],
                "type": "agentcore",
            }

    async def _initialize_aws_knowledge_mcp(self):
        """Initialize connection to the AWS Knowledge MCP Server (public server)"""
        try:
            logger.info("Initializing AWS Knowledge MCP connection...")

            # AWS Knowledge MCP Server runs as a public service
            # We'll use the MCP tools available in this environment
            self.mcp_connections["aws_knowledge"] = {
                "tools": [
                    {
                        "name": "search_documentation",
                        "description": "Search AWS documentation for relevant information",
                        "mcp_server": "aws_knowledge",
                    },
                    {
                        "name": "read_documentation",
                        "description": "Read specific AWS documentation pages",
                        "mcp_server": "aws_knowledge",
                    },
                    {
                        "name": "recommend",
                        "description": "Get content recommendations for AWS documentation",
                        "mcp_server": "aws_knowledge",
                    },
                ],
                "type": "direct",
            }

            self.all_tools.extend(self.mcp_connections["aws_knowledge"]["tools"])

            logger.info(
                f"✅ AWS Knowledge MCP initialized with {len(self.mcp_connections['aws_knowledge']['tools'])} tools"
            )

        except Exception as e:
            logger.error(f"Failed to initialize AWS Knowledge MCP: {e}")

    async def _discover_mcp_tools(self, mcp_name: str):
        """Discover available MCP tools for a specific MCP server"""
        try:
            connection = self.mcp_connections[mcp_name]

            if connection["type"] == "agentcore" and connection["url"]:
                async with streamablehttp_client(
                    connection["url"],
                    connection["headers"],
                    timeout=timedelta(seconds=60),
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
                                "mcp_server": mcp_name,
                            }
                            for tool in tool_result.tools
                        ]

                        connection["tools"] = tools
                        self.all_tools.extend(tools)

        except Exception as e:
            logger.error(f"Failed to discover tools for {mcp_name}: {e}")
            self.mcp_connections[mcp_name]["tools"] = []

    async def _call_security_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Optional[str]:
        """Call a tool on the Security MCP Server (AgentCore runtime)"""
        try:
            connection = self.mcp_connections["security"]

            if not connection["url"]:
                return "Security MCP Server not available"

            async with streamablehttp_client(
                connection["url"], connection["headers"], timeout=timedelta(seconds=120)
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        name=tool_name, arguments=arguments
                    )
                    raw_response = result.content[0].text

                    # Transform the response for human readability
                    transformed_response = self.response_transformer.transform_response(
                        tool_name=tool_name, raw_response=raw_response, user_query=""
                    )

                    return transformed_response

        except Exception as e:
            logger.error(f"Failed to call Security MCP tool {tool_name}: {e}")
            return f"Error calling {tool_name}: {str(e)}"

    async def _call_aws_knowledge_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Optional[str]:
        """Call a tool on the AWS Knowledge MCP Server (direct integration)"""
        try:
            logger.info(f"Calling AWS Knowledge tool: {tool_name}")

            if tool_name == "search_documentation":
                # Use the available AWS Knowledge MCP tools
                from mcp_aws_knowledge_mcp_server_aws___search_documentation import (
                    mcp_aws_knowledge_mcp_server_aws___search_documentation,
                )

                result = mcp_aws_knowledge_mcp_server_aws___search_documentation(
                    **arguments
                )
                return self._format_documentation_search_result(result)

            elif tool_name == "read_documentation":
                from mcp_aws_knowledge_mcp_server_aws___read_documentation import (
                    mcp_aws_knowledge_mcp_server_aws___read_documentation,
                )

                result = mcp_aws_knowledge_mcp_server_aws___read_documentation(
                    **arguments
                )
                return self._format_documentation_content(result)

            elif tool_name == "recommend":
                from mcp_aws_knowledge_mcp_server_aws___recommend import (
                    mcp_aws_knowledge_mcp_server_aws___recommend,
                )

                result = mcp_aws_knowledge_mcp_server_aws___recommend(**arguments)
                return self._format_documentation_recommendations(result)

            return "AWS Knowledge tool not available"

        except Exception as e:
            logger.error(f"Failed to call AWS Knowledge tool {tool_name}: {e}")
            return f"Error accessing AWS documentation: {str(e)}"

    def _format_documentation_search_result(self, result: Dict) -> str:
        """Format AWS documentation search results"""
        if not result or "response" not in result:
            return "No documentation found"

        content = result["response"]["payload"]["content"]["result"]
        if not content:
            return "No relevant documentation found"

        formatted = "📚 **AWS Documentation Search Results**\n\n"

        for i, doc in enumerate(content[:5], 1):  # Show top 5 results
            formatted += f"**{i}. {doc['title']}**\n"
            formatted += f"🔗 {doc['url']}\n"
            if doc.get("context"):
                formatted += f"📝 {doc['context']}\n"
            formatted += "\n"

        return formatted

    def _format_documentation_content(self, result: str) -> str:
        """Format AWS documentation content"""
        if not result:
            return "No documentation content available"

        # Truncate very long content
        if len(result) > 2000:
            result = result[:2000] + "\n\n... (content truncated for readability)"

        return f"📖 **AWS Documentation Content**\n\n{result}"

    def _format_documentation_recommendations(self, result: Dict) -> str:
        """Format AWS documentation recommendations"""
        if not result:
            return "No recommendations available"

        return f"💡 **Related AWS Documentation**\n\n{json.dumps(result, indent=2)}"

    def _get_system_prompt(self) -> str:
        """Get the enhanced system prompt with AWS Knowledge integration"""
        security_tools = [
            tool for tool in self.all_tools if tool["mcp_server"] == "security"
        ]
        knowledge_tools = [
            tool for tool in self.all_tools if tool["mcp_server"] == "aws_knowledge"
        ]

        security_tools_desc = "\n".join(
            [f"- {tool['name']}: {tool['description']}" for tool in security_tools]
        )

        knowledge_tools_desc = "\n".join(
            [f"- {tool['name']}: {tool['description']}" for tool in knowledge_tools]
        )

        return f"""You are an Enhanced AWS Security Expert with access to both real-time security data and comprehensive AWS documentation.

Your role is to provide the most comprehensive security guidance by combining:
1. **Real-time AWS security assessments** from your Security MCP Server
2. **Authoritative AWS documentation and best practices** from the AWS Knowledge MCP Server

## Available Tools:

### 🛡️ Security Assessment Tools (Real-time Data):
{security_tools_desc}

### 📚 AWS Knowledge Tools (Documentation & Best Practices):
{knowledge_tools_desc}

## Enhanced Capabilities:

### 1. **Comprehensive Security Analysis**
- Real-time security data + AWS best practice documentation
- Context-aware recommendations with official AWS guidance
- Risk assessment with authoritative remediation steps

### 2. **Intelligent Response Enhancement**
- Visual formatting with emojis and structured layouts
- Risk-based prioritization with AWS Well-Architected alignment
- Executive summaries with business impact analysis
- Actionable recommendations with official AWS documentation links

### 3. **Knowledge-Augmented Recommendations**
- Every security finding includes relevant AWS documentation
- Best practice recommendations backed by official AWS guidance
- Implementation steps with links to detailed AWS documentation
- Compliance mapping with AWS security frameworks

## How to Provide Enhanced Responses:

### For Security Assessments:
1. **Gather Real-time Data**: Use Security MCP tools to get current AWS security status
2. **Enhance with Knowledge**: Search AWS documentation for relevant best practices
3. **Synthesize Insights**: Combine real-time findings with authoritative guidance
4. **Provide Actionable Recommendations**: Include both immediate fixes and long-term improvements

### For Security Questions:
1. **Search AWS Documentation**: Find official AWS guidance on the topic
2. **Validate with Real-time Data**: Check current implementation against best practices
3. **Provide Comprehensive Answer**: Combine theoretical knowledge with practical assessment

## Example Enhanced Workflows:

### Security Service Status Check:
1. Call `CheckSecurityServices` to get current status
2. Search AWS documentation for security service best practices
3. Compare current state with AWS recommendations
4. Provide enhanced report with documentation links

### Storage Encryption Analysis:
1. Call `CheckStorageEncryption` to assess current encryption
2. Search for AWS encryption best practices documentation
3. Identify gaps and provide remediation steps with official guidance
4. Include links to relevant AWS documentation

### Security Findings Review:
1. Call `GetSecurityFindings` to get current security issues
2. For each finding, search for relevant AWS security documentation
3. Provide context-rich explanations with official remediation guidance
4. Include preventive measures from AWS best practices

## Response Style Guidelines:
- **Knowledge-Rich**: Always include relevant AWS documentation context
- **Authoritative**: Back recommendations with official AWS guidance
- **Actionable**: Provide specific steps with documentation links
- **Visual**: Use formatting, emojis, and structure for readability
- **Comprehensive**: Address both immediate issues and long-term security posture
- **Well-Architected Focused**: Align all recommendations with AWS Well-Architected Framework

## Key Enhancement: Knowledge Integration
Every response is enhanced with:
- 📚 Relevant AWS documentation and best practices
- 🔗 Direct links to official AWS guidance
- 📋 Step-by-step implementation guides from AWS docs
- 🎯 Context-aware recommendations based on AWS expertise
- 💡 Proactive suggestions from AWS security frameworks
- 🔄 Continuous learning from AWS knowledge base

Remember: You're not just a security assessment tool - you're a comprehensive AWS security advisor that combines real-time data with the full depth of AWS knowledge and best practices."""

    async def _determine_enhanced_strategy(
        self, user_message: str
    ) -> List[Dict[str, Any]]:
        """Determine which tools to call for enhanced security analysis"""
        user_message_lower = user_message.lower()
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
            # Get real-time data
            tool_calls.append(
                {
                    "tool": "CheckSecurityServices",
                    "mcp_server": "security",
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
            # Get AWS documentation
            tool_calls.append(
                {
                    "tool": "search_documentation",
                    "mcp_server": "aws_knowledge",
                    "args": {
                        "search_phrase": "security services GuardDuty Security Hub Inspector best practices",
                        "limit": 3,
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
            # Get real-time encryption data
            tool_calls.append(
                {
                    "tool": "CheckStorageEncryption",
                    "mcp_server": "security",
                    "args": {
                        "region": self.region,
                        "services": ["s3", "ebs", "rds", "dynamodb"],
                        "store_in_context": True,
                    },
                }
            )
            # Get AWS encryption best practices
            tool_calls.append(
                {
                    "tool": "search_documentation",
                    "mcp_server": "aws_knowledge",
                    "args": {
                        "search_phrase": "S3 encryption EBS encryption RDS encryption best practices",
                        "limit": 3,
                    },
                }
            )

        # Network security queries
        if any(
            word in user_message_lower
            for word in ["network", "https", "ssl", "tls", "load balancer", "transit"]
        ):
            # Get real-time network security data
            tool_calls.append(
                {
                    "tool": "CheckNetworkSecurity",
                    "mcp_server": "security",
                    "args": {
                        "region": self.region,
                        "services": ["elb", "apigateway", "cloudfront"],
                        "store_in_context": True,
                    },
                }
            )
            # Get AWS network security documentation
            tool_calls.append(
                {
                    "tool": "search_documentation",
                    "mcp_server": "aws_knowledge",
                    "args": {
                        "search_phrase": "network security HTTPS SSL TLS load balancer best practices",
                        "limit": 3,
                    },
                }
            )

        # Security findings queries
        if any(
            word in user_message_lower
            for word in ["findings", "alerts", "vulnerabilities", "issues"]
        ):
            # Get real-time findings
            tool_calls.append(
                {
                    "tool": "GetSecurityFindings",
                    "mcp_server": "security",
                    "args": {
                        "region": self.region,
                        "service": "guardduty",
                        "max_findings": 10,
                    },
                }
            )
            # Get AWS security incident response documentation
            tool_calls.append(
                {
                    "tool": "search_documentation",
                    "mcp_server": "aws_knowledge",
                    "args": {
                        "search_phrase": "security incident response vulnerability management",
                        "limit": 3,
                    },
                }
            )

        # Comprehensive security assessment
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
            # Get comprehensive real-time data
            tool_calls.extend(
                [
                    {
                        "tool": "CheckSecurityServices",
                        "mcp_server": "security",
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
                        "mcp_server": "security",
                        "args": {
                            "region": self.region,
                            "services": ["s3", "ebs"],
                            "store_in_context": True,
                        },
                    },
                ]
            )
            # Get comprehensive AWS security documentation
            tool_calls.append(
                {
                    "tool": "search_documentation",
                    "mcp_server": "aws_knowledge",
                    "args": {
                        "search_phrase": "AWS Well-Architected security pillar comprehensive assessment",
                        "limit": 5,
                    },
                }
            )

        # Best practices queries
        if any(
            word in user_message_lower
            for word in ["best practices", "recommendations", "guidance", "how to"]
        ):
            # Search for relevant AWS documentation
            tool_calls.append(
                {
                    "tool": "search_documentation",
                    "mcp_server": "aws_knowledge",
                    "args": {
                        "search_phrase": f"security best practices {user_message}",
                        "limit": 5,
                    },
                }
            )

        return tool_calls

    async def stream(self, user_query: str) -> AsyncGenerator[str, None]:
        """Stream enhanced response with both real-time data and AWS knowledge"""
        try:
            logger.info(
                f"Processing enhanced security query with AWS knowledge: {user_query}"
            )

            # Determine enhanced strategy
            tool_calls = await self._determine_enhanced_strategy(user_query)

            # Execute tool calls
            security_results = []
            knowledge_results = []

            for tool_call in tool_calls:
                if tool_call["mcp_server"] == "security":
                    result = await self._call_security_mcp_tool(
                        tool_name=tool_call["tool"], arguments=tool_call["args"]
                    )
                    if result:
                        security_results.append(
                            {"tool": tool_call["tool"], "result": result}
                        )

                elif tool_call["mcp_server"] == "aws_knowledge":
                    result = await self._call_aws_knowledge_tool(
                        tool_name=tool_call["tool"], arguments=tool_call["args"]
                    )
                    if result:
                        knowledge_results.append(
                            {"tool": tool_call["tool"], "result": result}
                        )

            # Stream results
            if security_results or knowledge_results:
                yield "# 🔍 Enhanced Security Analysis\n\n"

                # Stream security assessment results first
                if security_results:
                    yield "## 🛡️ Real-Time Security Assessment\n\n"
                    for result in security_results:
                        yield f"### {result['tool']}\n\n"
                        yield result["result"] + "\n\n"

                # Stream AWS knowledge results
                if knowledge_results:
                    yield "## 📚 AWS Official Guidance & Best Practices\n\n"
                    for result in knowledge_results:
                        yield f"### {result['tool']}\n\n"
                        yield result["result"] + "\n\n"

                # Generate enhanced analysis
                yield "---\n\n"
                yield "## 🧠 Enhanced Analysis & Strategic Recommendations\n\n"

                # Prepare enhanced query for Claude
                security_data = "\n".join([r["result"] for r in security_results])
                knowledge_data = "\n".join([r["result"] for r in knowledge_results])

                enhanced_query = f"""User Query: {user_query}

## Real-Time Security Assessment Data:
{security_data}

## AWS Official Documentation & Best Practices:
{knowledge_data}

Based on this comprehensive information combining real-time security data with official AWS guidance, provide:

1. **Integrated Analysis**: How does the current security posture align with AWS best practices?
2. **Gap Analysis**: What specific gaps exist between current state and AWS recommendations?
3. **Prioritized Action Plan**: What should be addressed first based on risk and AWS guidance?
4. **Implementation Roadmap**: Step-by-step plan with AWS documentation references
5. **Long-term Strategy**: How to maintain and improve security posture over time

Focus on actionable insights that combine the real-time assessment with authoritative AWS guidance."""

                # Stream Claude's enhanced analysis
                async for chunk in super().stream(user_query=enhanced_query):
                    yield chunk
            else:
                # No specific tools triggered, provide general guidance with AWS knowledge
                enhanced_query = f"""User Query: {user_query}

As an Enhanced AWS Security Expert with access to both real-time security assessment tools and comprehensive AWS documentation, provide guidance that includes:

1. **Direct Answer**: Address the specific security question
2. **AWS Best Practices**: Reference official AWS Well-Architected Framework principles
3. **Real-time Assessment Options**: Suggest which security tools could provide current data
4. **Documentation References**: Include relevant AWS documentation for deeper learning
5. **Implementation Guidance**: Practical steps with AWS best practice alignment

Use the AWS Knowledge MCP Server to search for relevant documentation if needed, and suggest specific security assessment tools that could provide real-time insights."""

                async for chunk in super().stream(user_query=enhanced_query):
                    yield chunk

        except Exception as e:
            logger.error(f"Error in enhanced security agent stream: {e}")
            error_message = f"""❌ **Error Processing Enhanced Security Query**

**Error Details**: {str(e)}

**Available Capabilities**:
- Security MCP Server: {len(self.mcp_connections.get("security", {}).get("tools", []))} tools
- AWS Knowledge MCP Server: {len(self.mcp_connections.get("aws_knowledge", {}).get("tools", []))} tools

**Troubleshooting Steps**:
1. Check AWS credentials and permissions
2. Verify MCP server connectivity
3. Ensure AWS Knowledge MCP Server is accessible
4. Review CloudWatch logs for detailed error information
"""
            yield error_message

    def get_available_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get list of available tools grouped by MCP server"""
        return {
            mcp_name: connection["tools"]
            for mcp_name, connection in self.mcp_connections.items()
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of all MCP connections"""
        health_status = {
            "agent_status": "healthy",
            "mcp_connections": {},
            "total_tools": len(self.all_tools),
            "region": self.region,
        }

        # Check Security MCP
        try:
            if self.mcp_connections["security"]["url"]:
                await self._discover_mcp_tools("security")
                health_status["mcp_connections"]["security"] = {
                    "status": "healthy",
                    "tools_count": len(self.mcp_connections["security"]["tools"]),
                    "type": "agentcore",
                }
            else:
                health_status["mcp_connections"]["security"] = {
                    "status": "not_configured",
                    "tools_count": 0,
                    "type": "agentcore",
                }
        except Exception as e:
            health_status["mcp_connections"]["security"] = {
                "status": f"error: {str(e)}",
                "tools_count": 0,
                "type": "agentcore",
            }
            health_status["agent_status"] = "degraded"

        # Check AWS Knowledge MCP
        try:
            # Test AWS Knowledge MCP by trying a simple search
            result = await self._call_aws_knowledge_tool(
                "search_documentation", {"search_phrase": "AWS security", "limit": 1}
            )
            if result and "Error" not in result:
                health_status["mcp_connections"]["aws_knowledge"] = {
                    "status": "healthy",
                    "tools_count": len(self.mcp_connections["aws_knowledge"]["tools"]),
                    "type": "direct",
                }
            else:
                health_status["mcp_connections"]["aws_knowledge"] = {
                    "status": "error: test search failed",
                    "tools_count": len(self.mcp_connections["aws_knowledge"]["tools"]),
                    "type": "direct",
                }
        except Exception as e:
            health_status["mcp_connections"]["aws_knowledge"] = {
                "status": f"error: {str(e)}",
                "tools_count": 0,
                "type": "direct",
            }
            health_status["agent_status"] = "degraded"

        return health_status
