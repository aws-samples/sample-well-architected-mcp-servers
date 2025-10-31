"""
SSM Parameter Store utilities for both BedrockAgent and AgentCore versions.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class ParameterManager:
    """Utility class for managing SSM Parameter Store operations."""
    
    def __init__(self, param_prefix: str, region: str = "us-east-1"):
        """
        Initialize Parameter Manager.
        
        Args:
            param_prefix: Parameter prefix (e.g., 'coa', 'coacost')
            region: AWS region
        """
        self.param_prefix = param_prefix
        self.region = region
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_update = {}
        
        try:
            self.ssm_client = boto3.client('ssm', region_name=region)
            logger.info(f"ParameterManager initialized with prefix: {param_prefix}, region: {region}")
        except (NoCredentialsError, ClientError) as e:
            logger.error(f"Failed to initialize SSM client: {e}")
            raise
    
    def get_parameter_path(self, category: str) -> str:
        """Get full parameter path for a category."""
        return f"/{self.param_prefix}/{category}/"
    
    def get_parameter(self, path: str, decrypt: bool = True) -> Optional[str]:
        """
        Get a single parameter value.
        
        Args:
            path: Full parameter path
            decrypt: Whether to decrypt SecureString parameters
            
        Returns:
            Parameter value or None if not found
        """
        try:
            # Check cache first
            cache_key = f"{path}:{decrypt}"
            if self._is_cached(cache_key):
                return self._cache[cache_key]
            
            response = self.ssm_client.get_parameter(
                Name=path,
                WithDecryption=decrypt
            )
            
            value = response['Parameter']['Value']
            self._update_cache(cache_key, value)
            return value
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.debug(f"Parameter not found: {path}")
                return None
            else:
                logger.error(f"Error getting parameter {path}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error getting parameter {path}: {e}")
            raise
    
    def get_parameters_by_path(
        self, 
        path: str, 
        recursive: bool = True, 
        decrypt: bool = True
    ) -> Dict[str, str]:
        """
        Get all parameters under a path.
        
        Args:
            path: Parameter path prefix
            recursive: Whether to get parameters recursively
            decrypt: Whether to decrypt SecureString parameters
            
        Returns:
            Dictionary of parameter names to values
        """
        try:
            # Check cache first
            cache_key = f"path:{path}:{recursive}:{decrypt}"
            if self._is_cached(cache_key):
                return self._cache[cache_key]
            
            parameters = {}
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            
            for page in paginator.paginate(
                Path=path,
                Recursive=recursive,
                WithDecryption=decrypt
            ):
                for param in page['Parameters']:
                    # Remove path prefix from parameter name for cleaner keys
                    param_name = param['Name'].replace(path, '').lstrip('/')
                    parameters[param_name] = param['Value']
            
            self._update_cache(cache_key, parameters)
            return parameters
            
        except Exception as e:
            logger.error(f"Error getting parameters by path {path}: {e}")
            raise
    
    def get_parameters_by_category(self, category: str) -> Dict[str, str]:
        """
        Get all parameters for a specific category.
        
        Args:
            category: Parameter category (e.g., 'agentcore', 'components')
            
        Returns:
            Dictionary of parameter names to values
        """
        path = self.get_parameter_path(category)
        return self.get_parameters_by_path(path)
    
    def list_parameter_names(self, path: str) -> List[str]:
        """
        List parameter names under a path.
        
        Args:
            path: Parameter path prefix
            
        Returns:
            List of parameter names
        """
        try:
            parameter_names = []
            paginator = self.ssm_client.get_paginator('describe_parameters')
            
            for page in paginator.paginate(
                ParameterFilters=[
                    {
                        'Key': 'Name',
                        'Option': 'BeginsWith',
                        'Values': [path]
                    }
                ]
            ):
                for param in page['Parameters']:
                    parameter_names.append(param['Name'])
            
            return parameter_names
            
        except Exception as e:
            logger.error(f"Error listing parameter names for path {path}: {e}")
            raise
    
    def validate_connectivity(self) -> Dict[str, Any]:
        """
        Validate SSM connectivity and permissions.
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Test basic connectivity
            self.ssm_client.describe_parameters(MaxResults=1)
            
            # Test parameter access for our prefix
            test_path = self.get_parameter_path("test")
            try:
                self.get_parameters_by_path(test_path)
                parameter_access = True
            except Exception:
                parameter_access = False
            
            return {
                "connectivity": True,
                "parameter_access": parameter_access,
                "region": self.region,
                "param_prefix": self.param_prefix,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"SSM connectivity validation failed: {e}")
            return {
                "connectivity": False,
                "error": str(e),
                "region": self.region,
                "param_prefix": self.param_prefix,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def clear_cache(self):
        """Clear parameter cache."""
        self._cache.clear()
        self._last_cache_update.clear()
        logger.info("Parameter cache cleared")
    
    def _is_cached(self, key: str) -> bool:
        """Check if a value is cached and still valid."""
        if key not in self._cache:
            return False
        
        last_update = self._last_cache_update.get(key, 0)
        return (datetime.utcnow().timestamp() - last_update) < self._cache_ttl
    
    def _update_cache(self, key: str, value: Any):
        """Update cache with new value."""
        self._cache[key] = value
        self._last_cache_update[key] = datetime.utcnow().timestamp()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "cache_ttl_seconds": self._cache_ttl,
            "cached_keys": list(self._cache.keys()),
            "last_updates": {
                key: datetime.fromtimestamp(timestamp).isoformat()
                for key, timestamp in self._last_cache_update.items()
            }
        }


# Global parameter manager instance
_parameter_manager: Optional[ParameterManager] = None


def initialize_parameter_manager(param_prefix: str, region: str = "us-east-1") -> ParameterManager:
    """
    Initialize global parameter manager instance.
    
    Args:
        param_prefix: Parameter prefix
        region: AWS region
        
    Returns:
        ParameterManager instance
    """
    global _parameter_manager
    _parameter_manager = ParameterManager(param_prefix, region)
    return _parameter_manager


def get_parameter_manager() -> Optional[ParameterManager]:
    """Get global parameter manager instance."""
    return _parameter_manager


def get_dynamic_parameter_prefix() -> str:
    """Get parameter prefix from environment or default."""
    return os.getenv('PARAM_PREFIX', 'coa')


class ParameterManagerError(Exception):
    """Exception raised by parameter manager operations."""
    pass