#!/usr/bin/env python3
"""
Centralized Configuration Manager for AWS Well-Architected Agents
Replaces hard-coded configurations with SSM Parameter Store values
"""

import boto3
import json
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


@dataclass
class ParameterCacheEntry:
    """Cache entry for SSM parameters"""
    value: Any
    timestamp: float
    ttl: int = 300  # 5 minutes default


class AgentConfigurationManager:
    """
    Centralized configuration manager for AWS Well-Architected Agents
    Retrieves configuration from SSM Parameter Store with caching and fallbacks
    """
    
    def __init__(self, region: str = None, cache_ttl: int = 300):
        """
        Initialize the configuration manager
        
        Args:
            region: AWS region (defaults to session region)
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        self.region = region or self._get_default_region()
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, ParameterCacheEntry] = {}
        
        try:
            self.ssm_client = boto3.client('ssm', region_name=self.region)
            self.secrets_client = boto3.client('secretsmanager', region_name=self.region)
        except NoCredentialsError:
            logger.warning("AWS credentials not found. Configuration manager will use fallback values.")
            self.ssm_client = None
            self.secrets_client = None
        
        logger.info(f"Configuration manager initialized for region: {self.region}")
    
    def _get_default_region(self) -> str:
        """Get default AWS region from session or environment"""
        try:
            session = boto3.Session()
            return session.region_name or "us-east-1"
        except Exception:
            return "us-east-1"
    
    def get_parameter(self, parameter_name: str, default: Any = None, parameter_type: str = "String") -> Any:
        """
        Get parameter from SSM Parameter Store with caching
        
        Args:
            parameter_name: SSM parameter name
            default: Default value if parameter not found
            parameter_type: Parameter type (String, StringList, SecureString)
            
        Returns:
            Parameter value or default
        """
        # Check cache first
        if self._is_cache_valid(parameter_name):
            logger.debug(f"Returning cached value for parameter: {parameter_name}")
            return self._cache[parameter_name].value
        
        if not self.ssm_client:
            logger.warning(f"SSM client not available, using default for {parameter_name}")
            return default
        
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            
            value = response['Parameter']['Value']
            
            # Parse JSON if it looks like JSON
            if parameter_type == "StringList" or (value.startswith('{') or value.startswith('[')):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON
            
            # Cache the value
            self._cache[parameter_name] = ParameterCacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=self.cache_ttl
            )
            
            logger.debug(f"Retrieved parameter: {parameter_name}")
            return value
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                logger.warning(f"Parameter not found: {parameter_name}, using default: {default}")
            else:
                logger.error(f"Error retrieving parameter {parameter_name}: {e}")
            return default
        except Exception as e:
            logger.error(f"Unexpected error retrieving parameter {parameter_name}: {e}")
            return default
    
    def get_secret(self, secret_name: str, default: Any = None) -> Any:
        """
        Get secret from AWS Secrets Manager
        
        Args:
            secret_name: Secret name or ARN
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        if not self.secrets_client:
            logger.warning(f"Secrets client not available, using default for {secret_name}")
            return default
        
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_value = response['SecretString']
            
            # Try to parse as JSON
            try:
                return json.loads(secret_value)
            except json.JSONDecodeError:
                return secret_value
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {secret_name}, using default: {default}")
            else:
                logger.error(f"Error retrieving secret {secret_name}: {e}")
            return default
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            return default
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """
        Get complete configuration for a specific agent
        
        Args:
            agent_name: Name of the agent (e.g., 'wa_security_agent')
            
        Returns:
            Dictionary containing all agent configuration
        """
        base_path = f"/coa/agents/{agent_name}"
        
        config = {
            'region': self.get_parameter(f"{base_path}/region", self.region),
            'model_id': self.get_parameter(f"{base_path}/model_id", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
            'model_version': self.get_parameter(f"{base_path}/model_version", "latest"),
            'memory_id': self.get_parameter(f"{base_path}/memory_id"),
            'session_ttl': self.get_parameter(f"{base_path}/session_ttl", "1800"),
            'idle_timeout': self.get_parameter(f"{base_path}/idle_timeout", "300"),
        }
        
        # Convert string numbers to integers
        for key in ['session_ttl', 'idle_timeout']:
            if config[key] and isinstance(config[key], str) and config[key].isdigit():
                config[key] = int(config[key])
        
        return config
    
    def get_component_config(self, component_name: str) -> Dict[str, Any]:
        """
        Get complete configuration for a specific component
        
        Args:
            component_name: Name of the component (e.g., 'wa_security_mcp')
            
        Returns:
            Dictionary containing all component configuration
        """
        base_path = f"/coa/components/{component_name}"
        
        config = {
            'agent_arn': self.get_parameter(f"{base_path}/agent_arn"),
            'agent_id': self.get_parameter(f"{base_path}/agent_id"),
            'runtime_id': self.get_parameter(f"{base_path}/runtime_id"),
            'server_url': self.get_parameter(f"{base_path}/server_url"),
            'timeout': self.get_parameter(f"{base_path}/timeout", "30"),
            'retry_attempts': self.get_parameter(f"{base_path}/retry_attempts", "3"),
        }
        
        # Convert string numbers to integers
        for key in ['timeout', 'retry_attempts']:
            if config[key] and isinstance(config[key], str) and config[key].isdigit():
                config[key] = int(config[key])
        
        return config
    
    def get_cognito_config(self) -> Dict[str, Any]:
        """
        Get Cognito configuration
        
        Returns:
            Dictionary containing Cognito configuration
        """
        base_path = "/coa/cognito"
        
        config = {
            'user_pool_id': self.get_parameter(f"{base_path}/user_pool_id"),
            'web_app_client_id': self.get_parameter(f"{base_path}/web_app_client_id"),
            'api_client_id': self.get_parameter(f"{base_path}/api_client_id"),
            'mcp_server_client_id': self.get_parameter(f"{base_path}/mcp_server_client_id"),
            'identity_pool_id': self.get_parameter(f"{base_path}/identity_pool_id"),
            'discovery_url': self.get_parameter(f"{base_path}/discovery_url"),
            'bearer_token_secret_name': self.get_parameter(f"{base_path}/bearer_token_secret_name"),
        }
        
        return config
    
    def get_mcp_server_credentials(self, component_name: str) -> Dict[str, Any]:
        """
        Get MCP server credentials from Secrets Manager
        
        Args:
            component_name: Name of the MCP component
            
        Returns:
            Dictionary containing credentials
        """
        secret_name = f"/coa/components/{component_name}/credentials"
        credentials = self.get_secret(secret_name, {})
        
        if not credentials:
            # Fallback to individual parameters
            base_path = f"/coa/components/{component_name}"
            credentials = {
                'bearer_token': self.get_parameter(f"{base_path}/bearer_token"),
                'client_id': self.get_parameter(f"{base_path}/client_id"),
                'user_pool_id': self.get_parameter(f"{base_path}/user_pool_id"),
            }
        
        return credentials
    
    def get_parameters_by_path(self, path: str) -> Dict[str, Any]:
        """
        Get all parameters under a specific path
        
        Args:
            path: Parameter path prefix
            
        Returns:
            Dictionary of parameter names and values
        """
        if not self.ssm_client:
            logger.warning(f"SSM client not available for path: {path}")
            return {}
        
        try:
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            parameters = {}
            
            for page in paginator.paginate(
                Path=path,
                Recursive=True,
                WithDecryption=True
            ):
                for param in page['Parameters']:
                    param_name = param['Name']
                    param_value = param['Value']
                    
                    # Try to parse JSON values
                    try:
                        param_value = json.loads(param_value)
                    except json.JSONDecodeError:
                        pass  # Keep as string
                    
                    # Remove path prefix from parameter name for cleaner keys
                    clean_name = param_name.replace(path.rstrip('/') + '/', '')
                    parameters[clean_name] = param_value
            
            return parameters
            
        except ClientError as e:
            logger.error(f"Error retrieving parameters by path {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error retrieving parameters by path {path}: {e}")
            return {}
    
    def _is_cache_valid(self, parameter_name: str) -> bool:
        """Check if cached parameter is still valid"""
        if parameter_name not in self._cache:
            return False
        
        entry = self._cache[parameter_name]
        return (time.time() - entry.timestamp) < entry.ttl
    
    def clear_cache(self, parameter_name: str = None):
        """
        Clear parameter cache
        
        Args:
            parameter_name: Specific parameter to clear, or None to clear all
        """
        if parameter_name:
            self._cache.pop(parameter_name, None)
            logger.debug(f"Cleared cache for parameter: {parameter_name}")
        else:
            self._cache.clear()
            logger.debug("Cleared all parameter cache")
    
    def validate_configuration(self, required_parameters: List[str]) -> Dict[str, bool]:
        """
        Validate that required parameters are available
        
        Args:
            required_parameters: List of required parameter names
            
        Returns:
            Dictionary mapping parameter names to availability status
        """
        validation_results = {}
        
        for param_name in required_parameters:
            try:
                value = self.get_parameter(param_name)
                validation_results[param_name] = value is not None
            except Exception as e:
                logger.error(f"Error validating parameter {param_name}: {e}")
                validation_results[param_name] = False
        
        return validation_results
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of configuration manager
        
        Returns:
            Health check results
        """
        health_status = {
            'status': 'healthy',
            'region': self.region,
            'ssm_available': self.ssm_client is not None,
            'secrets_available': self.secrets_client is not None,
            'cache_size': len(self._cache),
            'timestamp': time.time()
        }
        
        # Test SSM connectivity
        if self.ssm_client:
            try:
                # Try to get a test parameter (this will fail gracefully)
                self.ssm_client.get_parameter(Name='/test/connectivity/check')
            except ClientError as e:
                if e.response['Error']['Code'] != 'ParameterNotFound':
                    health_status['status'] = 'degraded'
                    health_status['ssm_error'] = str(e)
            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['ssm_error'] = str(e)
        
        return health_status


# Global configuration manager instance
_config_manager = None


def get_config_manager(region: str = None, cache_ttl: int = 300) -> AgentConfigurationManager:
    """
    Get global configuration manager instance
    
    Args:
        region: AWS region (only used for first initialization)
        cache_ttl: Cache TTL (only used for first initialization)
        
    Returns:
        AgentConfigurationManager instance
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = AgentConfigurationManager(region=region, cache_ttl=cache_ttl)
    
    return _config_manager


# Convenience functions for common configuration patterns
def get_agent_config(agent_name: str) -> Dict[str, Any]:
    """Get agent configuration"""
    return get_config_manager().get_agent_config(agent_name)


def get_component_config(component_name: str) -> Dict[str, Any]:
    """Get component configuration"""
    return get_config_manager().get_component_config(component_name)


def get_cognito_config() -> Dict[str, Any]:
    """Get Cognito configuration"""
    return get_config_manager().get_cognito_config()


def get_mcp_credentials(component_name: str) -> Dict[str, Any]:
    """Get MCP server credentials"""
    return get_config_manager().get_mcp_server_credentials(component_name)