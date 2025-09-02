#!/usr/bin/env python3
"""
Update Cognito User Pool Client callback URLs with CloudFront domain
This script runs after the stack is deployed to add the CloudFront URLs
"""

import boto3
import argparse
import logging
import sys
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_cognito_callbacks(stack_name: str, region: str, profile: str = None):
    """Update Cognito callback URLs with CloudFront domain"""
    
    # Create session with profile if specified
    if profile:
        session = boto3.Session(profile_name=profile)
        logger.info(f"Using AWS profile: {profile}")
    else:
        session = boto3.Session()
        logger.info("Using default AWS credentials")
    
    cf_client = session.client('cloudformation', region_name=region)
    cognito_client = session.client('cognito-idp', region_name=region)
    
    try:
        # Get stack outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        
        outputs = {}
        if 'Outputs' in stack:
            for output in stack['Outputs']:
                outputs[output['OutputKey']] = output['OutputValue']
        
        # Get required values
        user_pool_id = outputs.get('UserPoolId')
        web_app_client_id = outputs.get('WebAppClientId')
        cloudfront_domain = outputs.get('CloudFrontDomainName')
        
        if not all([user_pool_id, web_app_client_id, cloudfront_domain]):
            logger.error("Missing required stack outputs")
            logger.error(f"UserPoolId: {user_pool_id}")
            logger.error(f"WebAppClientId: {web_app_client_id}")
            logger.error(f"CloudFrontDomainName: {cloudfront_domain}")
            return False
        
        # Get current client configuration
        client_response = cognito_client.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=web_app_client_id
        )
        
        client_config = client_response['UserPoolClient']
        
        # Update callback URLs
        callback_urls = list(client_config.get('CallbackURLs', []))
        logout_urls = list(client_config.get('LogoutURLs', []))
        
        # Add CloudFront URLs if not already present
        cloudfront_callback = f'https://{cloudfront_domain}/callback'
        cloudfront_logout = f'https://{cloudfront_domain}/logout'
        
        if cloudfront_callback not in callback_urls:
            callback_urls.append(cloudfront_callback)
            logger.info(f"Added callback URL: {cloudfront_callback}")
        
        if cloudfront_logout not in logout_urls:
            logout_urls.append(cloudfront_logout)
            logger.info(f"Added logout URL: {cloudfront_logout}")
        
        # Update the client
        cognito_client.update_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=web_app_client_id,
            CallbackURLs=callback_urls,
            LogoutURLs=logout_urls,
            AllowedOAuthFlows=client_config.get('AllowedOAuthFlows', []),
            AllowedOAuthScopes=client_config.get('AllowedOAuthScopes', []),
            AllowedOAuthFlowsUserPoolClient=client_config.get('AllowedOAuthFlowsUserPoolClient', False),
            SupportedIdentityProviders=client_config.get('SupportedIdentityProviders', []),
            ExplicitAuthFlows=client_config.get('ExplicitAuthFlows', [])
        )
        
        logger.info("Successfully updated Cognito callback URLs")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to update Cognito callbacks: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Update Cognito callback URLs with CloudFront domain')
    parser.add_argument('--stack-name', default='cloud-optimization-assistant',
                       help='CloudFormation stack name')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--profile',
                       help='AWS CLI profile name')
    
    args = parser.parse_args()
    
    success = update_cognito_callbacks(args.stack_name, args.region, args.profile)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()