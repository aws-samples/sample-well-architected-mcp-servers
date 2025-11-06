"""
Simplified Authentication Service for JWT token validation.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

import jwt
from jwt import PyJWTError

from models.exceptions import AuthenticationError


logger = logging.getLogger(__name__)


class AuthService:
    """Simplified authentication service with JWT validation and rate limiting."""
    
    def __init__(self, jwt_secret: str = "dev-secret", jwt_algorithm: str = "HS256"):
        """
        Initialize the Authentication Service.
        
        Args:
            jwt_secret: Secret key for JWT validation
            jwt_algorithm: JWT algorithm to use
        """
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        
        # Rate limiting storage (in-memory for simplicity)
        self.rate_limits: Dict[str, Dict] = {}
        self.rate_limit_window = 300  # 5 minutes
        self.max_requests_per_window = 100
        
        logger.info("AuthService initialized with simplified JWT validation")

    def validate_token(self, token: str) -> Dict[str, any]:
        """
        Validate JWT token and extract user information.
        
        Args:
            token: JWT token string
            
        Returns:
            Dictionary with user information
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            if not token:
                raise AuthenticationError("No token provided")
            
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Decode and validate token
            payload = jwt.decode(
                token, 
                self.jwt_secret, 
                algorithms=[self.jwt_algorithm]
            )
            
            # Check token expiration
            if 'exp' in payload:
                if datetime.utcnow().timestamp() > payload['exp']:
                    raise AuthenticationError("Token has expired")
            
            # Extract user information
            user_info = {
                "user_id": payload.get("sub", "unknown"),
                "username": payload.get("username", "unknown"),
                "email": payload.get("email", ""),
                "roles": payload.get("roles", []),
                "token_issued_at": payload.get("iat", 0),
                "token_expires_at": payload.get("exp", 0)
            }
            
            logger.debug(f"Token validated for user: {user_info['username']}")
            return user_info
            
        except PyJWTError as e:
            logger.warning(f"JWT validation failed: {e}")
            raise AuthenticationError(f"Invalid token: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise AuthenticationError(f"Token validation error: {e}")

    def create_token(
        self, 
        user_id: str, 
        username: str, 
        email: str = "", 
        roles: list = None,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create a JWT token for testing purposes.
        
        Args:
            user_id: User identifier
            username: Username
            email: User email
            roles: User roles
            expires_in_hours: Token expiration in hours
            
        Returns:
            JWT token string
        """
        try:
            if roles is None:
                roles = ["user"]
            
            now = datetime.utcnow()
            expires_at = now + timedelta(hours=expires_in_hours)
            
            payload = {
                "sub": user_id,
                "username": username,
                "email": email,
                "roles": roles,
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp())
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            logger.debug(f"Created token for user: {username}")
            return token
            
        except Exception as e:
            logger.error(f"Error creating token: {e}")
            raise AuthenticationError(f"Failed to create token: {e}")

    def check_rate_limit(self, identifier: str, max_requests: Optional[int] = None) -> bool:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Unique identifier (user_id, IP, etc.)
            max_requests: Override default max requests
            
        Returns:
            True if within limits, False otherwise
        """
        try:
            current_time = time.time()
            max_reqs = max_requests or self.max_requests_per_window
            
            # Clean up old entries
            self._cleanup_rate_limits(current_time)
            
            # Get or create rate limit entry
            if identifier not in self.rate_limits:
                self.rate_limits[identifier] = {
                    "requests": [],
                    "first_request": current_time
                }
            
            rate_limit_data = self.rate_limits[identifier]
            
            # Check if window has expired
            if current_time - rate_limit_data["first_request"] > self.rate_limit_window:
                # Reset window
                rate_limit_data["requests"] = []
                rate_limit_data["first_request"] = current_time
            
            # Check current request count
            if len(rate_limit_data["requests"]) >= max_reqs:
                logger.warning(f"Rate limit exceeded for {identifier}")
                return False
            
            # Add current request
            rate_limit_data["requests"].append(current_time)
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Allow request on error to avoid blocking legitimate users
            return True

    def get_rate_limit_info(self, identifier: str) -> Dict[str, any]:
        """
        Get rate limit information for an identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Dictionary with rate limit information
        """
        try:
            current_time = time.time()
            
            if identifier not in self.rate_limits:
                return {
                    "requests_made": 0,
                    "requests_remaining": self.max_requests_per_window,
                    "window_reset_time": current_time + self.rate_limit_window,
                    "window_size_seconds": self.rate_limit_window
                }
            
            rate_limit_data = self.rate_limits[identifier]
            
            # Check if window has expired
            if current_time - rate_limit_data["first_request"] > self.rate_limit_window:
                requests_made = 0
                window_reset_time = current_time + self.rate_limit_window
            else:
                requests_made = len(rate_limit_data["requests"])
                window_reset_time = rate_limit_data["first_request"] + self.rate_limit_window
            
            return {
                "requests_made": requests_made,
                "requests_remaining": max(0, self.max_requests_per_window - requests_made),
                "window_reset_time": window_reset_time,
                "window_size_seconds": self.rate_limit_window
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit info: {e}")
            return {
                "requests_made": 0,
                "requests_remaining": self.max_requests_per_window,
                "window_reset_time": time.time() + self.rate_limit_window,
                "window_size_seconds": self.rate_limit_window,
                "error": str(e)
            }

    def _cleanup_rate_limits(self, current_time: float) -> None:
        """Clean up expired rate limit entries."""
        try:
            expired_identifiers = []
            
            for identifier, data in self.rate_limits.items():
                if current_time - data["first_request"] > self.rate_limit_window * 2:
                    expired_identifiers.append(identifier)
            
            for identifier in expired_identifiers:
                del self.rate_limits[identifier]
            
            if expired_identifiers:
                logger.debug(f"Cleaned up {len(expired_identifiers)} expired rate limit entries")
                
        except Exception as e:
            logger.error(f"Error during rate limit cleanup: {e}")

    def validate_user_permissions(self, user_info: Dict[str, any], required_roles: list = None) -> bool:
        """
        Validate user permissions based on roles.
        
        Args:
            user_info: User information from token validation
            required_roles: List of required roles
            
        Returns:
            True if user has required permissions
        """
        try:
            if not required_roles:
                return True
            
            user_roles = user_info.get("roles", [])
            
            # Check if user has any of the required roles
            for role in required_roles:
                if role in user_roles:
                    return True
            
            # Check for admin role (always has access)
            if "admin" in user_roles:
                return True
            
            logger.warning(f"User {user_info.get('username')} lacks required roles: {required_roles}")
            return False
            
        except Exception as e:
            logger.error(f"Error validating user permissions: {e}")
            return False

    def get_auth_stats(self) -> Dict[str, any]:
        """
        Get authentication service statistics.
        
        Returns:
            Dictionary with authentication statistics
        """
        try:
            current_time = time.time()
            
            # Count active rate limit entries
            active_entries = 0
            total_requests = 0
            
            for identifier, data in self.rate_limits.items():
                if current_time - data["first_request"] <= self.rate_limit_window:
                    active_entries += 1
                    total_requests += len(data["requests"])
            
            return {
                "active_rate_limit_entries": active_entries,
                "total_rate_limit_entries": len(self.rate_limits),
                "total_requests_in_window": total_requests,
                "rate_limit_window_seconds": self.rate_limit_window,
                "max_requests_per_window": self.max_requests_per_window,
                "jwt_algorithm": self.jwt_algorithm
            }
            
        except Exception as e:
            logger.error(f"Error getting auth stats: {e}")
            return {
                "error": str(e),
                "active_rate_limit_entries": 0,
                "total_rate_limit_entries": 0
            }