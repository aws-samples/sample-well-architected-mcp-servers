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
Setup SSM Parameters Script
Migrates configuration from .env file to AWS Systems Manager Parameter Store
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path to import services
sys.path.append(str(Path(__file__).parent.parent))

from services.config_service import ConfigService


def main():
    parser = argparse.ArgumentParser(
        description="Setup SSM Parameters for Cloud Optimization Web Interface"
    )
    parser.add_argument(
        "--prefix",
        default="/cloud-optimization-web-interface",
        help="SSM parameter prefix (default: /cloud-optimization-web-interface)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing parameters"
    )
    parser.add_argument(
        "--env-file", default=".env", help="Path to .env file (default: .env)"
    )

    args = parser.parse_args()

    # Initialize config service with custom prefix
    config_service = ConfigService(ssm_prefix=args.prefix)

    # Load .env file
    env_file = Path(args.env_file)
    if not env_file.exists():
        print(f"Error: .env file not found at {env_file}")
        return 1

    # Parse .env file
    env_vars = {}
    with open(env_file, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                try:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    env_vars[key] = value
                except ValueError:
                    print(f"Warning: Could not parse line {line_num}: {line}")

    if not env_vars:
        print("No environment variables found in .env file")
        return 1

    print(f"Found {len(env_vars)} environment variables in {env_file}")

    # Define parameter types and descriptions
    parameter_config = {
        "AWS_ROLE_ARN": {
            "type": "String",
            "description": "AWS IAM role ARN to assume for cross-account access",
        },
        "AWS_ROLE_SESSION_NAME": {
            "type": "String",
            "description": "Session name when assuming AWS IAM role",
        },
        "BEDROCK_REGION": {
            "type": "String",
            "description": "AWS region for Bedrock service",
        },
        "BEDROCK_MODEL_ID": {
            "type": "String",
            "description": "Bedrock model ID for LLM operations",
        },
        "AWS_BEARER_TOKEN_BEDROCK": {
            "type": "SecureString",
            "description": "Bearer token for Bedrock authentication (encrypted)",
        },
        "ENHANCED_SECURITY_AGENT_ID": {
            "type": "String",
            "description": "Bedrock Enhanced Security Agent ID",
        },
        "ENHANCED_SECURITY_AGENT_ALIAS_ID": {
            "type": "String",
            "description": "Bedrock Enhanced Security Agent Alias ID",
        },
    }

    # Check existing parameters if not forcing
    if not args.force:
        existing_params = config_service.list_ssm_parameters()
        if "parameters" in existing_params:
            existing_names = {
                p["name"].split("/")[-1] for p in existing_params["parameters"]
            }
            print(f"Found {len(existing_names)} existing parameters in SSM")

    # Process each environment variable
    success_count = 0
    skip_count = 0
    error_count = 0

    for key, value in env_vars.items():
        if not value:  # Skip empty values
            print(f"Skipping {key}: empty value")
            skip_count += 1
            continue

        # Get parameter configuration
        param_config = parameter_config.get(
            key, {"type": "String", "description": f"Configuration parameter for {key}"}
        )

        parameter_name = f"{args.prefix}/{key}"

        if args.dry_run:
            print(
                f"Would create: {parameter_name} = {value[:20]}{'...' if len(value) > 20 else ''} ({param_config['type']})"
            )
            continue

        # Check if parameter exists and we're not forcing
        if not args.force:
            try:
                existing_value = config_service._get_ssm_parameter(key)
                if existing_value is not None:
                    print(
                        f"Skipping {key}: parameter already exists (use --force to overwrite)"
                    )
                    skip_count += 1
                    continue
            except Exception as e:
                print(f"Error checking existing parameter {key}: {e}")
                pass  # Parameter doesn't exist, continue with creation

        # Create/update parameter
        try:
            success = config_service.set_ssm_parameter(
                key=key,
                value=value,
                parameter_type=param_config["type"],
                description=param_config["description"],
            )

            if success:
                print(f"✓ Created/updated: {parameter_name}")
                success_count += 1
            else:
                print(f"✗ Failed to create: {parameter_name}")
                error_count += 1

        except Exception as e:
            print(f"✗ Error creating {parameter_name}: {e}")
            error_count += 1

    # Summary
    print("\nSummary:")
    print(f"  Successfully processed: {success_count}")
    print(f"  Skipped: {skip_count}")
    print(f"  Errors: {error_count}")

    if args.dry_run:
        print(
            "\nThis was a dry run. Use without --dry-run to actually create parameters."
        )

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
