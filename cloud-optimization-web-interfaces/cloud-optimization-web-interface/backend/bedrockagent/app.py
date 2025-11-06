"""
BedrockAgent FastAPI Application Factory
Creates FastAPI application for traditional Bedrock Agent integration.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any

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

# BedrockAgent-specific imports will be added as services are migrated

logger = logging.getLogger(__name__)


def create_bedrockagent_app() -> FastAPI:
    """
    Create and configure BedrockAgent FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    logger.info("Initializing BedrockAgent FastAPI application...")
    
    # Create FastAPI app
    app = FastAPI(
        title="COA BedrockAgent Backend",
        description="Traditional Bedrock Agent integration for Cloud Optimization Assistant",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure logging for BedrockAgent version
    setup_logging(
        level="INFO",
        format_type="structured",
        include_extra=True
    )
    
    # Add version-specific CORS middleware
    configure_cors_for_version(app, "bedrockagent")
    
    # Add request logging middleware
    setup_request_logging(
        app=app,
        version="bedrockagent",
        log_body=False,
        log_headers=False,
        enable_performance_logging=True
    )
    
    # Initialize services
    services = initialize_bedrockagent_services()
    
    # Add authentication middleware (with local testing support)
    auth_dependency = setup_authentication(
        app=app,
        auth_service=services["auth"],
        version="bedrockagent",
        disable_auth=os.getenv("DISABLE_AUTH", "false").lower() in ["true", "1", "yes"]
    )
    
    # Add startup and shutdown event handlers
    add_event_handlers(app, services)
    
    # Register routes
    register_bedrockagent_routes(app, services)
    
    logger.info("✓ BedrockAgent FastAPI application initialized successfully")
    return app


def initialize_bedrockagent_services() -> Dict[str, Any]:
    """
    Initialize BedrockAgent-specific services.
    
    Returns:
        Dictionary of initialized services
    """
    logger.info("Initializing BedrockAgent services...")
    
    services = {}
    
    try:
        # Initialize shared services
        services["config"] = config_service
        services["auth"] = AuthService()
        services["aws_config"] = AWSConfigService()
        services["version_config"] = get_version_config_service()
        
        # Validate BedrockAgent configuration
        version_validation = services["version_config"].validate_version_constraints()
        if not version_validation["valid"]:
            logger.error("BedrockAgent configuration validation failed")
            for error in version_validation["errors"]:
                logger.error(f"Configuration error: {error}")
            raise RuntimeError("BedrockAgent configuration validation failed")
        
        # Log warnings and recommendations
        for warning in version_validation["warnings"]:
            logger.warning(f"Configuration warning: {warning}")
        for recommendation in version_validation["recommendations"]:
            logger.info(f"Configuration recommendation: {recommendation}")
        
        # Initialize BedrockAgent-specific services
        from bedrockagent.services.bedrock_chat_service import BedrockChatService
        from bedrockagent.services.llm_orchestrator_service import LLMOrchestratorService
        from bedrockagent.services.mcp_client_service import MCPClientService
        from shared.services.bedrock_model_service import BedrockModelService
        
        # Initialize services
        services["bedrock_model"] = BedrockModelService(region=services["config"].get_config_value("BEDROCK_REGION", "us-east-1"))
        services["bedrock_chat"] = BedrockChatService(region=services["config"].get_config_value("BEDROCK_REGION", "us-east-1"))
        services["llm_orchestrator"] = LLMOrchestratorService()
        services["mcp_client"] = MCPClientService()
        
        logger.info("✓ BedrockAgent-specific services initialized")
        
        logger.info("✓ BedrockAgent services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize BedrockAgent services: {e}")
        raise RuntimeError(f"BedrockAgent service initialization failed: {e}")
    
    return services


def add_event_handlers(app: FastAPI, services: Dict[str, Any]):
    """
    Add startup and shutdown event handlers.
    
    Args:
        app: FastAPI application instance
        services: Dictionary of initialized services
    """
    
    @app.on_event("startup")
    async def startup_event():
        """Handle application startup."""
        logger.info("BedrockAgent backend starting up...")
        
        try:
            # Validate AWS connectivity
            await validate_aws_connectivity()
            
            # Validate Bedrock access
            await validate_bedrock_access()
            
            # Initialize BedrockAgent services
            await initialize_bedrockagent_services(services)
            
            logger.info("✓ BedrockAgent backend startup completed successfully")
            
        except Exception as e:
            logger.error(f"BedrockAgent startup failed: {e}")
            # Continue startup even if some validations fail
            pass
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Handle application shutdown."""
        logger.info("BedrockAgent backend shutting down...")
        
        try:
            # Cleanup BedrockAgent services
            await cleanup_bedrockagent_services(services)
            
            logger.info("✓ BedrockAgent backend shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during BedrockAgent shutdown: {e}")


def register_bedrockagent_routes(app: FastAPI, services: Dict[str, Any]):
    """
    Register BedrockAgent-specific routes.
    
    Args:
        app: FastAPI application instance
        services: Dictionary of initialized services
    """
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """BedrockAgent health check endpoint."""
        try:
            service_status = {}
            
            # Check shared services
            service_status["config"] = "healthy"
            service_status["auth"] = "healthy"
            service_status["aws_config"] = "healthy"
            service_status["version_config"] = await services["version_config"].health_check()
            
            # Add BedrockAgent-specific service health checks
            service_status["bedrock_model"] = await services["bedrock_model"].health_check()
            service_status["bedrock_chat"] = await services["bedrock_chat"].health_check()
            service_status["llm_orchestrator"] = await services["llm_orchestrator"].health_check()
            service_status["mcp_client"] = "healthy"  # TODO: Implement MCP client health check
            
            # Determine overall status
            overall_status = "healthy"
            if any(status == "unhealthy" for status in service_status.values()):
                overall_status = "unhealthy"
            elif any(status == "degraded" for status in service_status.values()):
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "version": "bedrockagent",
                "services": service_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "version": "bedrockagent",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    # Version info endpoint
    @app.get("/api/version")
    async def get_version_info():
        """Get BedrockAgent version information."""
        try:
            version_service = services["version_config"]
            version_summary = version_service.get_version_summary()
            
            return {
                "backend_version": "bedrockagent",
                "version_info": version_summary,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get version info: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Configuration endpoint
    @app.get("/api/config/status")
    async def get_config_status():
        """Get BedrockAgent configuration status."""
        try:
            config_status = {
                "ssm_status": services["config"].get_ssm_status(),
                "version_config": services["version_config"].get_version_config(),
                "feature_flags": services["version_config"].get_feature_flags(),
                "service_flags": services["version_config"].get_service_flags()
            }
            
            return {
                "status": "success",
                "config": config_status,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get config status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Chat endpoint using BedrockAgent services
    @app.post("/api/chat")
    async def chat_endpoint(request: dict):
        """BedrockAgent chat endpoint."""
        try:
            # Handle both dict and ChatRequest formats for compatibility
            if isinstance(request, dict):
                message = request.get("message", "")
                session_id = request.get("session_id", "default")
            else:
                message = request.message
                session_id = request.session_id
            
            # Use chat service with agent fallback
            from shared.models.chat_models import ChatMessage
            messages = [ChatMessage(role="user", content=message)]
            
            response = await services["bedrock_chat"].chat_with_fallback(
                messages=messages,
                session_id=session_id,
                use_agent=True
            )
            
            return {
                "response": response["content"],
                "session_id": session_id,
                "response_type": response["response_type"],
                "tool_executions": response.get("tool_executions", []),
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
                "metadata": formatted_response["metadata"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Model invocation error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Service info endpoint
    @app.get("/api/services/info")
    async def get_services_info():
        """Get information about BedrockAgent services."""
        try:
            return {
                "bedrock_model": services["bedrock_model"].get_service_info(),
                "bedrock_chat": services["bedrock_chat"].get_service_info(),
                "version_config": services["version_config"].get_version_summary(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get services info: {e}")
            raise HTTPException(status_code=500, detail=str(e))


async def validate_aws_connectivity():
    """Validate AWS connectivity for BedrockAgent."""
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


async def validate_bedrock_access():
    """Validate Bedrock access for BedrockAgent."""
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        bedrock_region = config_service.get_config_value("BEDROCK_REGION", "us-east-1")
        
        # Test Bedrock connectivity
        bedrock_client = boto3.client("bedrock", region_name=bedrock_region)
        models = bedrock_client.list_foundation_models(byOutputModality="TEXT")
        model_count = len(models['modelSummaries'])
        
        logger.info(f"✓ Bedrock connectivity validated in {bedrock_region}")
        logger.info(f"  Foundation models available: {model_count}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            logger.warning("⚠ Limited Bedrock access - some features may not work")
        else:
            logger.error(f"✗ Bedrock validation error: {e}")
            raise RuntimeError(f"Bedrock validation failed: {e}")
    except Exception as e:
        logger.warning(f"⚠ Bedrock validation failed: {e}")
        # Don't fail startup for Bedrock issues


async def initialize_bedrockagent_services(services: Dict[str, Any]):
    """Initialize BedrockAgent-specific services during startup."""
    try:
        # Test model service connectivity
        model_health = await services["bedrock_model"].health_check()
        logger.info(f"Bedrock model service health: {model_health}")
        
        # Test chat service connectivity
        chat_health = await services["bedrock_chat"].health_check()
        logger.info(f"Bedrock chat service health: {chat_health}")
        
        logger.info("✓ BedrockAgent services startup initialization completed")
        
    except Exception as e:
        logger.error(f"BedrockAgent services initialization failed: {e}")
        # Continue startup even if some services fail


async def cleanup_bedrockagent_services(services: Dict[str, Any]):
    """Cleanup BedrockAgent services during shutdown."""
    try:
        # No specific cleanup needed for current services
        logger.info("✓ BedrockAgent services cleanup completed")
        
    except Exception as e:
        logger.error(f"Error during BedrockAgent services cleanup: {e}")


def create_bedrockagent_app_minimal() -> FastAPI:
    """
    Create and configure BedrockAgent FastAPI application in minimal mode (graceful degradation).
    Uses shared Bedrock model service when traditional agents are unavailable.
    
    Returns:
        Configured FastAPI application instance
    """
    logger.info("Initializing BedrockAgent FastAPI application in minimal mode...")
    
    try:
        # Create FastAPI app
        app = FastAPI(
            title="COA BedrockAgent Backend (Minimal Mode)",
            description="Traditional Bedrock Agent integration with graceful degradation",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Configure logging for BedrockAgent version
        setup_logging(
            level="INFO",
            format_type="structured",
            include_extra=True
        )
        
        # Add version-specific CORS middleware
        configure_cors_for_version(app, "bedrockagent")
        
        # Add request logging middleware
        setup_request_logging(
            app=app,
            version="bedrockagent",
            log_body=False,
            log_headers=False,
            enable_performance_logging=True
        )
        
        # Initialize minimal services (shared components only)
        services = {}
        services["config"] = config_service
        services["auth"] = AuthService()
        services["aws_config"] = AWSConfigService()
        services["version_config"] = get_version_config_service()
        
        # Add authentication middleware (with local testing support)
        auth_dependency = setup_authentication(
            app=app,
            auth_service=services["auth"],
            version="bedrockagent",
            disable_auth=os.getenv("DISABLE_AUTH", "false").lower() in ["true", "1", "yes"]
        )
        
        # Initialize parameter manager with dynamic prefix
        param_prefix = get_dynamic_parameter_prefix()
        region = services["config"].get_config_value("AWS_DEFAULT_REGION", "us-east-1")
        
        # Always initialize Bedrock model service for fallback
        services["bedrock_model"] = BedrockModelService(region=region)
        
        # Add minimal health endpoint
        @app.get("/health")
        async def health_check():
            """BedrockAgent minimal health check endpoint."""
            try:
                return {
                    "status": "healthy",
                    "version": "bedrockagent",
                    "mode": "minimal",
                    "services": {
                        "config": "healthy",
                        "auth": "healthy",
                        "aws_config": "healthy",
                        "bedrock_model": await services["bedrock_model"].health_check()
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Minimal health check failed: {e}")
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unhealthy",
                        "version": "bedrockagent",
                        "mode": "minimal",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        
        # Add minimal chat endpoint
        @app.post("/api/chat")
        async def chat_endpoint(request: dict):
            """BedrockAgent minimal chat endpoint with model fallback."""
            try:
                message = request.get("message", "")
                session_id = request.get("session_id", "default")
                
                # Use direct model access in minimal mode
                from shared.models.chat_models import ChatMessage
                messages = [ChatMessage(role="user", content=message)]
                
                model_id = services["bedrock_model"].get_standard_model()
                response = await services["bedrock_model"].invoke_model(
                    model_id=model_id,
                    messages=messages
                )
                
                formatted_response = services["bedrock_model"].format_response(response)
                
                return {
                    "response": formatted_response["content"],
                    "session_id": session_id,
                    "response_type": "model_fallback",
                    "model_id": model_id,
                    "tool_executions": [],
                    "metadata": formatted_response["metadata"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Minimal chat endpoint error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        logger.info("✓ BedrockAgent minimal FastAPI application initialized successfully")
        return app
        
    except Exception as e:
        logger.error(f"Failed to initialize BedrockAgent minimal application: {e}")
        # Return emergency app
        emergency_app = FastAPI(title="COA BedrockAgent Backend - Emergency Mode")
        
        @emergency_app.get("/health")
        async def emergency_health():
            return {
                "status": "emergency",
                "version": "bedrockagent",
                "mode": "emergency",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return emergency_app


def get_bedrockagent_info(minimal_mode: bool = False) -> Dict[str, Any]:
    """
    Get BedrockAgent application information.
    
    Args:
        minimal_mode: Whether running in minimal mode
    
    Returns:
        Dictionary with application information
    """
    return {
        "name": f"COA BedrockAgent Backend ({'Minimal' if minimal_mode else 'Full'} Mode)",
        "version": "1.0.0",
        "description": "Traditional Bedrock Agent integration for Cloud Optimization Assistant",
        "backend_type": "bedrockagent",
        "mode": "minimal" if minimal_mode else "full",
        "features": {
            "traditional_agents": not minimal_mode,
            "mcp_integration": not minimal_mode,
            "strands_agents": False,
            "agentcore_runtime": False,
            "graceful_degradation": True,
            "model_fallback": True
        },
        "parameter_prefix": get_dynamic_parameter_prefix(),
        "timestamp": datetime.utcnow().isoformat()
    }