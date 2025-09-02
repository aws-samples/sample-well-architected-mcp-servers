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
Agent Task for Well-Architected Security Agent
Integrates with Bedrock AgentCore and MCP Security Server
"""

import logging

from bedrock_agentcore.memory import MemoryClient

from .context import SecurityAgentContext
from .memory_hook_provider import MemoryHook
from .security_agent import SecurityAgent
from .utils import get_ssm_parameter

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory_client = MemoryClient()


async def agent_task(user_message: str, session_id: str, actor_id: str):
    """
    Main agent task for processing security-related queries
    """
    agent = SecurityAgentContext.get_agent_ctx()
    response_queue = SecurityAgentContext.get_response_queue_ctx()
    gateway_access_token = SecurityAgentContext.get_gateway_token_ctx()

    if not gateway_access_token:
        raise RuntimeError("Gateway Access token is none")

    try:
        if agent is None:
            # Initialize memory hook
            memory_hook = MemoryHook(
                memory_client=memory_client,
                memory_id=get_ssm_parameter("/app/security/agentcore/memory_id"),
                actor_id=actor_id,
                session_id=session_id,
            )

            # Create Security Agent with Claude 3.5 Sonnet
            agent = SecurityAgent(
                bearer_token=gateway_access_token,
                memory_hook=memory_hook,
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",  # Claude 3.7 Sonnet
                region="us-east-1",
                tools=[],  # MCP tools are handled internally
            )

            SecurityAgentContext.set_agent_ctx(agent)
            logger.info(
                "✅ Security Agent initialized with Claude 3.5 Sonnet and MCP integration"
            )

        # Stream response with security tool integration
        async for chunk in agent.stream(user_query=user_message):
            await response_queue.put(chunk)

    except Exception as e:
        logger.exception("Security Agent execution failed.")
        error_message = f"❌ Security assessment error: {str(e)}\n\n💡 Please try rephrasing your security question or contact support if the issue persists."
        await response_queue.put(error_message)
    finally:
        await response_queue.finish()
