"""
Base model classes used by both BedrockAgent and AgentCore versions.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class BaseConfigModel(BaseModel):
    """Base configuration model with common fields."""
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    version: str = "1.0.0"
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class BaseServiceModel(BaseModel):
    """Base service model with health check capabilities."""
    
    service_name: str
    status: str = "unknown"
    last_health_check: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def mark_healthy(self):
        """Mark service as healthy."""
        self.status = "healthy"
        self.last_health_check = datetime.utcnow()
        self.error_message = None
    
    def mark_unhealthy(self, error: str):
        """Mark service as unhealthy with error message."""
        self.status = "unhealthy"
        self.last_health_check = datetime.utcnow()
        self.error_message = error
    
    def mark_degraded(self, warning: str):
        """Mark service as degraded with warning message."""
        self.status = "degraded"
        self.last_health_check = datetime.utcnow()
        self.error_message = warning


class BaseAgentModel(BaseModel):
    """Base agent model with common agent properties."""
    
    agent_id: str
    agent_name: str
    status: str = "unknown"
    framework: str = "unknown"
    capabilities: list = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None
    
    def update_last_seen(self):
        """Update the last seen timestamp."""
        self.last_seen = datetime.utcnow()


class BaseResponseModel(BaseModel):
    """Base response model with common response fields."""
    
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to the response."""
        self.metadata[key] = value
    
    def mark_success(self, message: str = None):
        """Mark response as successful."""
        self.success = True
        if message:
            self.message = message
    
    def mark_failure(self, message: str):
        """Mark response as failed."""
        self.success = False
        self.message = message


class BaseHealthCheckInterface(ABC):
    """Abstract interface for health check functionality."""
    
    @abstractmethod
    async def health_check(self) -> str:
        """
        Perform health check and return status.
        
        Returns:
            Health status: "healthy", "degraded", or "unhealthy"
        """
        pass
    
    @abstractmethod
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information.
        
        Returns:
            Dictionary with service information
        """
        pass


class BaseServiceInterface(ABC):
    """Abstract interface for service functionality."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the service.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """
        Shutdown the service gracefully.
        
        Returns:
            True if shutdown successful, False otherwise
        """
        pass