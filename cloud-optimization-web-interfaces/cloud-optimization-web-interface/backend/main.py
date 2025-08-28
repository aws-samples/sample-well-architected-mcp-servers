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
Cloud Optimization MCP Web Interface - FastAPI Backend
Integrates AWS Bedrock with AgentCore MCP Server for cloud optimization assessments
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio
import uuid
import logging
import os
from datetime import datetime
from typing import Any
from pathlib import Path

# Load environment variables from .env file
def load_env_file():
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file()

from services.bedrock_chat_service import BedrockChatService
from services.bedrock_agent_service import BedrockAgentService
from services.mcp_client_service import MCPClientService
from services.auth_service import AuthService
from services.aws_config_service import AWSConfigService
from models.chat_models import ChatMessage, ChatSession, ToolExecution

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Cloud Optimization MCP Web Interface",
    description="Web interface for AWS cloud optimization assessments using Bedrock and MCP",
    version="1.0.0"
)

# CORS middleware - Allow local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "null"  # Allow file:// origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
auth_service = AuthService()

# Services
aws_config_service = AWSConfigService()

# Import the new LLM orchestrator service
from services.llm_orchestrator_service import LLMOrchestratorService

# Use LLM orchestrator as the primary service
orchestrator_service = LLMOrchestratorService()
logger.info("Using LLM Orchestrator service for intelligent tool routing")

# Keep legacy services for backward compatibility if needed
use_enhanced_agent = os.getenv('USE_ENHANCED_AGENT', 'false').lower() == 'true'
if use_enhanced_agent:
    bedrock_service = BedrockAgentService()
    logger.info("Enhanced Security Agent service available as fallback")
else:
    bedrock_service = None

mcp_service = MCPClientService(demo_mode=True)  # Keep for direct access if needed

# Connection manager for WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sessions: Dict[str, ChatSession] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.sessions[session_id] = ChatSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            messages=[],
            context={}
        )
        logger.info(f"WebSocket connected: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.sessions:
            del self.sessions[session_id]
        logger.info(f"WebSocket disconnected: {session_id}")

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(json.dumps(message, cls=DateTimeEncoder))

manager = ConnectionManager()

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}

class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_executions: List[ToolExecution] = []
    timestamp: datetime
    structured_data: Optional[Dict[str, Any]] = None
    human_summary: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, str]
    timestamp: datetime

class AWSConfigRequest(BaseModel):
    target_account_id: Optional[str] = None
    region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

class AWSConfigResponse(BaseModel):
    status: str
    message: str
    account_info: Optional[Dict[str, str]] = None
    role_arn: Optional[str] = None

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        user = await auth_service.verify_token(credentials.credentials)
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services_status = {
        "orchestrator": await orchestrator_service.health_check(),
        "mcp": await mcp_service.health_check(),
        "auth": "healthy"
    }
    
    # Add Enhanced Security Agent info if using it
    if use_enhanced_agent and bedrock_service and hasattr(bedrock_service, 'get_agent_info'):
        agent_info = bedrock_service.get_agent_info()
        services_status["enhanced_agent"] = "configured" if agent_info["configured"] else "not_configured"
    
    return HealthResponse(
        status="healthy" if all(s in ["healthy", "degraded"] for s in services_status.values()) else "unhealthy",
        services=services_status,
        timestamp=datetime.utcnow()
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    user = Depends(get_current_user)
):
    """REST endpoint for chat interactions"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        # Process the chat message
        response = await process_chat_message(
            message=request.message,
            session_id=session_id,
            context=request.context,
            user_id=user.get("user_id")
        )
        
        return response
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Verify authentication (you might want to implement WebSocket auth)
            # For now, we'll skip auth in WebSocket
            
            # Process the message
            response = await process_chat_message(
                message=message_data.get("message", ""),
                session_id=session_id,
                context=message_data.get("context", {}),
                user_id="websocket_user"  # You'd get this from auth
            )
            
            # Send response back
            await manager.send_message(session_id, {
                "type": "chat_response",
                "data": response.model_dump()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await manager.send_message(session_id, {
            "type": "error",
            "message": str(e)
        })
        manager.disconnect(session_id)

async def process_chat_message(
    message: str,
    session_id: str,
    context: Dict[str, Any],
    user_id: str
) -> ChatResponse:
    """Process a chat message through Bedrock and MCP integration"""
    
    # Get session
    session = manager.sessions.get(session_id)
    if not session:
        session = ChatSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            messages=[],
            context=context
        )
        manager.sessions[session_id] = session
    
    # Add user message to session
    user_message = ChatMessage(
        role="user",
        content=message,
        timestamp=datetime.utcnow()
    )
    session.messages.append(user_message)
    
    # Send typing indicator via WebSocket
    if session_id in manager.active_connections:
        await manager.send_message(session_id, {
            "type": "typing",
            "status": True
        })
    
    try:
        # Process with LLM Orchestrator
        bedrock_response = await orchestrator_service.process_message(
            message=message,
            session=session
        )
        
        # Add assistant response to session
        assistant_message = ChatMessage(
            role="assistant",
            content=bedrock_response.response,
            timestamp=datetime.utcnow(),
            tool_executions=bedrock_response.tool_executions
        )
        session.messages.append(assistant_message)
        
        # Stop typing indicator
        if session_id in manager.active_connections:
            await manager.send_message(session_id, {
                "type": "typing",
                "status": False
            })
        
        return ChatResponse(
            response=bedrock_response.response,
            session_id=session_id,
            tool_executions=bedrock_response.tool_executions,
            timestamp=datetime.utcnow(),
            structured_data=bedrock_response.structured_data,
            human_summary=bedrock_response.human_summary
        )
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        
        # Stop typing indicator
        if session_id in manager.active_connections:
            await manager.send_message(session_id, {
                "type": "typing",
                "status": False
            })
        
        raise e

@app.get("/api/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    user = Depends(get_current_user)
):
    """Get chat history for a session"""
    session = manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "messages": [msg.model_dump() for msg in session.messages],
        "created_at": session.created_at.isoformat()
    }

@app.get("/api/mcp/tools")
async def get_available_tools(user = Depends(get_current_user)):
    """Get list of available MCP tools"""
    try:
        tools = await mcp_service.get_available_tools()
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/{session_id}/info")
async def get_session_info(
    session_id: str,
    user = Depends(get_current_user)
):
    """Get session information including available tools"""
    session = manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        session_info = orchestrator_service.get_session_info(session)
        return session_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/{session_id}/initialize")
async def initialize_session(
    session_id: str,
    user = Depends(get_current_user)
):
    """Initialize session with tool discovery"""
    session = manager.sessions.get(session_id)
    if not session:
        # Create new session
        session = ChatSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            messages=[],
            context={}
        )
        manager.sessions[session_id] = session
    
    try:
        init_result = await orchestrator_service.initialize_session(session)
        return init_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/aws-config")
async def get_aws_config():
    """Get current AWS configuration"""
    try:
        config = await aws_config_service.get_current_config()
        return config
    except Exception as e:
        logger.error(f"Failed to get AWS config: {str(e)}")
        return {
            "account_id": None,
            "region": os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "role_arn": None,
            "status": "not_configured"
        }

@app.post("/api/aws-config", response_model=AWSConfigResponse)
async def update_aws_config(request: AWSConfigRequest):
    """Update AWS configuration"""
    try:
        # Update the configuration
        result = await aws_config_service.update_config(
            target_account_id=request.target_account_id,
            region=request.region,
            aws_access_key_id=request.aws_access_key_id,
            aws_secret_access_key=request.aws_secret_access_key
        )
        
        return AWSConfigResponse(
            status="success",
            message="AWS configuration updated successfully",
            account_info=result.get("account_info"),
            role_arn=result.get("role_arn")
        )
        
    except Exception as e:
        logger.error(f"Failed to update AWS config: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to update AWS configuration: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)