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

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models.chat_models import ChatMessage, ChatSession, ToolExecution
from pydantic import BaseModel
from services.auth_service import AuthService
from services.aws_config_service import AWSConfigService
from services.enhanced_bedrock_agent_service import EnhancedBedrockAgentService

# Import configuration service
from services.config_service import config_service, get_config

# Import the new LLM orchestrator service
from services.llm_orchestrator_service import LLMOrchestratorService

# Import StrandsAgent orchestrator service
from services.strands_llm_orchestrator_service import StrandsLLMOrchestratorService


# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Startup validation function
async def validate_startup_requirements():
    """Validate SSM access and agent configuration during startup"""
    logger.info("Starting backend service initialization...")

    # Validate SSM connectivity
    try:
        ssm_status = config_service.get_ssm_status()
        if ssm_status["available"]:
            logger.info("✓ SSM Parameter Store connectivity verified")

            # Test retrieving a configuration parameter
            test_config = config_service.get_all_config()
            logger.info(
                f"✓ Retrieved {len(test_config)} configuration parameters from SSM"
            )

            # Validate agent configuration
            agent_id = config_service.get_config_value("ENHANCED_SECURITY_AGENT_ID")
            agent_alias_id = config_service.get_config_value(
                "ENHANCED_SECURITY_AGENT_ALIAS_ID"
            )

            if agent_id and agent_alias_id:
                logger.info("✓ Enhanced Security Agent configuration found")
                logger.info(f"  Agent ID: {agent_id}")
                logger.info(f"  Agent Alias ID: {agent_alias_id}")
            else:
                logger.warning("⚠ Enhanced Security Agent configuration incomplete")
                logger.warning("  Some agent parameters missing from SSM")
        else:
            logger.warning(
                "⚠ SSM Parameter Store not available - using environment variables"
            )

    except Exception as e:
        logger.error(f"✗ SSM validation failed: {e}")
        logger.info("Falling back to environment variables")

    # Validate AWS credentials and permissions
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        # Test basic AWS connectivity
        sts_client = boto3.client("sts")
        identity = sts_client.get_caller_identity()
        logger.info(f"✓ AWS credentials valid - Account: {identity.get('Account')}")

        # Test SSM permissions specifically
        ssm_client = boto3.client("ssm")
        ssm_client.describe_parameters(MaxResults=1)
        logger.info("✓ SSM permissions verified")

    except NoCredentialsError:
        logger.error("✗ AWS credentials not found")
        logger.error(
            "  Please configure AWS credentials via environment variables, IAM role, or AWS CLI"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDenied":
            logger.error("✗ Insufficient AWS permissions for SSM access")
            logger.error(
                "  Please ensure the IAM role/user has ssm:GetParameter and ssm:DescribeParameters permissions"
            )
        else:
            logger.error(f"✗ AWS connectivity error: {e}")
    except Exception as e:
        logger.error(f"✗ Unexpected AWS validation error: {e}")

    # Validate Bedrock access
    try:
        bedrock_region = config_service.get_config_value("BEDROCK_REGION", "us-east-1")
        bedrock_client = boto3.client("bedrock-runtime", region_name=bedrock_region)

        # Test if we can list foundation models (basic connectivity test)
        bedrock_client = boto3.client("bedrock", region_name=bedrock_region)
        models = bedrock_client.list_foundation_models(byOutputModality="TEXT")
        logger.info(f"✓ Bedrock connectivity verified in {bedrock_region}")
        logger.info(f"  Foundation models available: {len(models['modelSummaries'])}")

    except Exception as e:
        logger.warning(f"⚠ Bedrock validation failed: {e}")
        logger.warning("  Bedrock functionality may be limited")

    logger.info("Backend service initialization complete")


app = FastAPI(
    title="Cloud Optimization MCP Web Interface",
    description="Web interface for AWS cloud optimization assessments using Bedrock and MCP",
    version="1.0.0",
)


# Add startup event handler
@app.on_event("startup")
async def startup_event():
    """Run startup validation when the application starts"""
    await validate_startup_requirements()


# CORS middleware - Allow local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "null",  # Allow file:// origins
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



# Determine which orchestrator to use based on configuration
use_strands_orchestrator = get_config("USE_STRANDS_ORCHESTRATOR", "true").lower() == "true"

if use_strands_orchestrator:
    orchestrator_service = StrandsLLMOrchestratorService()
    logger.info("Using StrandsAgent LLM Orchestrator service for AgentCore runtime integration")
else:
    orchestrator_service = LLMOrchestratorService()
    logger.info("Using standard LLM Orchestrator service for intelligent tool routing")

# Initialize Enhanced Bedrock Agent Service (supports both Bedrock Agent and AgentCore)
bedrock_service = EnhancedBedrockAgentService()
logger.info("Enhanced Bedrock Agent Service initialized with dual runtime support")

# MCP tools are now accessed through agents and dynamic MCP service


# Connection manager for WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sessions: Dict[str, ChatSession] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.sessions[session_id] = ChatSession(
            session_id=session_id, created_at=datetime.utcnow(), messages=[], context={}
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
            await self.active_connections[session_id].send_text(
                json.dumps(message, cls=DateTimeEncoder)
            )


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


class MCPServerInfo(BaseModel):
    name: str
    display_name: str
    agent_id: Optional[str] = None
    agent_arn: Optional[str] = None
    region: Optional[str] = None
    deployment_type: Optional[str] = None
    package_name: Optional[str] = None
    capabilities: List[str] = []
    capabilities_count: int = 0
    description: str = ""
    status: str = "unknown"
    framework: str = "unknown"
    available_tools: Optional[List[str]] = None
    tools_count: Optional[int] = None
    supported_services: Optional[List[str]] = None


class MCPServersResponse(BaseModel):
    total_servers: int
    servers: List[MCPServerInfo]
    timestamp: str
    source: str = "ssm_parameter_store"


class MCPToolInfo(BaseModel):
    name: str
    description: str = ""
    parameters: Dict[str, Any] = {}
    server_name: str
    server_display_name: str
    category: str
    status: str = "available"


class MCPToolsResponse(BaseModel):
    total_tools: int
    tools: List[MCPToolInfo]
    tools_by_server: Dict[str, Any] = {}
    tools_by_category: Dict[str, List[MCPToolInfo]] = {}
    servers_count: int = 0
    categories_count: int = 0
    timestamp: str


# Authentication dependency
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        user = await auth_service.verify_token(credentials.credentials)
        return user
    except Exception:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services_status = {
        "orchestrator": await orchestrator_service.health_check(),
        "auth": "healthy",
    }

    # Add Enhanced Bedrock Agent Service status
    if bedrock_service:
        services_status["bedrock_agents"] = await bedrock_service.health_check()

    return HealthResponse(
        status="healthy"
        if all(s in ["healthy", "degraded"] for s in services_status.values())
        else "unhealthy",
        services=services_status,
        timestamp=datetime.utcnow(),
    )


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check endpoint with MCP server breakdown"""
    try:
        # Get basic service status
        services_status = {
            "orchestrator": await orchestrator_service.health_check(),
            "dynamic_mcp": await dynamic_mcp_service.health_check(),
            "auth": "healthy",
        }
        
        # Get detailed MCP information
        dynamic_mcp_details = dynamic_mcp_service.get_detailed_health()
        orchestrator_details = orchestrator_service.get_detailed_health()
        
        # Get agent information from Enhanced Bedrock Agent Service
        agent_info = None
        if bedrock_service:
            try:
                agent_info = bedrock_service.get_agent_summary()
            except Exception as e:
                agent_info = {"error": str(e)}
        
        overall_status = "healthy"
        if services_status["mcp"] == "degraded" or services_status["orchestrator"] == "degraded":
            overall_status = "degraded"
        elif any(status == "unhealthy" for status in services_status.values()):
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "services": services_status,
            "dynamic_mcp_details": dynamic_mcp_details,
            "orchestrator_details": orchestrator_details,
            "agent_info": agent_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/agents/status")
async def get_agents_status():
    """Get basic agent status without authentication (for development/monitoring)"""
    try:
        # Check if using StrandsAgent orchestrator
        if isinstance(orchestrator_service, StrandsLLMOrchestratorService):
            # Get StrandsAgent status
            service_summary = orchestrator_service.strands_discovery.get_service_summary()
            
            return {
                "orchestrator_type": "strands_specialized",
                "total_agents": service_summary["total_agents"],
                "healthy_agents": service_summary["healthy_agents"],
                "total_tools": service_summary["total_tools"],
                "discovery_time": service_summary["last_discovery"],
                "cache_ttl_seconds": service_summary["cache_ttl_seconds"],
                "agents": service_summary["agents"]
            }
        
        # Fallback to standard Bedrock agent service
        elif bedrock_service:
            agents = bedrock_service.get_available_agents()
            
            # Return basic info without sensitive details
            agent_summary = {}
            for agent_type, agent in agents.items():
                agent_summary[agent_type] = {
                    "status": agent.status,
                    "framework": agent.framework,
                    "capabilities_count": len(agent.capabilities),
                    "has_endpoint": bool(agent.endpoint_url)
                }
            
            return {
                "orchestrator_type": "standard",
                "total_agents": len(agents),
                "discovery_time": bedrock_service.agents_discovered_at.isoformat() if bedrock_service.agents_discovered_at else None,
                "agents": agent_summary,
                "cache_ttl_seconds": bedrock_service.discovery_cache_ttl
            }
        else:
            return {"error": "No agent service available"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/mcp/status")
async def get_mcp_status():
    """Get detailed MCP server status without authentication (for development/monitoring)"""
    try:
        # Get orchestrator MCP status
        orchestrator_health = await orchestrator_service.health_check()
        
        return {
            "orchestrator_status": orchestrator_health,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/mcp/servers", response_model=MCPServersResponse)
async def list_mcp_servers():
    """List all available MCP servers integrated with the agent"""
    try:
        # Get MCP servers from SSM Parameter Store
        import boto3
        ssm_client = boto3.client("ssm")
        
        # Get all MCP server connection info parameters
        response = ssm_client.get_parameters_by_path(
            Path="/coa/components",
            Recursive=True
        )
        
        # Filter for connection_info parameters
        connection_info_params = [
            param for param in response.get('Parameters', [])
            if param['Name'].endswith('/connection_info')
        ]
        
        mcp_servers = []
        for param in connection_info_params:
            try:
                # Parse the connection info
                connection_info = json.loads(param['Value'])
                
                # Extract server name from parameter path
                # /coa/components/wa_security_mcp/connection_info -> wa_security_mcp
                path_parts = param['Name'].split('/')
                server_name = path_parts[-2] if len(path_parts) >= 3 else "unknown"
                
                # Create server info
                server_info = {
                    "name": server_name,
                    "display_name": server_name.replace('_', ' ').title(),
                    "agent_id": connection_info.get("agent_id"),
                    "agent_arn": connection_info.get("agent_arn"),
                    "region": connection_info.get("region"),
                    "deployment_type": connection_info.get("deployment_type"),
                    "package_name": connection_info.get("package_name"),
                    "capabilities": connection_info.get("capabilities", []),
                    "capabilities_count": len(connection_info.get("capabilities", [])),
                    "description": connection_info.get("description", f"{server_name} MCP server"),
                    "status": "deployed",  # Since it's in Parameter Store, it's deployed
                    "framework": "agentcore_runtime"
                }
                
                # Add additional metadata if available
                if "available_tools" in connection_info:
                    server_info["available_tools"] = connection_info["available_tools"]
                    server_info["tools_count"] = len(connection_info["available_tools"])
                
                if "supported_services" in connection_info:
                    server_info["supported_services"] = connection_info["supported_services"]
                
                mcp_servers.append(server_info)
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse connection info for {param['Name']}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error processing MCP server {param['Name']}: {e}")
                continue
        
        # Sort servers by name for consistent ordering
        mcp_servers.sort(key=lambda x: x["name"])
        
        return {
            "total_servers": len(mcp_servers),
            "servers": mcp_servers,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "ssm_parameter_store"
        }
        
    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        return {
            "error": str(e),
            "total_servers": 0,
            "servers": [],
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/mcp/tools", response_model=MCPToolsResponse)
async def list_mcp_tools():
    """List all available tools integrated with the agent"""
    try:
        # Get available tools from agents via dynamic MCP service
        available_tools = []
        
        # Get tools from all discovered agents
        agents = bedrock_service.get_available_agents()
        for agent_type, agent_info in agents.items():
            try:
                agent_tools = await dynamic_mcp_service.load_agent_tools(agent_type, agent_info.metadata)
                for tool_key, tool_data in agent_tools.items():
                    available_tools.append({
                        "name": tool_data["name"],
                        "description": tool_data["description"],
                        "parameters": tool_data.get("inputSchema", {}),
                        "agent_type": agent_type,
                        "server": tool_data["server"]
                    })
            except Exception as e:
                logger.warning(f"Failed to load tools for agent {agent_type}: {e}")
                continue
        
        # Enhance tool information with server mapping
        enhanced_tools = []
        
        # Process tools from agents
        for tool in available_tools:
            tool_name = tool.get("name", "")
            server_name = tool.get("server", "unknown")
            
            enhanced_tool = {
                "name": tool_name,
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
                "server_name": server_name,
                "server_display_name": server_name.replace('_', ' ').title(),
                "category": _get_tool_category(tool_name),
                "status": "available",
                "agent_type": tool.get("agent_type", "unknown")
            }
            
            enhanced_tools.append(enhanced_tool)
        
        # Group tools by server for better organization
        tools_by_server = {}
        for tool in enhanced_tools:
            server_name = tool["server_name"]
            if server_name not in tools_by_server:
                tools_by_server[server_name] = {
                    "server_name": server_name,
                    "server_display_name": tool["server_display_name"],
                    "tools": [],
                    "tools_count": 0
                }
            tools_by_server[server_name]["tools"].append(tool)
            tools_by_server[server_name]["tools_count"] += 1
        
        # Group tools by category
        tools_by_category = {}
        for tool in enhanced_tools:
            category = tool["category"]
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append(tool)
        
        return {
            "total_tools": len(enhanced_tools),
            "tools": enhanced_tools,
            "tools_by_server": tools_by_server,
            "tools_by_category": tools_by_category,
            "servers_count": len(tools_by_server),
            "categories_count": len(tools_by_category),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}")
        return {
            "error": str(e),
            "total_tools": 0,
            "tools": [],
            "tools_by_server": {},
            "tools_by_category": {},
            "timestamp": datetime.utcnow().isoformat()
        }


def _get_tool_category(tool_name: str) -> str:
    """Categorize tools based on their name and functionality"""
    tool_name_lower = tool_name.lower()
    
    if any(keyword in tool_name_lower for keyword in ["security", "check", "findings", "encryption", "network"]):
        return "security"
    elif any(keyword in tool_name_lower for keyword in ["cost", "usage", "rightsizing", "savings", "budget"]):
        return "cost_optimization"
    elif any(keyword in tool_name_lower for keyword in ["service", "region", "list", "discover"]):
        return "discovery"
    elif any(keyword in tool_name_lower for keyword in ["storage", "encryption"]):
        return "storage"
    elif any(keyword in tool_name_lower for keyword in ["network", "vpc", "elb"]):
        return "networking"
    else:
        return "general"


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    """REST endpoint for chat interactions"""
    try:
        session_id = request.session_id or str(uuid.uuid4())

        # Process the chat message
        response = await process_chat_message(
            message=request.message,
            session_id=session_id,
            context=request.context,
            user_id=user.get("user_id"),
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
                user_id="websocket_user",  # You'd get this from auth
            )

            # Send response back
            await manager.send_message(
                session_id, {"type": "chat_response", "data": response.model_dump()}
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await manager.send_message(session_id, {"type": "error", "message": str(e)})
        manager.disconnect(session_id)


async def process_chat_message(
    message: str, session_id: str, context: Dict[str, Any], user_id: str
) -> ChatResponse:
    """Process a chat message through Bedrock and MCP integration"""

    # Get session
    session = manager.sessions.get(session_id)
    if not session:
        session = ChatSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            messages=[],
            context=context,
        )
        manager.sessions[session_id] = session

    # Add user message to session
    user_message = ChatMessage(
        role="user", content=message, timestamp=datetime.utcnow()
    )
    session.messages.append(user_message)

    # Send typing indicator via WebSocket
    if session_id in manager.active_connections:
        await manager.send_message(session_id, {"type": "typing", "status": True})

    # Check if a specific agent is selected for this session
    selected_agent_id = agent_selection_manager.get_selected_agent(session_id)
    if selected_agent_id:
        logger.info(f"Using selected agent: {selected_agent_id} for session: {session_id}")
        # Add selected agent to session context
        session.context["selected_agent"] = selected_agent_id

    try:
        # Process with LLM Orchestrator
        bedrock_response = await orchestrator_service.process_message(
            message=message, session=session
        )

        # Add assistant response to session
        assistant_message = ChatMessage(
            role="assistant",
            content=bedrock_response.response,
            timestamp=datetime.utcnow(),
            tool_executions=bedrock_response.tool_executions,
        )
        session.messages.append(assistant_message)

        # Stop typing indicator
        if session_id in manager.active_connections:
            await manager.send_message(session_id, {"type": "typing", "status": False})

        return ChatResponse(
            response=bedrock_response.response,
            session_id=session_id,
            tool_executions=bedrock_response.tool_executions,
            timestamp=datetime.utcnow(),
            structured_data=bedrock_response.structured_data,
            human_summary=bedrock_response.human_summary,
        )

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

        # Stop typing indicator
        if session_id in manager.active_connections:
            await manager.send_message(session_id, {"type": "typing", "status": False})

        raise e


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str, user=Depends(get_current_user)):
    """Get chat history for a session"""
    session = manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "messages": [msg.model_dump() for msg in session.messages],
        "created_at": session.created_at.isoformat(),
    }


@app.get("/api/mcp/tools")
async def get_available_tools(user=Depends(get_current_user)):
    """Get list of available MCP tools through agents"""
    try:
        # Get tools from all agents via orchestrator
        tools = await orchestrator_service.get_available_tools()
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{session_id}/info")
async def get_session_info(session_id: str, user=Depends(get_current_user)):
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
async def initialize_session(session_id: str, user=Depends(get_current_user)):
    """Initialize session with tool discovery"""
    session = manager.sessions.get(session_id)
    if not session:
        # Create new session
        session = ChatSession(
            session_id=session_id, created_at=datetime.utcnow(), messages=[], context={}
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
            "status": "not_configured",
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
            aws_secret_access_key=request.aws_secret_access_key,
        )

        return AWSConfigResponse(
            status="success",
            message="AWS configuration updated successfully",
            account_info=result.get("account_info"),
            role_arn=result.get("role_arn"),
        )

    except Exception as e:
        logger.error(f"Failed to update AWS config: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update AWS configuration: {str(e)}"
        )


@app.get("/api/config")
async def get_all_config(user=Depends(get_current_user)):
    """Get all application configuration (excluding sensitive values)"""
    try:
        config = config_service.get_all_config()

        # Filter out sensitive values for API response
        safe_config = {}
        sensitive_keys = [
            "AWS_BEARER_TOKEN_BEDROCK",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_ACCESS_KEY_ID",
        ]

        for key, value in config.items():
            if key in sensitive_keys:
                safe_config[key] = "***" if value else None
            else:
                safe_config[key] = value

        return {"config": safe_config, "ssm_status": config_service.get_ssm_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/refresh")
async def refresh_config(user=Depends(get_current_user)):
    """Refresh configuration cache from SSM"""
    try:
        config_service.refresh_cache()
        return {"status": "success", "message": "Configuration cache refreshed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/ssm/parameters")
async def list_ssm_parameters(user=Depends(get_current_user)):
    """List all SSM parameters for this application"""
    try:
        result = config_service.list_ssm_parameters()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents")
async def get_available_agents(user=Depends(get_current_user)):
    """Get information about all available agents"""
    try:
        if bedrock_service:
            agent_info = bedrock_service.get_agent_info()
            return agent_info
        else:
            return {"error": "Bedrock agent service not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/refresh")
async def refresh_agents(user=Depends(get_current_user)):
    """Force refresh of agent discovery"""
    try:
        if bedrock_service:
            agent_info = bedrock_service.refresh_agents()
            return {
                "status": "success",
                "message": "Agents refreshed",
                "agents": agent_info,
            }
        else:
            return {"error": "Bedrock agent service not available"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/enhanced")
async def get_enhanced_agents(user=Depends(get_current_user)):
    """Get information about all available agents from enhanced service"""
    try:
        agents = bedrock_service.get_available_agents()
        summary = bedrock_service.get_agent_summary()
        
        return {
            "status": "success",
            "summary": summary,
            "agents": {
                agent_type: {
                    "agent_id": agent.agent_id,
                    "agent_alias_id": agent.agent_alias_id,
                    "runtime_type": agent.runtime_type.value,
                    "status": agent.status,
                    "framework": agent.framework,
                    "capabilities": agent.capabilities,
                    "model_id": agent.model_id,
                    "endpoint_url": agent.endpoint_url,
                    "health_check_url": agent.health_check_url,
                    "agent_arn": agent.agent_arn
                }
                for agent_type, agent in agents.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/enhanced/runtime-types")
async def get_runtime_types(user=Depends(get_current_user)):
    """Get agents grouped by runtime type"""
    try:
        from services.enhanced_bedrock_agent_service import AgentType
        
        bedrock_agents = bedrock_service.get_agents_by_runtime_type(AgentType.BEDROCK_AGENT)
        agentcore_agents = bedrock_service.get_agents_by_runtime_type(AgentType.BEDROCK_AGENTCORE)
        
        return {
            "status": "success",
            "runtime_types": {
                "bedrock-agent": {
                    "count": len(bedrock_agents),
                    "agents": [
                        {
                            "agent_type": agent.agent_type,
                            "agent_id": agent.agent_id,
                            "status": agent.status,
                            "capabilities": agent.capabilities
                        }
                        for agent in bedrock_agents
                    ]
                },
                "bedrock-agentcore": {
                    "count": len(agentcore_agents),
                    "agents": [
                        {
                            "agent_type": agent.agent_type,
                            "agent_id": agent.agent_id,
                            "status": agent.status,
                            "capabilities": agent.capabilities,
                            "endpoint_url": agent.endpoint_url
                        }
                        for agent in agentcore_agents
                    ]
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/enhanced/refresh")
async def refresh_enhanced_agents(user=Depends(get_current_user)):
    """Force refresh of enhanced agent discovery"""
    try:
        bedrock_service._discover_agents()
        summary = bedrock_service.get_agent_summary()
        
        return {
            "status": "success",
            "message": "Enhanced agents refreshed",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/enhanced")
async def enhanced_chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    """Enhanced chat endpoint using the dual runtime service"""
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        session = manager.sessions.get(session_id)
        
        if not session:
            session = ChatSession(
                session_id=session_id,
                created_at=datetime.utcnow(),
                messages=[],
                context={}
            )
            manager.sessions[session_id] = session

        # Add user message to session
        user_message = ChatMessage(
            role="user",
            content=request.message,
            timestamp=datetime.utcnow()
        )
        session.messages.append(user_message)

        # Process message with enhanced service
        response = await bedrock_service.process_message(
            message=request.message,
            session=session,
            agent_type=request.agent_type if hasattr(request, 'agent_type') else None
        )

        # Add assistant response to session
        assistant_message = ChatMessage(
            role="assistant",
            content=response.response,
            timestamp=datetime.utcnow(),
            tool_executions=response.tool_executions
        )
        session.messages.append(assistant_message)

        return {
            "response": response.response,
            "session_id": session_id,
            "model_id": response.model_id,
            "tool_executions": [
                {
                    "tool_name": te.tool_name,
                    "tool_input": te.tool_input,
                    "tool_output": te.tool_output,
                    "status": te.status.value,
                    "timestamp": te.timestamp.isoformat()
                }
                for te in response.tool_executions
            ] if response.tool_executions else []
        }

    except Exception as e:
        logger.error(f"Enhanced chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Agent selection state management
class AgentSelectionManager:
    def __init__(self):
        self.selected_agents = {}  # session_id -> agent_type mapping
        
    def select_agent(self, session_id: str, agent_type: str) -> bool:
        """Select an agent for a session"""
        # Validate agent exists
        if bedrock_service:
            available_agents = bedrock_service.get_available_agents()
            if agent_type not in available_agents:
                return False
        
        self.selected_agents[session_id] = agent_type
        return True
    
    def get_selected_agent(self, session_id: str) -> Optional[str]:
        """Get selected agent for a session"""
        return self.selected_agents.get(session_id)
    
    def clear_selection(self, session_id: str):
        """Clear agent selection for a session"""
        if session_id in self.selected_agents:
            del self.selected_agents[session_id]

# Global agent selection manager
agent_selection_manager = AgentSelectionManager()


# Agent management endpoints (no authentication for local testing)
@app.get("/agents")
async def list_agents():
    """List all available agents (no authentication required for local testing)"""
    try:
        if not bedrock_service:
            return {
                "error": "Bedrock agent service not available",
                "agents": []
            }
        
        agents = bedrock_service.get_available_agents()
        
        # Format agents for display
        formatted_agents = []
        for agent_type, agent_info in agents.items():
            formatted_agents.append({
                "id": agent_type,
                "name": _format_agent_name(agent_type),
                "description": _get_agent_description(agent_type),
                "status": agent_info.status,
                "framework": agent_info.framework,
                "capabilities": agent_info.capabilities,
                "agent_id": agent_info.agent_id,
                "agent_alias_id": agent_info.agent_alias_id
            })
        
        return {
            "agents": formatted_agents,
            "total": len(formatted_agents),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        return {
            "error": str(e),
            "agents": []
        }


@app.post("/agents/select/{agent_id}")
async def select_agent(agent_id: str, session_id: str = "default"):
    """Select an agent for subsequent chat messages"""
    try:
        # Validate agent exists
        if not bedrock_service:
            raise HTTPException(status_code=503, detail="Bedrock agent service not available")
        
        agents = bedrock_service.get_available_agents()
        if agent_id not in agents:
            available_ids = list(agents.keys())
            raise HTTPException(
                status_code=404, 
                detail=f"Agent '{agent_id}' not found. Available agents: {available_ids}"
            )
        
        # Select the agent
        success = agent_selection_manager.select_agent(session_id, agent_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to select agent")
        
        agent_info = agents[agent_id]
        
        return {
            "status": "success",
            "message": f"Selected agent: {_format_agent_name(agent_id)}",
            "selected_agent": {
                "id": agent_id,
                "name": _format_agent_name(agent_id),
                "description": _get_agent_description(agent_id),
                "status": agent_info.status,
                "framework": agent_info.framework,
                "agent_id": agent_info.agent_id
            },
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/selected")
async def get_selected_agent(session_id: str = "default"):
    """Get the currently selected agent for a session"""
    try:
        selected_agent_id = agent_selection_manager.get_selected_agent(session_id)
        
        if not selected_agent_id:
            return {
                "selected_agent": None,
                "message": "No agent selected for this session"
            }
        
        # Get agent details
        if bedrock_service:
            agents = bedrock_service.get_available_agents()
            if selected_agent_id in agents:
                agent_info = agents[selected_agent_id]
                return {
                    "selected_agent": {
                        "id": selected_agent_id,
                        "name": _format_agent_name(selected_agent_id),
                        "description": _get_agent_description(selected_agent_id),
                        "status": agent_info.status,
                        "framework": agent_info.framework,
                        "agent_id": agent_info.agent_id
                    },
                    "session_id": session_id
                }
        
        # Agent no longer exists, clear selection
        agent_selection_manager.clear_selection(session_id)
        return {
            "selected_agent": None,
            "message": "Previously selected agent no longer available"
        }
        
    except Exception as e:
        logger.error(f"Error getting selected agent: {e}")
        return {
            "error": str(e),
            "selected_agent": None
        }


@app.delete("/agents/selected")
async def clear_agent_selection(session_id: str = "default"):
    """Clear agent selection for a session"""
    try:
        agent_selection_manager.clear_selection(session_id)
        return {
            "status": "success",
            "message": "Agent selection cleared",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error clearing agent selection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Local testing endpoints (no authentication required)
@app.post("/api/chat/local")
async def local_chat_endpoint(request: ChatRequest):
    """Local chat endpoint without authentication for testing"""
    try:
        session_id = request.session_id or "local-test-session"

        # Process the chat message
        response = await process_chat_message(
            message=request.message,
            session_id=session_id,
            context=request.context or {},
            user_id="local-test-user",
        )

        return response
    except Exception as e:
        logger.error(f"Local chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _format_agent_name(agent_type: str) -> str:
    """Convert agent type to human-readable name"""
    return agent_type.replace('_', ' ').replace('-', ' ').title().replace('Wa ', 'WA ').replace('Mcp', 'MCP')


def _get_agent_description(agent_type: str) -> str:
    """Get description for an agent type"""
    descriptions = {
        'wa-security-agent': 'AWS security analysis and Well-Architected security pillar assessments',
        'strands_aws_wa_sec_cost': 'Dual-domain specialist for AWS security and cost optimization analysis',
        'wa_cost_agent': 'Cost optimization and financial analysis',
        'wa_reliability_agent': 'Reliability assessments and resilience analysis',
        'multi_agent_supervisor': 'Coordinating multiple specialized agents for comprehensive analysis'
    }
    return descriptions.get(agent_type, 'Cloud optimization and analysis specialist')


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
