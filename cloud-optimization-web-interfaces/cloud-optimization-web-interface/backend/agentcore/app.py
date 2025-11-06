"""
AgentCore FastAPI Application Factory
Creates FastAPI application for Strands Agent integration via Bedrock AgentCore Runtime.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Shared components
from shared.services.config_service import config_service
from shared.services.auth_service import AuthService
from shared.services.aws_config_service import AWSConfigService
from shared.services.version_config import get_version_config_service
from shared.services.bedrock_model_service import BedrockModelService
from shared.middleware.cors_middleware import configure_cors_for_version
from shared.middleware.logging_middleware import setup_request_logging
from shared.middleware.auth_middleware import setup_authentication
from shared.utils.logging_utils import setup_logging
from shared.utils.parameter_manager import get_dynamic_parameter_prefix

logger = logging.getLogger(__name__)


def create_agentcore_app() -> FastAPI:
    """
    Create and configure AgentCore FastAPI application with full agent support.
    
    Returns:
        Configured FastAPI application instance
    """
    logger.info("Initializing AgentCore FastAPI application with full agent support...")
    
    # Create FastAPI app
    app = FastAPI(
        title="COA AgentCore Backend",
        description="Strands Agent integration via Bedrock AgentCore Runtime for Cloud Optimization Assistant",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure logging for AgentCore version
    setup_logging(
        level="INFO",
        format_type="structured",
        include_extra=True
    )
    
    # Add version-specific CORS middleware
    configure_cors_for_version(app, "agentcore")
    
    # Add request logging middleware
    setup_request_logging(
        app=app,
        version="agentcore",
        log_body=False,
        log_headers=False,
        enable_performance_logging=True
    )
    
    # Initialize services
    services = initialize_agentcore_services(full_mode=True)
    
    # Add authentication middleware (with local testing support)
    auth_dependency = setup_authentication(
        app=app,
        auth_service=services["auth"],
        version="agentcore",
        disable_auth=os.getenv("DISABLE_AUTH", "false").lower() in ["true", "1", "yes"]
    )
    
    # Add startup and shutdown event handlers
    add_agentcore_event_handlers(app, services, full_mode=True)
    
    # Register routes
    register_agentcore_routes(app, services, full_mode=True)
    
    logger.info("✓ AgentCore FastAPI application initialized successfully with full agent support")
    return app


def create_agentcore_app_minimal() -> FastAPI:
    """
    Create and configure AgentCore FastAPI application in minimal mode (graceful degradation).
    
    Returns:
        Configured FastAPI application instance in minimal mode
    """
    logger.info("Initializing AgentCore FastAPI application in minimal mode...")
    
    # Create FastAPI app
    app = FastAPI(
        title="COA AgentCore Backend (Minimal)",
        description="AgentCore backend running without agent registration - using direct Bedrock model access",
        version="1.0.0-minimal",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure logging for AgentCore version
    setup_logging(
        level="INFO",
        format_type="structured",
        include_extra=True
    )
    
    # Add version-specific CORS middleware
    configure_cors_for_version(app, "agentcore")
    
    # Add request logging middleware
    setup_request_logging(
        app=app,
        version="agentcore_minimal",
        log_body=False,
        log_headers=False,
        enable_performance_logging=True
    )
    
    # Initialize services in minimal mode
    services = initialize_agentcore_services(full_mode=False)
    
    # Add authentication middleware (with local testing support)
    auth_dependency = setup_authentication(
        app=app,
        auth_service=services["auth"],
        version="agentcore",
        disable_auth=os.getenv("DISABLE_AUTH", "false").lower() in ["true", "1", "yes"]
    )
    
    # Add startup and shutdown event handlers
    add_agentcore_event_handlers(app, services, full_mode=False)
    
    # Register routes
    register_agentcore_routes(app, services, full_mode=False)
    
    logger.info("✓ AgentCore FastAPI application initialized successfully in minimal mode")
    return app


def initialize_agentcore_services(full_mode: bool = True) -> Dict[str, Any]:
    """
    Initialize AgentCore-specific services.
    
    Args:
        full_mode: Whether to initialize full agent services or minimal mode
        
    Returns:
        Dictionary of initialized services
    """
    logger.info(f"Initializing AgentCore services (full_mode={full_mode})...")
    
    services = {}
    
    try:
        # Initialize shared services
        services["config"] = config_service
        services["auth"] = AuthService()
        services["aws_config"] = AWSConfigService()
        services["version_config"] = get_version_config_service()
        
        # Always initialize Bedrock model service for fallback
        bedrock_region = services["config"].get_config_value("AWS_DEFAULT_REGION", "us-east-1")
        services["bedrock_model"] = BedrockModelService(region=bedrock_region)
        
        # Validate AgentCore configuration
        version_validation = services["version_config"].validate_version_constraints()
        if not version_validation["valid"]:
            logger.error("AgentCore configuration validation failed")
            for error in version_validation["errors"]:
                logger.error(f"Configuration error: {error}")
            if full_mode:
                raise RuntimeError("AgentCore configuration validation failed")
        
        # Log warnings and recommendations
        for warning in version_validation["warnings"]:
            logger.warning(f"Configuration warning: {warning}")
        for recommendation in version_validation["recommendations"]:
            logger.info(f"Configuration recommendation: {recommendation}")
        
        if full_mode:
            # Initialize full AgentCore services
            try:
                from agentcore.services.strands_agent_discovery_service import StrandsAgentDiscoveryService
                from agentcore.services.strands_llm_orchestrator_service import StrandsLLMOrchestratorService
                from agentcore.services.agentcore_invocation_service import AgentCoreInvocationService
                
                # Initialize parameter manager for dynamic prefix
                from shared.utils.parameter_manager import initialize_parameter_manager
                param_prefix = get_dynamic_parameter_prefix()
                region = services["config"].get_config_value("AWS_DEFAULT_REGION", "us-east-1")
                parameter_manager = initialize_parameter_manager(param_prefix, region)
                
                services["strands_discovery"] = StrandsAgentDiscoveryService(
                    region=region,
                    param_prefix=param_prefix
                )
                services["strands_orchestrator"] = StrandsLLMOrchestratorService()
                services["agentcore_invocation"] = AgentCoreInvocationService()
                services["parameter_manager"] = parameter_manager
                
                logger.info("✓ Full AgentCore services initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize full AgentCore services: {e}")
                logger.info("Falling back to minimal mode services")
                full_mode = False
        
        if not full_mode:
            # Minimal mode - only essential services
            logger.info("✓ Minimal AgentCore services initialized (using Bedrock model fallback)")
        
        services["mode"] = "full" if full_mode else "minimal"
        
    except Exception as e:
        logger.error(f"Failed to initialize AgentCore services: {e}")
        raise RuntimeError(f"AgentCore service initialization failed: {e}")
    
    return services


def add_agentcore_event_handlers(app: FastAPI, services: Dict[str, Any], full_mode: bool = True):
    """
    Add startup and shutdown event handlers.
    
    Args:
        app: FastAPI application instance
        services: Dictionary of initialized services
        full_mode: Whether running in full mode
    """
    
    @app.on_event("startup")
    async def startup_event():
        """Handle application startup."""
        mode_str = "full agent support" if full_mode else "minimal mode"
        logger.info(f"AgentCore backend starting up with {mode_str}...")
        
        try:
            # Validate AWS connectivity
            await validate_aws_connectivity()
            
            # Check parameter prefix configuration
            param_prefix = get_dynamic_parameter_prefix()
            logger.info(f"Using parameter prefix: {param_prefix}")
            
            if full_mode:
                # Initialize agent discovery and registration
                await initialize_agent_services(services)
            else:
                # Validate Bedrock model service
                await validate_bedrock_model_service(services)
            
            logger.info(f"✓ AgentCore backend startup completed successfully ({mode_str})")
            
        except Exception as e:
            logger.error(f"AgentCore startup failed: {e}")
            # Continue startup even if some validations fail
            pass
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Handle application shutdown."""
        logger.info("AgentCore backend shutting down...")
        
        try:
            if full_mode:
                # Cleanup agent services
                await cleanup_agent_services(services)
            
            logger.info("✓ AgentCore backend shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during AgentCore shutdown: {e}")


def register_agentcore_routes(app: FastAPI, services: Dict[str, Any], full_mode: bool = True):
    """
    Register AgentCore-specific routes.
    
    Args:
        app: FastAPI application instance
        services: Dictionary of initialized services
        full_mode: Whether running in full mode
    """
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """AgentCore health check endpoint."""
        try:
            service_status = {}
            
            # Check shared services
            service_status["config"] = "healthy"
            service_status["auth"] = "healthy"
            service_status["aws_config"] = "healthy"
            service_status["version_config"] = await services["version_config"].health_check()
            service_status["bedrock_model"] = await services["bedrock_model"].health_check()
            
            if full_mode:
                # Add AgentCore-specific service health checks
                if "strands_discovery" in services:
                    try:
                        service_status["strands_discovery"] = "healthy"  # TODO: Add actual health check
                    except Exception:
                        service_status["strands_discovery"] = "unhealthy"
                
                if "strands_orchestrator" in services:
                    service_status["strands_orchestrator"] = "healthy"  # TODO: Add actual health check
                
                if "agentcore_invocation" in services:
                    service_status["agentcore_invocation"] = "healthy"  # TODO: Add actual health check
            
            # Determine overall status
            overall_status = "healthy"
            if any(status == "unhealthy" for status in service_status.values()):
                overall_status = "unhealthy"
            elif any(status == "degraded" for status in service_status.values()):
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "version": "agentcore",
                "mode": services.get("mode", "unknown"),
                "services": service_status,
                "param_prefix": get_dynamic_parameter_prefix(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "version": "agentcore",
                    "mode": services.get("mode", "unknown"),
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    # Version info endpoint
    @app.get("/api/version")
    async def get_version_info():
        """Get AgentCore version information."""
        try:
            version_service = services["version_config"]
            version_summary = version_service.get_version_summary()
            
            return {
                "backend_version": "agentcore",
                "mode": services.get("mode", "unknown"),
                "version_info": version_summary,
                "param_prefix": get_dynamic_parameter_prefix(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get version info: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Configuration endpoint
    @app.get("/api/config/status")
    async def get_config_status():
        """Get AgentCore configuration status."""
        try:
            config_status = {
                "ssm_status": services["config"].get_ssm_status(),
                "version_config": services["version_config"].get_version_config(),
                "feature_flags": services["version_config"].get_feature_flags(),
                "service_flags": services["version_config"].get_service_flags(),
                "param_prefix": get_dynamic_parameter_prefix(),
                "mode": services.get("mode", "unknown")
            }
            
            return {
                "status": "success",
                "config": config_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get config status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Chat endpoint (always available via Bedrock model fallback)
    @app.post("/api/chat")
    async def chat_endpoint(request: dict):
        """AgentCore chat endpoint with agent/model fallback."""
        try:
            # Handle both dict and ChatRequest formats for compatibility
            if isinstance(request, dict):
                message = request.get("message", "")
                session_id = request.get("session_id", "default")
                context = request.get("context", {})
            else:
                message = request.message
                session_id = request.session_id
                context = getattr(request, 'context', {})
            
            # Check for manual agent selection
            selected_agent = context.get("selected_agent")
            agent_selection_mode = context.get("agent_selection_mode", "auto")
            
            if full_mode and "strands_orchestrator" in services:
                # Try Strands agents first, then fallback to model
                try:
                    from shared.models.chat_models import ChatMessage
                    messages = [ChatMessage(role="user", content=message)]
                    
                    # Pass agent selection context to orchestrator
                    response = await services["strands_orchestrator"].process_message(
                        message=message,
                        session_id=session_id,
                        selected_agent=selected_agent,
                        agent_selection_mode=agent_selection_mode,
                        context=context
                    )
                    
                    return {
                        "response": response["content"],
                        "session_id": session_id,
                        "response_type": "strands_agent",
                        "agent_used": response.get("agent_id", "unknown"),
                        "mode": services.get("mode", "unknown"),
                        "metadata": response.get("metadata", {}),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                except Exception as agent_error:
                    logger.warning(f"Strands agent failed, falling back to model: {agent_error}")
                    response = await fallback_to_model_chat(services, message, session_id)
            else:
                # Minimal mode or no orchestrator - direct model access
                response = await fallback_to_model_chat(services, message, session_id)
            
            return {
                "response": response["content"],
                "session_id": session_id,
                "response_type": response["response_type"],
                "mode": services.get("mode", "unknown"),
                "metadata": response.get("metadata", {}),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Chat endpoint error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Model service endpoint
    @app.post("/api/model/invoke")
    async def invoke_model_endpoint(request: dict):
        """Direct model invocation endpoint."""
        try:
            message = request.get("message", "")
            model_id = request.get("model_id") or services["bedrock_model"].get_standard_model()
            
            from shared.models.chat_models import ChatMessage
            messages = [ChatMessage(role="user", content=message)]
            
            response = await services["bedrock_model"].invoke_model(
                model_id=model_id,
                messages=messages
            )
            
            formatted_response = services["bedrock_model"].format_response(response)
            
            return {
                "response": formatted_response["content"],
                "model_id": model_id,
                "mode": services.get("mode", "unknown"),
                "metadata": formatted_response["metadata"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Model invocation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    if full_mode:
        # Full mode specific endpoints
        
        @app.get("/api/agents/status")
        async def get_agents_status():
            """Get AgentCore agents status."""
            try:
                if "strands_discovery" in services:
                    discovered_agents = await services["strands_discovery"].get_discovered_agents()
                    return {
                        "agents": discovered_agents,
                        "count": len(discovered_agents),
                        "mode": "full",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        "agents": [],
                        "count": 0,
                        "message": "Discovery service not available",
                        "mode": "full",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
            except Exception as e:
                logger.error(f"Failed to get agents status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/agents/discover")
        async def trigger_agent_discovery():
            """Trigger agent discovery."""
            try:
                if "strands_discovery" in services:
                    result = await services["strands_discovery"].discover_agents()
                    return {
                        "discovery_result": result,
                        "mode": "full",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        "message": "Discovery service not available",
                        "mode": "full",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
            except Exception as e:
                logger.error(f"Failed to trigger discovery: {e}")
                raise HTTPException(status_code=500, detail=str(e))


async def fallback_to_model_chat(services: Dict[str, Any], message: str, session_id: str) -> Dict[str, Any]:
    """
    Fallback to direct Bedrock model chat.
    
    Args:
        services: Dictionary of services
        message: User message
        session_id: Session ID
        
    Returns:
        Chat response dictionary
    """
    try:
        from shared.models.chat_models import ChatMessage
        messages = [ChatMessage(role="user", content=message)]
        
        model_id = services["bedrock_model"].get_standard_model()
        response = await services["bedrock_model"].invoke_model(
            model_id=model_id,
            messages=messages
        )
        
        formatted_response = services["bedrock_model"].format_response(response)
        
        return {
            "content": formatted_response["content"],
            "response_type": "model_fallback",
            "metadata": formatted_response["metadata"]
        }
        
    except Exception as e:
        logger.error(f"Model fallback failed: {e}")
        return {
            "content": f"I apologize, but I'm experiencing technical difficulties. Error: {str(e)}",
            "response_type": "error_fallback",
            "metadata": {"error": str(e)}
        }


async def validate_aws_connectivity():
    """Validate AWS connectivity for AgentCore."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # Test basic AWS connectivity
        sts_client = boto3.client("sts")
        identity = sts_client.get_caller_identity()
        logger.info(f"✓ AWS connectivity validated - Account: {identity.get('Account')}")
        
    except NoCredentialsError:
        logger.error("✗ AWS credentials not found")
        raise RuntimeError("AWS credentials not configured")
    except ClientError as e:
        logger.error(f"✗ AWS connectivity error: {e}")
        raise RuntimeError(f"AWS connectivity failed: {e}")
    except Exception as e:
        logger.error(f"✗ Unexpected AWS validation error: {e}")
        raise RuntimeError(f"AWS validation failed: {e}")


async def validate_bedrock_model_service(services: Dict[str, Any]):
    """Validate Bedrock model service for minimal mode."""
    try:
        model_health = await services["bedrock_model"].health_check()
        logger.info(f"✓ Bedrock model service validated - Health: {model_health}")
        
    except Exception as e:
        logger.warning(f"⚠ Bedrock model service validation failed: {e}")
        # Don't fail startup for Bedrock issues


async def initialize_agent_services(services: Dict[str, Any]):
    """Initialize agent services for full mode."""
    try:
        if "strands_discovery" in services:
            # Trigger initial discovery
            discovery_result = await services["strands_discovery"].discover_agents()
            logger.info(f"✓ Initial agent discovery completed: {len(discovery_result.get('agents_discovered', []))} agents found")
        
        logger.info("✓ Agent services initialization completed")
        
    except Exception as e:
        logger.error(f"Agent services initialization failed: {e}")
        # Continue startup even if agent services fail


async def cleanup_agent_services(services: Dict[str, Any]):
    """Cleanup agent services during shutdown."""
    try:
        # TODO: Cleanup agent services when they are migrated
        # await services["strands_discovery"].shutdown()
        # await services["agent_registry"].shutdown()
        
        logger.info("✓ Agent services cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during agent services cleanup: {e}")


def get_agentcore_info(minimal_mode: bool = False) -> Dict[str, Any]:
    """
    Get AgentCore application information.
    
    Args:
        minimal_mode: Whether running in minimal mode
        
    Returns:
        Dictionary with application information
    """
    full_mode = not minimal_mode
    return {
        "name": f"COA AgentCore Backend ({'Minimal' if minimal_mode else 'Full'} Mode)",
        "version": "1.0.0",
        "description": "Strands Agent integration via Bedrock AgentCore Runtime for Cloud Optimization Assistant",
        "backend_type": "agentcore",
        "mode": "minimal" if minimal_mode else "full",
        "features": {
            "traditional_agents": False,
            "mcp_integration": False,
            "strands_agents": full_mode,
            "agentcore_runtime": full_mode,
            "graceful_degradation": True,
            "bedrock_model_fallback": True
        },
        "parameter_prefix": get_dynamic_parameter_prefix(),
        "timestamp": datetime.utcnow().isoformat()
    }