# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions for AWS credential management including AssumeRole support."""

import os
import sys
from typing import Optional

import boto3
from botocore.config import Config
from loguru import logger

from .config import get_user_agent_extra, AWS_API_MCP_PROFILE_NAME, get_region
from .models import Credentials

# Configure Loguru logging
logger.remove()
logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'INFO'))

# User agent configuration for AWS API calls
USER_AGENT_CONFIG = Config(
    user_agent_extra=get_user_agent_extra()
)


def create_aws_session() -> boto3.Session:
    """Create an AWS session with support for AssumeRole via environment variables.
    
    This function checks for AssumeRole environment variables and creates an appropriate
    session. If AssumeRole variables are present, it assumes the specified role.
    Otherwise, it falls back to the default AWS credentials chain.
    
    Environment Variables for AssumeRole:
    - AWS_ASSUME_ROLE_ARN: The ARN of the role to assume (required for AssumeRole)
    - AWS_ASSUME_ROLE_SESSION_NAME: Session name for the assumed role (optional, defaults to 'aws-api-mcp-session')
    - AWS_ASSUME_ROLE_EXTERNAL_ID: External ID for enhanced security (optional)
    
    Standard AWS Environment Variables:
    - AWS_API_MCP_PROFILE_NAME: AWS profile to use (optional)
    - AWS_REGION: AWS region (optional, uses boto3 default)
    
    Returns:
        boto3.Session: Configured AWS session
        
    Raises:
        Exception: If AssumeRole operation fails
    """
    assume_role_arn = os.environ.get("AWS_ASSUME_ROLE_ARN")
    
    if assume_role_arn:
        logger.info(f"AssumeRole configuration detected. Assuming role: {assume_role_arn}")
        return _create_assume_role_session(assume_role_arn)
    else:
        logger.info("Using default AWS credentials chain")
        return _create_default_session()


def _create_default_session() -> boto3.Session:
    """Create a session using the default AWS credentials chain.
    
    Returns:
        boto3.Session: Session with default credentials
    """
    # Use the existing profile logic from the original implementation
    profile_name = AWS_API_MCP_PROFILE_NAME
    region = get_region(profile_name)
    
    if profile_name:
        logger.info(f"Using AWS profile: {profile_name}")
        return boto3.Session(profile_name=profile_name, region_name=region)
    else:
        logger.info(f"Using default AWS credentials chain with region: {region}")
        return boto3.Session(region_name=region)


def _create_assume_role_session(role_arn: str) -> boto3.Session:
    """Create a session using AssumeRole with the specified role ARN.
    
    Args:
        role_arn: The ARN of the role to assume
        
    Returns:
        boto3.Session: Session with assumed role credentials
        
    Raises:
        Exception: If AssumeRole operation fails
    """
    try:
        # Get optional parameters from environment
        session_name = os.environ.get("AWS_ASSUME_ROLE_SESSION_NAME", "aws-api-mcp-session")
        external_id = os.environ.get("AWS_ASSUME_ROLE_EXTERNAL_ID")
        
        # Create initial session for STS operations
        initial_session = _create_default_session()
        sts_client = initial_session.client("sts", config=USER_AGENT_CONFIG)
        
        # Prepare AssumeRole parameters
        assume_role_params = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
        }
        
        # Add external ID if provided
        if external_id:
            assume_role_params["ExternalId"] = external_id
            logger.info("Using external ID for AssumeRole operation")
        
        logger.info(f"Attempting to assume role with session name: {session_name}")
        
        # Assume the role
        response = sts_client.assume_role(**assume_role_params)
        credentials = response["Credentials"]
        
        # Get region from initial session or environment
        region = initial_session.region_name or get_region()
        
        # Create new session with assumed role credentials
        assumed_session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=region,
        )
        
        logger.info("Successfully assumed role and created session")
        
        # Log some basic info about the assumed role (without sensitive data)
        assumed_role_info = response.get("AssumedRoleUser", {})
        if assumed_role_info:
            logger.info(f"Assumed role user ARN: {assumed_role_info.get('Arn', 'Unknown')}")
        
        return assumed_session
        
    except Exception as e:
        logger.error(f"Failed to assume role {role_arn}: {str(e)}")
        raise Exception(f"AssumeRole operation failed: {str(e)}")


def get_session_info(session: boto3.Session) -> dict:
    """Get information about the current AWS session for debugging purposes.
    
    Args:
        session: The boto3 session to inspect
        
    Returns:
        dict: Information about the session including caller identity
    """
    try:
        sts_client = session.client("sts", config=USER_AGENT_CONFIG)
        caller_identity = sts_client.get_caller_identity()
        
        return {
            "account_id": caller_identity.get("Account"),
            "user_id": caller_identity.get("UserId"),
            "arn": caller_identity.get("Arn"),
            "assume_role_configured": bool(os.environ.get("AWS_ASSUME_ROLE_ARN")),
        }
    except Exception as e:
        logger.warning(f"Could not retrieve session info: {str(e)}")
        return {
            "error": str(e),
            "assume_role_configured": bool(os.environ.get("AWS_ASSUME_ROLE_ARN")),
        }


def validate_assume_role_config() -> dict:
    """Validate AssumeRole configuration from environment variables.
    
    Returns:
        dict: Validation results with status and any issues found
    """
    assume_role_arn = os.environ.get("AWS_ASSUME_ROLE_ARN")
    
    if not assume_role_arn:
        return {
            "configured": False,
            "valid": True,
            "message": "No AssumeRole configuration found. Using default credentials chain.",
        }
    
    issues = []
    
    # Validate ARN format
    if not assume_role_arn.startswith("arn:aws:iam::"):
        issues.append("AWS_ASSUME_ROLE_ARN does not appear to be a valid IAM role ARN")
    
    # Check session name
    session_name = os.environ.get("AWS_ASSUME_ROLE_SESSION_NAME", "aws-api-mcp-session")
    if len(session_name) < 2 or len(session_name) > 64:
        issues.append("AWS_ASSUME_ROLE_SESSION_NAME must be between 2 and 64 characters")
    
    # Check external ID if provided
    external_id = os.environ.get("AWS_ASSUME_ROLE_EXTERNAL_ID")
    if external_id and (len(external_id) < 2 or len(external_id) > 1224):
        issues.append("AWS_ASSUME_ROLE_EXTERNAL_ID must be between 2 and 1224 characters")
    
    return {
        "configured": True,
        "valid": len(issues) == 0,
        "role_arn": assume_role_arn,
        "session_name": session_name,
        "external_id_configured": bool(external_id),
        "issues": issues,
        "message": "AssumeRole configuration is valid" if len(issues) == 0 else f"Configuration issues: {'; '.join(issues)}",
    }


def get_enhanced_credentials(profile: str | None = None) -> Credentials:
    """Get AWS credentials with enhanced support for AssumeRole.
    
    This function replaces the original get_local_credentials function and adds
    support for cross-account AssumeRole operations while maintaining backward
    compatibility with profile-based authentication.
    
    Args:
        profile: Optional AWS profile name (overrides AssumeRole if both are configured)
        
    Returns:
        Credentials: AWS credentials object
        
    Raises:
        Exception: If credential retrieval fails
    """
    try:
        # If a specific profile is requested, use it directly (backward compatibility)
        if profile:
            logger.info(f"Using specified profile: {profile}")
            session = boto3.Session(profile_name=profile)
        else:
            # Use enhanced session creation with AssumeRole support
            session = create_aws_session()
        
        aws_creds = session.get_credentials()
        
        if aws_creds is None:
            from botocore.exceptions import NoCredentialsError
            raise NoCredentialsError()
        
        return Credentials(
            access_key_id=aws_creds.access_key,
            secret_access_key=aws_creds.secret_key,
            session_token=aws_creds.token,
        )
        
    except Exception as e:
        logger.error(f"Failed to get enhanced credentials: {str(e)}")
        raise