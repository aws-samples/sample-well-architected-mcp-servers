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
Utility script to retrieve shared Cognito configuration from Parameter Store
"""

import boto3
import json
import argparse
import sys
from typing import Dict, Any

def get_cognito_config_from_parameters(region: str = "us-east-1") -> Dict[str, Any]:
    """
    Get Cognito configuration from Parameter Store using standardized paths
    
    Args:
        region: AWS region
        
    Returns:
        Dictionary with Cognito configuration
    """
    ssm_client = boto3.client('ssm', region_name=region)
    
    parameter_names = [
        '/coa/cognito/user_pool_id',
        '/coa/cognito/web_app_client_id',
        '/coa/cognito/api_client_id',
        '/coa/cognito/mcp_server_client_id',
        '/coa/cognito/identity_pool_id',
        '/coa/cognito/user_pool_domain',
        '/coa/cognito/discovery_url',
        '/coa/cognito/region',
        '/coa/cognito/user_pool_arn'
    ]
    
    try:
        response = ssm_client.get_parameters(
            Names=parameter_names,
            WithDecryption=False
        )
        
        config = {}
        for param in response['Parameters']:
            name = param['Name']
            value = param['Value']
            
            # Use the parameter name as the key (without the prefix)
            key = name.replace('/coa/cognito/', '')
            config[key] = value
        
        # Check for missing parameters
        missing_params = response.get('InvalidParameters', [])
        if missing_params:
            print(f"⚠️ Missing parameters: {missing_params}")
        
        return config
        
    except Exception as e:
        print(f"❌ Failed to get Cognito configuration: {e}")
        raise

def print_config(config: Dict[str, Any], format_type: str = "table"):
    """Print configuration in different formats"""
    
    if format_type == "json":
        print(json.dumps(config, indent=2))
    elif format_type == "env":
        print("# Cognito Environment Variables")
        print(f"export COGNITO_USER_POOL_ID={config.get('user_pool_id', '')}")
        print(f"export COGNITO_WEB_APP_CLIENT_ID={config.get('web_app_client_id', '')}")
        print(f"export COGNITO_API_CLIENT_ID={config.get('api_client_id', '')}")
        print(f"export COGNITO_MCP_SERVER_CLIENT_ID={config.get('mcp_server_client_id', '')}")
        print(f"export COGNITO_IDENTITY_POOL_ID={config.get('identity_pool_id', '')}")
        print(f"export COGNITO_USER_POOL_DOMAIN={config.get('user_pool_domain', '')}")
        print(f"export COGNITO_DISCOVERY_URL={config.get('discovery_url', '')}")
        print(f"export COGNITO_REGION={config.get('region', '')}")
    elif format_type == "yaml":
        print("# Cognito Configuration (YAML)")
        print("cognito:")
        for key, value in config.items():
            print(f"  {key}: {value}")
    else:  # table format
        print("🔐 Shared Cognito Configuration")
        print("=" * 50)
        for key, value in config.items():
            formatted_key = key.replace('_', ' ').title()
            print(f"{formatted_key:25}: {value}")

def main():
    parser = argparse.ArgumentParser(description='Get shared Cognito configuration')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region (default: us-east-1)')
    parser.add_argument('--format', choices=['table', 'json', 'env', 'yaml'],
                       default='table',
                       help='Output format (default: table)')
    parser.add_argument('--parameter', 
                       help='Get specific parameter (e.g., user_pool_id)')
    
    args = parser.parse_args()
    
    try:
        config = get_cognito_config_from_parameters(args.region)
        
        if not config:
            print("❌ No Cognito configuration found in Parameter Store")
            print("Make sure to deploy the shared Cognito infrastructure first:")
            print("  python deployment-scripts/deploy_shared_cognito.py --create-test-user")
            sys.exit(1)
        
        if args.parameter:
            # Get specific parameter
            if args.parameter in config:
                print(config[args.parameter])
            else:
                print(f"❌ Parameter '{args.parameter}' not found")
                print(f"Available parameters: {', '.join(config.keys())}")
                sys.exit(1)
        else:
            # Print all configuration
            print_config(config, args.format)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()