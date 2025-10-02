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

"""Utility functions for AWS credential management including AssumeRole support."""

import os
from typing import Optional

import boto3
from botocore.config import Config
from loguru import logger

from src import __version__

# User agent configuration for AWS API calls
USER_AGENT_CONFIG = Config(
    user_agent_extra=f"awslabs/mcp/well-architected-security-mcp-server/{__version__}"
)


def create_aws_session() -> boto3.Session:
    """Create an AWS session with support for AssumeRole via environment variables.
    
    This function checks for AssumeRole environment variables and creates an appropriate
    session. If AssumeRole variables are present, it assumes the specified role.
    Otherwise, it falls back to the default AWS credentials chain.
    
    Environment Variables for AssumeRole:
    - AWS_ASSUME_ROLE_ARN: The ARN of the role to assume (required for AssumeRole)
    - AWS_ASSUME_ROLE_SESSION_NAME: Session name for the assumed role (optional, defaults to 'mcp-server-session')
    - AWS_ASSUME_ROLE_EXTERNAL_ID: External ID for enhanced security (optional)
    
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
        return boto3.Session()


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
        session_name = os.environ.get("AWS_ASSUME_ROLE_SESSION_NAME", "mcp-server-session")
        external_id = os.environ.get("AWS_ASSUME_ROLE_EXTERNAL_ID")
        
        # Create initial session for STS operations
        initial_session = boto3.Session()
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
        
        # Create new session with assumed role credentials
        assumed_session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
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
    session_name = os.environ.get("AWS_ASSUME_ROLE_SESSION_NAME", "mcp-server-session")
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