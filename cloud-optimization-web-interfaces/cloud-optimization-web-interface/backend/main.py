"""
Cloud Optimization Assistant (COA) Backend - Root Mode Selector
Determines backend mode and loads appropriate application factory.
"""

import os
import sys
import logging
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackendMode(Enum):
    """Backend operation modes"""
    AGENTCORE = "agentcore"
    BEDROCKAGENT = "bedrockagent"


class ModeValidationError(Exception):
    """Exception raised when mode validation fails"""
    pass


class AppInitializationError(Exception):
    """Exception raised when app initialization fails"""
    pass


def get_backend_mode() -> BackendMode:
    """Get backend mode from environment variable with default to AgentCore"""
    mode = os.getenv("BACKEND_MODE", "agentcore").lower().strip()
    
    try:
        return BackendMode(mode)
    except ValueError:
        valid_modes = [m.value for m in BackendMode]
        logger.error(f"Invalid BACKEND_MODE: '{mode}'. Must be one of: {valid_modes}")
        raise ValueError(f"Invalid BACKEND_MODE: '{mode}'. Must be one of: {valid_modes}")


def validate_environment_variables(mode: BackendMode) -> Dict[str, Any]:
    """Validate environment variables for the selected mode"""
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "recommendations": []
    }
    
    # Common environment variables
    aws_region = os.getenv("AWS_DEFAULT_REGION")
    if not aws_region:
        validation_result["warnings"].append("AWS_DEFAULT_REGION not set, using default 'us-east-1'")
    
    if mode == BackendMode.AGENTCORE:
        # AgentCore-specific validation
        param_prefix = os.getenv("PARAM_PREFIX")
        if not param_prefix:
            validation_result["warnings"].append("PARAM_PREFIX not set, using default 'coa'")
            validation_result["recommendations"].append("Set PARAM_PREFIX for proper AgentCore configuration")
        
        # Check for conflicting BedrockAgent variables
        bedrock_vars = ["ENHANCED_SECURITY_AGENT_ID", "ENHANCED_SECURITY_AGENT_ALIAS_ID"]
        for var in bedrock_vars:
            if os.getenv(var):
                validation_result["warnings"].append(f"BedrockAgent variable {var} set in AgentCore mode")
    
    elif mode == BackendMode.BEDROCKAGENT:
        # BedrockAgent-specific validation
        # Check for conflicting AgentCore variables
        agentcore_vars = ["PARAM_PREFIX", "AGENTCORE_PERIODIC_DISCOVERY_ENABLED"]
        for var in agentcore_vars:
            if os.getenv(var):
                validation_result["warnings"].append(f"AgentCore variable {var} set in BedrockAgent mode")
        
        # Check for recommended BedrockAgent configuration
        required_vars = ["ENHANCED_SECURITY_AGENT_ID", "ENHANCED_SECURITY_AGENT_ALIAS_ID"]
        for var in required_vars:
            if not os.getenv(var):
                validation_result["recommendations"].append(f"Consider setting {var} for enhanced BedrockAgent functionality")
    
    return validation_result


def validate_mode_constraints(mode: BackendMode) -> None:
    """Ensure strict mode constraints are enforced"""
    logger.info(f"Validating mode constraints for {mode.value} mode")
    
    # Validate environment variables
    env_validation = validate_environment_variables(mode)
    
    # Log validation results
    for warning in env_validation["warnings"]:
        logger.warning(f"Environment validation: {warning}")
    
    for recommendation in env_validation["recommendations"]:
        logger.info(f"Recommendation: {recommendation}")
    
    if env_validation["errors"]:
        for error in env_validation["errors"]:
            logger.error(f"Environment validation error: {error}")
        raise ModeValidationError("Environment validation failed")
    
    # Check for forbidden module imports
    if mode == BackendMode.AGENTCORE:
        forbidden_modules = ["bedrockagent.services", "bedrock_agent_service"]
        for module in sys.modules:
            if any(forbidden in module for forbidden in forbidden_modules):
                raise ModeValidationError(f"BedrockAgent module {module} loaded in AgentCore mode")
    
    elif mode == BackendMode.BEDROCKAGENT:
        forbidden_modules = ["agentcore.services", "strands_agent_discovery"]
        for module in sys.modules:
            if any(forbidden in module for forbidden in forbidden_modules):
                raise ModeValidationError(f"AgentCore module {module} loaded in BedrockAgent mode")
    
    logger.info("✓ Mode constraints validation passed")


def check_agentcore_availability() -> Dict[str, Any]:
    """Check if AgentCore services are available"""
    availability_result = {
        "available": False,
        "param_prefix": os.getenv("PARAM_PREFIX", "coa"),
        "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        "parameters_found": 0,
        "error": None
    }
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        ssm_client = boto3.client("ssm", region_name=availability_result["region"])
        
        # Try to access AgentCore parameters
        response = ssm_client.get_parameters_by_path(
            Path=f"/{availability_result['param_prefix']}/agentcore/",
            MaxResults=10
        )
        
        parameters_found = len(response.get('Parameters', []))
        availability_result["parameters_found"] = parameters_found
        availability_result["available"] = parameters_found > 0
        
        if availability_result["available"]:
            logger.info(f"✓ AgentCore availability check passed - found {parameters_found} parameters")
        else:
            logger.warning("⚠ AgentCore parameters not found - will run in minimal mode")
        
    except NoCredentialsError as e:
        availability_result["error"] = f"AWS credentials not configured: {e}"
        logger.warning(f"AgentCore availability check failed: {availability_result['error']}")
    except ClientError as e:
        availability_result["error"] = f"AWS client error: {e}"
        logger.warning(f"AgentCore availability check failed: {availability_result['error']}")
    except Exception as e:
        availability_result["error"] = f"Unexpected error: {e}"
        logger.warning(f"AgentCore availability check failed: {availability_result['error']}")
    
    return availability_result


def log_startup_info(mode: BackendMode):
    """Log startup information"""
    startup_info = {
        "backend_mode": mode.value,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
        "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        "param_prefix": os.getenv("PARAM_PREFIX", "coa"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info("=== COA Backend Startup ===")
    for key, value in startup_info.items():
        logger.info(f"{key}: {value}")
    logger.info("===========================")


def create_app_with_error_handling(mode: BackendMode):
    """Create application with comprehensive error handling"""
    try:
        if mode == BackendMode.AGENTCORE:
            return create_agentcore_app_with_fallback()
        elif mode == BackendMode.BEDROCKAGENT:
            return create_bedrockagent_app()
        else:
            raise AppInitializationError(f"Unsupported backend mode: {mode}")
    
    except ImportError as e:
        logger.error(f"Failed to import required modules for {mode.value} mode: {e}")
        raise AppInitializationError(f"Module import failed for {mode.value} mode: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize {mode.value} backend: {e}")
        raise AppInitializationError(f"{mode.value} backend initialization failed: {e}")


def create_agentcore_app_with_fallback():
    """Create AgentCore app with automatic fallback to minimal mode"""
    try:
        # Check if forced to use real AgentCore mode
        force_real_agentcore = os.getenv("FORCE_REAL_AGENTCORE", "false").lower() == "true"
        
        if force_real_agentcore:
            logger.info("FORCE_REAL_AGENTCORE=true - Attempting forced full AgentCore initialization...")
            from agentcore.app import create_agentcore_app
            app = create_agentcore_app()
            logger.info("✓ AgentCore backend initialized successfully with full agent support (forced mode)")
            return app
        
        # Check AgentCore availability first
        availability = check_agentcore_availability()
        
        if availability["available"]:
            logger.info("Attempting full AgentCore initialization...")
            from agentcore.app import create_agentcore_app
            app = create_agentcore_app()
            logger.info("✓ AgentCore backend initialized successfully with full agent support")
            return app
        else:
            logger.info("AgentCore services not available, initializing minimal mode...")
            from agentcore.app import create_agentcore_app_minimal
            app = create_agentcore_app_minimal()
            logger.info("✓ AgentCore backend initialized in minimal mode")
            return app
            
    except ImportError as e:
        logger.error(f"Failed to import AgentCore modules: {e}")
        raise AppInitializationError(f"AgentCore module import failed: {e}")
    except Exception as e:
        logger.warning(f"Full AgentCore initialization failed: {e}")
        logger.info("Attempting minimal mode initialization...")
        
        try:
            from agentcore.app import create_agentcore_app_minimal
            app = create_agentcore_app_minimal()
            logger.info("✓ AgentCore backend initialized in minimal mode (fallback)")
            return app
        except Exception as minimal_error:
            logger.error(f"Minimal mode initialization also failed: {minimal_error}")
            raise AppInitializationError("AgentCore backend initialization failed completely")


def create_bedrockagent_app():
    """Create BedrockAgent app"""
    logger.info("Initializing BedrockAgent backend...")
    from bedrockagent.app import create_bedrockagent_app
    app = create_bedrockagent_app()
    logger.info("✓ BedrockAgent backend initialized successfully")
    return app


def main():
    """Main entry point - determines mode and loads appropriate app"""
    try:
        # Get and validate backend mode
        mode = get_backend_mode()
        
        # Log startup information
        log_startup_info(mode)
        
        # Validate mode constraints
        validate_mode_constraints(mode)
        
        # Create application
        app = create_app_with_error_handling(mode)
        
        logger.info(f"🚀 COA Backend successfully started in {mode.value} mode")
        return app
        
    except (ValueError, ModeValidationError, AppInitializationError) as e:
        logger.error(f"❌ Backend startup failed: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error during backend startup: {e}")
        raise RuntimeError(f"Backend startup failed: {e}")


# FastAPI app instance
try:
    app = main()
except Exception as e:
    logger.error(f"Failed to initialize COA Backend: {e}")
    # Create a minimal error app for debugging
    from fastapi import FastAPI, HTTPException
    
    app = FastAPI(title="COA Backend - Initialization Failed")
    
    @app.get("/health")
    async def health_check():
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/")
    async def root():
        raise HTTPException(
            status_code=503,
            detail=f"Backend initialization failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)