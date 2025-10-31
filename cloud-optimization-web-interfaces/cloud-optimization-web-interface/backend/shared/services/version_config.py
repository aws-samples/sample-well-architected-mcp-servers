"""
Backend version management service for mode detection and validation.
"""

import os
import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BackendVersion(Enum):
    """Backend version types."""
    BEDROCKAGENT = "bedrockagent"
    AGENTCORE = "agentcore"


class VersionConfigService:
    """Service for managing backend version configuration and validation."""
    
    def __init__(self):
        """Initialize version configuration service."""
        self.current_version = self._detect_version()
        self.version_info = self._get_version_info()
        
    def _detect_version(self) -> BackendVersion:
        """Detect current backend version from environment."""
        version_str = os.getenv("BACKEND_MODE", "agentcore").lower()
        
        try:
            return BackendVersion(version_str)
        except ValueError:
            logger.warning(f"Invalid BACKEND_MODE: {version_str}, defaulting to agentcore")
            return BackendVersion.AGENTCORE
    
    def _get_version_info(self) -> Dict[str, Any]:
        """Get version information and metadata."""
        return {
            "version": self.current_version.value,
            "detected_at": datetime.utcnow().isoformat(),
            "environment_variable": os.getenv("BACKEND_MODE"),
            "default_used": os.getenv("BACKEND_MODE") is None,
            "param_prefix": os.getenv("PARAM_PREFIX", "coa"),
            "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        }
    
    def get_backend_version(self) -> BackendVersion:
        """Get current backend version."""
        return self.current_version
    
    def is_bedrockagent_version(self) -> bool:
        """Check if running BedrockAgent version."""
        return self.current_version == BackendVersion.BEDROCKAGENT
    
    def is_agentcore_version(self) -> bool:
        """Check if running AgentCore version."""
        return self.current_version == BackendVersion.AGENTCORE
    
    def get_version_config(self) -> Dict[str, Any]:
        """Get version-specific configuration."""
        if self.current_version == BackendVersion.BEDROCKAGENT:
            return self._get_bedrockagent_config()
        else:
            return self._get_agentcore_config()
    
    def _get_bedrockagent_config(self) -> Dict[str, Any]:
        """Get BedrockAgent-specific configuration."""
        return {
            "version": "bedrockagent",
            "features": {
                "traditional_agents": True,
                "mcp_integration": True,
                "strands_agents": False,
                "agentcore_runtime": False
            },
            "services": {
                "bedrock_agent_service": True,
                "mcp_client_service": True,
                "llm_orchestrator_service": True,
                "strands_discovery": False,
                "agentcore_invocation": False
            },
            "fallback_mode": False
        }
    
    def _get_agentcore_config(self) -> Dict[str, Any]:
        """Get AgentCore-specific configuration."""
        return {
            "version": "agentcore",
            "features": {
                "traditional_agents": False,
                "mcp_integration": False,
                "strands_agents": True,
                "agentcore_runtime": True
            },
            "services": {
                "bedrock_agent_service": False,
                "mcp_client_service": False,
                "llm_orchestrator_service": False,
                "strands_discovery": True,
                "agentcore_invocation": True
            },
            "fallback_mode": True,  # Can fall back to minimal mode
            "graceful_degradation": True
        }
    
    def validate_version_constraints(self) -> Dict[str, Any]:
        """Validate version-specific constraints."""
        validation_result = {
            "valid": True,
            "version": self.current_version.value,
            "errors": [],
            "warnings": [],
            "recommendations": []
        }
        
        if self.current_version == BackendVersion.BEDROCKAGENT:
            validation_result.update(self._validate_bedrockagent_constraints())
        else:
            validation_result.update(self._validate_agentcore_constraints())
        
        return validation_result
    
    def _validate_bedrockagent_constraints(self) -> Dict[str, Any]:
        """Validate BedrockAgent-specific constraints."""
        errors = []
        warnings = []
        recommendations = []
        
        # Check for AgentCore-specific environment variables
        agentcore_vars = ["PARAM_PREFIX", "AGENTCORE_PERIODIC_DISCOVERY_ENABLED"]
        for var in agentcore_vars:
            if os.getenv(var):
                warnings.append(f"AgentCore environment variable {var} set in BedrockAgent mode")
        
        # Check required BedrockAgent configuration
        required_vars = ["ENHANCED_SECURITY_AGENT_ID", "ENHANCED_SECURITY_AGENT_ALIAS_ID"]
        for var in required_vars:
            if not os.getenv(var):
                recommendations.append(f"Consider setting {var} for enhanced BedrockAgent functionality")
        
        return {
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations,
            "valid": len(errors) == 0
        }
    
    def _validate_agentcore_constraints(self) -> Dict[str, Any]:
        """Validate AgentCore-specific constraints."""
        errors = []
        warnings = []
        recommendations = []
        
        # Check for required AgentCore configuration
        param_prefix = os.getenv("PARAM_PREFIX")
        if not param_prefix:
            warnings.append("PARAM_PREFIX not set, using default 'coa'")
            recommendations.append("Set PARAM_PREFIX environment variable for proper AgentCore configuration")
        
        # Check AWS region configuration
        aws_region = os.getenv("AWS_DEFAULT_REGION")
        if not aws_region:
            warnings.append("AWS_DEFAULT_REGION not set, using default 'us-east-1'")
        
        # Check for BedrockAgent-specific variables that might cause confusion
        bedrock_vars = ["ENHANCED_SECURITY_AGENT_ID", "ENHANCED_SECURITY_AGENT_ALIAS_ID"]
        for var in bedrock_vars:
            if os.getenv(var):
                warnings.append(f"BedrockAgent environment variable {var} set in AgentCore mode")
        
        return {
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations,
            "valid": len(errors) == 0
        }
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """Get feature flags based on current version."""
        config = self.get_version_config()
        return config.get("features", {})
    
    def get_service_flags(self) -> Dict[str, bool]:
        """Get service flags based on current version."""
        config = self.get_version_config()
        return config.get("services", {})
    
    def supports_graceful_degradation(self) -> bool:
        """Check if current version supports graceful degradation."""
        config = self.get_version_config()
        return config.get("graceful_degradation", False)
    
    def get_version_summary(self) -> Dict[str, Any]:
        """Get comprehensive version summary."""
        validation = self.validate_version_constraints()
        
        return {
            "version_info": self.version_info,
            "configuration": self.get_version_config(),
            "validation": validation,
            "feature_flags": self.get_feature_flags(),
            "service_flags": self.get_service_flags(),
            "supports_degradation": self.supports_graceful_degradation(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def health_check(self) -> str:
        """Perform health check for version configuration."""
        try:
            validation = self.validate_version_constraints()
            
            if not validation["valid"]:
                return "unhealthy"
            elif validation["warnings"]:
                return "degraded"
            else:
                return "healthy"
                
        except Exception as e:
            logger.error(f"Version config health check failed: {e}")
            return "unhealthy"


# Global version config service instance
_version_config_service: Optional[VersionConfigService] = None


def get_version_config_service() -> VersionConfigService:
    """Get global version configuration service instance."""
    global _version_config_service
    
    if _version_config_service is None:
        _version_config_service = VersionConfigService()
    
    return _version_config_service


def get_backend_version() -> BackendVersion:
    """Get current backend version."""
    return get_version_config_service().get_backend_version()


def is_bedrockagent_version() -> bool:
    """Check if running BedrockAgent version."""
    return get_version_config_service().is_bedrockagent_version()


def is_agentcore_version() -> bool:
    """Check if running AgentCore version."""
    return get_version_config_service().is_agentcore_version()


def get_version_specific_config() -> Dict[str, Any]:
    """Get version-specific configuration."""
    return get_version_config_service().get_version_config()