"""
Simplified main.py for the Cloud Optimization Assistant backend.
Single entry point with essential services only.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .models.data_models import ChatMessage, QueryRoute, RouteType
from .models.exceptions import COABaseException, BedrockCommunicationError
from .services.agent_manager import AgentManager
from .services.bedrock_service import BedrockService
from .services.query_router import QueryRouter
from .services.session_manager import SessionManager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Cloud Optimization Assistant",
    description="Simplified backend for AWS cloud optimization and security analysis",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
agent_manager: Optional[AgentManager] = None
bedrock_service: Optional[BedrockService] = None
query_router: Optional[QueryRouter] = None
session_manager: Optional[SessionManager] = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending WebSocket message to {session_id}: {e}")
                self.disconnect(session_id)

manager = ConnectionManager()


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    streaming: bool = False


class ChatResponse(BaseModel):
    response: str
    session_id: str
    metadata: Dict
    success: bool = True


class AgentSelectRequest(BaseModel):
    agent_id: str
    session_id: str


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global agent_manager, bedrock_service, query_router, session_manager
    
    try:
        logger.info("Initializing Cloud Optimization Assistant backend...")
        
        # Get AWS region from environment
        region = os.getenv("AWS_REGION", "us-east-1")
        
        # Initialize core services
        agent_manager = AgentManager(region=region)
        bedrock_service = BedrockService(region=region)
        query_router = QueryRouter(agent_manager)
        session_manager = SessionManager()
        
        # Perform initial agent discovery
        await agent_manager.discover_agents()
        
        logger.info("Backend initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize backend: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Cloud Optimization Assistant backend...")
    
    # Cleanup sessions
    if session_manager:
        session_manager.cleanup_expired_sessions()
    
    logger.info("Backend shutdown completed")


# Dependency injection
async def get_services():
    """Dependency to ensure services are initialized."""
    if not all([agent_manager, bedrock_service, query_router, session_manager]):
        raise HTTPException(status_code=503, detail="Services not initialized")
    return {
        "agent_manager": agent_manager,
        "bedrock_service": bedrock_service,
        "query_router": query_router,
        "session_manager": session_manager
    }


# API Endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint with service status."""
    try:
        services = await get_services()
        
        # Check Bedrock service health
        bedrock_health = await services["bedrock_service"].health_check()
        
        # Get agent manager stats
        agent_stats = await services["agent_manager"].get_agent_status_summary()
        
        # Get session stats
        session_stats = services["session_manager"].get_session_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "bedrock": bedrock_health,
                "agents": {
                    "total_agents": agent_stats.get("total_agents", 0),
                    "healthy_agents": agent_stats.get("healthy_agents", 0),
                    "status": "healthy" if agent_stats.get("healthy_agents", 0) > 0 else "degraded"
                },
                "sessions": {
                    "active_sessions": session_stats.get("active_sessions", 0),
                    "total_sessions": session_stats.get("total_sessions", 0),
                    "status": "healthy"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.get("/api/agents")
async def list_agents(services: dict = Depends(get_services)):
    """List all available agents."""
    try:
        response = await services["agent_manager"].list_agents()
        return {
            "success": response.success,
            "agents": response.data.get("agents", []),
            "total_count": response.data.get("total_count", 0)
        }
        
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/select")
async def select_agent(
    request: AgentSelectRequest,
    services: dict = Depends(get_services)
):
    """Select an agent for a session."""
    try:
        response = services["agent_manager"].select_agent_for_session(
            request.session_id, 
            request.agent_id
        )
        
        return {
            "success": response.success,
            "message": response.message,
            "data": response.data
        }
        
    except Exception as e:
        logger.error(f"Error selecting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat_endpoint(
    request: ChatRequest,
    services: dict = Depends(get_services)
):
    """Process chat messages with intelligent routing."""
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get or create session
        session = services["session_manager"].get_session(session_id)
        if not session:
            session = services["session_manager"].create_session(session_id)
        
        # Add user message to session
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=datetime.utcnow()
        )
        services["session_manager"].add_message(session_id, user_message)
        
        # Get conversation history
        conversation_history = services["session_manager"].get_conversation_history(
            session_id, limit=10
        )
        
        # Route the query
        route = await services["query_router"].route_query(
            request.message, 
            session_id, 
            conversation_history
        )
        
        # Process based on route type
        if route.route_type == RouteType.AGENT and route.target == "command_processor":
            # Handle agent commands
            command_response = await services["query_router"].process_agent_command(
                request.message, session_id
            )
            
            response_content = command_response.message
            metadata = {
                "route_type": "command",
                "command_type": command_response.command_type,
                "success": command_response.success
            }
            
        elif route.route_type == RouteType.AGENT:
            # Route to agent
            response_content, metadata = await process_agent_query(
                route.target, session_id, request.message, conversation_history, services
            )
            
        else:
            # Route to model
            response_content, metadata = await process_model_query(
                route.target, request.message, conversation_history, services
            )
        
        # Add assistant response to session
        assistant_message = ChatMessage(
            role="assistant",
            content=response_content,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        services["session_manager"].add_message(session_id, assistant_message)
        
        return ChatResponse(
            response=response_content,
            session_id=session_id,
            metadata=metadata,
            success=True
        )
        
    except COABaseException as e:
        logger.error(f"COA error in chat endpoint: {e}")
        return ChatResponse(
            response=f"I encountered an error: {e.message}",
            session_id=request.session_id or "unknown",
            metadata={"error": e.to_dict()},
            success=False
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_model_query(
    model_id: str,
    query: str,
    conversation_history: List[ChatMessage],
    services: dict
) -> tuple[str, dict]:
    """Process query using Bedrock model."""
    try:
        # Invoke model
        response = await services["bedrock_service"].invoke_model(
            model_id=model_id,
            messages=conversation_history + [ChatMessage(role="user", content=query)],
            max_tokens=4096,
            temperature=0.1,
            streaming=False
        )
        
        # Format response
        formatted_response = services["bedrock_service"].format_response(response, "model")
        
        return formatted_response["content"], formatted_response["metadata"]
        
    except Exception as e:
        logger.error(f"Error processing model query: {e}")
        raise BedrockCommunicationError(
            f"Failed to process query with model {model_id}: {e}",
            service_type="model",
            target_id=model_id
        )


async def process_agent_query(
    agent_id: str,
    session_id: str,
    query: str,
    conversation_history: List[ChatMessage],
    services: dict
) -> tuple[str, dict]:
    """Process query using Bedrock agent."""
    try:
        # Get agent info
        agent_info = await services["agent_manager"].get_agent_info(agent_id)
        if not agent_info:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        # For now, we'll use a placeholder agent alias ID
        # In production, this would be retrieved from agent metadata
        agent_alias_id = "TSTALIASID"
        
        # Invoke agent
        response = await services["bedrock_service"].invoke_agent(
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            session_id=session_id,
            input_text=query,
            streaming=False
        )
        
        # Format response
        formatted_response = services["bedrock_service"].format_response(response, "agent")
        
        return formatted_response["content"], formatted_response["metadata"]
        
    except Exception as e:
        logger.error(f"Error processing agent query: {e}")
        raise BedrockCommunicationError(
            f"Failed to process query with agent {agent_id}: {e}",
            service_type="agent",
            target_id=agent_id
        )


# WebSocket endpoint for real-time chat
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat."""
    await manager.connect(websocket, session_id)
    
    try:
        services = await get_services()
        
        # Get or create session
        session = services["session_manager"].get_session(session_id)
        if not session:
            session = services["session_manager"].create_session(session_id)
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            query = message_data.get("message", "")
            if not query:
                continue
            
            try:
                # Add user message to session
                user_message = ChatMessage(
                    role="user",
                    content=query,
                    timestamp=datetime.utcnow()
                )
                services["session_manager"].add_message(session_id, user_message)
                
                # Get conversation history
                conversation_history = services["session_manager"].get_conversation_history(
                    session_id, limit=10
                )
                
                # Route the query
                route = await services["query_router"].route_query(
                    query, session_id, conversation_history
                )
                
                # Send routing info to client
                await manager.send_message(session_id, {
                    "type": "routing",
                    "route_type": route.route_type.value,
                    "target": route.target,
                    "reasoning": route.reasoning
                })
                
                # Process query and send response
                if route.route_type == RouteType.AGENT and route.target == "command_processor":
                    # Handle agent commands
                    command_response = await services["query_router"].process_agent_command(
                        query, session_id
                    )
                    
                    await manager.send_message(session_id, {
                        "type": "response",
                        "content": command_response.message,
                        "metadata": {
                            "command_type": command_response.command_type,
                            "success": command_response.success
                        }
                    })
                    
                elif route.route_type == RouteType.AGENT:
                    # Route to agent
                    response_content, metadata = await process_agent_query(
                        route.target, session_id, query, conversation_history, services
                    )
                    
                    await manager.send_message(session_id, {
                        "type": "response",
                        "content": response_content,
                        "metadata": metadata
                    })
                    
                else:
                    # Route to model
                    response_content, metadata = await process_model_query(
                        route.target, query, conversation_history, services
                    )
                    
                    await manager.send_message(session_id, {
                        "type": "response",
                        "content": response_content,
                        "metadata": metadata
                    })
                
                # Add assistant response to session
                assistant_message = ChatMessage(
                    role="assistant",
                    content=response_content,
                    timestamp=datetime.utcnow()
                )
                services["session_manager"].add_message(session_id, assistant_message)
                
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await manager.send_message(session_id, {
                    "type": "error",
                    "error": str(e)
                })
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(session_id)


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main_simplified:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )