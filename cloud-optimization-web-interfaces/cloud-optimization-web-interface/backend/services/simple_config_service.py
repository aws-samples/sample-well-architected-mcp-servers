"""
Simplified Configuration Service for essential configuration management.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from models.exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class SimpleConfigService:
    """Simplified configuration service with SSM Parameter Store and environment variables."""
    
    def __init__(self, region: str = "us-east-1", ssm_prefix: str = "/coa/"):
        """
        Initialize the Configuration Service.
        
        Args:
            region: AWS region for SSM Parameter Store
            ssm_prefix: Prefix for SSM parameters
        """
        self.region = region
        self.ssm_prefix = ssm_prefix
        self.ssm_client = None
        self.config_cache = {}
        
        # Essential configuration keys with defaults
        self.default_config = {
            "AWS_REGION": region,
            "JWT_SECRET": "dev-secret-change-in-production",
            "JWT_ALGORITHM": "HS256",
            "SESSION_TTL_HOURS": "24",
            "AGENT_CACHE_TTL_SECONDS": "300",
            "MAX_CONVERSATION_MESSAGES": "100",
            "RATE_LIMIT_REQUESTS_PER_WINDOW": "100",
            "RATE_LIMIT_WINDOW_SECONDS": "300"
        }
        
        # Initialize SSM client
        self._initialize_ssm()
        
        logger.info(f"SimpleConfigService initialized for region {region}")

    def _initialize_ssm(self) -> None:
        """Initialize SSM client with error handling."""
        try:
            self.ssm_client = boto3.client('ssm', region_name=self.region)
            
            # Test connectivity
            self.ssm_client.describe_parameters(MaxResults=1)
            logger.info("SSM client initialized successfully")
            
        except (NoCredentialsError, ClientError, Exception) as e:
            logger.warning(f"SSM client initialization failed: {e}")
            self.ssm_client = None

    def get_config(self, key: str, default: Optional[str] = None) -> str:
        """
        Get configuration value with priority: SSM > Environment > Default.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        try:
            # Check cache first
            if key in self.config_cache:
                return self.config_cache[key]
            
            # Try SSM Parameter Store
            ssm_value = self._get_ssm_parameter(key)
            if ssm_value is not None:
                self.config_cache[key] = ssm_value
                return ssm_value
            
            # Try environment variable
            env_value = os.getenv(key)
            if env_value is not None:
                self.config_cache[key] = env_value
                return env_value
            
            # Use provided default
            if default is not None:
                return default
            
            # Use built-in default
            if key in self.default_config:
                return self.default_config[key]
            
            # No value found
            logger.warning(f"Configuration key '{key}' not found")
            raise ConfigurationError(f"Configuration key '{key}' not found", config_key=key)
            
        except ConfigurationError:
            raise
        except Exception as e:
            logger.error(f"Error getting configuration for key '{key}': {e}")
            raise ConfigurationError(f"Failed to get configuration for '{key}': {e}", config_key=key)

    def _get_ssm_parameter(self, key: str) -> Optional[str]:
        """Get parameter from SSM Parameter Store."""
        if not self.ssm_client:
            return None
        
        try:
            # Map common keys to SSM parameter paths
            parameter_mappings = {
                "ENHANCED_SECURITY_AGENT_ID": f"{self.ssm_prefix}agents/wa-security-agent/agent_id",
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": f"{self.ssm_prefix}agents/wa-security-agent/agent_alias_id",
                "COST_OPTIMIZATION_AGENT_ID": f"{self.ssm_prefix}agents/cost-optimization-agent/agent_id",
                "COST_OPTIMIZATION_AGENT_ALIAS_ID": f"{self.ssm_prefix}agents/cost-optimization-agent/agent_alias_id",
                "JWT_SECRET": f"{self.ssm_prefix}auth/jwt_secret",
                "COGNITO_USER_POOL_ID": f"{self.ssm_prefix}cognito/user_pool_id",
                "COGNITO_CLIENT_ID": f"{self.ssm_prefix}cognito/client_id"
            }
            
            parameter_name = parameter_mappings.get(key, f"{self.ssm_prefix}config/{key}")
            
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            
            value = response['Parameter']['Value']
            logger.debug(f"Retrieved '{key}' from SSM Parameter Store")
            return value
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.debug(f"SSM parameter not found: {parameter_name}")
            else:
                logger.warning(f"Error retrieving SSM parameter '{parameter_name}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error retrieving SSM parameter: {e}")
            return None

    def get_int_config(self, key: str, default: Optional[int] = None) -> int:
        """
        Get integer configuration value.
        
        Args:
            key: Configuration key
            default: Default integer value
            
        Returns:
            Integer configuration value
        """
        try:
            value = self.get_config(key, str(default) if default is not None else None)
            return int(value)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid integer value for '{key}': {value}")
            if default is not None:
                return default
            raise ConfigurationError(f"Invalid integer configuration for '{key}': {value}", config_key=key)

    def get_bool_config(self, key: str, default: Optional[bool] = None) -> bool:
        """
        Get boolean configuration value.
        
        Args:
            key: Configuration key
            default: Default boolean value
            
        Returns:
            Boolean configuration value
        """
        try:
            value = self.get_config(key, str(default).lower() if default is not None else None)
            return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
        except Exception as e:
            logger.error(f"Invalid boolean value for '{key}': {value}")
            if default is not None:
                return default
            raise ConfigurationError(f"Invalid boolean configuration for '{key}': {value}", config_key=key)

    def get_json_config(self, key: str, default: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Get JSON configuration value.
        
        Args:
            key: Configuration key
            default: Default dictionary value
            
        Returns:
            Dictionary from JSON configuration
        """
        try:
            value = self.get_config(key, json.dumps(default) if default is not None else None)
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Invalid JSON value for '{key}': {value}")
            if default is not None:
                return default
            raise ConfigurationError(f"Invalid JSON configuration for '{key}': {value}", config_key=key)

    def get_all_config(self) -> Dict[str, str]:
        """
        Get all essential configuration values.
        
        Returns:
            Dictionary with all configuration values
        """
        config = {}
        
        # Essential configuration keys
        essential_keys = [
            "AWS_REGION",
            "JWT_SECRET",
            "JWT_ALGORITHM",
            "SESSION_TTL_HOURS",
            "AGENT_CACHE_TTL_SECONDS",
            "MAX_CONVERSATION_MESSAGES",
            "RATE_LIMIT_REQUESTS_PER_WINDOW",
            "RATE_LIMIT_WINDOW_SECONDS",
            "ENHANCED_SECURITY_AGENT_ID",
            "ENHANCED_SECURITY_AGENT_ALIAS_ID",
            "COST_OPTIMIZATION_AGENT_ID",
            "COST_OPTIMIZATION_AGENT_ALIAS_ID"
        ]
        
        for key in essential_keys:
            try:
                config[key] = self.get_config(key)
            except ConfigurationError:
                # Skip missing optional configuration
                pass
        
        return config

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate essential configuration and return status.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "config_sources": {
                "ssm_available": self.ssm_client is not None,
                "environment_variables": 0,
                "ssm_parameters": 0,
                "defaults_used": 0
            }
        }
        
        # Required configuration keys
        required_keys = ["AWS_REGION", "JWT_SECRET"]
        
        for key in required_keys:
            try:
                value = self.get_config(key)
                
                # Check configuration source
                if key in self.config_cache:
                    if self._get_ssm_parameter(key) is not None:
                        validation_results["config_sources"]["ssm_parameters"] += 1
                    elif os.getenv(key) is not None:
                        validation_results["config_sources"]["environment_variables"] += 1
                    else:
                        validation_results["config_sources"]["defaults_used"] += 1
                
                # Validate specific configurations
                if key == "JWT_SECRET" and value == "dev-secret-change-in-production":
                    validation_results["warnings"].append(
                        "Using default JWT secret - change for production"
                    )
                
            except ConfigurationError as e:
                validation_results["valid"] = False
                validation_results["errors"].append(f"Missing required configuration: {key}")
        
        # Validate optional integer configurations
        int_configs = {
            "SESSION_TTL_HOURS": (1, 168),  # 1 hour to 1 week
            "AGENT_CACHE_TTL_SECONDS": (60, 3600),  # 1 minute to 1 hour
            "MAX_CONVERSATION_MESSAGES": (10, 1000),  # 10 to 1000 messages
            "RATE_LIMIT_REQUESTS_PER_WINDOW": (10, 10000),  # 10 to 10000 requests
            "RATE_LIMIT_WINDOW_SECONDS": (60, 3600)  # 1 minute to 1 hour
        }
        
        for key, (min_val, max_val) in int_configs.items():
            try:
                value = self.get_int_config(key)
                if not (min_val <= value <= max_val):
                    validation_results["warnings"].append(
                        f"Configuration '{key}' value {value} outside recommended range [{min_val}, {max_val}]"
                    )
            except ConfigurationError:
                # Optional configuration, skip if missing
                pass
        
        return validation_results

    def refresh_cache(self) -> None:
        """Clear configuration cache to force refresh."""
        self.config_cache.clear()
        logger.info("Configuration cache cleared")

    def get_config_stats(self) -> Dict[str, Any]:
        """
        Get configuration service statistics.
        
        Returns:
            Dictionary with configuration statistics
        """
        return {
            "ssm_available": self.ssm_client is not None,
            "ssm_prefix": self.ssm_prefix,
            "region": self.region,
            "cached_configs": len(self.config_cache),
            "default_configs": len(self.default_config),
            "cache_keys": list(self.config_cache.keys())
        }