"""
CORS middleware configuration for both BedrockAgent and AgentCore versions.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os


def add_cors_middleware(
    app: FastAPI,
    allowed_origins: Optional[List[str]] = None,
    allow_credentials: bool = True,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None
) -> None:
    """
    Add CORS middleware to FastAPI application.
    
    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origins (defaults to development origins)
        allow_credentials: Whether to allow credentials
        allow_methods: List of allowed HTTP methods
        allow_headers: List of allowed headers
    """
    # Default allowed origins for development
    if allowed_origins is None:
        allowed_origins = get_default_cors_origins()
    
    # Default allowed methods
    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"]
    
    # Default allowed headers
    if allow_headers is None:
        allow_headers = [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Request-ID",
            "X-Session-ID"
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )


def get_default_cors_origins() -> List[str]:
    """
    Get default CORS origins based on environment.
    
    Returns:
        List of allowed origins
    """
    # Base development origins
    default_origins = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "null",  # Allow file:// origins for local development
    ]
    
    # Add environment-specific origins
    custom_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if custom_origins:
        # Parse comma-separated origins
        additional_origins = [origin.strip() for origin in custom_origins.split(",")]
        default_origins.extend(additional_origins)
    
    # Add production origins based on environment
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        # Add production-specific origins
        production_origins = get_production_cors_origins()
        default_origins.extend(production_origins)
    
    return default_origins


def get_production_cors_origins() -> List[str]:
    """
    Get production CORS origins.
    
    Returns:
        List of production origins
    """
    production_origins = []
    
    # CloudFront distribution URL
    cloudfront_url = os.getenv("CLOUDFRONT_DISTRIBUTION_URL")
    if cloudfront_url:
        production_origins.append(cloudfront_url)
    
    # ALB URL
    alb_url = os.getenv("ALB_URL")
    if alb_url:
        production_origins.append(alb_url)
    
    # Custom domain
    custom_domain = os.getenv("CUSTOM_DOMAIN")
    if custom_domain:
        production_origins.extend([
            f"https://{custom_domain}",
            f"https://www.{custom_domain}"
        ])
    
    return production_origins


def get_cors_config_for_version(version: str) -> dict:
    """
    Get CORS configuration specific to backend version.
    
    Args:
        version: Backend version ("bedrockagent" or "agentcore")
        
    Returns:
        Dictionary with CORS configuration
    """
    base_config = {
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
        "allow_headers": [
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "X-Request-ID",
            "X-Session-ID",
            f"X-Backend-Version"  # Add version header
        ]
    }
    
    if version == "bedrockagent":
        base_config["allow_headers"].extend([
            "X-Agent-ID",
            "X-Agent-Alias-ID",
            "X-MCP-Server"
        ])
    elif version == "agentcore":
        base_config["allow_headers"].extend([
            "X-Strands-Agent",
            "X-AgentCore-Session",
            "X-Parameter-Prefix"
        ])
    
    return base_config


def configure_cors_for_version(app: FastAPI, version: str) -> None:
    """
    Configure CORS middleware for specific backend version.
    
    Args:
        app: FastAPI application instance
        version: Backend version ("bedrockagent" or "agentcore")
    """
    cors_config = get_cors_config_for_version(version)
    allowed_origins = get_default_cors_origins()
    
    add_cors_middleware(
        app=app,
        allowed_origins=allowed_origins,
        **cors_config
    )


class CORSConfigManager:
    """Manager for CORS configuration across different environments."""
    
    def __init__(self, version: str):
        """
        Initialize CORS config manager.
        
        Args:
            version: Backend version
        """
        self.version = version
        self.environment = os.getenv("ENVIRONMENT", "development")
    
    def get_allowed_origins(self) -> List[str]:
        """Get allowed origins for current environment."""
        if self.environment == "production":
            return self._get_production_origins()
        elif self.environment == "staging":
            return self._get_staging_origins()
        else:
            return self._get_development_origins()
    
    def _get_development_origins(self) -> List[str]:
        """Get development origins."""
        return [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "null"
        ]
    
    def _get_staging_origins(self) -> List[str]:
        """Get staging origins."""
        staging_origins = self._get_development_origins()
        
        # Add staging-specific origins
        staging_domain = os.getenv("STAGING_DOMAIN")
        if staging_domain:
            staging_origins.extend([
                f"https://{staging_domain}",
                f"https://staging.{staging_domain}"
            ])
        
        return staging_origins
    
    def _get_production_origins(self) -> List[str]:
        """Get production origins."""
        return get_production_cors_origins()
    
    def apply_to_app(self, app: FastAPI) -> None:
        """Apply CORS configuration to FastAPI app."""
        cors_config = get_cors_config_for_version(self.version)
        allowed_origins = self.get_allowed_origins()
        
        add_cors_middleware(
            app=app,
            allowed_origins=allowed_origins,
            **cors_config
        )
    
    def get_config_summary(self) -> dict:
        """Get CORS configuration summary."""
        return {
            "version": self.version,
            "environment": self.environment,
            "allowed_origins": self.get_allowed_origins(),
            "cors_config": get_cors_config_for_version(self.version)
        }