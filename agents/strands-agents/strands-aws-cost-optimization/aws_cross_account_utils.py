"""
AWS Cross-Account Utilities

Shared utilities for handling cross-account access, ARN validation, and environment configuration
across AWS agents. This module provides consistent functionality for both API and billing agents.
"""

import os
import re
import boto3
import logging
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_AWS_REGION = "us-east-1"
DEFAULT_ROLE_NAME = "COAReadOnlyRole"

# AWS credential environment variables
AWS_CREDENTIAL_VARS = [
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
    'AWS_PROFILE', 'AWS_DEFAULT_PROFILE', 'AWS_REGION', 'AWS_DEFAULT_REGION',
    'AWS_CONFIG_FILE', 'AWS_SHARED_CREDENTIALS_FILE'
]


def validate_role_arn(role_arn: str) -> bool:
    """
    Validate that the role ARN has the correct format.
    
    Args:
        role_arn: The role ARN to validate
        
    Returns:
        True if the ARN format is valid, False otherwise
    """
    if not role_arn:
        return False
        
    # AWS IAM role ARN pattern: arn:aws:iam::account-id:role/role-name
    pattern = r'^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@_-]+$'
    return bool(re.match(pattern, role_arn))


def validate_account_id(account_id: str) -> bool:
    """
    Validate that the account ID has the correct format.
    
    Args:
        account_id: The AWS account ID to validate
        
    Returns:
        True if the account ID format is valid, False otherwise
    """
    if not account_id:
        return False
    
    # AWS account ID is a 12-digit number
    return account_id.isdigit() and len(account_id) == 12


def construct_role_arn(account_id: str, role_name: str = DEFAULT_ROLE_NAME) -> str:
    """
    Construct a role ARN from account ID and role name.
    
    Args:
        account_id: The AWS account ID
        role_name: The IAM role name (defaults to COAReadOnlyRole)
        
    Returns:
        The constructed role ARN
        
    Raises:
        ValueError: If account_id format is invalid
    """
    if not validate_account_id(account_id):
        raise ValueError(f"Invalid account ID format: {account_id}. Expected 12-digit number.")
    
    return f"arn:aws:iam::{account_id}:role/{role_name}"


def resolve_cross_account_parameters(role_arn: Optional[str] = None, 
                                   account_id: Optional[str] = None,
                                   role_name: str = DEFAULT_ROLE_NAME) -> Optional[str]:
    """
    Resolve cross-account parameters to a final role ARN.
    
    Args:
        role_arn: Optional role ARN (takes precedence)
        account_id: Optional account ID (used to construct ARN if role_arn not provided)
        role_name: Role name to use when constructing from account_id
        
    Returns:
        The resolved role ARN, or None if no cross-account access needed
        
    Raises:
        ValueError: If parameters are invalid
    """
    if role_arn is not None and account_id is not None:
        logger.info(f"Both role_arn and account_id provided. Using role_arn: {role_arn}")
        logger.info(f"Ignoring account_id: {account_id}")
    
    if role_arn is not None:
        if not validate_role_arn(role_arn):
            raise ValueError(f"Invalid role ARN format: {role_arn}. Expected format: arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME")
        return role_arn
    
    if account_id is not None:
        resolved_arn = construct_role_arn(account_id, role_name)
        logger.info(f"Constructed role ARN from account ID: {resolved_arn}")
        return resolved_arn
    
    return None


def extract_credentials_from_session() -> Dict[str, str]:
    """
    Extract AWS credentials from the current boto3 session.
    
    Returns:
        Dictionary of credential environment variables
    """
    env = {}
    
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials:
            env['AWS_ACCESS_KEY_ID'] = credentials.access_key
            env['AWS_SECRET_ACCESS_KEY'] = credentials.secret_key
            if credentials.token:
                env['AWS_SESSION_TOKEN'] = credentials.token
            logger.info("✅ Extracted credentials from current boto3 session")
        else:
            logger.warning("⚠️  No credentials found in current session")
    except Exception as cred_error:
        logger.warning(f"⚠️  Failed to extract credentials from session: {cred_error}")
    
    return env


def get_environment_config(role_arn: Optional[str] = None, 
                          external_id: Optional[str] = None, 
                          session_name: Optional[str] = None, 
                          custom_env: Optional[Dict[str, str]] = None,
                          default_session_name: str = "aws-agent",
                          working_dir: str = "/tmp/aws-mcp/workdir") -> Dict[str, str]:
    """
    Get environment configuration for MCP server with AWS credentials and cross-account setup.
    
    Args:
        role_arn: Optional ARN of the role to assume for cross-account access
        external_id: Optional external ID for enhanced security when assuming roles
        session_name: Optional session name for the assumed role
        custom_env: Optional custom environment variables to merge
        default_session_name: Default session name if none provided
        working_dir: Working directory for the MCP server
        
    Returns:
        Dictionary of environment variables for MCP server
    """
    env = {}
    
    # Start with custom environment if provided
    if custom_env:
        env.update(custom_env)
    
    # Configure AssumeRole environment variables for the MCP server
    if role_arn is not None:
        if not validate_role_arn(role_arn):
            raise ValueError(f"Invalid role ARN format: {role_arn}. Expected format: arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME")
            
        logger.info(f"Configuring cross-account access to: {role_arn}")
        env["AWS_ASSUME_ROLE_ARN"] = role_arn
        env["AWS_ASSUME_ROLE_SESSION_NAME"] = session_name or default_session_name
        
        if external_id is not None:
            env["AWS_ASSUME_ROLE_EXTERNAL_ID"] = external_id
            logger.info("Using external ID for enhanced security")
            
        # Extract account ID from ARN for logging
        account_id = role_arn.split(':')[4]
        logger.info(f"Target account ID: {account_id}")
    else:
        # Ensure AssumeRole environment variables are not set if not using cross-account
        env.pop("AWS_ASSUME_ROLE_ARN", None)
        env.pop("AWS_ASSUME_ROLE_SESSION_NAME", None)
        env.pop("AWS_ASSUME_ROLE_EXTERNAL_ID", None)
        logger.info("Using same-account operations (no AssumeRole configured)")

    # Ensure AWS credentials are passed to the subprocess
    # This is critical for cross-account functionality to work
    for var in AWS_CREDENTIAL_VARS:
        if os.getenv(var) is not None:
            env[var] = os.getenv(var)
            logger.debug(f"Passing {var} to MCP server subprocess")
    
    # If no explicit credentials are set, try to extract from current session
    if not any(os.getenv(var) for var in ['AWS_ACCESS_KEY_ID', 'AWS_PROFILE']):
        session_creds = extract_credentials_from_session()
        env.update(session_creds)
    
    # Set standard AWS environment variables
    if not env.get("AWS_REGION"):
        env["AWS_REGION"] = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
        
    if os.getenv("BEDROCK_LOG_GROUP_NAME") is not None:
        env["BEDROCK_LOG_GROUP_NAME"] = os.getenv("BEDROCK_LOG_GROUP_NAME")
    
    # Set MCP server specific environment variables
    env["AWS_API_MCP_WORKING_DIR"] = working_dir
    env["FASTMCP_LOG_LEVEL"] = os.getenv("FASTMCP_LOG_LEVEL", "INFO")
    
    # Performance optimizations
    env["MCP_CLIENT_TIMEOUT"] = os.getenv("MCP_CLIENT_TIMEOUT", "300")  # 5 minutes
    env["MCP_MAX_RETRIES"] = os.getenv("MCP_MAX_RETRIES", "3")
    
    # Log environment (excluding secrets)
    safe_env = {k: v for k, v in env.items() if not k.startswith("AWS_SECRET")}
    logger.debug(f"MCP server environment: {safe_env}")
    
    return env


def get_current_identity() -> Dict[str, Any]:
    """
    Get the current AWS identity information.
    
    Returns:
        Dictionary containing caller identity information
    """
    try:
        sts_client = boto3.client('sts')
        return sts_client.get_caller_identity()
    except Exception as e:
        logger.error(f"Failed to get current identity: {e}")
        return {}


def handle_cross_account_parameters(role_arn: Optional[str] = None,
                                  account_id: Optional[str] = None,
                                  external_id: Optional[str] = None,
                                  session_name: Optional[str] = None,
                                  default_session_name: str = "aws-agent") -> Dict[str, Any]:
    """
    Handle and validate cross-account parameters, returning resolved configuration.
    
    Args:
        role_arn: Optional role ARN
        account_id: Optional account ID
        external_id: Optional external ID
        session_name: Optional session name
        default_session_name: Default session name prefix
        
    Returns:
        Dictionary containing resolved cross-account configuration
    """
    # Log debug information
    logger.debug(f"Cross-account parameters: role_arn={role_arn}, account_id={account_id}, "
                f"external_id={'***' if external_id else None}, session_name={session_name}")
    
    # Resolve role ARN
    resolved_role_arn = resolve_cross_account_parameters(role_arn, account_id)
    
    # Get current identity for debugging
    current_identity = get_current_identity()
    if current_identity:
        logger.info(f"Current identity: {current_identity}")
    
    return {
        "role_arn": resolved_role_arn,
        "external_id": external_id,
        "session_name": session_name or default_session_name,
        "current_identity": current_identity
    }


def format_cross_account_error(error_msg: str) -> str:
    """
    Format cross-account specific error messages with helpful guidance.
    
    Args:
        error_msg: The original error message
        
    Returns:
        Formatted error message with troubleshooting guidance
    """
    if "AssumeRole" in error_msg:
        return (f"Cross-account access error: {error_msg}\n\n"
                "Please verify:\n"
                "1. The target role ARN is correct\n"
                "2. The role trusts your current identity\n"
                "3. External ID matches (if required)\n"
                "4. Your current role has sts:AssumeRole permissions")
    elif "AccessDenied" in error_msg or "NoCredentialsError" in error_msg:
        return (f"AWS credentials error: {error_msg}\n\n"
                "Please ensure:\n"
                "1. AWS credentials are properly configured\n"
                "2. Your IAM user/role has the necessary permissions\n"
                "3. If using cross-account access, verify the AssumeRole configuration")
    else:
        return error_msg


# Utility functions for common patterns
def log_cross_account_success(role_arn: Optional[str], operation_type: str = "operations"):
    """Log successful cross-account operation completion."""
    if role_arn:
        logger.info(f"Successfully completed cross-account {operation_type} for: {role_arn}")
    else:
        logger.info(f"Successfully completed same-account {operation_type}")


def create_session_name(base_name: str, sequence: Optional[int] = None) -> str:
    """Create a session name with optional sequence number."""
    if sequence is not None:
        return f"{base_name}-{sequence}"
    return base_name