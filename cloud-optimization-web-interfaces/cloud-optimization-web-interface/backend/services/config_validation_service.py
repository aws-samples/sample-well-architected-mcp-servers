"""
Configuration Validation Service

This service provides comprehensive validation for parameter prefix configuration,
including startup-time validation, health checks, and parameter discovery validation.
"""

import os
import boto3
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime
import json
import re


logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Base exception for configuration validation errors"""
    pass


class ParameterPrefixValidationError(ConfigValidationError):
    """Raised when parameter prefix validation fails"""
    pass


class SSMConnectivityError(ConfigValidationError):
    """Raised when SSM connectivity validation fails"""
    pass


class ConfigurationValidationService:
    """
    Service for validating parameter prefix configuration and system health
    
    This service provides comprehensive validation capabilities including:
    - Parameter prefix format validation
    - SSM connectivity verification
    - Parameter discovery validation
    - Health check endpoints
    - Startup-time validation
    """
    
    def __init__(self, param_prefix: str = None, region: str = None):
        """
        Initialize configuration validation service
        
        Args:
            param_prefix: Parameter prefix to validate
            region: AWS region
        """
        self.param_prefix = param_prefix or os.getenv('PARAM_PREFIX')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            self.ssm_client = boto3.client('ssm', region_name=self.region)
            self.sts_client = boto3.client('sts', region_name=self.region)
        except NoCredentialsError:
            logger.error("AWS credentials not configured")
            raise ConfigValidationError("AWS credentials not configured")
        
        # Parameter categories and validation rules
        self.parameter_categories = ['agentcore', 'cognito', 'components', 'agent']
        self.validation_rules = {
            'max_prefix_length': 50,
            'allowed_characters': r'^[a-zA-Z0-9_]+$',
            'reserved_prefixes': ['aws', 'amazon', 'system'],
            'required_categories': self.parameter_categories
        }
        
        # Validation cache
        self._validation_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info(f"ConfigurationValidationService initialized with prefix: {self.param_prefix}, region: {self.region}")
    
    async def validate_startup_configuration(self) -> Dict[str, Any]:
        """
        Comprehensive startup-time validation
        
        Validates all aspects of parameter prefix configuration during application startup.
        
        Returns:
            Dictionary with validation results and recommendations
            
        Raises:
            ConfigValidationError: If critical validation fails
        """
        logger.info("Starting comprehensive configuration validation...")
        
        validation_result = {
            'timestamp': datetime.utcnow().isoformat(),
            'param_prefix': self.param_prefix,
            'region': self.region,
            'validation_status': 'unknown',
            'critical_errors': [],
            'warnings': [],
            'recommendations': [],
            'validation_details': {}
        }
        
        try:
            # 1. Validate parameter prefix format
            logger.info("Validating parameter prefix format...")
            prefix_validation = self._validate_parameter_prefix_format()
            validation_result['validation_details']['prefix_format'] = prefix_validation
            
            if not prefix_validation['valid']:
                validation_result['critical_errors'].extend(prefix_validation['errors'])
            
            # 2. Validate AWS connectivity and permissions
            logger.info("Validating AWS connectivity and permissions...")
            aws_validation = await self._validate_aws_connectivity()
            validation_result['validation_details']['aws_connectivity'] = aws_validation
            
            if not aws_validation['valid']:
                validation_result['critical_errors'].extend(aws_validation['errors'])
            
            # 3. Validate SSM parameter access
            logger.info("Validating SSM parameter access...")
            ssm_validation = await self._validate_ssm_parameter_access()
            validation_result['validation_details']['ssm_access'] = ssm_validation
            
            if not ssm_validation['valid']:
                validation_result['critical_errors'].extend(ssm_validation['errors'])
            
            # 4. Validate parameter structure and discovery
            logger.info("Validating parameter structure...")
            structure_validation = await self._validate_parameter_structure()
            validation_result['validation_details']['parameter_structure'] = structure_validation
            
            if structure_validation['warnings']:
                validation_result['warnings'].extend(structure_validation['warnings'])
            
            # 5. Check for legacy parameters and migration needs
            logger.info("Checking for legacy parameters...")
            migration_validation = await self._validate_migration_status()
            validation_result['validation_details']['migration_status'] = migration_validation
            
            if migration_validation['migration_needed']:
                validation_result['warnings'].append("Legacy parameters detected - migration may be needed")
            
            # 6. Generate recommendations
            validation_result['recommendations'] = self._generate_recommendations(validation_result)
            
            # Determine overall validation status
            if validation_result['critical_errors']:
                validation_result['validation_status'] = 'failed'
                logger.error(f"Configuration validation failed with {len(validation_result['critical_errors'])} critical errors")
            elif validation_result['warnings']:
                validation_result['validation_status'] = 'warning'
                logger.warning(f"Configuration validation completed with {len(validation_result['warnings'])} warnings")
            else:
                validation_result['validation_status'] = 'success'
                logger.info("Configuration validation completed successfully")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Unexpected error during configuration validation: {e}")
            validation_result['critical_errors'].append(f"Validation error: {str(e)}")
            validation_result['validation_status'] = 'error'
            return validation_result
    
    def _validate_parameter_prefix_format(self) -> Dict[str, Any]:
        """Validate parameter prefix format against AWS and COA requirements"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'details': {}
        }
        
        if not self.param_prefix:
            validation_result['valid'] = False
            validation_result['errors'].append("Parameter prefix not configured (PARAM_PREFIX environment variable missing)")
            return validation_result
        
        # Check length
        if len(self.param_prefix) > self.validation_rules['max_prefix_length']:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Parameter prefix too long: {len(self.param_prefix)} > {self.validation_rules['max_prefix_length']}")
        
        # Check character pattern
        if not re.match(self.validation_rules['allowed_characters'], self.param_prefix):
            validation_result['valid'] = False
            validation_result['errors'].append(f"Parameter prefix contains invalid characters: {self.param_prefix}")
        
        # Check for reserved prefixes
        if self.param_prefix.lower() in self.validation_rules['reserved_prefixes']:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Parameter prefix uses reserved name: {self.param_prefix}")
        
        # Check if starts with number
        if self.param_prefix and self.param_prefix[0].isdigit():
            validation_result['valid'] = False
            validation_result['errors'].append(f"Parameter prefix cannot start with a number: {self.param_prefix}")
        
        # Check for consecutive underscores
        if '__' in self.param_prefix:
            validation_result['warnings'].append(f"Parameter prefix contains consecutive underscores: {self.param_prefix}")
        
        validation_result['details'] = {
            'prefix': self.param_prefix,
            'length': len(self.param_prefix) if self.param_prefix else 0,
            'character_pattern_valid': bool(re.match(self.validation_rules['allowed_characters'], self.param_prefix or '')),
            'reserved_prefix': self.param_prefix.lower() in self.validation_rules['reserved_prefixes'] if self.param_prefix else False
        }
        
        return validation_result
    
    async def _validate_aws_connectivity(self) -> Dict[str, Any]:
        """Validate AWS connectivity and basic permissions"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'details': {}
        }
        
        try:
            # Test STS connectivity and get caller identity
            identity = self.sts_client.get_caller_identity()
            validation_result['details']['account_id'] = identity.get('Account')
            validation_result['details']['user_arn'] = identity.get('Arn')
            validation_result['details']['user_id'] = identity.get('UserId')
            
            logger.info(f"AWS connectivity verified - Account: {identity.get('Account')}")
            
        except NoCredentialsError:
            validation_result['valid'] = False
            validation_result['errors'].append("AWS credentials not found")
        except ClientError as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"AWS connectivity error: {e}")
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Unexpected AWS error: {e}")
        
        return validation_result
    
    async def _validate_ssm_parameter_access(self) -> Dict[str, Any]:
        """Validate SSM Parameter Store access and permissions"""
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'details': {}
        }
        
        try:
            # Test basic SSM connectivity
            response = self.ssm_client.describe_parameters(MaxResults=1)
            validation_result['details']['ssm_connectivity'] = True
            
            # Test parameter access for each category
            category_access = {}
            for category in self.parameter_categories:
                try:
                    parameter_path = f"/{self.param_prefix}/{category}"
                    
                    # Try to list parameters in this path
                    response = self.ssm_client.get_parameters_by_path(
                        Path=parameter_path,
                        MaxResults=1
                    )
                    
                    category_access[category] = {
                        'accessible': True,
                        'parameter_count': len(response.get('Parameters', [])),
                        'path': parameter_path
                    }
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'AccessDenied':
                        validation_result['errors'].append(f"Access denied for category {category}: {parameter_path}")
                        category_access[category] = {
                            'accessible': False,
                            'error': 'AccessDenied',
                            'path': parameter_path
                        }
                    else:
                        # Other errors are not necessarily critical (e.g., no parameters exist yet)
                        category_access[category] = {
                            'accessible': True,
                            'parameter_count': 0,
                            'path': parameter_path,
                            'note': f"No parameters found ({error_code})"
                        }
            
            validation_result['details']['category_access'] = category_access
            
            # Check if any categories are inaccessible
            inaccessible_categories = [cat for cat, access in category_access.items() if not access['accessible']]
            if inaccessible_categories:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Cannot access parameter categories: {', '.join(inaccessible_categories)}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                validation_result['valid'] = False
                validation_result['errors'].append("Access denied to SSM Parameter Store")
            else:
                validation_result['valid'] = False
                validation_result['errors'].append(f"SSM access error: {e}")
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Unexpected SSM error: {e}")
        
        return validation_result
    
    async def _validate_parameter_structure(self) -> Dict[str, Any]:
        """Validate parameter structure and discover existing parameters"""
        validation_result = {
            'warnings': [],
            'details': {}
        }
        
        parameter_discovery = {}
        total_parameters = 0
        
        for category in self.parameter_categories:
            try:
                parameter_path = f"/{self.param_prefix}/{category}"
                
                # Get all parameters for this category
                response = self.ssm_client.get_parameters_by_path(
                    Path=parameter_path,
                    Recursive=True
                )
                
                parameters = response.get('Parameters', [])
                parameter_count = len(parameters)
                total_parameters += parameter_count
                
                parameter_discovery[category] = {
                    'path': parameter_path,
                    'parameter_count': parameter_count,
                    'parameters': [
                        {
                            'name': param['Name'],
                            'type': param['Type'],
                            'last_modified': param['LastModifiedDate'].isoformat(),
                            'version': param['Version']
                        }
                        for param in parameters
                    ]
                }
                
                if parameter_count == 0:
                    validation_result['warnings'].append(f"No parameters found for category: {category}")
                
            except Exception as e:
                parameter_discovery[category] = {
                    'path': parameter_path,
                    'error': str(e),
                    'parameter_count': 0
                }
                validation_result['warnings'].append(f"Error discovering parameters for {category}: {e}")
        
        validation_result['details'] = {
            'total_parameters': total_parameters,
            'categories': parameter_discovery,
            'discovery_timestamp': datetime.utcnow().isoformat()
        }
        
        return validation_result
    
    async def _validate_migration_status(self) -> Dict[str, Any]:
        """Check for legacy parameters and migration requirements"""
        migration_result = {
            'migration_needed': False,
            'legacy_parameters_found': {},
            'current_parameters_found': {},
            'recommendations': []
        }
        
        legacy_prefix = "/coa"
        
        for category in self.parameter_categories:
            try:
                # Check current parameters
                current_path = f"/{self.param_prefix}/{category}"
                current_response = self.ssm_client.get_parameters_by_path(
                    Path=current_path,
                    Recursive=True
                )
                current_count = len(current_response.get('Parameters', []))
                migration_result['current_parameters_found'][category] = current_count
                
                # Check legacy parameters
                legacy_path = f"{legacy_prefix}/{category}"
                try:
                    legacy_response = self.ssm_client.get_parameters_by_path(
                        Path=legacy_path,
                        Recursive=True
                    )
                    legacy_count = len(legacy_response.get('Parameters', []))
                    migration_result['legacy_parameters_found'][category] = legacy_count
                    
                    # Determine if migration is needed
                    if legacy_count > 0 and current_count == 0:
                        migration_result['migration_needed'] = True
                        migration_result['recommendations'].append(
                            f"Consider migrating {legacy_count} parameters from {legacy_path} to {current_path}"
                        )
                    elif legacy_count > 0 and current_count > 0:
                        migration_result['recommendations'].append(
                            f"Both legacy ({legacy_count}) and current ({current_count}) parameters exist for {category}"
                        )
                
                except ClientError:
                    # Legacy parameters don't exist, which is fine
                    migration_result['legacy_parameters_found'][category] = 0
                
            except Exception as e:
                logger.warning(f"Error checking migration status for {category}: {e}")
                migration_result['current_parameters_found'][category] = f"Error: {str(e)}"
                migration_result['legacy_parameters_found'][category] = 0
        
        return migration_result
    
    def _generate_recommendations(self, validation_result: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Critical error recommendations
        if validation_result['critical_errors']:
            recommendations.append("Address critical configuration errors before proceeding")
            
            for error in validation_result['critical_errors']:
                if "Parameter prefix not configured" in error:
                    recommendations.append("Set PARAM_PREFIX environment variable with a valid parameter prefix")
                elif "AWS credentials" in error:
                    recommendations.append("Configure AWS credentials via IAM role, environment variables, or AWS CLI")
                elif "Access denied" in error:
                    recommendations.append("Ensure IAM permissions include ssm:GetParameter, ssm:GetParametersByPath, and ssm:DescribeParameters")
        
        # Warning-based recommendations
        if validation_result['warnings']:
            for warning in validation_result['warnings']:
                if "No parameters found" in warning:
                    recommendations.append("Run deployment scripts to create required SSM parameters")
                elif "Legacy parameters detected" in warning:
                    recommendations.append("Consider running parameter migration to move from legacy /coa/ prefix")
        
        # Migration recommendations
        migration_details = validation_result['validation_details'].get('migration_status', {})
        if migration_details.get('migration_needed'):
            recommendations.append("Run parameter migration script: python deployment-scripts/migrate_parameters.py")
        
        # Performance recommendations
        structure_details = validation_result['validation_details'].get('parameter_structure', {})
        if structure_details.get('details', {}).get('total_parameters', 0) > 100:
            recommendations.append("Consider parameter cleanup for better performance with large parameter sets")
        
        return recommendations
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Health check endpoint for parameter configuration
        
        Returns:
            Health check results suitable for API endpoints
        """
        try:
            # Use cached validation if available and recent
            cache_key = f"health_check_{self.param_prefix}"
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            health_result = {
                'status': 'unknown',
                'param_prefix': self.param_prefix,
                'region': self.region,
                'timestamp': datetime.utcnow().isoformat(),
                'checks': {}
            }
            
            # Quick validation checks
            prefix_check = self._validate_parameter_prefix_format()
            health_result['checks']['prefix_format'] = {
                'status': 'healthy' if prefix_check['valid'] else 'unhealthy',
                'details': prefix_check['details']
            }
            
            # SSM connectivity check
            try:
                self.ssm_client.describe_parameters(MaxResults=1)
                health_result['checks']['ssm_connectivity'] = {
                    'status': 'healthy',
                    'details': {'connectivity': True}
                }
            except Exception as e:
                health_result['checks']['ssm_connectivity'] = {
                    'status': 'unhealthy',
                    'details': {'error': str(e)}
                }
            
            # Parameter access check (quick test)
            accessible_categories = 0
            for category in self.parameter_categories:
                try:
                    parameter_path = f"/{self.param_prefix}/{category}"
                    self.ssm_client.get_parameters_by_path(Path=parameter_path, MaxResults=1)
                    accessible_categories += 1
                except Exception:
                    pass
            
            health_result['checks']['parameter_access'] = {
                'status': 'healthy' if accessible_categories == len(self.parameter_categories) else 'degraded',
                'details': {
                    'accessible_categories': accessible_categories,
                    'total_categories': len(self.parameter_categories)
                }
            }
            
            # Determine overall health status
            check_statuses = [check['status'] for check in health_result['checks'].values()]
            if all(status == 'healthy' for status in check_statuses):
                health_result['status'] = 'healthy'
            elif any(status == 'unhealthy' for status in check_statuses):
                health_result['status'] = 'unhealthy'
            else:
                health_result['status'] = 'degraded'
            
            # Cache the result
            self._set_cache(cache_key, health_result)
            
            return health_result
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def validate_parameter_discovery(self, deployment_scripts_path: str = None) -> Dict[str, Any]:
        """
        Validate parameter discovery for deployment scripts
        
        Args:
            deployment_scripts_path: Path to deployment scripts directory
            
        Returns:
            Validation results for parameter discovery
        """
        discovery_result = {
            'validation_status': 'unknown',
            'param_prefix': self.param_prefix,
            'parameter_discovery': {},
            'deployment_validation': {},
            'recommendations': [],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            # Validate parameter structure
            structure_validation = await self._validate_parameter_structure()
            discovery_result['parameter_discovery'] = structure_validation['details']
            
            # Check if deployment scripts can access configuration
            if deployment_scripts_path:
                deployment_validation = self._validate_deployment_script_access(deployment_scripts_path)
                discovery_result['deployment_validation'] = deployment_validation
            
            # Generate discovery-specific recommendations
            total_params = discovery_result['parameter_discovery'].get('total_parameters', 0)
            if total_params == 0:
                discovery_result['recommendations'].append("No parameters found - run deployment scripts to initialize")
            elif total_params < 10:
                discovery_result['recommendations'].append("Few parameters found - deployment may be incomplete")
            
            discovery_result['validation_status'] = 'success'
            
        except Exception as e:
            discovery_result['validation_status'] = 'error'
            discovery_result['error'] = str(e)
        
        return discovery_result
    
    def _validate_deployment_script_access(self, deployment_scripts_path: str) -> Dict[str, Any]:
        """Validate that deployment scripts can access configuration"""
        validation_result = {
            'config_file_exists': False,
            'config_file_valid': False,
            'param_prefix_matches': False,
            'details': {}
        }
        
        try:
            import json
            from pathlib import Path
            
            config_file = Path(deployment_scripts_path) / "deployment-config.json"
            
            if config_file.exists():
                validation_result['config_file_exists'] = True
                
                try:
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    validation_result['config_file_valid'] = True
                    
                    # Check if parameter prefix matches
                    config_prefix = config.get('deployment', {}).get('param_prefix')
                    validation_result['param_prefix_matches'] = (config_prefix == self.param_prefix)
                    validation_result['details'] = {
                        'config_prefix': config_prefix,
                        'runtime_prefix': self.param_prefix
                    }
                    
                except Exception as e:
                    validation_result['details']['config_error'] = str(e)
            
        except Exception as e:
            validation_result['details']['validation_error'] = str(e)
        
        return validation_result
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from validation cache if not expired"""
        if key in self._validation_cache:
            value, timestamp = self._validation_cache[key]
            if (datetime.utcnow().timestamp() - timestamp) < self._cache_ttl:
                return value
            else:
                del self._validation_cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any) -> None:
        """Set value in validation cache with timestamp"""
        self._validation_cache[key] = (value, datetime.utcnow().timestamp())
    
    def clear_cache(self) -> None:
        """Clear validation cache"""
        self._validation_cache.clear()
        logger.debug("Validation cache cleared")


# Global validation service instance
_validation_service: Optional[ConfigurationValidationService] = None


def get_validation_service() -> ConfigurationValidationService:
    """
    Get global validation service instance
    
    Returns:
        ConfigurationValidationService instance
        
    Raises:
        ConfigValidationError: If validation service not initialized
    """
    global _validation_service
    if _validation_service is None:
        raise ConfigValidationError("Validation service not initialized")
    return _validation_service


def initialize_validation_service(param_prefix: str = None, region: str = None) -> ConfigurationValidationService:
    """
    Initialize global validation service instance
    
    Args:
        param_prefix: Parameter prefix
        region: AWS region
        
    Returns:
        ConfigurationValidationService instance
    """
    global _validation_service
    _validation_service = ConfigurationValidationService(param_prefix, region)
    return _validation_service