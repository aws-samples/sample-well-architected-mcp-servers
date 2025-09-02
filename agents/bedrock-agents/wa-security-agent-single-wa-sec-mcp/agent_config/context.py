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
Context management for Security Agent
"""

from contextvars import ContextVar
from typing import Optional

from bedrock_agentcore.queue import ResponseQueue

from .security_agent import SecurityAgent


class SecurityAgentContext:
    """Context manager for Security Agent state"""

    _agent_ctx: ContextVar[Optional[SecurityAgent]] = ContextVar(
        "agent_ctx", default=None
    )
    _response_queue_ctx: ContextVar[Optional[ResponseQueue]] = ContextVar(
        "response_queue_ctx", default=None
    )
    _gateway_token_ctx: ContextVar[Optional[str]] = ContextVar(
        "gateway_token_ctx", default=None
    )

    @classmethod
    def get_agent_ctx(cls) -> Optional[SecurityAgent]:
        return cls._agent_ctx.get()

    @classmethod
    def set_agent_ctx(cls, agent: SecurityAgent):
        cls._agent_ctx.set(agent)

    @classmethod
    def get_response_queue_ctx(cls) -> Optional[ResponseQueue]:
        return cls._response_queue_ctx.get()

    @classmethod
    def set_response_queue_ctx(cls, response_queue: ResponseQueue):
        cls._response_queue_ctx.set(response_queue)

    @classmethod
    def get_gateway_token_ctx(cls) -> Optional[str]:
        return cls._gateway_token_ctx.get()

    @classmethod
    def set_gateway_token_ctx(cls, gateway_token: str):
        cls._gateway_token_ctx.set(gateway_token)
