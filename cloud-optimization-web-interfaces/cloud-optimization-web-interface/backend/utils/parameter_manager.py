"""
Dynamic Parameter Manager for COA Backend Service

This module provides dynamic parameter management for the COA backend service,
enabling parameter access using configurable prefixes based on deployment configuration.
"""

import os
import boto3
import logging
from typing import Dict, List, Optional, Any
from botocore.exceptions import ClientError, NoCredentialsError
import json
from functools import lru_cache
import time


logger = logging.getLogger(__name__)


class ParameterManagerError(Exception):
    """Base exception for parameter manager errors"""
    pass


class ParameterNotFoundError(ParameterManagerError):
    """Raised when a required parameter is not found"""
    pass


class ParameterValidationError(ParameterManagerError):
    """Raised when parameter validation fails"""
    pass


class ParameterManager:
    """
    Manages dynamic parameter access for COA backend service
    
    This class provides prefix-aware parameter access to AWS Systems Manager
    Parameter Store, enabling multiple COA deployments to coexist with
    isolated parameter namespaces.
    """
    
    def __init__(self, param_prefix: str = None, region: str = None):
        """
        Initialize parameter manager
        
        Args:
            param_prefix: Parameter prefix (e.g., "coa_1027"). If None, reads from environment
            region: AWS region. If None, uses default region
            
        Raises:
            ParameterManagerError: If param_prefix is not provided and not in environment
        """
        self.param_prefix = param_prefix or os.getenv('PARAM_PREFIX')
        if not self.param_prefix:
            raise ParameterManagerError(
                "Parameter prefix not provided. Set PARAM_PREFIX environment variable or pass param_prefix argument"
            )
        
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize SSM client
        try:
            self.ssm_client = boto3.client('ssm', region_name=self.region)
        except NoCredentialsError:
            logger.error("AWS credentials not configured")
            raise ParameterManagerError("AWS credentials not configured")
        
        # Parameter categories and their paths
        self.parameter_paths = {
            'agentcore': f"/{self.param_prefix}/agentcore",
            'cognito': f"/{self.param_prefix}/cognito",
            'components': f"/{self.param_prefix}/components",
            'agent': f"/{self.param_prefix}/agent"
        }
        
        # Cache for parameters (TTL: 5 minutes)
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info(f"ParameterManager initialized with prefix: {self.param_prefix}, region: {self.region}")
    
    def get_parameter_path(self, category: str, name: str = None) -> str:
        """
        Get full parameter path for category and optional parameter name
        
        Args:
            category: Parameter category (agentcore, cognito, components, agent)
            name: Optional parameter name
            
        Returns:
            Full parameter path
            
        Raises:
            ParameterValidationError: If category is invalid
        """
        if category not in self.parameter_paths:
            raise ParameterValidationError(f"Invalid parameter category: {category}")
        
        base_path = self.parameter_paths[category]
        if name:
            return f"{base_path}/{name}"
        return base_path
    
    def get_parameter(self, category: str, name: str, default: Any = None, 
                     decrypt: bool = True, use_cache: bool = True) -> Optional[str]:
        """
        Get parameter value from SSM Parameter Store
        
        Args:
            category: Parameter category
            name: Parameter name
            default: Default value if parameter not found
            decrypt: Whether to decrypt SecureString parameters
            use_cache: Whether to use cached values
            
        Returns:
            Parameter value or default if not found
            
        Raises:
            ParameterNotFoundError: If parameter not found and no default provided
        """
        path = self.get_parameter_path(category, name)
        
        # Check cache first
        if use_cache:
            cached_value = self._get_from_cache(path)
            if cached_value is not None:
                return cached_value
        
        try:
            response = self.ssm_client.get_parameter(
                Name=path,
                WithDecryption=decrypt
            )
            value = response['Parameter']['Value']
            
            # Cache the value
            if use_cache:
                self._set_cache(path, value)
            
            logger.debug(f"Retrieved parameter: {path}")
            return value
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                if default is not None:
                    logger.debug(f"Parameter not found, using default: {path}")
                    return default
                else:
                    logger.error(f"Parameter not found: {path}")
                    raise ParameterNotFoundError(f"Parameter not found: {path}")
            else:
                logger.error(f"Error retrieving parameter {path}: {e}")
                raise ParameterManagerError(f"Error retrieving parameter {path}: {e}")
    
    def get_parameters_by_category(self, category: str, decrypt: bool = True, 
                                 use_cache: bool = True) -> Dict[str, str]:
        """
        Get all parameters for a category
        
        Args:
            category: Parameter category
            decrypt: Whether to decrypt SecureString parameters
            use_cache: Whether to use cached values
            
        Returns:
            Dictionary mapping parameter names to values
        """
        path = self.get_parameter_path(category)
        
        # Check cache first
        cache_key = f"{path}/*"
        if use_cache:
            cached_value = self._get_from_cache(cache_key)
            if cached_value is not None:
                return cached_value
        
        try:
            response = self.ssm_client.get_parameters_by_path(
                Path=path,
                Recursive=True,
                WithDecryption=decrypt
            )
            
            parameters = {}
            for param in response['Parameters']:
                # Extract parameter name from full path
                param_name = param['Name'].replace(f"{path}/", "")
                parameters[param_name] = param['Value']
            
            # Cache the result
            if use_cache:
                self._set_cache(cache_key, parameters)
            
            logger.debug(f"Retrieved {len(parameters)} parameters from category: {category}")
            return parameters
            
        except ClientError as e:
            logger.error(f"Error retrieving parameters for category {category}: {e}")
            raise ParameterManagerError(f"Error retrieving parameters for category {category}: {e}")
    
    def set_parameter(self, category: str, name: str, value: str, 
                     description: str = None, parameter_type: str = 'String',
                     overwrite: bool = True) -> bool:
        """
        Set parameter value in SSM Parameter Store
        
        Args:
            category: Parameter category
            name: Parameter name
            value: Parameter value
            description: Parameter description
            parameter_type: Parameter type (String, StringList, SecureString)
            overwrite: Whether to overwrite existing parameter
            
        Returns:
            True if successful
            
        Raises:
            ParameterManagerError: If parameter creation fails
        """
        path = self.get_parameter_path(category, name)
        
        try:
            params = {
                'Name': path,
                'Value': value,
                'Type': parameter_type,
                'Overwrite': overwrite
            }
            
            if description:
                params['Description'] = f"[{self.param_prefix}] {description}"
            
            self.ssm_client.put_parameter(**params)
            
            # Invalidate cache
            self._invalidate_cache(path)
            
            logger.info(f"Set parameter: {path}")
            return True
            
        except ClientError as e:
            logger.error(f"Error setting parameter {path}: {e}")
            raise ParameterManagerError(f"Error setting parameter {path}: {e}")
    
    def delete_parameter(self, category: str, name: str) -> bool:
        """
        Delete parameter from SSM Parameter Store
        
        Args:
            category: Parameter category
            name: Parameter name
            
        Returns:
            True if successful
        """
        path = self.get_parameter_path(category, name)
        
        try:
            self.ssm_client.delete_parameter(Name=path)
            
            # Invalidate cache
            self._invalidate_cache(path)
            
            logger.info(f"Deleted parameter: {path}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ParameterNotFound':
                logger.warning(f"Parameter not found for deletion: {path}")
                return True  # Consider it successful if already doesn't exist
            else:
                logger.error(f"Error deleting parameter {path}: {e}")
                raise ParameterManagerError(f"Error deleting parameter {path}: {e}")
    
    def list_parameters(self, category: str = None) -> List[Dict[str, Any]]:
        """
        List parameters, optionally filtered by category
        
        Args:
            category: Optional category filter
            
        Returns:
            List of parameter information dictionaries
        """
        try:
            if category:
                path = self.get_parameter_path(category)
                response = self.ssm_client.get_parameters_by_path(
                    Path=path,
                    Recursive=True
                )
            else:
                # List all parameters with the prefix
                path = f"/{self.param_prefix}"
                response = self.ssm_client.get_parameters_by_path(
                    Path=path,
                    Recursive=True
                )
            
            parameters = []
            for param in response['Parameters']:
                parameters.append({
                    'name': param['Name'],
                    'type': param['Type'],
                    'last_modified': param['LastModifiedDate'],
                    'version': param['Version']
                })
            
            logger.debug(f"Listed {len(parameters)} parameters")
            return parameters
            
        except ClientError as e:
            logger.error(f"Error listing parameters: {e}")
            raise ParameterManagerError(f"Error listing parameters: {e}")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate parameter manager configuration and connectivity
        
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'param_prefix': self.param_prefix,
            'region': self.region,
            'ssm_connectivity': False,
            'parameter_paths': self.parameter_paths,
            'errors': []
        }
        
        try:
            # Test SSM connectivity
            self.ssm_client.describe_parameters(MaxResults=1)
            validation_result['ssm_connectivity'] = True
            
            # Test parameter access for each category
            for category in self.parameter_paths:
                try:
                    self.list_parameters(category)
                    validation_result[f'{category}_accessible'] = True
                except Exception as e:
                    validation_result[f'{category}_accessible'] = False
                    validation_result['errors'].append(f"Category {category}: {str(e)}")
            
        except Exception as e:
            validation_result['errors'].append(f"SSM connectivity: {str(e)}")
        
        return validation_result
    
    def get_legacy_parameter(self, category: str, name: str, 
                           legacy_prefix: str = "/coa") -> Optional[str]:
        """
        Get parameter from legacy prefix for backward compatibility
        
        Args:
            category: Parameter category
            name: Parameter name
            legacy_prefix: Legacy parameter prefix
            
        Returns:
            Parameter value if found, None otherwise
        """
        legacy_path = f"{legacy_prefix}/{category}/{name}"
        
        try:
            response = self.ssm_client.get_parameter(
                Name=legacy_path,
                WithDecryption=True
            )
            
            logger.warning(f"Using legacy parameter: {legacy_path}")
            return response['Parameter']['Value']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                return None
            else:
                logger.error(f"Error retrieving legacy parameter {legacy_path}: {e}")
                return None
    
    def get_parameter_with_fallback(self, category: str, name: str, 
                                  default: Any = None) -> Optional[str]:
        """
        Get parameter with fallback to legacy prefix
        
        Args:
            category: Parameter category
            name: Parameter name
            default: Default value if parameter not found
            
        Returns:
            Parameter value, legacy value, or default
        """
        # Try current prefix first
        try:
            return self.get_parameter(category, name)
        except ParameterNotFoundError:
            pass
        
        # Try legacy prefix
        legacy_value = self.get_legacy_parameter(category, name)
        if legacy_value is not None:
            return legacy_value
        
        # Return default
        if default is not None:
            return default
        
        raise ParameterNotFoundError(f"Parameter not found in current or legacy locations: {category}/{name}")
    
    def clear_cache(self) -> None:
        """Clear parameter cache"""
        self._cache.clear()
        logger.debug("Parameter cache cleared")
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            else:
                # Remove expired entry
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any) -> None:
        """Set value in cache with timestamp"""
        self._cache[key] = (value, time.time())
    
    def _invalidate_cache(self, key: str) -> None:
        """Invalidate specific cache entry"""
        if key in self._cache:
            del self._cache[key]
        
        # Also invalidate category-level cache
        for cache_key in list(self._cache.keys()):
            if cache_key.startswith(key.rsplit('/', 1)[0]):
                del self._cache[cache_key]


# Global parameter manager instance
_parameter_manager: Optional[ParameterManager] = None


def get_parameter_manager() -> ParameterManager:
    """
    Get global parameter manager instance
    
    Returns:
        ParameterManager instance
        
    Raises:
        ParameterManagerError: If parameter manager not initialized
    """
    global _parameter_manager
    if _parameter_manager is None:
        raise ParameterManagerError("Parameter manager not initialized. Call initialize_parameter_manager() first")
    return _parameter_manager


def initialize_parameter_manager(param_prefix: str = None, region: str = None) -> ParameterManager:
    """
    Initialize global parameter manager instance
    
    Args:
        param_prefix: Parameter prefix
        region: AWS region
        
    Returns:
        ParameterManager instance
    """
    global _parameter_manager
    _parameter_manager = ParameterManager(param_prefix, region)
    return _parameter_manager


# Convenience functions for common operations
def get_parameter(category: str, name: str, default: Any = None) -> Optional[str]:
    """Convenience function to get parameter"""
    return get_parameter_manager().get_parameter(category, name, default)


def get_parameters_by_category(category: str) -> Dict[str, str]:
    """Convenience function to get parameters by category"""
    return get_parameter_manager().get_parameters_by_category(category)


def set_parameter(category: str, name: str, value: str, description: str = None) -> bool:
    """Convenience function to set parameter"""
    return get_parameter_manager().set_parameter(category, name, value, description)