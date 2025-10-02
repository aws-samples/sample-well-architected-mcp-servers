"""
Exception classes for the simplified backend refactor.
"""

from typing import Any, Dict, Optional


class COABaseException(Exception):
    """Base exception class for Cloud Optimization Assistant."""
    
    def __init__(self, message: str, error_code: str = "COA_ERROR", 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class AgentDiscoveryError(COABaseException):
    """Exception raised when agent discovery fails."""
    
    def __init__(self, message: str, agent_id: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AGENT_DISCOVERY_ERROR", details)
        self.agent_id = agent_id


class BedrockCommunicationError(COABaseException):
    """Exception raised when Bedrock communication fails."""
    
    def __init__(self, message: str, service_type: str = "unknown",
                 target_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "BEDROCK_COMMUNICATION_ERROR", details)
        self.service_type = service_type  # 'model' or 'agent'
        self.target_id = target_id


class SessionManagementError(COABaseException):
    """Exception raised when session management operations fail."""
    
    def __init__(self, message: str, session_id: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "SESSION_MANAGEMENT_ERROR", details)
        self.session_id = session_id


class CommandProcessingError(COABaseException):
    """Exception raised when agent command processing fails."""
    
    def __init__(self, message: str, command: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "COMMAND_PROCESSING_ERROR", details)
        self.command = command


class ConfigurationError(COABaseException):
    """Exception raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)
        self.config_key = config_key


class AuthenticationError(COABaseException):
    """Exception raised when authentication fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHENTICATION_ERROR", details)


class RateLimitError(COABaseException):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "RATE_LIMIT_ERROR", details)
        self.retry_after = retry_after


class ValidationError(COABaseException):
    """Exception raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


# Legacy exception classes for backward compatibility
class BackendError(COABaseException):
    """Base exception for backend errors."""
    pass


class AgentManagerError(COABaseException):
    """Exception raised by Agent Manager operations."""
    pass


class BedrockServiceError(COABaseException):
    """Exception raised by Bedrock Service operations."""
    pass


class ModelInvocationError(BedrockServiceError):
    """Exception raised when model invocation fails."""
    pass


class AgentInvocationError(BedrockServiceError):
    """Exception raised when agent invocation fails."""
    pass


class QueryRouterError(COABaseException):
    """Exception raised by Query Router operations."""
    pass