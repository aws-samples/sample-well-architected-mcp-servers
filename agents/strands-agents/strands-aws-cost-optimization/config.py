"""
Configuration module for AWS Billing Management Agent.

This module provides centralized configuration management for the agent,
including environment variables, model settings, and optimization parameters.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Supported log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ModelType(Enum):
    """Supported Bedrock model types."""
    CLAUDE_3_HAIKU = "us.anthropic.claude-3-haiku-20240307-v1:0"
    CLAUDE_3_SONNET = "us.anthropic.claude-3-sonnet-20240229-v1:0"
    CLAUDE_3_5_SONNET = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    CLAUDE_3_7_SONNET = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"


@dataclass
class AgentConfig:
    """Configuration class for AWS Billing Management Agent."""
    
    # Model Configuration
    model_id: str = ModelType.CLAUDE_3_7_SONNET.value
    model_temperature: float = 0.1
    model_max_tokens: int = 4000
    
    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_profile: Optional[str] = None
    
    # MCP Server Configuration
    mcp_server_command: str = "awslabs.billing-cost-management-mcp-server"
    mcp_working_dir: str = "/tmp/aws-billing-mcp/workdir"
    mcp_timeout: int = 300  # 5 minutes
    mcp_max_retries: int = 3
    
    # Logging Configuration
    log_level: LogLevel = LogLevel.INFO
    bedrock_log_group: Optional[str] = None
    
    # Performance Configuration
    enable_caching: bool = True
    cache_ttl: int = 3600  # 1 hour
    max_concurrent_requests: int = 5
    
    # Cost Analysis Configuration
    default_cost_period_days: int = 30
    cost_threshold_warning: float = 1000.0  # USD
    cost_threshold_critical: float = 5000.0  # USD
    
    # Optimization Configuration
    min_savings_threshold: float = 50.0  # Minimum savings to recommend (USD)
    ri_utilization_threshold: float = 0.8  # 80% utilization threshold
    savings_plans_utilization_threshold: float = 0.8
    
    @classmethod
    def from_environment(cls) -> 'AgentConfig':
        """Create configuration from environment variables."""
        return cls(
            # Model Configuration
            model_id=os.getenv("BEDROCK_MODEL_ID", cls.model_id),
            model_temperature=float(os.getenv("BEDROCK_MODEL_TEMPERATURE", cls.model_temperature)),
            model_max_tokens=int(os.getenv("BEDROCK_MODEL_MAX_TOKENS", cls.model_max_tokens)),
            
            # AWS Configuration
            aws_region=os.getenv("AWS_REGION", cls.aws_region),
            aws_profile=os.getenv("AWS_PROFILE"),
            
            # MCP Configuration
            mcp_server_command=os.getenv("MCP_SERVER_COMMAND", cls.mcp_server_command),
            mcp_working_dir=os.getenv("AWS_API_MCP_WORKING_DIR", cls.mcp_working_dir),
            mcp_timeout=int(os.getenv("MCP_CLIENT_TIMEOUT", cls.mcp_timeout)),
            mcp_max_retries=int(os.getenv("MCP_MAX_RETRIES", cls.mcp_max_retries)),
            
            # Logging Configuration
            log_level=LogLevel(os.getenv("FASTMCP_LOG_LEVEL", cls.log_level.value)),
            bedrock_log_group=os.getenv("BEDROCK_LOG_GROUP_NAME"),
            
            # Performance Configuration
            enable_caching=os.getenv("ENABLE_CACHING", "true").lower() == "true",
            cache_ttl=int(os.getenv("CACHE_TTL", cls.cache_ttl)),
            max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", cls.max_concurrent_requests)),
            
            # Cost Analysis Configuration
            default_cost_period_days=int(os.getenv("DEFAULT_COST_PERIOD_DAYS", cls.default_cost_period_days)),
            cost_threshold_warning=float(os.getenv("COST_THRESHOLD_WARNING", cls.cost_threshold_warning)),
            cost_threshold_critical=float(os.getenv("COST_THRESHOLD_CRITICAL", cls.cost_threshold_critical)),
            
            # Optimization Configuration
            min_savings_threshold=float(os.getenv("MIN_SAVINGS_THRESHOLD", cls.min_savings_threshold)),
            ri_utilization_threshold=float(os.getenv("RI_UTILIZATION_THRESHOLD", cls.ri_utilization_threshold)),
            savings_plans_utilization_threshold=float(os.getenv("SP_UTILIZATION_THRESHOLD", cls.savings_plans_utilization_threshold)),
        )
    
    def to_mcp_env(self) -> Dict[str, str]:
        """Convert configuration to MCP environment variables."""
        env = {
            "AWS_REGION": self.aws_region,
            "AWS_API_MCP_WORKING_DIR": self.mcp_working_dir,
            "FASTMCP_LOG_LEVEL": self.log_level.value,
            "MCP_CLIENT_TIMEOUT": str(self.mcp_timeout),
            "MCP_MAX_RETRIES": str(self.mcp_max_retries),
        }
        
        if self.aws_profile:
            env["AWS_PROFILE"] = self.aws_profile
            
        if self.bedrock_log_group:
            env["BEDROCK_LOG_GROUP_NAME"] = self.bedrock_log_group
            
        return env
    
    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.model_temperature < 0 or self.model_temperature > 1:
            raise ValueError("Model temperature must be between 0 and 1")
            
        if self.model_max_tokens < 100 or self.model_max_tokens > 8000:
            raise ValueError("Model max tokens must be between 100 and 8000")
            
        if self.mcp_timeout < 30:
            raise ValueError("MCP timeout must be at least 30 seconds")
            
        if self.mcp_max_retries < 1 or self.mcp_max_retries > 10:
            raise ValueError("MCP max retries must be between 1 and 10")
            
        if self.min_savings_threshold < 0:
            raise ValueError("Minimum savings threshold must be non-negative")
            
        if not (0 < self.ri_utilization_threshold <= 1):
            raise ValueError("RI utilization threshold must be between 0 and 1")
            
        if not (0 < self.savings_plans_utilization_threshold <= 1):
            raise ValueError("Savings Plans utilization threshold must be between 0 and 1")


# Global configuration instance
config = AgentConfig.from_environment()

# Validate configuration on import
try:
    config.validate()
except ValueError as e:
    print(f"Configuration validation error: {e}")
    # Use default configuration
    config = AgentConfig()


def get_config() -> AgentConfig:
    """Get the global configuration instance."""
    return config


def update_config(**kwargs) -> None:
    """Update configuration parameters."""
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            raise ValueError(f"Unknown configuration parameter: {key}")
    
    # Validate updated configuration
    config.validate()


# Cost optimization presets
COST_OPTIMIZATION_PRESETS = {
    "aggressive": {
        "min_savings_threshold": 10.0,
        "ri_utilization_threshold": 0.7,
        "savings_plans_utilization_threshold": 0.7,
    },
    "balanced": {
        "min_savings_threshold": 50.0,
        "ri_utilization_threshold": 0.8,
        "savings_plans_utilization_threshold": 0.8,
    },
    "conservative": {
        "min_savings_threshold": 100.0,
        "ri_utilization_threshold": 0.9,
        "savings_plans_utilization_threshold": 0.9,
    }
}


def apply_preset(preset_name: str) -> None:
    """Apply a cost optimization preset."""
    if preset_name not in COST_OPTIMIZATION_PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(COST_OPTIMIZATION_PRESETS.keys())}")
    
    preset = COST_OPTIMIZATION_PRESETS[preset_name]
    update_config(**preset)
    print(f"Applied {preset_name} cost optimization preset")


# Environment-specific configurations
ENVIRONMENT_CONFIGS = {
    "development": {
        "log_level": LogLevel.DEBUG,
        "mcp_timeout": 60,
        "enable_caching": False,
    },
    "staging": {
        "log_level": LogLevel.INFO,
        "mcp_timeout": 180,
        "enable_caching": True,
    },
    "production": {
        "log_level": LogLevel.WARNING,
        "mcp_timeout": 300,
        "enable_caching": True,
        "max_concurrent_requests": 10,
    }
}


def apply_environment_config(environment: str) -> None:
    """Apply environment-specific configuration."""
    if environment not in ENVIRONMENT_CONFIGS:
        raise ValueError(f"Unknown environment: {environment}. Available: {list(ENVIRONMENT_CONFIGS.keys())}")
    
    env_config = ENVIRONMENT_CONFIGS[environment]
    update_config(**env_config)
    print(f"Applied {environment} environment configuration")


if __name__ == "__main__":
    # Configuration testing
    print("AWS Billing Management Agent Configuration")
    print("=" * 50)
    print(f"Model ID: {config.model_id}")
    print(f"AWS Region: {config.aws_region}")
    print(f"Log Level: {config.log_level.value}")
    print(f"MCP Timeout: {config.mcp_timeout}s")
    print(f"Min Savings Threshold: ${config.min_savings_threshold}")
    print(f"RI Utilization Threshold: {config.ri_utilization_threshold * 100}%")
    
    # Test environment variables
    print("\nMCP Environment Variables:")
    for key, value in config.to_mcp_env().items():
        print(f"  {key}: {value}")