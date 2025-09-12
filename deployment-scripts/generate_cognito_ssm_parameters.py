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
Generate Cognito SSM Parameters from CloudFormation Stack
Scans a CloudFormation stack and creates SSM parameters for Cognito configuration
"""

import argparse
import logging
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CognitoSSMParameterGenerator:
    """Generates SSM parameters from CloudFormation stack Cognito resources"""

    def __init__(self, region: str = "us-east-1", profile: str = None):
        """Initialize the generator with AWS clients"""
        self.region = region
        self.profile = profile
        try:
            # Create session with profile if specified
            if profile:
                session = boto3.Session(profile_name=profile)
                logger.info(f"Using AWS profile: {profile}")
            else:
                session = boto3.Session()
                logger.info("Using default AWS credentials")

            # Initialize AWS clients with session
            self.cf_client = session.client("cloudformation", region_name=region)
            self.ssm_client = session.client("ssm", region_name=region)
            self.cognito_client = session.client("cognito-idp", region_name=region)
            logger.info(f"Initialized AWS clients for region: {region}")
        except NoCredentialsError:
            logger.error(
                "AWS credentials not found. Please configure your credentials."
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise

    def get_stack_resources(self, stack_name: str) -> Dict[str, Any]:
        """Get all resources from a CloudFormation stack"""
        try:
            logger.info(f"Scanning CloudFormation stack: {stack_name}")

            # Get stack resources
            paginator = self.cf_client.get_paginator("list_stack_resources")
            resources = {}

            for page in paginator.paginate(StackName=stack_name):
                for resource in page["StackResourceSummaries"]:
                    resource_type = resource["ResourceType"]
                    logical_id = resource["LogicalResourceId"]
                    physical_id = resource.get("PhysicalResourceId", "")

                    resources[logical_id] = {
                        "Type": resource_type,
                        "PhysicalResourceId": physical_id,
                        "ResourceStatus": resource["ResourceStatus"],
                    }

            logger.info(f"Found {len(resources)} resources in stack {stack_name}")
            return resources

        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationError":
                logger.error(
                    f"Stack '{stack_name}' does not exist or is not accessible"
                )
            else:
                logger.error(f"Error accessing stack '{stack_name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting stack resources: {e}")
            raise

    def extract_cognito_resources(self, resources: Dict[str, Any]) -> Dict[str, str]:
        """Extract Cognito-related resources from stack resources"""
        cognito_resources = {}

        # Map logical resource names to their physical IDs
        resource_mappings = {
            "SharedUserPool": "user_pool_id",
            "WebAppClient": "web_app_client_id",
            "APIClient": "api_client_id",
            "MCPServerClient": "mcp_server_client_id",
            "IdentityPool": "identity_pool_id",
            "UserPoolDomain": "user_pool_domain",
        }

        for logical_id, resource_info in resources.items():
            if logical_id in resource_mappings:
                parameter_key = resource_mappings[logical_id]
                physical_id = resource_info["PhysicalResourceId"]

                if physical_id:
                    cognito_resources[parameter_key] = physical_id
                    logger.info(f"Found {logical_id}: {physical_id}")
                else:
                    logger.warning(f"No physical ID found for {logical_id}")

        return cognito_resources

    def get_user_pool_details(self, user_pool_id: str) -> Dict[str, str]:
        """Get additional details from the User Pool"""
        try:
            response = self.cognito_client.describe_user_pool(UserPoolId=user_pool_id)
            user_pool = response["UserPool"]

            # Extract additional information
            details = {
                "user_pool_arn": user_pool["Arn"],
                "region": self.region,
                "discovery_url": f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration",
            }

            # Get domain if it exists - this is optional and might fail
            try:
                domain_response = self.cognito_client.describe_user_pool_domain(
                    Domain=f"{user_pool_id}"  # This might not work, domain name is different
                )
                if "DomainDescription" in domain_response:
                    details["user_pool_domain"] = domain_response["DomainDescription"][
                        "Domain"
                    ]
            except (ClientError, Exception) as e:
                # Domain might not exist or have different name - this is not critical
                logger.debug(
                    f"Could not retrieve domain for user pool {user_pool_id}: {e}"
                )

            return details

        except ClientError as e:
            logger.error(f"Error getting user pool details: {e}")
            return {
                "region": self.region,
                "discovery_url": f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration",
            }
        except Exception as e:
            logger.warning(f"Unexpected error getting user pool details: {e}")
            return {
                "region": self.region,
                "discovery_url": f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration",
            }

    def create_ssm_parameters(
        self, cognito_resources: Dict[str, str], stack_name: str, dry_run: bool = False
    ) -> Dict[str, bool]:
        """Create SSM parameters for Cognito resources"""

        # Get additional user pool details if we have a user pool ID
        if "user_pool_id" in cognito_resources:
            user_pool_details = self.get_user_pool_details(
                cognito_resources["user_pool_id"]
            )
            cognito_resources.update(user_pool_details)

        # Define the SSM parameters to create
        ssm_parameters = {
            "/coa/cognito/user_pool_id": {
                "value": cognito_resources.get("user_pool_id", ""),
                "description": "Shared Cognito User Pool ID for Cloud Optimization Platform",
            },
            "/coa/cognito/web_app_client_id": {
                "value": cognito_resources.get("web_app_client_id", ""),
                "description": "Web Application Client ID for frontend apps",
            },
            "/coa/cognito/api_client_id": {
                "value": cognito_resources.get("api_client_id", ""),
                "description": "API Client ID for backend services",
            },
            "/coa/cognito/mcp_server_client_id": {
                "value": cognito_resources.get("mcp_server_client_id", ""),
                "description": "MCP Server Client ID for AgentCore Runtime",
            },
            "/coa/cognito/identity_pool_id": {
                "value": cognito_resources.get("identity_pool_id", ""),
                "description": "Cognito Identity Pool ID for AWS resource access",
            },
            "/coa/cognito/discovery_url": {
                "value": cognito_resources.get("discovery_url", ""),
                "description": "OIDC Discovery URL for JWT validation",
            },
            "/coa/cognito/region": {
                "value": self.region,
                "description": "AWS Region where Cognito is deployed",
            },
            "/coa/cognito/user_pool_arn": {
                "value": cognito_resources.get("user_pool_arn", ""),
                "description": "Cognito User Pool ARN",
            },
        }

        # Add user pool domain if available
        if "user_pool_domain" in cognito_resources:
            ssm_parameters["/coa/cognito/user_pool_domain"] = {
                "value": cognito_resources["user_pool_domain"],
                "description": "Cognito User Pool Domain for OAuth flows",
            }

        results = {}

        for param_name, param_config in ssm_parameters.items():
            if not param_config["value"]:
                logger.warning(f"Skipping {param_name} - no value found")
                results[param_name] = False
                continue

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would create: {param_name} = {param_config['value']}"
                )
                results[param_name] = True
                continue

            try:
                # Check if parameter exists
                parameter_exists = False
                try:
                    self.ssm_client.get_parameter(Name=param_name)
                    parameter_exists = True
                except ClientError as e:
                    if e.response["Error"]["Code"] != "ParameterNotFound":
                        raise

                if parameter_exists:
                    # Update existing parameter (without tags)
                    self.ssm_client.put_parameter(
                        Name=param_name,
                        Value=param_config["value"],
                        Type="String",
                        Description=param_config["description"],
                        Overwrite=True,
                    )
                    logger.info(f"✅ Updated SSM parameter: {param_name}")
                else:
                    # Create new parameter (with tags)
                    self.ssm_client.put_parameter(
                        Name=param_name,
                        Value=param_config["value"],
                        Type="String",
                        Description=param_config["description"],
                        Tags=[
                            {"Key": "StackName", "Value": stack_name},
                            {"Key": "Component", "Value": "Cognito"},
                            {"Key": "GeneratedBy", "Value": "cognito-ssm-generator"},
                        ],
                    )
                    logger.info(f"✅ Created SSM parameter: {param_name}")

                results[param_name] = True

            except ClientError as e:
                logger.error(f"❌ Failed to create {param_name}: {e}")
                results[param_name] = False
            except Exception as e:
                logger.error(f"❌ Unexpected error creating {param_name}: {e}")
                results[param_name] = False

        return results

    def validate_parameters(self) -> Dict[str, bool]:
        """Validate that all required SSM parameters exist and have values"""
        required_parameters = [
            "/coa/cognito/user_pool_id",
            "/coa/cognito/web_app_client_id",
            "/coa/cognito/api_client_id",
            "/coa/cognito/mcp_server_client_id",
            "/coa/cognito/identity_pool_id",
            "/coa/cognito/discovery_url",
        ]

        results = {}

        for param_name in required_parameters:
            try:
                response = self.ssm_client.get_parameter(Name=param_name)
                value = response["Parameter"]["Value"]

                if value and value.strip():
                    results[param_name] = True
                    logger.info(f"✅ {param_name}: {value}")
                else:
                    results[param_name] = False
                    logger.warning(f"⚠️  {param_name}: Empty value")

            except ClientError as e:
                if e.response["Error"]["Code"] == "ParameterNotFound":
                    results[param_name] = False
                    logger.error(f"❌ {param_name}: Not found")
                else:
                    results[param_name] = False
                    logger.error(f"❌ {param_name}: Error - {e}")
            except Exception as e:
                results[param_name] = False
                logger.error(f"❌ {param_name}: Unexpected error - {e}")

        return results

    def generate_parameters_from_stack(
        self, stack_name: str, dry_run: bool = False
    ) -> bool:
        """Main method to generate SSM parameters from a CloudFormation stack"""
        try:
            logger.info(f"🚀 Starting SSM parameter generation for stack: {stack_name}")

            # Get stack resources
            resources = self.get_stack_resources(stack_name)

            # Extract Cognito resources
            cognito_resources = self.extract_cognito_resources(resources)

            if not cognito_resources:
                logger.error("❌ No Cognito resources found in the stack")
                return False

            logger.info(f"📋 Found Cognito resources: {list(cognito_resources.keys())}")

            # Create SSM parameters
            results = self.create_ssm_parameters(cognito_resources, stack_name, dry_run)

            # Summary
            successful = sum(1 for success in results.values() if success)
            total = len(results)

            logger.info("\n📊 Summary:")
            logger.info(f"   ✅ Successful: {successful}/{total}")
            logger.info(f"   ❌ Failed: {total - successful}/{total}")

            if dry_run:
                logger.info(
                    "   🔍 This was a dry run - no parameters were actually created"
                )

            return successful == total

        except Exception as e:
            logger.error(f"💥 Failed to generate parameters: {e}")
            return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Generate Cognito SSM parameters from CloudFormation stack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate parameters from stack (dry run)
  python generate_cognito_ssm_parameters.py --stack-name my-coa-stack --dry-run

  # Generate parameters from stack (actual creation)
  python generate_cognito_ssm_parameters.py --stack-name my-coa-stack

  # Validate existing parameters
  python generate_cognito_ssm_parameters.py --validate

  # Generate with specific region
  python generate_cognito_ssm_parameters.py --stack-name my-coa-stack --region us-west-2
        """,
    )

    parser.add_argument(
        "--stack-name", type=str, help="CloudFormation stack name to scan"
    )

    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )

    parser.add_argument(
        "--profile",
        type=str,
        help="AWS CLI profile name",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without actually creating parameters",
    )

    parser.add_argument(
        "--validate", action="store_true", help="Validate existing SSM parameters"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        generator = CognitoSSMParameterGenerator(region=args.region, profile=args.profile)

        if args.validate:
            logger.info("🔍 Validating existing SSM parameters...")
            results = generator.validate_parameters()

            valid_count = sum(1 for valid in results.values() if valid)
            total_count = len(results)

            if valid_count == total_count:
                logger.info(f"🎉 All {total_count} parameters are valid!")
                return 0
            else:
                logger.error(
                    f"❌ {total_count - valid_count} parameters are invalid or missing"
                )
                return 1

        elif args.stack_name:
            success = generator.generate_parameters_from_stack(
                args.stack_name, args.dry_run
            )

            if success:
                logger.info("🎉 Successfully generated all SSM parameters!")

                if not args.dry_run:
                    logger.info("\n🔍 Validating created parameters...")
                    generator.validate_parameters()

                return 0
            else:
                logger.error("❌ Failed to generate some SSM parameters")
                return 1

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
