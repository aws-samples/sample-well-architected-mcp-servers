#!/usr/bin/env python3

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
Generate CloudFormation template for remote IAM roles that can be assumed by AgentCore Runtime.

This script creates CloudFormation templates for deploying IAM roles in target AWS accounts
that can be assumed by the AgentCore Runtime Role, enabling MCP servers to perform
cross-account operations.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import yaml
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("remote_role_stack_generation.log"),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class RemoteRoleConfig:
    """Configuration for remote role generation."""

    runtime_role_arn: str
    role_name: str
    external_id: Optional[str] = None
    additional_managed_policies: List[str] = None
    custom_policy_statements: List[Dict[str, Any]] = None
    tags: Dict[str, str] = None

    def __post_init__(self):
        if self.additional_managed_policies is None:
            self.additional_managed_policies = []
        if self.custom_policy_statements is None:
            self.custom_policy_statements = []
        if self.tags is None:
            self.tags = {}


def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate CloudFormation template for remote IAM roles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_remote_role_stack.py
  python generate_remote_role_stack.py --role-name MyRemoteRole --external-id my-unique-id
  python generate_remote_role_stack.py --additional-policies arn:aws:iam::aws:policy/ReadOnlyAccess
        """,
    )

    parser.add_argument(
        "--role-name",
        default="CrossAccountMCPRole",
        help="Name for the IAM role (default: CrossAccountMCPRole)",
    )

    parser.add_argument(
        "--external-id", help="External ID for additional security in trust policy"
    )

    parser.add_argument(
        "--additional-policies",
        nargs="*",
        default=[],
        help="Additional managed policy ARNs to attach to the role",
    )

    parser.add_argument(
        "--environment",
        default="prod",
        choices=["dev", "staging", "prod"],
        help="Environment tag for resources (default: prod)",
    )

    parser.add_argument(
        "--output-dir",
        default="generated-templates/remote-role-stack",
        help="Output directory for generated templates (default: generated-templates/remote-role-stack)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    return parser


def get_agentcore_runtime_role_arn(region: str) -> str:
    """
    Retrieve the AgentCore Runtime Role ARN from Parameter Store.

    Args:
        region: AWS region to use for Parameter Store lookup

    Returns:
        The AgentCore Runtime Role ARN

    Raises:
        ValueError: If the parameter is not found or invalid
        ClientError: If AWS API call fails
    """
    logger.info(
        f"Retrieving AgentCore Runtime Role ARN from Parameter Store in region {region}"
    )

    try:
        ssm_client = boto3.client("ssm", region_name=region)

        # First try to get the connection info which contains the agent ARN
        try:
            response = ssm_client.get_parameter(
                Name="/coa/components/wa_security_mcp/connection_info"
            )
            connection_info = json.loads(response["Parameter"]["Value"])
            agent_arn = connection_info.get("agent_arn")

            if agent_arn:
                logger.info(f"Retrieved agent ARN from connection info: {agent_arn}")
                # Extract the execution role ARN from the agent ARN
                # Agent ARN format: arn:aws:bedrock:region:account:agent/agent-id
                # We need to find the associated execution role

                # Try to get the execution role directly from parameter store
                try:
                    execution_role_response = ssm_client.get_parameter(
                        Name="/coa/components/wa_security_mcp/execution_role_arn"
                    )
                    execution_role_arn = execution_role_response["Parameter"]["Value"]
                    logger.info(f"Retrieved execution role ARN: {execution_role_arn}")
                    return execution_role_arn
                except ClientError:
                    logger.debug(
                        "Execution role ARN not found in parameter store, will derive from agent ARN"
                    )

                # If execution role not in parameter store, derive it from agent ARN
                # This is a fallback - the execution role typically follows a pattern
                account_id = agent_arn.split(":")[4]
                execution_role_arn = f"arn:aws:iam::{account_id}:role/AmazonBedrockExecutionRoleForAgents_*"
                logger.warning(f"Derived execution role pattern: {execution_role_arn}")
                logger.warning(
                    "Note: You may need to specify the exact execution role ARN manually"
                )
                return execution_role_arn

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.debug(
                    "Connection info parameter not found, trying direct agent ARN parameter"
                )
            else:
                raise

        # Fallback: try to get agent ARN directly
        try:
            response = ssm_client.get_parameter(
                Name="/coa/components/wa_security_mcp/agent_arn"
            )
            agent_arn = response["Parameter"]["Value"]
            logger.info(f"Retrieved agent ARN directly: {agent_arn}")

            # Derive execution role ARN from agent ARN
            account_id = agent_arn.split(":")[4]
            execution_role_arn = (
                f"arn:aws:iam::{account_id}:role/AmazonBedrockExecutionRoleForAgents_*"
            )
            logger.warning(f"Derived execution role pattern: {execution_role_arn}")
            logger.warning(
                "Note: You may need to specify the exact execution role ARN manually"
            )
            return execution_role_arn

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                raise ValueError(
                    "AgentCore Runtime configuration not found in Parameter Store. "
                    "Please ensure the WA Security MCP deployment has completed successfully. "
                    "Expected parameters: /coa/components/wa_security_mcp/connection_info or "
                    "/coa/components/wa_security_mcp/agent_arn"
                )
            else:
                raise

    except NoCredentialsError:
        raise ValueError(
            "AWS credentials not found. Please configure AWS credentials using "
            "AWS CLI, environment variables, or IAM roles."
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDenied":
            raise ValueError(
                "Access denied when retrieving configuration from Parameter Store. "
                "Please ensure you have ssm:GetParameter permissions for "
                "/coa/components/wa_security_mcp/* parameters."
            )
        else:
            raise ValueError(f"AWS API error: {e}")


def validate_role_arn(role_arn: str) -> bool:
    """
    Validate that the role ARN has the correct format.

    Args:
        role_arn: The role ARN to validate

    Returns:
        True if valid, False otherwise
    """
    if not role_arn:
        return False

    # Basic ARN format validation
    arn_parts = role_arn.split(":")
    if len(arn_parts) != 6:
        return False

    if arn_parts[0] != "arn" or arn_parts[1] != "aws" or arn_parts[2] != "iam":
        return False

    if not arn_parts[5].startswith("role/"):
        return False

    return True


def generate_cloudformation_template(config: RemoteRoleConfig) -> Dict[str, Any]:
    """
    Generate CloudFormation template for the remote role.

    Args:
        config: Configuration object with role settings

    Returns:
        CloudFormation template as dictionary
    """
    logger.info(f"Generating CloudFormation template for role: {config.role_name}")

    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "Remote IAM Role for Cross-Account MCP Server Access - Generated by generate_remote_role_stack.py",
        "Metadata": {
            "GeneratedBy": "generate_remote_role_stack.py",
            "GeneratedAt": datetime.utcnow().isoformat() + "Z",
            "Purpose": "Enable AgentCore Runtime to assume role for cross-account MCP operations",
            "RuntimeRoleArn": config.runtime_role_arn,
        },
        "Parameters": {},
        "Resources": {},
        "Outputs": {},
    }

    # Add parameters
    template["Parameters"] = {
        "RoleName": {
            "Type": "String",
            "Default": config.role_name,
            "Description": "Name for the IAM role that will be assumed by AgentCore Runtime",
            "AllowedPattern": "^[a-zA-Z][a-zA-Z0-9_+=,.@-]{0,63}$",
            "ConstraintDescription": "Role name must be 1-64 characters long and contain only valid IAM role name characters",
        },
        "Environment": {
            "Type": "String",
            "Default": config.tags.get("Environment", "prod"),
            "AllowedValues": ["dev", "staging", "prod"],
            "Description": "Environment tag for the resources",
        },
    }

    # Add external ID parameter if specified
    if config.external_id:
        template["Parameters"]["ExternalId"] = {
            "Type": "String",
            "Default": config.external_id,
            "Description": "External ID for additional security in role assumption",
            "MinLength": 2,
            "MaxLength": 1224,
            "AllowedPattern": "^[a-zA-Z0-9+=,.@:/-]*$",
        }

    # Generate IAM role resource
    role_resource = generate_iam_role_resource(config)
    template["Resources"]["CrossAccountMCPRole"] = role_resource

    # Add custom inline policy for security services
    inline_policy = generate_security_services_policy(config)
    template["Resources"]["MCPSecurityServicesPolicy"] = inline_policy

    # Managed policies will be attached directly to the role via ManagedPolicyArns property

    # Add template outputs
    template["Outputs"] = generate_template_outputs(config)

    logger.debug(
        f"Generated template parameters: {list(template['Parameters'].keys())}"
    )
    logger.debug(f"Generated template resources: {list(template['Resources'].keys())}")
    return template


def generate_iam_role_resource(config: RemoteRoleConfig) -> Dict[str, Any]:
    """
    Generate the IAM role resource for the CloudFormation template.

    Args:
        config: Configuration object with role settings

    Returns:
        IAM role resource definition
    """
    logger.debug("Generating IAM role resource")

    # Create trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": config.runtime_role_arn},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    # Add external ID condition if specified
    if config.external_id:
        trust_policy["Statement"][0]["Condition"] = {
            "StringEquals": {"sts:ExternalId": {"Ref": "ExternalId"}}
        }
        logger.debug("Added external ID condition to trust policy")

    # Get managed policy ARNs
    managed_policy_arns = get_managed_policy_arns(config)

    # Create role resource
    role_resource = {
        "Type": "AWS::IAM::Role",
        "Properties": {
            "RoleName": {"Ref": "RoleName"},
            "AssumeRolePolicyDocument": trust_policy,
            "Description": "Cross-account role for AgentCore Runtime MCP server operations",
            "MaxSessionDuration": 3600,  # 1 hour
            "ManagedPolicyArns": managed_policy_arns,
            "Tags": [{"Key": key, "Value": value} for key, value in config.tags.items()]
            + [{"Key": "Environment", "Value": {"Ref": "Environment"}}],
        },
    }

    logger.debug("Generated IAM role resource with trust policy")
    return role_resource


def generate_security_services_policy(config: RemoteRoleConfig) -> Dict[str, Any]:
    """
    Generate inline policy for security services permissions.

    Args:
        config: Configuration object with role settings

    Returns:
        IAM policy resource definition
    """
    logger.debug("Generating security services inline policy")

    # Define security services permissions
    policy_statements = [
        {
            "Sid": "SecurityServicesAccess",
            "Effect": "Allow",
            "Action": [
                # GuardDuty permissions
                "guardduty:GetDetector",
                "guardduty:ListDetectors",
                "guardduty:GetFindings",
                "guardduty:ListFindings",
                "guardduty:GetFindingsStatistics",
                # Security Hub permissions
                "securityhub:DescribeHub",
                "securityhub:GetFindings",
                "securityhub:GetInsight",
                "securityhub:GetInsightResults",
                "securityhub:ListFindings",
                # Inspector permissions
                "inspector2:GetStatus",
                "inspector2:ListFindings",
                "inspector2:GetFindingsReportStatus",
                "inspector2:ListCoverage",
                # Access Analyzer permissions
                "access-analyzer:ListAnalyzers",
                "access-analyzer:ListFindings",
                "access-analyzer:GetFinding",
                "access-analyzer:GetAnalyzer",
                # Macie permissions
                "macie2:GetMacieSession",
                "macie2:ListFindings",
                "macie2:GetFindings",
                "macie2:GetFindingStatistics",
                # Trusted Advisor permissions (requires Support plan)
                "support:DescribeTrustedAdvisorChecks",
                "support:DescribeTrustedAdvisorCheckResult",
                "support:DescribeTrustedAdvisorCheckSummaries",
            ],
            "Resource": "*",
        },
        {
            "Sid": "ResourceDiscoveryAccess",
            "Effect": "Allow",
            "Action": [
                # Resource Explorer permissions
                "resource-explorer-2:Search",
                "resource-explorer-2:ListResources",
                "resource-explorer-2:GetDefaultView",
                # Config permissions for resource discovery
                "config:DescribeConfigurationRecorders",
                "config:DescribeDeliveryChannels",
                "config:GetResourceConfigHistory",
                "config:ListDiscoveredResources",
                # CloudTrail for audit information
                "cloudtrail:DescribeTrails",
                "cloudtrail:GetTrailStatus",
                "cloudtrail:LookupEvents",
            ],
            "Resource": "*",
        },
        {
            "Sid": "ReadOnlyResourceAccess",
            "Effect": "Allow",
            "Action": [
                # EC2 read-only for security analysis
                "ec2:DescribeInstances",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeVpcs",
                "ec2:DescribeSubnets",
                "ec2:DescribeNetworkAcls",
                "ec2:DescribeVolumes",
                "ec2:DescribeSnapshots",
                # S3 read-only for security analysis
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "s3:GetBucketVersioning",
                "s3:GetBucketEncryption",
                "s3:GetBucketPublicAccessBlock",
                "s3:GetBucketPolicy",
                "s3:GetBucketAcl",
                # RDS read-only for security analysis
                "rds:DescribeDBInstances",
                "rds:DescribeDBClusters",
                "rds:DescribeDBSnapshots",
                "rds:DescribeDBClusterSnapshots",
                # Lambda read-only for security analysis
                "lambda:ListFunctions",
                "lambda:GetFunction",
                "lambda:GetPolicy",
                # ELB read-only for security analysis
                "elasticloadbalancing:DescribeLoadBalancers",
                "elasticloadbalancing:DescribeTargetGroups",
                "elasticloadbalancing:DescribeListeners",
                # CloudFront read-only for security analysis
                "cloudfront:ListDistributions",
                "cloudfront:GetDistribution",
                "cloudfront:GetDistributionConfig",
            ],
            "Resource": "*",
        },
        {
            "Sid": "TaggingOperations",
            "Effect": "Allow",
            "Action": [
                "tag:GetResources",
                "tag:GetTagKeys",
                "tag:GetTagValues",
                "resourcegroupstaggingapi:GetResources",
                "resourcegroupstaggingapi:GetTagKeys",
                "resourcegroupstaggingapi:GetTagValues",
            ],
            "Resource": "*",
        },
    ]

    # Add any custom policy statements from config
    if config.custom_policy_statements:
        policy_statements.extend(config.custom_policy_statements)
        logger.debug(
            f"Added {len(config.custom_policy_statements)} custom policy statements"
        )

    policy_resource = {
        "Type": "AWS::IAM::Policy",
        "Properties": {
            "PolicyName": "MCPSecurityServicesPolicy",
            "PolicyDocument": {"Version": "2012-10-17", "Statement": policy_statements},
            "Roles": [{"Ref": "CrossAccountMCPRole"}],
        },
    }

    logger.debug(
        f"Generated security services policy with {len(policy_statements)} statements"
    )
    return policy_resource


def validate_managed_policy_arn(policy_arn: str) -> bool:
    """
    Validate that a managed policy ARN has the correct format.

    Args:
        policy_arn: The policy ARN to validate

    Returns:
        True if valid, False otherwise
    """
    if not policy_arn:
        return False

    # Basic ARN format validation
    arn_parts = policy_arn.split(":")
    if len(arn_parts) != 6:
        return False

    if arn_parts[0] != "arn" or arn_parts[1] != "aws" or arn_parts[2] != "iam":
        return False

    if not arn_parts[5].startswith("policy/"):
        return False

    return True


def get_managed_policy_arns(config: RemoteRoleConfig) -> List[str]:
    """
    Get list of managed policy ARNs to attach to the role.

    Args:
        config: Configuration object with role settings

    Returns:
        List of valid managed policy ARNs
    """
    logger.debug("Getting managed policy ARNs")

    # Default managed policies for comprehensive access
    default_policies = [
        "arn:aws:iam::aws:policy/SecurityAudit",  # Security-focused read access
        "arn:aws:iam::aws:policy/ReadOnlyAccess",  # Full read-only access to all AWS services
    ]

    # Combine default and additional policies
    all_policies = default_policies + config.additional_managed_policies

    # Validate all policy ARNs
    valid_policies = []
    for policy_arn in all_policies:
        if validate_managed_policy_arn(policy_arn):
            valid_policies.append(policy_arn)
            logger.debug(f"Validated managed policy ARN: {policy_arn}")
        else:
            logger.warning(f"Invalid managed policy ARN format, skipping: {policy_arn}")

    logger.debug(f"Generated {len(valid_policies)} managed policy ARNs")
    return valid_policies


def generate_template_outputs(config: RemoteRoleConfig) -> Dict[str, Any]:
    """
    Generate CloudFormation template outputs.

    Args:
        config: Configuration object with role settings

    Returns:
        Template outputs dictionary
    """
    logger.debug("Generating template outputs")

    outputs = {
        "RoleArn": {
            "Description": "ARN of the created cross-account MCP role",
            "Value": {"Fn::GetAtt": ["CrossAccountMCPRole", "Arn"]},
            "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-RoleArn"}},
        },
        "RoleName": {
            "Description": "Name of the created cross-account MCP role",
            "Value": {"Ref": "CrossAccountMCPRole"},
            "Export": {"Name": {"Fn::Sub": "${AWS::StackName}-RoleName"}},
        },
        "TrustedRoleArn": {
            "Description": "ARN of the AgentCore Runtime role that can assume this role",
            "Value": config.runtime_role_arn,
        },
    }

    # Add external ID output if specified
    if config.external_id:
        outputs["ExternalId"] = {
            "Description": "External ID required for role assumption",
            "Value": {"Ref": "ExternalId"},
        }

    # Add usage instructions
    outputs["UsageInstructions"] = {
        "Description": "Instructions for using this role with AgentCore Runtime",
        "Value": {
            "Fn::Sub": [
                "To assume this role from AgentCore Runtime, use: aws sts assume-role --role-arn ${RoleArn} --role-session-name MCP-Session${ExternalIdParam}",
                {
                    "RoleArn": {"Fn::GetAtt": ["CrossAccountMCPRole", "Arn"]},
                    "ExternalIdParam": " --external-id " + config.external_id
                    if config.external_id
                    else "",
                },
            ]
        },
    }

    logger.debug(f"Generated {len(outputs)} template outputs")
    return outputs


def save_template(
    template: Dict[str, Any], output_dir: str, config: RemoteRoleConfig
) -> str:
    """
    Save CloudFormation template to YAML file.

    Args:
        template: CloudFormation template dictionary
        output_dir: Output directory path
        config: Configuration object

    Returns:
        Path to saved template file
    """
    logger.info("Saving CloudFormation template to YAML file")

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created output directory: {output_path}")

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"remote-role-{config.role_name.lower()}-{timestamp}.yaml"
    file_path = output_path / filename

    try:
        # Convert template to YAML with proper formatting
        yaml_content = yaml.dump(
            template,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=120,
            allow_unicode=True,
        )

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

        logger.info(f"Template saved successfully: {file_path}")
        return str(file_path)

    except Exception as e:
        raise ValueError(f"Failed to save template to {file_path}: {e}")


def save_metadata(config: RemoteRoleConfig, output_dir: str, template_path: str) -> str:
    """
    Save metadata about the template generation.

    Args:
        config: Configuration object
        output_dir: Output directory path
        template_path: Path to the saved template

    Returns:
        Path to saved metadata file
    """
    logger.debug("Saving template generation metadata")

    # Create metadata
    metadata = {
        "generation_info": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "script_version": "1.0.0",
            "template_path": template_path,
        },
        "configuration": {
            "runtime_role_arn": config.runtime_role_arn,
            "role_name": config.role_name,
            "external_id": config.external_id,
            "additional_managed_policies": config.additional_managed_policies,
            "tags": config.tags,
        },
        "deployment_instructions": {
            "description": "Deploy this template to target AWS account to create cross-account MCP role",
            "aws_cli_command": f"aws cloudformation deploy --template-file {Path(template_path).name} --stack-name remote-mcp-role --capabilities CAPABILITY_IAM --profile target-account-profile",
            "parameters": {
                "RoleName": config.role_name,
                "Environment": config.tags.get("Environment", "prod"),
            },
        },
    }

    if config.external_id:
        metadata["deployment_instructions"]["parameters"]["ExternalId"] = (
            config.external_id
        )

    # Save metadata file
    output_path = Path(output_dir)
    metadata_filename = f"remote-role-{config.role_name.lower()}-metadata.json"
    metadata_path = output_path / metadata_filename

    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.debug(f"Metadata saved: {metadata_path}")
        return str(metadata_path)

    except Exception as e:
        logger.warning(f"Failed to save metadata to {metadata_path}: {e}")
        return ""


def validate_input_parameters(args) -> None:
    """
    Validate command-line input parameters.

    Args:
        args: Parsed command-line arguments

    Raises:
        ValueError: If any parameter is invalid
    """
    logger.debug("Validating input parameters")

    # Validate role name
    if not validate_role_name(args.role_name):
        raise ValueError(
            f"Invalid role name: {args.role_name}. "
            "Role name must be 1-64 characters long and contain only "
            "alphanumeric characters plus these special characters: +=,.@-_"
        )

    # Validate external ID if provided
    if args.external_id and not validate_external_id(args.external_id):
        raise ValueError(
            f"Invalid external ID: {args.external_id}. "
            "External ID must be 2-1224 characters long and contain only "
            "alphanumeric characters plus these special characters: +=,.@:/-"
        )

    # Validate additional managed policies
    for policy_arn in args.additional_policies:
        if not validate_managed_policy_arn(policy_arn):
            raise ValueError(
                f"Invalid managed policy ARN: {policy_arn}. "
                "Policy ARN must be in format: arn:aws:iam::account:policy/PolicyName"
            )

    # Validate output directory path
    if not validate_output_directory(args.output_dir):
        raise ValueError(
            f"Invalid output directory: {args.output_dir}. "
            "Directory path contains invalid characters or is too long."
        )

    logger.debug("All input parameters validated successfully")


def validate_role_name(role_name: str) -> bool:
    """
    Validate IAM role name format.

    Args:
        role_name: Role name to validate

    Returns:
        True if valid, False otherwise
    """
    if not role_name or len(role_name) < 1 or len(role_name) > 64:
        return False

    # Check allowed characters: alphanumeric plus +=,.@-_
    import re

    pattern = r"^[a-zA-Z][a-zA-Z0-9_+=,.@-]*$"
    return bool(re.match(pattern, role_name))


def validate_external_id(external_id: str) -> bool:
    """
    Validate external ID format.

    Args:
        external_id: External ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not external_id or len(external_id) < 2 or len(external_id) > 1224:
        return False

    # Check allowed characters: alphanumeric plus +=,.@:/-
    import re

    pattern = r"^[a-zA-Z0-9+=,.@:/-]*$"
    return bool(re.match(pattern, external_id))


def validate_output_directory(output_dir: str) -> bool:
    """
    Validate output directory path.

    Args:
        output_dir: Directory path to validate

    Returns:
        True if valid, False otherwise
    """
    if not output_dir or len(output_dir) > 255:
        return False

    # Check for invalid characters (basic validation)
    invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
    if any(char in output_dir for char in invalid_chars):
        return False

    return True


def get_aws_session_and_region() -> tuple[boto3.Session, str]:
    """
    Get AWS session and region, using the same configuration as parent deployment.

    Returns:
        Tuple of (boto3.Session, region_name)
    """
    try:
        session = boto3.Session()
        region = session.region_name

        if not region:
            # Default to us-east-1 if no region configured
            region = "us-east-1"
            logger.warning(f"No AWS region configured, defaulting to {region}")

        logger.info(f"Using AWS region: {region}")
        return session, region

    except Exception as e:
        raise ValueError(f"Failed to initialize AWS session: {e}")


def main():
    """Main entry point for the script."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    logger.info("Starting Remote Role Stack template generation")
    logger.info(f"Role name: {args.role_name}")
    logger.info(f"External ID: {args.external_id or 'Not specified'}")
    logger.info(f"Additional policies: {args.additional_policies or 'None'}")
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Output directory: {args.output_dir}")

    try:
        # Validate input parameters first
        validate_input_parameters(args)

        # Get AWS session and region
        try:
            session, region = get_aws_session_and_region()
        except Exception as e:
            logger.error("Failed to initialize AWS session")
            logger.error("Please ensure AWS credentials are configured properly")
            logger.error("You can configure credentials using:")
            logger.error("  - AWS CLI: aws configure")
            logger.error(
                "  - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
            )
            logger.error("  - IAM roles (if running on EC2)")
            raise e

        # Retrieve AgentCore Runtime Role ARN
        try:
            runtime_role_arn = get_agentcore_runtime_role_arn(region)
        except ValueError as e:
            logger.error("Failed to retrieve AgentCore Runtime Role configuration")
            logger.error(str(e))
            logger.error("\nTroubleshooting steps:")
            logger.error(
                "1. Ensure the WA Security MCP deployment completed successfully"
            )
            logger.error(
                "2. Check that you have access to Parameter Store in the current AWS account"
            )
            logger.error(
                "3. Verify the deployment created parameters under /coa/components/wa_security_mcp/"
            )
            raise e
        except Exception as e:
            logger.error(f"Unexpected error retrieving runtime role configuration: {e}")
            raise e

        # Validate the retrieved role ARN
        if not validate_role_arn(runtime_role_arn):
            error_msg = f"Invalid role ARN format retrieved from Parameter Store: {runtime_role_arn}"
            logger.error(error_msg)
            logger.error(
                "The role ARN should be in format: arn:aws:iam::account:role/RoleName"
            )
            raise ValueError(error_msg)

        logger.info(f"Successfully retrieved runtime role ARN: {runtime_role_arn}")

        # Create configuration object
        config = RemoteRoleConfig(
            runtime_role_arn=runtime_role_arn,
            role_name=args.role_name,
            external_id=args.external_id,
            additional_managed_policies=args.additional_policies,
            tags={
                "Environment": args.environment,
                "Component": "RemoteRoleStack",
                "Purpose": "CrossAccountMCPAccess",
                "GeneratedBy": "generate_remote_role_stack.py",
            },
        )

        # Generate CloudFormation template
        try:
            template = generate_cloudformation_template(config)
        except Exception as e:
            logger.error(f"Failed to generate CloudFormation template: {e}")
            raise e

        # Save template to file
        try:
            output_path = save_template(template, args.output_dir, config)
            logger.info(f"Template saved to: {output_path}")
        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            logger.error("Please check:")
            logger.error("1. Write permissions to the output directory")
            logger.error("2. Available disk space")
            logger.error("3. Directory path validity")
            raise e

        # Generate metadata file
        try:
            metadata_path = save_metadata(config, args.output_dir, output_path)
            if metadata_path:
                logger.info(f"Metadata saved to: {metadata_path}")
        except Exception as e:
            logger.warning(
                f"Failed to save metadata (template generation still successful): {e}"
            )

        # Print success summary
        print("\n" + "=" * 60)
        print("✅ Remote Role Stack Template Generated Successfully!")
        print("=" * 60)
        print(f"Template file: {output_path}")
        print(f"Role name: {config.role_name}")
        print(f"Runtime role ARN: {config.runtime_role_arn}")
        if config.external_id:
            print(f"External ID: {config.external_id}")
        print(f"Environment: {args.environment}")
        print("\nNext steps:")
        print("1. Review the generated template")
        print("2. Deploy to target AWS account using:")
        print("   aws cloudformation deploy \\")
        print(f"     --template-file {Path(output_path).name} \\")
        print("     --stack-name remote-mcp-role \\")
        print("     --capabilities CAPABILITY_IAM \\")
        print("     --profile target-account-profile")
        print("=" * 60)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"AWS API error ({error_code}): {error_message}")

        if error_code == "AccessDenied":
            logger.error("Please ensure you have the necessary AWS permissions")
        elif error_code == "ParameterNotFound":
            logger.error("Required configuration parameters not found")

        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error("Please check the logs above for more details")
        if args.verbose:
            import traceback

            logger.error("Full traceback:")
            logger.error(traceback.format_exc())
        sys.exit(1)

    logger.info("Remote Role Stack template generation completed successfully")


if __name__ == "__main__":
    main()
