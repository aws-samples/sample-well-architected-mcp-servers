"""Data models for environment detection and credential management."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class EnvironmentType(Enum):
    """Supported AWS compute environment types."""
    EC2 = "ec2"
    ECS = "ecs"
    EKS = "eks"
    LAMBDA = "lambda"
    BEDROCK_AGENTCORE = "bedrock-agentcore"
    FARGATE = "fargate"
    LOCAL = "local"


@dataclass
class EnvironmentInfo:
    """Information about the detected AWS hosting environment."""
    
    environment_type: EnvironmentType
    role_arn: Optional[str] = None
    region: str = "us-east-1"
    account_id: Optional[str] = None
    
    # Environment-specific identifiers
    instance_id: Optional[str] = None  # EC2
    task_arn: Optional[str] = None     # ECS/Fargate
    pod_name: Optional[str] = None     # EKS
    service_account: Optional[str] = None  # EKS
    function_name: Optional[str] = None    # Lambda
    runtime_id: Optional[str] = None       # Bedrock AgentCore
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate environment information after initialization."""
        if self.environment_type == EnvironmentType.EC2 and not self.instance_id:
            self.metadata.setdefault("warnings", []).append("EC2 environment detected but no instance ID found")
        
        if self.environment_type == EnvironmentType.ECS and not self.task_arn:
            self.metadata.setdefault("warnings", []).append("ECS environment detected but no task ARN found")
        
        if self.environment_type == EnvironmentType.EKS and not (self.pod_name or self.service_account):
            self.metadata.setdefault("warnings", []).append("EKS environment detected but no pod name or service account found")
        
        if self.environment_type == EnvironmentType.LAMBDA and not self.function_name:
            self.metadata.setdefault("warnings", []).append("Lambda environment detected but no function name found")
        
        if self.environment_type == EnvironmentType.BEDROCK_AGENTCORE and not self.runtime_id:
            self.metadata.setdefault("warnings", []).append("Bedrock AgentCore environment detected but no runtime ID found")


@dataclass
class ValidationResult:
    """Result of validation operations with detailed feedback."""
    
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, message: str) -> None:
        """Add an error message and mark validation as invalid."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
    
    def add_recommendation(self, message: str) -> None:
        """Add a recommendation message."""
        self.recommendations.append(message)
    
    def add_detail(self, key: str, value: Any) -> None:
        """Add detailed information."""
        self.details[key] = value
    
    @property
    def has_issues(self) -> bool:
        """Check if there are any errors or warnings."""
        return len(self.errors) > 0 or len(self.warnings) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "details": self.details,
            "has_issues": self.has_issues
        }


@dataclass
class RoleConfiguration:
    """Configuration for cross-account role assumption."""
    
    role_arn: str
    target_account: str
    external_id: Optional[str] = None
    session_name: str = "mcp-server-session"
    permissions: List[str] = field(default_factory=list)
    trust_policy: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate role configuration after initialization."""
        if not self.role_arn.startswith("arn:aws:iam::"):
            raise ValueError(f"Invalid role ARN format: {self.role_arn}")
        
        if not self.target_account.isdigit() or len(self.target_account) != 12:
            raise ValueError(f"Invalid AWS account ID: {self.target_account}")
        
        if self.external_id and (len(self.external_id) < 2 or len(self.external_id) > 1224):
            raise ValueError(f"External ID must be between 2 and 1224 characters: {len(self.external_id)}")
        
        if len(self.session_name) < 2 or len(self.session_name) > 64:
            raise ValueError(f"Session name must be between 2 and 64 characters: {len(self.session_name)}")
    
    @classmethod
    def from_arn(cls, role_arn: str, external_id: Optional[str] = None, session_name: str = "mcp-server-session") -> "RoleConfiguration":
        """Create role configuration from ARN."""
        # Extract account ID from ARN: arn:aws:iam::123456789012:role/RoleName
        try:
            arn_parts = role_arn.split(":")
            if len(arn_parts) >= 5:
                target_account = arn_parts[4]
            else:
                raise ValueError("Invalid ARN format")
        except (IndexError, ValueError) as e:
            raise ValueError(f"Could not extract account ID from ARN {role_arn}: {e}")
        
        return cls(
            role_arn=role_arn,
            target_account=target_account,
            external_id=external_id,
            session_name=session_name
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert role configuration to dictionary."""
        return {
            "role_arn": self.role_arn,
            "target_account": self.target_account,
            "external_id": self.external_id,
            "session_name": self.session_name,
            "permissions": self.permissions,
            "trust_policy": self.trust_policy
        }


@dataclass
class MetadataServiceInfo:
    """Information retrieved from AWS metadata services."""
    
    service_type: str  # "ec2", "ecs", "eks", "lambda", "bedrock-agentcore"
    endpoint_url: Optional[str] = None
    token: Optional[str] = None
    available: bool = False
    response_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def mark_available(self, endpoint_url: str, response_data: Dict[str, Any]) -> None:
        """Mark metadata service as available with response data."""
        self.available = True
        self.endpoint_url = endpoint_url
        self.response_data = response_data
        self.error_message = None
    
    def mark_unavailable(self, error_message: str) -> None:
        """Mark metadata service as unavailable with error message."""
        self.available = False
        self.error_message = error_message
        self.response_data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata service info to dictionary."""
        return {
            "service_type": self.service_type,
            "endpoint_url": self.endpoint_url,
            "available": self.available,
            "response_data": self.response_data,
            "error_message": self.error_message
        }


# Custom exceptions for environment detection
class EnvironmentDetectionError(Exception):
    """Base exception for environment detection errors."""
    pass


class MetadataServiceError(EnvironmentDetectionError):
    """Exception raised when metadata service is unavailable or returns invalid data."""
    pass


class RoleDiscoveryError(EnvironmentDetectionError):
    """Exception raised when IAM role cannot be discovered from environment."""
    pass


class CredentialValidationError(Exception):
    """Exception raised when credential validation fails."""
    pass


class CrossAccountAccessError(Exception):
    """Exception raised when cross-account access validation fails."""
    pass