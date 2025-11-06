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
Configuration Service - Manages application configuration with SSM Parameter Store fallback to .env
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class ConfigService:
    def __init__(self, ssm_prefix: str = "/coa/"):
        self.ssm_prefix = ssm_prefix
        self._ssm_client = None
        self._config_cache = {}
        self._ssm_available = None
        self._initialization_attempted = False

        # Load .env file first as baseline
        self._load_env_file()

        # Initialize SSM client on startup
        self._initialize_ssm_client()

    def _initialize_ssm_client(self):
        """Initialize SSM client with proper error handling"""
        if self._initialization_attempted:
            return

        self._initialization_attempted = True

        try:
            region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
            logger.info(f"Initializing SSM client in region: {region}")

            self._ssm_client = boto3.client("ssm", region_name=region)

            # Test SSM connectivity and permissions
            self._ssm_client.describe_parameters(MaxResults=1)
            self._ssm_available = True
            logger.info("✓ SSM client initialized successfully")

            # Test parameter access with our prefix
            if self.ssm_prefix:
                try:
                    self._ssm_client.describe_parameters(
                        ParameterFilters=[
                            {
                                "Key": "Name",
                                "Option": "BeginsWith",
                                "Values": [self.ssm_prefix],
                            }
                        ],
                        MaxResults=1,
                    )
                    logger.info(
                        f"✓ SSM parameter access verified for prefix: {self.ssm_prefix}"
                    )
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ParameterNotFound":
                        logger.warning(f"SSM parameter access test failed: {e}")

        except (ClientError, NoCredentialsError) as e:
            logger.warning(f"SSM client initialization failed: {e}")
            self._ssm_available = False
            self._ssm_client = None
        except Exception as e:
            logger.warning(f"Unexpected error initializing SSM client: {e}")
            self._ssm_available = False
            self._ssm_client = None

    @property
    def ssm_client(self):
        """Get SSM client, initializing if needed"""
        if not self._initialization_attempted:
            self._initialize_ssm_client()
        return self._ssm_client

    def _load_env_file(self):
        """Load environment variables from .env file"""
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            logger.info(f"Loading .env file from {env_file}")
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
        else:
            logger.info("No .env file found")

    def get_config_value(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        """
        Get configuration value with priority: SSM Parameter Store > Environment Variable > Default

        Args:
            key: Configuration key (e.g., 'AWS_DEFAULT_REGION')
            default: Default value if not found anywhere

        Returns:
        """
        # Check cache first
        cache_key = f"ssm:{key}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        # Try SSM Parameter Store first
        ssm_value = self._get_ssm_parameter(key)
        if ssm_value is not None:
            self._config_cache[cache_key] = ssm_value
            return ssm_value

        # Fallback to environment variable
        env_value = os.environ.get(key)
        if env_value is not None:
            logger.debug(f"Using environment variable for {key}")
            return env_value

        # Return default
        logger.debug(f"Using default value for {key}: {default}")
        return default

    def _get_ssm_parameter(self, key: str) -> Optional[str]:
        """Get parameter from SSM Parameter Store with fallback to legacy paths"""
        if not self.ssm_client or self._ssm_available is False:
            return None

        # Try to use parameter manager with fallback if available
        try:
            from utils.parameter_manager import get_parameter_manager
            parameter_manager = get_parameter_manager()
            
            # Map configuration keys to category and parameter names
            parameter_mapping = {
                "ENHANCED_SECURITY_AGENT_ID": ("agents", "strands_aws_wa_sec_cost/agent_id"),
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": ("agents", "strands_aws_wa_sec_cost/agent_alias_id"),
            }
            
            if key in parameter_mapping:
                category, param_name = parameter_mapping[key]
                try:
                    # Try with parameter manager fallback
                    value = parameter_manager.get_parameter_with_fallback(category, param_name)
                    if value:
                        logger.info(f"Retrieved {key} using parameter manager")
                        return value
                except Exception as e:
                    logger.debug(f"Parameter manager fallback failed for {key}: {e}")
            
        except Exception as e:
            logger.debug(f"Parameter manager not available: {e}")

        # Fallback to direct SSM access with legacy paths
        legacy_parameter_mapping = {
            "ENHANCED_SECURITY_AGENT_ID": "/coa/agents/strands_aws_wa_sec_cost/agent_id",
            "ENHANCED_SECURITY_AGENT_ALIAS_ID": "/coa/agents/strands_aws_wa_sec_cost/agent_alias_id",
        }

        parameter_name = legacy_parameter_mapping.get(key)
        if not parameter_name:
            return None

        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True,  # Decrypt SecureString parameters
            )
            value = response["Parameter"]["Value"]
            logger.warning(f"Using legacy parameter path for {key}: {parameter_name}")

            # Special handling for USE_MULTI_AGENT_SUPERVISOR - extract status from metadata
            if key == "USE_MULTI_AGENT_SUPERVISOR":
                try:
                    import json

                    metadata = json.loads(value)
                    # Return "true" if status is DEPLOYED, "false" otherwise
                    return "true" if metadata.get("status") == "DEPLOYED" else "false"
                except (json.JSONDecodeError, KeyError):
                    logger.warning(f"Failed to parse metadata for {key}")
                    return "false"

            logger.info(f"Retrieved {key} from SSM Parameter Store")
            return value

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ParameterNotFound":
                logger.debug(f"SSM parameter not found: {parameter_name}")
            else:
                logger.warning(f"Error retrieving SSM parameter {parameter_name}: {e}")
            return None
        except Exception as e:
            logger.warning(
                f"Unexpected error retrieving SSM parameter {parameter_name}: {e}"
            )
            return None

    def get_all_config(self) -> Dict[str, str]:
        """Get all configuration values for the application"""
        config_keys = [
            # AWS Configuration
            "AWS_ROLE_ARN",
            "AWS_ROLE_SESSION_NAME",
            # Enhanced Security Agent Configuration
            "ENHANCED_SECURITY_AGENT_ID",
            "ENHANCED_SECURITY_AGENT_ALIAS_ID",
            # Multi-Agent Supervisor Configuration
            "USE_MULTI_AGENT_SUPERVISOR",
            "MULTI_AGENT_SUPERVISOR_AGENT_ID",
            "MULTI_AGENT_SUPERVISOR_AGENT_ALIAS_ID",
        ]

        config = {}
        for key in config_keys:
            value = self.get_config_value(key)
            if value is not None:
                config[key] = value

        return config

    def refresh_cache(self):
        """Clear configuration cache to force refresh from SSM"""
        self._config_cache.clear()
        logger.info("Configuration cache cleared")

    def get_ssm_status(self) -> Dict[str, Any]:
        """Get SSM connectivity status"""
        return {
            "available": self._ssm_available,
            "prefix": self.ssm_prefix,
            "cached_parameters": len(self._config_cache),
        }

    def set_ssm_parameter(
        self,
        key: str,
        value: str,
        parameter_type: str = "String",
        description: str = None,
    ) -> bool:
        """
        Set a parameter in SSM Parameter Store

        Args:
            key: Parameter key
            value: Parameter value
            parameter_type: SSM parameter type (String, StringList, SecureString)
            description: Parameter description

        Returns:
            True if successful, False otherwise
        """
        if not self.ssm_client:
            logger.error("SSM client not available")
            return False

        parameter_name = f"{self.ssm_prefix}/{key}"

        try:
            put_params = {
                "Name": parameter_name,
                "Value": value,
                "Type": parameter_type,
                "Overwrite": True,
            }

            if description:
                put_params["Description"] = description

            self.ssm_client.put_parameter(**put_params)

            # Clear cache for this parameter
            cache_key = f"ssm:{key}"
            if cache_key in self._config_cache:
                del self._config_cache[cache_key]

            logger.info(f"Successfully set SSM parameter: {parameter_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to set SSM parameter {parameter_name}: {e}")
            return False

    def list_ssm_parameters(self) -> Dict[str, Any]:
        """List all parameters under the configured prefix"""
        if not self.ssm_client:
            return {"error": "SSM client not available"}

        try:
            response = self.ssm_client.describe_parameters(
                ParameterFilters=[
                    {"Key": "Name", "Option": "BeginsWith", "Values": [self.ssm_prefix]}
                ]
            )

            parameters = []
            for param in response.get("Parameters", []):
                parameters.append(
                    {
                        "name": param["Name"],
                        "type": param["Type"],
                        "last_modified": param.get("LastModifiedDate"),
                        "description": param.get("Description", ""),
                    }
                )

            return {"parameters": parameters, "count": len(parameters)}

        except Exception as e:
            logger.error(f"Failed to list SSM parameters: {e}")
            return {"error": str(e)}


# Global configuration service instance with dynamic parameter prefix
def _get_param_prefix():
    """Get parameter prefix from deployment config or environment variable"""
    # First try environment variable
    env_prefix = os.environ.get('PARAM_PREFIX')
    if env_prefix:
        return f"/{env_prefix}/"
    
    # Then try deployment config file
    try:
        import json
        from pathlib import Path
        
        # Look for deployment-config.json in the project root
        config_path = Path(__file__).parent.parent.parent.parent / "deployment-config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            param_prefix = config.get('deployment', {}).get('param_prefix', 'coa')
            return f"/{param_prefix}/"
    except Exception as e:
        logger.warning(f"Failed to load deployment config: {e}")
    
    # Fallback to default
    return "/coa/"

config_service = ConfigService(ssm_prefix=_get_param_prefix())


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to get configuration value"""
    return config_service.get_config_value(key, default)
