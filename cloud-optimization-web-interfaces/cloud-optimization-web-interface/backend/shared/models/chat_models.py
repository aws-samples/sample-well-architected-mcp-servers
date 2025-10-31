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

# MIT No Attribution
"""
Chat Models - Pydantic models for chat functionality
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class ToolExecution(BaseModel):
    tool_name: str
    parameters: Dict[str, Any] = {}
    result: Any = None
    timestamp: datetime
    status: ToolExecutionStatus = ToolExecutionStatus.SUCCESS
    error_message: Optional[str] = None
    # Additional fields used in bedrock_agent_service
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = None
    tool_executions: List[ToolExecution] = []
    
    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


class ChatSession(BaseModel):
    session_id: str
    created_at: datetime
    messages: List[ChatMessage]
    context: Dict[str, Any] = {}


class ChatRequest(BaseModel):
    """Request model for chat endpoints."""
    message: str = Field(..., min_length=1, description="The user message")
    session_id: str = Field(default="default", description="Session identifier")
    agent_id: Optional[str] = Field(default=None, description="Specific agent to use")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Response model for chat endpoints."""
    response: str
    session_id: str
    response_type: str
    tool_executions: List[ToolExecution] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = None
    
    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)


class BedrockResponse(BaseModel):
    response: str
    tool_executions: List[ToolExecution] = []
    structured_data: Optional[Dict[str, Any]] = None
    human_summary: Optional[str] = None
    timestamp: datetime = None
    model_id: Optional[str] = None
    session_id: Optional[str] = None

    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.utcnow()
        super().__init__(**data)
