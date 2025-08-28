# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Configuration management for Enhanced Security Agent with Multi-MCP Integration
Handles configuration for multiple MCP servers and deployment environments
"""

import json
import os
import boto3
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from .interfaces import MCPServerConfig, MCPServerType

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class AuthConfig:
    """Authentication configuration for MCP servers"""
    type: str  # 'bearer', 'aws_iam', 'api_key', 'none'
    credentials: Dict[str, str]
    refresh_mechanism: Optional[str] = None
    token_expiry: Optional[int] = None


@dataclass
class RetryConfig:
    """Retry configuration for MCP server calls"""
    max_attempts: int = 3
    backoff_factor: float = 2.0
    max_delay: int = 60
    exponential_base: float = 2.0


@dataclass
class HealthCheckConfig:
    """Health check configuration for MCP servers"""
    enabled: bool = True
    interval: int = 300  # seconds
    timeout: int = 30
    failure_threshold: int = 3
    recovery_threshold: int = 2


@dataclass
class EnhancedMCPServerConfig(MCPServerConfig):
    """Enhanced MCP server configuration with additional settings"""
    auth_config: AuthConfig
    retry_config: RetryConfig
    health_check_config: HealthCheckConfig
    feature_flags: Dict[str, bool]
    region_specific: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedMCPServerConfig':
        """Create configuration from dictionary"""
        # Extract nested configurations
        auth_config = AuthConfig(**data.pop('auth_config', {}))
        retry_config = RetryConfig(**data.pop('retry_config', {}))
        health_check_config = HealthCheckConfig(**data.pop('health_check_config', {}))
        
        return cls(
            auth_config=auth_config,
            retry_config=retry_config,
            health_check_config=health_check_config,
            **data
        )


class MCPConfigurationManager:
    """Manages configuration for multiple MCP servers across environments"""
    
    def __init__(self, environment: Environment = Environment.DEVELOPMENT, region: str = "us-east-1"):
        self.environment = environment
        self.region = region
        self.ssm_client = boto3.client('ssm', region_name=region)
        self.secrets_client = boto3.client('secretsmanager', region_name=region)
        self._configs: Dict[str, EnhancedMCPServerConfig] = {}
        self._feature_flags: Dict[str, bool] = {}
    
    def get_default_security_mcp_config(self) -> EnhancedMCPServerConfig:
        """Get default configuration for Security MCP Server"""
        return EnhancedMCPServerConfig(
            name="security",
            server_type=MCPServerType.SECURITY,
            connection_type="agentcore",
            url=None,  # Will be populated from SSM
            headers=None,  # Will be populated from secrets
            timeout=120,
            retry_attempts=3,
            health_check_interval=300,
            auth_config=AuthConfig(
                type="bearer",
                credentials={},  # Will be populated from secrets
                refresh_mechanism="aws_secrets_manager"
            ),
            retry_config=RetryConfig(
                max_attempts=3,
                backoff_factor=2.0,
                max_delay=60
            ),
            health_check_config=HealthCheckConfig(
                enabled=True,
                interval=300,
                timeout=30,
                failure_threshold=3
            ),
            feature_flags={
                "parallel_execution": True,
                "response_caching": True,
                "enhanced_error_handling": True
            },
            region_specific={
                "parameter_prefix": "/wa_security_direct_mcp",
                "secret_name": "wa_security_direct_mcp/cognito/credentials"
            }
        )
    
    def get_default_knowledge_mcp_config(self) -> EnhancedMCPServerConfig:
        """Get default configuration for AWS Knowledge MCP Server"""
        return EnhancedMCPServerConfig(
            name="aws_knowledge",
            server_type=MCPServerType.KNOWLEDGE,
            connection_type="direct",
            url="https://knowledge-mcp.global.api.aws",  # Public AWS Knowledge MCP endpoint
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AWS-Enhanced-Security-Agent/1.0"
            },
            timeout=60,
            retry_attempts=2,
            health_check_interval=600,
            auth_config=AuthConfig(
                type="none",  # Public documentation access
                credentials={}
            ),
            retry_config=RetryConfig(
                max_attempts=2,
                backoff_factor=1.5,
                max_delay=30
            ),
            health_check_config=HealthCheckConfig(
                enabled=True,
                interval=600,
                timeout=20,
                failure_threshold=2
            ),
            feature_flags={
                "documentation_caching": True,
                "relevance_scoring": True,
                "content_summarization": True,
                "direct_http_calls": True
            },
            region_specific={
                "documentation_regions": ["us-east-1", "us-west-2", "eu-west-1"],
                "cache_ttl": 3600,
                "public_endpoint": "https://knowledge-mcp.global.api.aws"
            }
        )
    
    def get_default_api_mcp_config(self) -> EnhancedMCPServerConfig:
        """Get default configuration for AWS API MCP Server"""
        return EnhancedMCPServerConfig(
            name="aws_api",
            server_type=MCPServerType.API,
            connection_type="api",
            url=None,  # Will be configured based on deployment
            headers=None,
            timeout=180,
            retry_attempts=3,
            health_check_interval=300,
            auth_config=AuthConfig(
                type="aws_iam",
                credentials={},  # Will use IAM role
                refresh_mechanism="aws_sts"
            ),
            retry_config=RetryConfig(
                max_attempts=3,
                backoff_factor=2.0,
                max_delay=120
            ),
            health_check_config=HealthCheckConfig(
                enabled=True,
                interval=300,
                timeout=45,
                failure_threshold=3
            ),
            feature_flags={
                "automated_remediation": False,  # Disabled by default for safety
                "resource_analysis": True,
                "permission_validation": True,
                "rate_limiting": True
            },
            region_specific={
                "api_endpoints": {},  # Will be populated per region
                "rate_limits": {
                    "default": 100,  # requests per minute
                    "describe": 200,
                    "list": 150
                }
            }
        )
    
    async def load_configurations(self) -> Dict[str, EnhancedMCPServerConfig]:
        """Load all MCP server configurations"""
        try:
            logger.info(f"Loading MCP configurations for environment: {self.environment.value}")
            
            # Load default configurations
            configs = {
                "security": self.get_default_security_mcp_config(),
                "aws_knowledge": self.get_default_knowledge_mcp_config(),
                "aws_api": self.get_default_api_mcp_config()
            }
            
            # Load environment-specific overrides
            for config_name, config in configs.items():
                await self._load_environment_specific_config(config)
            
            # Load feature flags
            await self._load_feature_flags()
            
            self._configs = configs
            logger.info(f"Successfully loaded {len(configs)} MCP configurations")
            
            return configs
            
        except Exception as e:
            logger.error(f"Failed to load MCP configurations: {e}")
            # Return default configurations as fallback
            return {
                "security": self.get_default_security_mcp_config(),
                "aws_knowledge": self.get_default_knowledge_mcp_config(),
                "aws_api": self.get_default_api_mcp_config()
            }
    
    async def _load_environment_specific_config(self, config: EnhancedMCPServerConfig) -> None:
        """Load environment-specific configuration overrides"""
        try:
            if config.name == "security":
                await self._load_security_mcp_credentials(config)
            elif config.name == "aws_api":
                await self._load_api_mcp_configuration(config)
            # aws_knowledge doesn't need special loading as it uses direct integration
            
        except Exception as e:
            logger.warning(f"Failed to load environment config for {config.name}: {e}")
    
    async def _load_security_mcp_credentials(self, config: EnhancedMCPServerConfig) -> None:
        """Load Security MCP server credentials from AWS services"""
        try:
            # Get Agent ARN from SSM
            parameter_name = f"{config.region_specific['parameter_prefix']}/runtime/agent_arn"
            agent_arn_response = self.ssm_client.get_parameter(Name=parameter_name)
            agent_arn = agent_arn_response['Parameter']['Value']
            
            # Build MCP URL
            encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
            config.url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            
            # Get bearer token from Secrets Manager
            secret_name = config.region_specific['secret_name']
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_value = json.loads(response['SecretString'])
            
            # Update configuration
            config.auth_config.credentials = {
                'bearer_token': secret_value['bearer_token']
            }
            config.headers = {
                "authorization": f"Bearer {secret_value['bearer_token']}",
                "Content-Type": "application/json"
            }
            
            logger.info("Successfully loaded Security MCP credentials")
            
        except Exception as e:
            logger.error(f"Failed to load Security MCP credentials: {e}")
            # Keep default configuration
    
    async def _load_api_mcp_configuration(self, config: EnhancedMCPServerConfig) -> None:
        """Load AWS API MCP server configuration"""
        try:
            # For now, use placeholder configuration
            # This will be implemented when AWS API MCP server is deployed
            config.region_specific['api_endpoints'] = {
                self.region: f"https://api-mcp-server.{self.region}.amazonaws.com"
            }
            
            logger.info("AWS API MCP configuration loaded (placeholder)")
            
        except Exception as e:
            logger.error(f"Failed to load API MCP configuration: {e}")
    
    async def _load_feature_flags(self) -> None:
        """Load feature flags from configuration"""
        try:
            # Try to load feature flags from SSM Parameter Store
            parameter_name = f"/enhanced_security_agent/{self.environment.value}/feature_flags"
            
            try:
                response = self.ssm_client.get_parameter(Name=parameter_name)
                self._feature_flags = json.loads(response['Parameter']['Value'])
                logger.info(f"Loaded feature flags: {self._feature_flags}")
            except self.ssm_client.exceptions.ParameterNotFound:
                # Use default feature flags
                self._feature_flags = {
                    "multi_mcp_orchestration": True,
                    "parallel_tool_execution": True,
                    "enhanced_response_formatting": True,
                    "session_context_management": True,
                    "automated_remediation": False,  # Disabled by default
                    "comprehensive_reporting": True,
                    "health_monitoring": True
                }
                logger.info("Using default feature flags")
                
        except Exception as e:
            logger.error(f"Failed to load feature flags: {e}")
            self._feature_flags = {}
    
    def get_config(self, mcp_server_name: str) -> Optional[EnhancedMCPServerConfig]:
        """Get configuration for specific MCP server"""
        return self._configs.get(mcp_server_name)
    
    def get_all_configs(self) -> Dict[str, EnhancedMCPServerConfig]:
        """Get all MCP server configurations"""
        return self._configs.copy()
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled"""
        return self._feature_flags.get(feature_name, False)
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """Get all feature flags"""
        return self._feature_flags.copy()
    
    async def update_config(self, mcp_server_name: str, updates: Dict[str, Any]) -> bool:
        """Update configuration for specific MCP server"""
        try:
            if mcp_server_name not in self._configs:
                logger.error(f"MCP server {mcp_server_name} not found in configurations")
                return False
            
            config = self._configs[mcp_server_name]
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    logger.warning(f"Unknown configuration key: {key}")
            
            logger.info(f"Updated configuration for {mcp_server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update configuration for {mcp_server_name}: {e}")
            return False
    
    async def validate_configurations(self) -> Dict[str, bool]:
        """Validate all MCP server configurations"""
        validation_results = {}
        
        for name, config in self._configs.items():
            try:
                # Basic validation
                is_valid = True
                
                # Check required fields
                if not config.name or not config.server_type:
                    is_valid = False
                
                # Check connection-specific requirements
                if config.connection_type == "agentcore" and not config.url:
                    is_valid = False
                
                # Check authentication configuration
                if config.auth_config.type == "bearer" and not config.auth_config.credentials.get('bearer_token'):
                    is_valid = False
                
                validation_results[name] = is_valid
                
                if is_valid:
                    logger.info(f"Configuration for {name} is valid")
                else:
                    logger.warning(f"Configuration for {name} has validation issues")
                    
            except Exception as e:
                logger.error(f"Failed to validate configuration for {name}: {e}")
                validation_results[name] = False
        
        return validation_results
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get current environment information"""
        return {
            "environment": self.environment.value,
            "region": self.region,
            "config_count": len(self._configs),
            "feature_flags_count": len(self._feature_flags),
            "loaded_configs": list(self._configs.keys())
        }