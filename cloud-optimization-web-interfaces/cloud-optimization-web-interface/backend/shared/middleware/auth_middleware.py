"""
Authentication middleware for both BedrockAgent and AgentCore versions.
"""

import os
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, Callable
import logging

from shared.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Authentication middleware for FastAPI applications."""
    
    def __init__(self, auth_service: AuthService, skip_auth_paths: Optional[list] = None, disable_auth: bool = False):
        """
        Initialize authentication middleware.
        
        Args:
            auth_service: Authentication service instance
            skip_auth_paths: List of paths to skip authentication for
            disable_auth: Whether to disable authentication entirely (for local testing)
        """
        self.auth_service = auth_service
        self.skip_auth_paths = skip_auth_paths or self._get_default_skip_paths()
        self.security = HTTPBearer(auto_error=False)
        self.disable_auth = disable_auth or self._should_disable_auth()
        
        if self.disable_auth:
            logger.warning("🚨 Authentication is DISABLED for local testing. Do not use in production!")
    
    def _should_disable_auth(self) -> bool:
        """Check if authentication should be disabled based on environment variables."""
        # Check for explicit disable flag
        if os.getenv("DISABLE_AUTH", "false").lower() in ["true", "1", "yes"]:
            return True
        
        # Check for local testing environment
        if os.getenv("ENVIRONMENT", "").lower() in ["local", "test", "development"]:
            return True
        
        # Check if running in local mode (localhost)
        if os.getenv("BACKEND_MODE") and "localhost" in os.getenv("API_BASE_URL", ""):
            return True
        
        return False
    
    def _get_default_skip_paths(self) -> list:
        """Get default paths that skip authentication."""
        return [
            "/health",
            "/health/detailed",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/mcp/status",
            "/api/agents/status",
            "/agents",  # For local testing
            "/api/prompt-templates"
        ]
    
    async def __call__(self, request: Request, call_next):
        """
        Process request through authentication middleware.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response from next middleware/endpoint
        """
        # If authentication is disabled, create a mock user and skip all auth checks
        if self.disable_auth:
            # Create a mock user for local testing
            request.state.user = {
                "sub": "local-test-user",
                "email": "test@localhost",
                "name": "Local Test User",
                "groups": ["local-testing"],
                "auth_disabled": True
            }
            return await call_next(request)
        
        # Skip authentication for certain paths
        if self._should_skip_auth(request.url.path):
            return await call_next(request)
        
        # Extract and validate token
        try:
            credentials = await self.security(request)
            if credentials:
                user = await self.auth_service.verify_token(credentials.credentials)
                # Add user to request state
                request.state.user = user
            else:
                # No credentials provided
                if self._is_auth_required(request.url.path):
                    raise HTTPException(
                        status_code=401,
                        detail="Authentication required"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
        
        return await call_next(request)
    
    def _should_skip_auth(self, path: str) -> bool:
        """Check if authentication should be skipped for path."""
        return any(path.startswith(skip_path) for skip_path in self.skip_auth_paths)
    
    def _is_auth_required(self, path: str) -> bool:
        """Check if authentication is required for path."""
        # Authentication is required for API endpoints by default
        return path.startswith("/api/")


def create_auth_dependency(auth_service: AuthService) -> Callable:
    """
    Create authentication dependency for FastAPI endpoints.
    
    Args:
        auth_service: Authentication service instance
        
    Returns:
        Authentication dependency function
    """
    security = HTTPBearer()
    
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> Dict[str, Any]:
        """
        Get current authenticated user.
        
        Args:
            credentials: HTTP authorization credentials
            
        Returns:
            User information dictionary
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            user = await auth_service.verify_token(credentials.credentials)
            return user
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials"
            )
    
    return get_current_user


def create_optional_auth_dependency(auth_service: AuthService) -> Callable:
    """
    Create optional authentication dependency for FastAPI endpoints.
    
    Args:
        auth_service: Authentication service instance
        
    Returns:
        Optional authentication dependency function
    """
    security = HTTPBearer(auto_error=False)
    
    async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> Optional[Dict[str, Any]]:
        """
        Get current authenticated user (optional).
        
        Args:
            credentials: HTTP authorization credentials (optional)
            
        Returns:
            User information dictionary or None if not authenticated
        """
        if not credentials:
            return None
        
        try:
            user = await auth_service.verify_token(credentials.credentials)
            return user
        except Exception as e:
            logger.warning(f"Optional authentication failed: {e}")
            return None
    
    return get_current_user_optional


class AuthConfig:
    """Configuration for authentication middleware."""
    
    def __init__(self, version: str):
        """
        Initialize auth configuration.
        
        Args:
            version: Backend version ("bedrockagent" or "agentcore")
        """
        self.version = version
        self.skip_auth_paths = self._get_version_specific_skip_paths()
    
    def _get_version_specific_skip_paths(self) -> list:
        """Get version-specific paths that skip authentication."""
        base_paths = [
            "/health",
            "/health/detailed",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/mcp/status",
            "/api/agents/status",
            "/agents",  # For local testing
            "/api/prompt-templates"
        ]
        
        if self.version == "bedrockagent":
            base_paths.extend([
                "/api/orchestration/status",
                "/api/orchestration/config",
                "/api/mcp/servers",
                "/api/mcp/tools"
            ])
        elif self.version == "agentcore":
            base_paths.extend([
                "/api/agentcore/status",
                "/api/debug/strands-agents",
                "/api/parameter-manager/config"
            ])
        
        return base_paths
    
    def create_middleware(self, auth_service: AuthService, disable_auth: bool = False) -> AuthMiddleware:
        """Create authentication middleware with version-specific configuration."""
        return AuthMiddleware(
            auth_service=auth_service,
            skip_auth_paths=self.skip_auth_paths,
            disable_auth=disable_auth
        )


def setup_authentication(app, auth_service: AuthService, version: str, disable_auth: bool = False) -> Callable:
    """
    Set up authentication for FastAPI application.
    
    Args:
        app: FastAPI application instance
        auth_service: Authentication service instance
        version: Backend version
        disable_auth: Whether to disable authentication for local testing
        
    Returns:
        Authentication dependency function
    """
    # Create version-specific auth config
    auth_config = AuthConfig(version)
    
    # Add authentication middleware
    auth_middleware = auth_config.create_middleware(auth_service, disable_auth=disable_auth)
    app.middleware("http")(auth_middleware)
    
    # Create and return auth dependency
    return create_auth_dependency(auth_service)


def get_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get user information from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User information dictionary or None
    """
    return getattr(request.state, 'user', None)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""
    pass


class AuthorizationError(Exception):
    """Exception raised for authorization errors."""
    pass