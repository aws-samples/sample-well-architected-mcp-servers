# MIT No Attribution
"""
Chat Models - Pydantic models for chat functionality
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

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
    timestamp: datetime
    tool_executions: List[ToolExecution] = []

class ChatSession(BaseModel):
    session_id: str
    created_at: datetime
    messages: List[ChatMessage]
    context: Dict[str, Any] = {}

class BedrockResponse(BaseModel):
    response: str
    tool_executions: List[ToolExecution] = []
    structured_data: Optional[Dict[str, Any]] = None
    human_summary: Optional[str] = None
    timestamp: datetime = None
    model_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)