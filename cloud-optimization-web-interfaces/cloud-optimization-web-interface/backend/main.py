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

import asyncio
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

# Import AgentCore services
from services.agent_registry_service import AgentRegistryService
from services.agentcore_discovery_service import AgentCoreDiscoveryService
from services.agentcore_invocation_service import AgentCoreInvocationService
from services.command_manager import CommandManager
from services.agent_unregistration_service import AgentUnregistrationService

# Import Runtime Orchestrator Service
from services.runtime_orchestrator_service import RuntimeOrchestratorService

# Import Parameter Manager
from utils.parameter_manager import initialize_parameter_manager, ParameterManagerError

# Import Configuration Validation Service
from services.config_validation_service import initialize_validation_service, ConfigValidationError


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

    # Initialize Parameter Manager with dynamic prefix
    try:
        param_prefix = os.getenv('PARAM_PREFIX')
        if not param_prefix:
            logger.error("✗ PARAM_PREFIX environment variable not set")
            raise ParameterManagerError("PARAM_PREFIX environment variable is required")
        
        region = os.getenv('AWS_REGION', 'us-east-1')
        parameter_manager = initialize_parameter_manager(param_prefix, region)
        
        logger.info(f"✓ Parameter Manager initialized with prefix: {param_prefix}")
        logger.info(f"✓ Parameter Manager region: {region}")
        
        # Initialize Configuration Validation Service
        validation_service = initialize_validation_service(param_prefix, region)
        logger.info("✓ Configuration Validation Service initialized")
        
        # Perform comprehensive startup validation
        logger.info("🔍 Performing comprehensive configuration validation...")
        startup_validation = await validation_service.validate_startup_configuration()
        
        # Log validation results
        validation_status = startup_validation['validation_status']
        if validation_status == 'success':
            logger.info("✅ Configuration validation completed successfully")
        elif validation_status == 'warning':
            logger.warning(f"⚠️ Configuration validation completed with warnings:")
            for warning in startup_validation['warnings']:
                logger.warning(f"  - {warning}")
        elif validation_status == 'failed':
            logger.error("❌ Configuration validation failed with critical errors:")
            for error in startup_validation['critical_errors']:
                logger.error(f"  - {error}")
            
            # Log recommendations for fixing issues
            if startup_validation['recommendations']:
                logger.info("💡 Recommendations to fix configuration issues:")
                for recommendation in startup_validation['recommendations']:
                    logger.info(f"  - {recommendation}")
            
            raise ConfigValidationError("Critical configuration validation errors detected")
        else:
            logger.error("❌ Configuration validation encountered unexpected errors")
            raise ConfigValidationError("Configuration validation failed unexpectedly")
        
        # Log parameter paths
        logger.info("✓ Parameter paths configured:")
        for category, path in parameter_manager.parameter_paths.items():
            logger.info(f"  {category}: {path}")
        
        # Log validation summary
        validation_details = startup_validation['validation_details']
        if 'parameter_structure' in validation_details:
            total_params = validation_details['parameter_structure']['details'].get('total_parameters', 0)
            logger.info(f"✓ Parameter discovery: {total_params} parameters found across all categories")
        
        if startup_validation['recommendations']:
            logger.info("💡 Configuration recommendations:")
            for recommendation in startup_validation['recommendations']:
                logger.info(f"  - {recommendation}")
            
    except (ParameterManagerError, ConfigValidationError) as e:
        logger.error(f"✗ Configuration initialization failed: {e}")
        logger.error("  Backend service will not function properly without valid configuration")
        raise
    except Exception as e:
        logger.error(f"✗ Unexpected error during configuration initialization: {e}")
        raise

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
    
    # Initialize Runtime Orchestrator Services
    try:
        logger.info("Initializing Runtime Orchestrator services...")
        
        # Initialize the orchestrator services based on configuration
        if isinstance(orchestrator_service, RuntimeOrchestratorService):
            await orchestrator_service.initialize_services()
            logger.info("✓ Runtime Orchestrator services initialized")
            
            # Log routing statistics
            routing_stats = orchestrator_service.get_routing_stats()
            logger.info(f"✓ Runtime Orchestrator ready - Configuration: {routing_stats['configuration']}")
        else:
            logger.info("✓ Legacy orchestrator service initialized")
            
    except Exception as e:
        logger.error(f"✗ Runtime Orchestrator initialization failed: {e}")
        # Continue startup even if orchestrator fails
        pass
    
    # Initialize AgentCore services
    try:
        logger.info("Initializing AgentCore services...")
        
        # Initialize invocation service
        await agent_invocation.initialize_client()
        logger.info("✓ AgentCore invocation service initialized")
        
        # Conditionally start periodic discovery based on configuration
        if periodic_discovery_enabled:
            await agent_discovery.start_periodic_discovery()
            logger.info(f"✓ AgentCore periodic discovery started (interval: {discovery_interval}s)")
            
            # Set up discovery callback to update registry
            def update_registry_callback(discovered_agents):
                """Callback to update registry when agents are discovered"""
                asyncio.create_task(_update_registry_with_discovered_agents(discovered_agents))
            
            agent_discovery.add_discovery_callback(update_registry_callback)
            logger.info("✓ AgentCore discovery callback registered")
        else:
            logger.info("⚠ AgentCore periodic discovery is disabled (AGENTCORE_PERIODIC_DISCOVERY_ENABLED=false)")
        
        # Perform initial discovery regardless of periodic setting
        discovered_agents = await agent_discovery.discover_agents()
        for agent_info in discovered_agents:
            await agent_registry.register_agent(agent_info)
        
        logger.info(f"✓ AgentCore initialization complete - {len(discovered_agents)} agents discovered")
        
    except Exception as e:
        logger.error(f"✗ AgentCore initialization failed: {e}")
        # Continue startup even if AgentCore fails
        pass


async def _update_registry_with_discovered_agents(discovered_agents):
    """Helper function to update registry with discovered agents"""
    try:
        for agent_info in discovered_agents:
            await agent_registry.register_agent(agent_info)
        logger.info(f"Registry updated with {len(discovered_agents)} agents")
    except Exception as e:
        logger.error(f"Failed to update registry: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the application shuts down"""
    try:
        logger.info("Shutting down AgentCore services...")
        
        # Stop periodic discovery if it was running
        if agent_discovery.is_discovery_running():
            await agent_discovery.stop_periodic_discovery()
            logger.info("✓ AgentCore discovery service stopped")
        else:
            logger.info("✓ AgentCore discovery service was not running")
        
        # Clear sessions
        agent_invocation.clear_sessions()
        logger.info("✓ AgentCore sessions cleared")
        
        logger.info("AgentCore services shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during AgentCore shutdown: {e}")


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



# Initialize Runtime Orchestrator Service with environment variable configuration
try:
    from services.runtime_orchestrator_service import RuntimeOrchestratorService
    orchestrator_service = RuntimeOrchestratorService()
    logger.info("Runtime Orchestrator Service initialized with environment configuration")
    
    # Log the runtime configuration
    orchestrator_service.log_environment_config()
    
    # Get enabled runtimes for logging
    enabled_runtimes = orchestrator_service.get_enabled_runtimes()
    logger.info(f"Enabled runtime types: {[rt.value for rt in enabled_runtimes]}")
    
except Exception as e:
    logger.error(f"Failed to initialize Runtime Orchestrator Service: {e}")
    logger.info("Falling back to legacy orchestrator selection")
    
    # Fallback to legacy orchestrator selection
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

# Initialize AgentCore services
agent_registry = AgentRegistryService(cache_ttl=300)

# Get periodic discovery configuration - default is OFF
periodic_discovery_enabled = get_config("AGENTCORE_PERIODIC_DISCOVERY_ENABLED", "false").lower() == "true"
discovery_interval = int(get_config("AGENTCORE_DISCOVERY_INTERVAL", "300"))

agent_discovery = AgentCoreDiscoveryService(
    ssm_prefix=f"/{get_config('PARAM_PREFIX', 'coa')}/agentcore/",  # Use dynamic parameter prefix
    region=get_config("AWS_DEFAULT_REGION", "us-east-1"),
    discovery_interval=discovery_interval
)
agent_invocation = AgentCoreInvocationService(
    region=get_config("AWS_DEFAULT_REGION", "us-east-1"),
    timeout=120
)
command_manager = CommandManager(agent_registry, agent_discovery)
agent_unregistration = AgentUnregistrationService(
    region=get_config("AWS_DEFAULT_REGION", "us-east-1"),
    param_prefix=get_config('PARAM_PREFIX', 'coa')
)

logger.info("AgentCore services initialized: registry, discovery, invocation, command manager, and unregistration")

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

    # Add Parameter Manager status
    try:
        from utils.parameter_manager import get_parameter_manager
        parameter_manager = get_parameter_manager()
        validation_result = parameter_manager.validate_configuration()
        
        if validation_result['ssm_connectivity'] and not validation_result['errors']:
            services_status["parameter_manager"] = "healthy"
        elif validation_result['ssm_connectivity']:
            services_status["parameter_manager"] = "degraded"
        else:
            services_status["parameter_manager"] = "unhealthy"
    except Exception:
        services_status["parameter_manager"] = "unhealthy"
    
    # Add Configuration Validation Service status
    try:
        from services.config_validation_service import get_validation_service
        validation_service = get_validation_service()
        config_health = await validation_service.health_check()
        services_status["configuration_validation"] = config_health['status']
    except Exception:
        services_status["configuration_validation"] = "unhealthy"

    # Add Enhanced Bedrock Agent Service status
    if bedrock_service:
        services_status["bedrock_agents"] = await bedrock_service.health_check()
    
    # Add AgentCore services status
    services_status["agentcore_registry"] = await agent_registry.health_check()
    services_status["agentcore_discovery"] = await agent_discovery.health_check()
    services_status["agentcore_invocation"] = await agent_invocation.health_check()
    services_status["agentcore_commands"] = await command_manager.health_check()
    services_status["agentcore_unregistration"] = await agent_unregistration.health_check()

    return HealthResponse(
        status="healthy"
        if all(s in ["healthy", "degraded"] for s in services_status.values())
        else "unhealthy",
        services=services_status,
        timestamp=datetime.utcnow(),
    )


@app.get("/api/debug/strands-agents")
async def debug_strands_agents():
    """Debug endpoint to check StrandsAgent discovery status"""
    try:
        if hasattr(orchestrator_service, 'agentcore_service') and orchestrator_service.agentcore_service:
            strands_service = orchestrator_service.agentcore_service
            if hasattr(strands_service, 'strands_discovery'):
                discovery_service = strands_service.strands_discovery
                
                # Get raw SSM parameters for debugging
                param_prefix = get_config('PARAM_PREFIX', 'coa')
                agentcore_path = f"/{param_prefix}/agentcore/"
                
                try:
                    import boto3
                    ssm_client = boto3.client("ssm", region_name=discovery_service.region)
                    response = ssm_client.get_parameters_by_path(
                        Path=agentcore_path,
                        Recursive=True,
                        WithDecryption=True
                    )
                    
                    raw_parameters = [
                        {"name": param["Name"], "value": param["Value"][:200] + "..." if len(param["Value"]) > 200 else param["Value"]}
                        for param in response.get("Parameters", [])
                    ]
                except Exception as e:
                    raw_parameters = [{"error": str(e)}]
                
                # Force discovery
                discovered_agents = await discovery_service.discover_strands_agents(force_refresh=True)
                
                return {
                    "param_prefix": param_prefix,
                    "search_path": agentcore_path,
                    "raw_parameters": raw_parameters,
                    "discovered_agents_count": len(discovered_agents),
                    "agents": {
                        name: {
                            "status": agent.status,
                            "framework": agent.framework,
                            "agent_arn": agent.agent_arn,
                            "endpoint_url": agent.endpoint_url,
                            "capabilities": agent.capabilities,
                            "domains": list(agent.domains.keys()) if agent.domains else []
                        }
                        for name, agent in discovered_agents.items()
                    },
                    "service_summary": discovery_service.get_service_summary()
                }
        
        return {"error": "StrandsAgent discovery service not available"}
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check endpoint with MCP server breakdown"""
    try:
        # Get basic service status
        services_status = {
            "orchestrator": await orchestrator_service.health_check(),
            "auth": "healthy",
        }
        
        # Get detailed orchestrator information
        orchestrator_details = None
        if hasattr(orchestrator_service, 'get_detailed_health'):
            try:
                orchestrator_details = orchestrator_service.get_detailed_health()
            except Exception as e:
                orchestrator_details = {"error": str(e)}
        
        # Get agent information from Enhanced Bedrock Agent Service
        agent_info = None
        if bedrock_service:
            try:
                agent_info = bedrock_service.get_agent_summary()
            except Exception as e:
                agent_info = {"error": str(e)}
        
        overall_status = "healthy"
        if services_status["orchestrator"] == "degraded":
            overall_status = "degraded"
        elif any(status == "unhealthy" for status in services_status.values()):
            overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "services": services_status,
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


# Prompt Templates endpoints
@app.get("/api/prompt-templates")
async def list_prompt_templates():
    """List available prompt templates organized by category"""
    try:
        import os
        from pathlib import Path
        
        # Get the frontend directory path
        current_dir = Path(__file__).parent
        templates_dir = current_dir / "frontend" / "prompt-templates"
        
        if not templates_dir.exists():
            return {"categories": {}, "total_templates": 0}
        
        templates = {}
        total_count = 0
        
        # Scan directories for categories
        for category_dir in templates_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                category_name = category_dir.name
                templates[category_name] = []
                
                # Scan for markdown files in category
                for template_file in category_dir.iterdir():
                    if template_file.is_file() and template_file.suffix.lower() == '.md':
                        templates[category_name].append(template_file.name)
                        total_count += 1
                
                # Sort templates within category
                templates[category_name].sort()
        
        return {
            "categories": templates,
            "total_templates": total_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to list prompt templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompt-templates/{category}/{template_name}")
async def get_prompt_template(category: str, template_name: str):
    """Get the content of a specific prompt template"""
    try:
        import os
        from pathlib import Path
        
        # Get the frontend directory path
        current_dir = Path(__file__).parent
        template_path = current_dir / "frontend" / "prompt-templates" / category / template_name
        
        # Security check: ensure the path is within the templates directory
        templates_dir = current_dir / "frontend" / "prompt-templates"
        try:
            template_path.resolve().relative_to(templates_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid template path")
        
        if not template_path.exists() or not template_path.is_file():
            raise HTTPException(status_code=404, detail="Template not found")
        
        if not template_path.suffix.lower() == '.md':
            raise HTTPException(status_code=400, detail="Only markdown templates are supported")
        
        # Read template content
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "category": category,
            "template_name": template_name,
            "content": content,
            "size": len(content),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get prompt template {category}/{template_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Orchestration monitoring endpoints
@app.get("/api/orchestration/status")
async def get_orchestration_status():
    """Get runtime orchestration status and configuration"""
    try:
        if isinstance(orchestrator_service, RuntimeOrchestratorService):
            # Get orchestrator configuration and stats
            routing_stats = orchestrator_service.get_routing_stats()
            enabled_runtimes = orchestrator_service.get_enabled_runtimes()
            
            # Get health status for each runtime
            runtime_health = {}
            for runtime_type in enabled_runtimes:
                runtime_health[runtime_type.value] = await orchestrator_service.check_runtime_health(runtime_type)
            
            return {
                "orchestrator_type": "runtime_orchestrator",
                "configuration": routing_stats["configuration"],
                "enabled_runtimes": [rt.value for rt in enabled_runtimes],
                "runtime_health": runtime_health,
                "routing_statistics": {
                    "total_requests": routing_stats["total_requests"],
                    "bedrock_agent_requests": routing_stats["bedrock_agent_requests"],
                    "agentcore_requests": routing_stats["agentcore_requests"],
                    "fallback_requests": routing_stats["fallback_requests"],
                    "failed_requests": routing_stats["failed_requests"]
                },
                "overall_health": await orchestrator_service.health_check(),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Legacy orchestrator
            return {
                "orchestrator_type": "legacy",
                "health": await orchestrator_service.health_check(),
                "message": "Using legacy orchestrator service",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "orchestrator_type": "unknown",
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/orchestration/config")
async def get_orchestration_config():
    """Get runtime orchestration configuration details"""
    try:
        if isinstance(orchestrator_service, RuntimeOrchestratorService):
            from services.runtime_orchestrator_service import EnvironmentConfig
            
            # Get current configuration
            config = EnvironmentConfig.get_runtime_config()
            enabled_runtimes = config.get_enabled_runtimes()
            
            return {
                "configuration": {
                    "bedrock_agent_enabled": config.bedrock_agent_enabled,
                    "agentcore_enabled": config.agentcore_enabled,
                    "priority_runtime": config.priority_runtime.value,
                    "fallback_enabled": config.fallback_enabled,
                    "keyword_analysis_enabled": config.keyword_analysis_enabled,
                    "health_check_interval": config.health_check_interval
                },
                "enabled_runtimes": [rt.value for rt in enabled_runtimes],
                "runtime_count": len(enabled_runtimes),
                "environment_variables": {
                    "ENABLE_BEDROCK_AGENT": os.getenv("ENABLE_BEDROCK_AGENT", "true"),
                    "ENABLE_BEDROCK_AGENTCORE": os.getenv("ENABLE_BEDROCK_AGENTCORE", "true"),
                    "ENABLE_KEYWORD_ANALYSIS": os.getenv("ENABLE_KEYWORD_ANALYSIS", "true"),
                    "RUNTIME_HEALTH_CHECK_INTERVAL": os.getenv("RUNTIME_HEALTH_CHECK_INTERVAL", "30")
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "error": "Runtime orchestrator not available",
                "message": "Using legacy orchestrator service",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/orchestration/routing-stats")
async def get_routing_statistics():
    """Get detailed routing statistics and decisions"""
    try:
        if isinstance(orchestrator_service, RuntimeOrchestratorService):
            routing_stats = orchestrator_service.get_routing_stats()
            
            # Calculate percentages
            total_requests = routing_stats["total_requests"]
            if total_requests > 0:
                bedrock_percentage = (routing_stats["bedrock_agent_requests"] / total_requests) * 100
                agentcore_percentage = (routing_stats["agentcore_requests"] / total_requests) * 100
                fallback_percentage = (routing_stats["fallback_requests"] / total_requests) * 100
                failure_percentage = (routing_stats["failed_requests"] / total_requests) * 100
            else:
                bedrock_percentage = agentcore_percentage = fallback_percentage = failure_percentage = 0
            
            return {
                "routing_statistics": routing_stats,
                "percentages": {
                    "bedrock_agent": round(bedrock_percentage, 2),
                    "agentcore_runtime": round(agentcore_percentage, 2),
                    "fallback": round(fallback_percentage, 2),
                    "failures": round(failure_percentage, 2)
                },
                "configuration": routing_stats["configuration"],
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "error": "Runtime orchestrator not available",
                "message": "Routing statistics only available with runtime orchestrator",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/orchestration/diagnostics")
async def get_orchestration_diagnostics():
    """Get comprehensive orchestration diagnostics for troubleshooting"""
    try:
        if isinstance(orchestrator_service, RuntimeOrchestratorService):
            # Get detailed health for each runtime
            runtime_diagnostics = {}
            enabled_runtimes = orchestrator_service.get_enabled_runtimes()
            
            for runtime_type in enabled_runtimes:
                try:
                    health_status = await orchestrator_service.check_runtime_health(runtime_type)
                    
                    # Get service-specific diagnostics
                    service_diagnostics = {"health": health_status}
                    
                    if runtime_type.value == "agentcore_runtime" and orchestrator_service.agentcore_service:
                        try:
                            if hasattr(orchestrator_service.agentcore_service, 'get_detailed_health'):
                                service_diagnostics.update(orchestrator_service.agentcore_service.get_detailed_health())
                        except Exception as e:
                            service_diagnostics["error"] = str(e)
                    
                    elif runtime_type.value == "bedrock_agent" and orchestrator_service.bedrock_agent_service:
                        try:
                            if hasattr(orchestrator_service.bedrock_agent_service, 'get_detailed_health'):
                                service_diagnostics.update(orchestrator_service.bedrock_agent_service.get_detailed_health())
                        except Exception as e:
                            service_diagnostics["error"] = str(e)
                    
                    runtime_diagnostics[runtime_type.value] = service_diagnostics
                    
                except Exception as e:
                    runtime_diagnostics[runtime_type.value] = {"error": str(e)}
            
            # Get orchestrator diagnostics
            orchestrator_diagnostics = orchestrator_service.get_detailed_health()
            routing_stats = orchestrator_service.get_routing_stats()
            
            # Calculate performance metrics
            total_requests = routing_stats["total_requests"]
            performance_metrics = {
                "requests_per_runtime": {
                    "bedrock_agent": routing_stats["bedrock_agent_requests"],
                    "agentcore_runtime": routing_stats["agentcore_requests"]
                },
                "failure_rate": (routing_stats["failed_requests"] / max(total_requests, 1)) * 100,
                "fallback_rate": (routing_stats["fallback_requests"] / max(total_requests, 1)) * 100,
                "total_requests": total_requests
            }
            
            return {
                "orchestrator_diagnostics": orchestrator_diagnostics,
                "runtime_diagnostics": runtime_diagnostics,
                "performance_metrics": performance_metrics,
                "configuration": routing_stats["configuration"],
                "environment_variables": {
                    "ENABLE_BEDROCK_AGENT": os.getenv("ENABLE_BEDROCK_AGENT"),
                    "ENABLE_BEDROCK_AGENTCORE": os.getenv("ENABLE_BEDROCK_AGENTCORE"),
                    "ENABLE_KEYWORD_ANALYSIS": os.getenv("ENABLE_KEYWORD_ANALYSIS"),
                    "RUNTIME_HEALTH_CHECK_INTERVAL": os.getenv("RUNTIME_HEALTH_CHECK_INTERVAL")
                },
                "system_info": {
                    "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
                    "platform": os.name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        else:
            return {
                "error": "Runtime orchestrator not available",
                "orchestrator_type": type(orchestrator_service).__name__,
                "message": "Diagnostics only available with runtime orchestrator",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/orchestration/performance")
async def get_orchestration_performance():
    """Get orchestration performance metrics"""
    try:
        if isinstance(orchestrator_service, RuntimeOrchestratorService):
            routing_stats = orchestrator_service.get_routing_stats()
            total_requests = routing_stats["total_requests"]
            
            if total_requests == 0:
                return {
                    "message": "No requests processed yet",
                    "metrics": {
                        "total_requests": 0,
                        "success_rate": 0,
                        "failure_rate": 0,
                        "fallback_rate": 0,
                        "runtime_distribution": {}
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Calculate performance metrics
            successful_requests = total_requests - routing_stats["failed_requests"]
            success_rate = (successful_requests / total_requests) * 100
            failure_rate = (routing_stats["failed_requests"] / total_requests) * 100
            fallback_rate = (routing_stats["fallback_requests"] / total_requests) * 100
            
            runtime_distribution = {
                "bedrock_agent": {
                    "requests": routing_stats["bedrock_agent_requests"],
                    "percentage": (routing_stats["bedrock_agent_requests"] / total_requests) * 100
                },
                "agentcore_runtime": {
                    "requests": routing_stats["agentcore_requests"],
                    "percentage": (routing_stats["agentcore_requests"] / total_requests) * 100
                }
            }
            
            return {
                "metrics": {
                    "total_requests": total_requests,
                    "successful_requests": successful_requests,
                    "failed_requests": routing_stats["failed_requests"],
                    "fallback_requests": routing_stats["fallback_requests"],
                    "success_rate": round(success_rate, 2),
                    "failure_rate": round(failure_rate, 2),
                    "fallback_rate": round(fallback_rate, 2),
                    "runtime_distribution": runtime_distribution
                },
                "configuration": routing_stats["configuration"],
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "error": "Runtime orchestrator not available",
                "message": "Performance metrics only available with runtime orchestrator",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        return {
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
        param_prefix = get_config('PARAM_PREFIX', 'coa')
        response = ssm_client.get_parameters_by_path(
            Path=f"/{param_prefix}/components",
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
                # /{param_prefix}/components/wa_security_mcp/connection_info -> wa_security_mcp
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
        
        # Get tools from orchestrator service
        try:
            if hasattr(orchestrator_service, 'get_available_tools'):
                orchestrator_tools = await orchestrator_service.get_available_tools()
                for tool in orchestrator_tools:
                    available_tools.append({
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                        "agent_type": tool.get("agent_type", "unknown"),
                        "server": tool.get("server", "unknown")
                    })
        except Exception as e:
            logger.warning(f"Failed to load tools from orchestrator: {e}")
            
        # Fallback: Get tools from bedrock service if available
        if not available_tools and bedrock_service:
            try:
                agents = bedrock_service.get_available_agents()
                for agent_type, agent_info in agents.items():
                    # Add basic agent info as "tools"
                    available_tools.append({
                        "name": f"{agent_type}_agent",
                        "description": f"Agent: {agent_info.agent_id}",
                        "parameters": {},
                        "agent_type": agent_type,
                        "server": "bedrock_agent"
                    })
            except Exception as e:
                logger.warning(f"Failed to load tools from bedrock service: {e}")
        
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

    try:
        # Check if this is an AgentCore command
        if command_manager.is_agentcore_command(message):
            logger.info(f"Processing AgentCore command: {message}")
            
            # Process command
            command_response = await command_manager.process_command(message, session_id)
            
            # Format response for chat
            if command_response.status == "success":
                response_text = f"**{command_response.message}**\n\n"
                
                # Add formatted data based on command type
                if "agents" in command_response.data:
                    agents = command_response.data["agents"]
                    if agents:
                        response_text += "**Available Agents:**\n"
                        for agent in agents:
                            response_text += f"• **{agent['agent_name']}** ({agent['agent_id']})\n"
                            response_text += f"  - Status: {agent['deployment_status']}\n"
                            response_text += f"  - Runtime: {agent['runtime_type']}\n"
                            response_text += f"  - Capabilities: {', '.join(agent['capabilities'])}\n\n"
                    else:
                        response_text += "No agents found.\n"
                
                elif "discovered_agents" in command_response.data:
                    discovered = command_response.data["discovered_agents"]
                    summary = command_response.data["summary"]
                    response_text += f"**Discovery Results:**\n"
                    response_text += f"• Total discovered: {summary['total_discovered']}\n"
                    response_text += f"• New agents: {summary['new_agents']}\n"
                    response_text += f"• Updated agents: {summary['updated_agents']}\n"
                    response_text += f"• Scan duration: {summary['scan_duration']:.2f}s\n\n"
                    
                    if discovered:
                        response_text += "**Discovered Agents:**\n"
                        for agent in discovered:
                            status_icon = "🆕" if agent['is_new'] else "🔄" if agent['is_updated'] else "✅"
                            response_text += f"{status_icon} **{agent['agent_name']}** ({agent['agent_id']})\n"
                
                elif "overall_status" in command_response.data:
                    status_data = command_response.data
                    status_icon = "✅" if status_data['overall_status'] == "healthy" else "⚠️" if status_data['overall_status'] == "degraded" else "❌"
                    response_text += f"**System Status:** {status_icon} {status_data['overall_status'].title()}\n\n"
                    response_text += f"**Registry:** {status_data['registry']['total_agents']} agents ({status_data['registry']['healthy_agents']} healthy)\n"
                    response_text += f"**Discovery:** {'Running' if status_data['discovery']['running'] else 'Stopped'} (interval: {status_data['discovery']['interval']}s)\n"
                
                elif "help_text" in command_response.data:
                    response_text += command_response.data["help_text"]
            else:
                response_text = f"❌ **Command Error:** {command_response.message}"
            
            # Add assistant response to session
            assistant_message = ChatMessage(
                role="assistant",
                content=response_text,
                timestamp=datetime.utcnow(),
                tool_executions=[],
            )
            session.messages.append(assistant_message)

            # Stop typing indicator
            if session_id in manager.active_connections:
                await manager.send_message(session_id, {"type": "typing", "status": False})

            return ChatResponse(
                response=response_text,
                session_id=session_id,
                tool_executions=[],
                timestamp=datetime.utcnow(),
                structured_data=command_response.data,
                human_summary=command_response.message,
            )

        # Check if a specific agent is selected for this session
        selected_agent_id = agent_selection_manager.get_selected_agent(session_id)
        if selected_agent_id:
            logger.info(f"Using selected agent: {selected_agent_id} for session: {session_id}")
            # Add selected agent to session context
            session.context["selected_agent"] = selected_agent_id

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
# AgentCore API endpoints
@app.get("/api/agentcore/agents")
async def get_agentcore_agents(user=Depends(get_current_user)):
    """Get all AgentCore agents from registry"""
    try:
        agents = await agent_registry.get_all_agents()
        registry_stats = agent_registry.get_registry_stats()
        
        return {
            "status": "success",
            "agents": {agent_id: agent.to_dict() for agent_id, agent in agents.items()},
            "summary": registry_stats.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agentcore/discover")
async def trigger_agentcore_discovery(user=Depends(get_current_user)):
    """Manually trigger AgentCore agent discovery"""
    try:
        discovered_agents = await agent_discovery.discover_agents()
        
        # Register discovered agents
        for agent_info in discovered_agents:
            await agent_registry.register_agent(agent_info)
        
        discovery_stats = agent_discovery.get_discovery_stats()
        
        return {
            "status": "success",
            "message": f"Discovery completed - found {len(discovered_agents)} agents",
            "discovered_agents": [agent.to_dict() for agent in discovered_agents],
            "discovery_stats": discovery_stats.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agentcore/status")
async def get_agentcore_status(user=Depends(get_current_user)):
    """Get comprehensive AgentCore system status"""
    try:
        registry_health = await agent_registry.health_check()
        discovery_health = await agent_discovery.health_check()
        invocation_health = await agent_invocation.health_check()
        command_health = await command_manager.health_check()
        
        registry_stats = agent_registry.get_registry_stats()
        discovery_stats = agent_discovery.get_discovery_stats()
        invocation_stats = agent_invocation.get_invocation_stats()
        
        overall_status = "healthy"
        if any(h == "unhealthy" for h in [registry_health, discovery_health, invocation_health, command_health]):
            overall_status = "unhealthy"
        elif any(h == "degraded" for h in [registry_health, discovery_health, invocation_health, command_health]):
            overall_status = "degraded"
        
        return {
            "status": "success",
            "overall_status": overall_status,
            "services": {
                "registry": {
                    "health": registry_health,
                    "stats": registry_stats.to_dict()
                },
                "discovery": {
                    "health": discovery_health,
                    "stats": discovery_stats.to_dict(),
                    "status": agent_discovery.get_discovery_status()
                },
                "invocation": {
                    "health": invocation_health,
                    "stats": invocation_stats.to_dict(),
                    "client_status": agent_invocation.get_client_status()
                },
                "commands": {
                    "health": command_health,
                    "stats": command_manager.get_command_stats()
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agentcore/invoke/{agent_id}")
async def invoke_agentcore_agent(
    agent_id: str, 
    request: ChatRequest, 
    user=Depends(get_current_user)
):
    """Invoke a specific AgentCore agent"""
    try:
        # Get agent from registry
        agent_info = await agent_registry.get_agent(agent_id)
        if not agent_info:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        # Invoke agent
        session_id = request.session_id or str(uuid.uuid4())
        response = await agent_invocation.invoke_agent(
            agent_info, 
            request.message, 
            session_id
        )
        
        return {
            "status": "success",
            "response": response.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agentcore/discovery/status")
async def get_discovery_status(user=Depends(get_current_user)):
    """Get periodic discovery status"""
    try:
        status = agent_discovery.get_discovery_status()
        stats = agent_discovery.get_discovery_stats()
        
        return {
            "status": "success",
            "discovery_status": status,
            "discovery_stats": {
                "last_scan": stats.last_scan.isoformat() if stats.last_scan else None,
                "total_scanned": stats.total_scanned,
                "agents_found": stats.agents_found,
                "scan_duration": stats.scan_duration,
                "errors": stats.errors
            },
            "configuration": {
                "enabled_by_default": periodic_discovery_enabled,
                "interval": discovery_interval,
                "ssm_prefix": agent_discovery.ssm_prefix
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agentcore/discovery/start")
async def start_periodic_discovery(user=Depends(get_current_user)):
    """Start periodic discovery"""
    try:
        if agent_discovery.is_discovery_running():
            return {
                "status": "already_running",
                "message": "Periodic discovery is already running",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        await agent_discovery.start_periodic_discovery()
        
        # Set up discovery callback to update registry if not already set
        def update_registry_callback(discovered_agents):
            """Callback to update registry when agents are discovered"""
            asyncio.create_task(_update_registry_with_discovered_agents(discovered_agents))
        
        # Check if callback is already registered (avoid duplicates)
        if not any(callback.__name__ == 'update_registry_callback' 
                  for callback in agent_discovery._discovery_callbacks):
            agent_discovery.add_discovery_callback(update_registry_callback)
        
        return {
            "status": "success",
            "message": f"Periodic discovery started with {discovery_interval}s interval",
            "interval": discovery_interval,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agentcore/discovery/stop")
async def stop_periodic_discovery(user=Depends(get_current_user)):
    """Stop periodic discovery"""
    try:
        if not agent_discovery.is_discovery_running():
            return {
                "status": "not_running",
                "message": "Periodic discovery is not currently running",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        await agent_discovery.stop_periodic_discovery()
        
        return {
            "status": "success",
            "message": "Periodic discovery stopped",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DiscoveryConfigRequest(BaseModel):
    interval: Optional[int] = None
    enabled: Optional[bool] = None


class AgentUnregistrationRequest(BaseModel):
    agent_name: str
    dry_run: Optional[bool] = False
    force: Optional[bool] = False


class BulkAgentUnregistrationRequest(BaseModel):
    agent_names: List[str]
    dry_run: Optional[bool] = False
    force: Optional[bool] = False


class AgentUnregistrationResponse(BaseModel):
    status: str
    agent_name: str
    agent_type: str
    parameters_deleted: List[str]
    parameters_failed: List[str]
    error_message: Optional[str] = None
    timestamp: str
    summary: Dict[str, Any]


class BulkAgentUnregistrationResponse(BaseModel):
    status: str
    results: Dict[str, AgentUnregistrationResponse]
    summary: Dict[str, Any]
    timestamp: str


@app.post("/api/agentcore/discovery/configure")
async def configure_periodic_discovery(
    request: DiscoveryConfigRequest, 
    user=Depends(get_current_user)
):
    """Configure periodic discovery settings"""
    try:
        changes_made = []
        
        # Update interval if provided
        if request.interval is not None:
            if request.interval < 30:
                raise HTTPException(status_code=400, detail="Interval must be at least 30 seconds")
            
            old_interval = agent_discovery.discovery_interval
            agent_discovery.set_discovery_interval(request.interval)
            changes_made.append(f"Interval changed from {old_interval}s to {request.interval}s")
        
        # Start/stop discovery if enabled flag is provided
        if request.enabled is not None:
            is_running = agent_discovery.is_discovery_running()
            
            if request.enabled and not is_running:
                await agent_discovery.start_periodic_discovery()
                
                # Set up discovery callback
                def update_registry_callback(discovered_agents):
                    asyncio.create_task(_update_registry_with_discovered_agents(discovered_agents))
                
                if not any(callback.__name__ == 'update_registry_callback' 
                          for callback in agent_discovery._discovery_callbacks):
                    agent_discovery.add_discovery_callback(update_registry_callback)
                
                changes_made.append("Periodic discovery started")
                
            elif not request.enabled and is_running:
                await agent_discovery.stop_periodic_discovery()
                changes_made.append("Periodic discovery stopped")
        
        return {
            "status": "success",
            "message": "Configuration updated",
            "changes": changes_made,
            "current_config": {
                "running": agent_discovery.is_discovery_running(),
                "interval": agent_discovery.discovery_interval,
                "ssm_prefix": agent_discovery.ssm_prefix
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# Agent Unregistration Endpoints
@app.get("/api/agents/registered")
async def list_registered_agents(user=Depends(get_current_user)):
    """List all registered agents across all SSM prefixes"""
    try:
        agents = await agent_unregistration.list_registered_agents()
        
        return {
            "status": "success",
            "agents": agents,
            "total_agents": len(agents),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list registered agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_name}/parameters")
async def get_agent_parameters(agent_name: str, user=Depends(get_current_user)):
    """Get all SSM parameters associated with an agent"""
    try:
        parameters = await agent_unregistration.get_agent_parameters(agent_name)
        
        if not parameters:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        return {
            "status": "success",
            "agent_name": agent_name,
            "parameters": parameters,
            "parameter_count": len(parameters),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get parameters for agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_name}/unregister", response_model=AgentUnregistrationResponse)
async def unregister_agent(
    agent_name: str, 
    request: AgentUnregistrationRequest, 
    user=Depends(get_current_user)
):
    """Unregister an agent from the COA system"""
    try:
        # Validate agent exists
        if not await agent_unregistration.validate_agent_exists(agent_name):
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        # Perform unregistration
        result = await agent_unregistration.unregister_agent(
            agent_name=agent_name,
            dry_run=request.dry_run,
            force=request.force
        )
        
        # Convert result to response model
        response_data = result.to_dict()
        
        return AgentUnregistrationResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unregister agent {agent_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/unregister/bulk", response_model=BulkAgentUnregistrationResponse)
async def bulk_unregister_agents(
    request: BulkAgentUnregistrationRequest, 
    user=Depends(get_current_user)
):
    """Unregister multiple agents in bulk"""
    try:
        if not request.agent_names:
            raise HTTPException(status_code=400, detail="No agent names provided")
        
        # Perform bulk unregistration
        results = await agent_unregistration.bulk_unregister_agents(
            agent_names=request.agent_names,
            dry_run=request.dry_run,
            force=request.force
        )
        
        # Convert results to response models
        response_results = {}
        total_success = 0
        total_failed = 0
        total_partial = 0
        
        for agent_name, result in results.items():
            result_data = result.to_dict()
            response_results[agent_name] = AgentUnregistrationResponse(**result_data)
            
            if result.status == "success":
                total_success += 1
            elif result.status == "failed":
                total_failed += 1
            elif result.status == "partial":
                total_partial += 1
        
        # Determine overall status
        if total_failed == 0 and total_partial == 0:
            overall_status = "success"
        elif total_success == 0:
            overall_status = "failed"
        else:
            overall_status = "partial"
        
        return BulkAgentUnregistrationResponse(
            status=overall_status,
            results=response_results,
            summary={
                "total_agents": len(request.agent_names),
                "successful": total_success,
                "failed": total_failed,
                "partial": total_partial,
                "dry_run": request.dry_run
            },
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to bulk unregister agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/cleanup/orphaned")
async def cleanup_orphaned_parameters(
    dry_run: bool = True, 
    user=Depends(get_current_user)
):
    """Clean up orphaned parameters that don't belong to any complete agent"""
    try:
        result = await agent_unregistration.cleanup_orphaned_parameters(dry_run=dry_run)
        
        return {
            "status": "success",
            "cleanup_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned parameters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/unregistration/health")
async def get_unregistration_service_health():
    """Get health status of the agent unregistration service"""
    try:
        health_status = await agent_unregistration.health_check()
        
        return {
            "status": "success",
            "service_health": health_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Unregistration service health check failed: {e}")
        return {
            "status": "error",
            "service_health": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


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


# Parameter Manager Configuration Endpoints
@app.get("/api/parameter-manager/config")
async def get_parameter_manager_config():
    """Get parameter manager configuration and status"""
    try:
        from utils.parameter_manager import get_parameter_manager
        parameter_manager = get_parameter_manager()
        
        validation_result = parameter_manager.validate_configuration()
        
        return {
            "param_prefix": parameter_manager.param_prefix,
            "region": parameter_manager.region,
            "parameter_paths": parameter_manager.parameter_paths,
            "ssm_connectivity": validation_result['ssm_connectivity'],
            "validation_errors": validation_result.get('errors', []),
            "cache_size": len(parameter_manager._cache),
            "status": "healthy" if validation_result['ssm_connectivity'] and not validation_result.get('errors') else "degraded"
        }
    except Exception as e:
        logger.error(f"Error getting parameter manager config: {e}")
        raise HTTPException(status_code=500, detail=f"Parameter manager error: {str(e)}")


@app.get("/api/parameter-manager/parameters")
async def list_parameters(category: Optional[str] = None):
    """List parameters, optionally filtered by category"""
    try:
        from utils.parameter_manager import get_parameter_manager
        parameter_manager = get_parameter_manager()
        
        parameters = parameter_manager.list_parameters(category)
        
        return {
            "category": category,
            "parameters": parameters,
            "count": len(parameters)
        }
    except Exception as e:
        logger.error(f"Error listing parameters: {e}")
        raise HTTPException(status_code=500, detail=f"Parameter listing error: {str(e)}")


@app.post("/api/parameter-manager/cache/clear")
async def clear_parameter_cache():
    """Clear parameter manager cache"""
    try:
        from utils.parameter_manager import get_parameter_manager
        parameter_manager = get_parameter_manager()
        
        parameter_manager.clear_cache()
        
        return {"message": "Parameter cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing parameter cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear error: {str(e)}")


@app.get("/api/parameter-manager/discovery")
async def discover_deployment_parameters():
    """Discover all parameters for the current deployment"""
    try:
        from utils.parameter_manager import get_parameter_manager
        parameter_manager = get_parameter_manager()
        
        # Get parameters for all categories
        all_parameters = {}
        total_count = 0
        
        for category in parameter_manager.parameter_paths.keys():
            try:
                category_params = parameter_manager.get_parameters_by_category(category)
                all_parameters[category] = {
                    "path": parameter_manager.parameter_paths[category],
                    "parameters": category_params,
                    "count": len(category_params)
                }
                total_count += len(category_params)
            except Exception as e:
                all_parameters[category] = {
                    "path": parameter_manager.parameter_paths[category],
                    "error": str(e),
                    "count": 0
                }
        
        return {
            "deployment": {
                "param_prefix": parameter_manager.param_prefix,
                "region": parameter_manager.region,
                "total_parameters": total_count
            },
            "categories": all_parameters,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error discovering parameters: {e}")
        raise HTTPException(status_code=500, detail=f"Parameter discovery error: {str(e)}")


@app.get("/api/parameter-manager/migration-status")
async def check_migration_status():
    """Check if migration from legacy parameters is needed"""
    try:
        from utils.parameter_manager import get_parameter_manager
        parameter_manager = get_parameter_manager()
        
        migration_status = {
            "current_prefix": parameter_manager.param_prefix,
            "legacy_prefix": "/coa",
            "migration_needed": False,
            "legacy_parameters_found": {},
            "current_parameters_found": {}
        }
        
        # Check for legacy parameters
        for category in parameter_manager.parameter_paths.keys():
            try:
                # Check current parameters
                current_params = parameter_manager.get_parameters_by_category(category)
                migration_status["current_parameters_found"][category] = len(current_params)
                
                # Check legacy parameters
                legacy_params = {}
                try:
                    # Try to get parameters from legacy path
                    param_prefix = get_config('PARAM_PREFIX', 'coa')
                    legacy_path = f"/{param_prefix}/{category}"
                    response = parameter_manager.ssm_client.get_parameters_by_path(
                        Path=legacy_path,
                        Recursive=True
                    )
                    for param in response['Parameters']:
                        param_name = param['Name'].replace(f"{legacy_path}/", "")
                        legacy_params[param_name] = param['Value']
                    
                    migration_status["legacy_parameters_found"][category] = len(legacy_params)
                    
                    if len(legacy_params) > 0 and len(current_params) == 0:
                        migration_status["migration_needed"] = True
                        
                except Exception:
                    migration_status["legacy_parameters_found"][category] = 0
                    
            except Exception as e:
                migration_status["current_parameters_found"][category] = f"Error: {str(e)}"
                migration_status["legacy_parameters_found"][category] = 0
        
        return migration_status
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Migration status error: {str(e)}")


# Configuration Validation Endpoints
@app.get("/api/config/validation/startup")
async def get_startup_validation():
    """Get comprehensive startup configuration validation results"""
    try:
        from services.config_validation_service import get_validation_service
        validation_service = get_validation_service()
        
        validation_result = await validation_service.validate_startup_configuration()
        
        return {
            "validation_result": validation_result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting startup validation: {e}")
        raise HTTPException(status_code=500, detail=f"Startup validation error: {str(e)}")


@app.get("/api/config/validation/health")
async def get_configuration_health():
    """Get configuration health check results"""
    try:
        from services.config_validation_service import get_validation_service
        validation_service = get_validation_service()
        
        health_result = await validation_service.health_check()
        
        return health_result
    except Exception as e:
        logger.error(f"Error getting configuration health: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration health error: {str(e)}")


@app.get("/api/config/validation/discovery")
async def validate_parameter_discovery():
    """Validate parameter discovery for deployment scripts"""
    try:
        from services.config_validation_service import get_validation_service
        validation_service = get_validation_service()
        
        # Try to find deployment scripts path
        deployment_scripts_path = None
        possible_paths = [
            "deployment-scripts",
            "../../../deployment-scripts",
            "/app/deployment-scripts"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                deployment_scripts_path = path
                break
        
        discovery_result = await validation_service.validate_parameter_discovery(deployment_scripts_path)
        
        return discovery_result
    except Exception as e:
        logger.error(f"Error validating parameter discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Parameter discovery validation error: {str(e)}")


@app.post("/api/config/validation/cache/clear")
async def clear_validation_cache():
    """Clear configuration validation cache"""
    try:
        from services.config_validation_service import get_validation_service
        validation_service = get_validation_service()
        
        validation_service.clear_cache()
        
        return {"message": "Configuration validation cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing validation cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear error: {str(e)}")


@app.get("/api/config/validation/recommendations")
async def get_configuration_recommendations():
    """Get configuration recommendations based on current state"""
    try:
        from services.config_validation_service import get_validation_service
        validation_service = get_validation_service()
        
        # Get fresh validation results
        validation_result = await validation_service.validate_startup_configuration()
        
        return {
            "recommendations": validation_result.get('recommendations', []),
            "validation_status": validation_result.get('validation_status'),
            "critical_errors": validation_result.get('critical_errors', []),
            "warnings": validation_result.get('warnings', []),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting configuration recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration recommendations error: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
