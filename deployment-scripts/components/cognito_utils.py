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
Utility functions for integrating with shared Cognito user pool
"""

import boto3
import json
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class SharedCognitoClient:
    """Client for interacting with shared Cognito infrastructure"""
    
    def __init__(self, region: str = "us-east-1", 
                 shared_stack_name: str = "cloud-optimization-shared-cognito",
                 use_parameter_store: bool = True):
        """
        Initialize the shared Cognito client
        
        Args:
            region: AWS region
            shared_stack_name: Name of the shared Cognito CloudFormation stack (fallback)
            use_parameter_store: Whether to use Parameter Store for configuration (default: True)
        """
        self.region = region
        self.shared_stack_name = shared_stack_name
        self.use_parameter_store = use_parameter_store
        
        self.cf_client = boto3.client('cloudformation', region_name=region)
        self.cognito_client = boto3.client('cognito-idp', region_name=region)
        self.ssm_client = boto3.client('ssm', region_name=region)
        
        # Cache for configuration
        self._config_cache = None
    
    def get_config(self) -> Dict[str, str]:
        """Get Cognito configuration from Parameter Store or CloudFormation stack"""
        if self._config_cache is None:
            if self.use_parameter_store:
                try:
                    # Try to get configuration from Parameter Store first
                    self._config_cache = self._get_config_from_parameter_store()
                    logger.info("✓ Retrieved Cognito configuration from Parameter Store")
                except Exception as e:
                    logger.warning(f"Failed to get config from Parameter Store: {e}")
                    logger.info("Falling back to CloudFormation stack outputs...")
                    self._config_cache = self._get_config_from_stack()
            else:
                # Use CloudFormation stack outputs directly
                self._config_cache = self._get_config_from_stack()
        
        return self._config_cache
    
    def _get_config_from_parameter_store(self) -> Dict[str, str]:
        """Get configuration from Parameter Store using standardized paths"""
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
            response = self.ssm_client.get_parameters(
                Names=parameter_names,
                WithDecryption=False
            )
            
            config = {}
            for param in response['Parameters']:
                name = param['Name']
                value = param['Value']
                
                # Map parameter names to output keys
                if name == '/coa/cognito/user_pool_id':
                    config['UserPoolId'] = value
                elif name == '/coa/cognito/web_app_client_id':
                    config['WebAppClientId'] = value
                elif name == '/coa/cognito/api_client_id':
                    config['APIClientId'] = value
                elif name == '/coa/cognito/mcp_server_client_id':
                    config['MCPServerClientId'] = value
                elif name == '/coa/cognito/identity_pool_id':
                    config['IdentityPoolId'] = value
                elif name == '/coa/cognito/user_pool_domain':
                    config['UserPoolDomain'] = value
                elif name == '/coa/cognito/discovery_url':
                    config['DiscoveryUrl'] = value
                elif name == '/coa/cognito/region':
                    config['Region'] = value
                elif name == '/coa/cognito/user_pool_arn':
                    config['UserPoolArn'] = value
            
            # Check if we got all required parameters
            required_keys = ['UserPoolId', 'WebAppClientId', 'APIClientId', 'MCPServerClientId']
            missing_keys = [key for key in required_keys if key not in config]
            
            if missing_keys:
                raise ValueError(f"Missing required parameters: {missing_keys}")
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to get parameters from Parameter Store: {e}")
            raise
    
    def _get_config_from_stack(self) -> Dict[str, str]:
        """Get configuration from CloudFormation stack outputs (fallback)"""
        try:
            response = self.cf_client.describe_stacks(StackName=self.shared_stack_name)
            outputs = {}
            if 'Outputs' in response['Stacks'][0]:
                for output in response['Stacks'][0]['Outputs']:
                    outputs[output['OutputKey']] = output['OutputValue']
            
            if not outputs:
                raise ValueError("No outputs found in CloudFormation stack")
            
            return outputs
            
        except Exception as e:
            logger.error(f"Failed to get shared Cognito stack outputs: {e}")
            raise ValueError(f"Shared Cognito stack '{self.shared_stack_name}' not found or accessible")
    
    def get_user_pool_id(self) -> str:
        """Get the shared user pool ID"""
        return self.get_config()['UserPoolId']
    
    def get_web_app_client_id(self) -> str:
        """Get the web application client ID"""
        return self.get_config()['WebAppClientId']
    
    def get_api_client_id(self) -> str:
        """Get the API client ID"""
        return self.get_config()['APIClientId']
    
    def get_mcp_server_client_id(self) -> str:
        """Get the MCP server client ID"""
        return self.get_config()['MCPServerClientId']
    
    def get_identity_pool_id(self) -> str:
        """Get the identity pool ID"""
        return self.get_config()['IdentityPoolId']
    
    def get_discovery_url(self) -> str:
        """Get the OIDC discovery URL"""
        return self.get_config()['DiscoveryUrl']
    
    def get_user_pool_domain(self) -> str:
        """Get the user pool domain"""
        return self.get_config()['UserPoolDomain']
    
    def get_user_pool_arn(self) -> str:
        """Get the user pool ARN"""
        return self.get_config().get('UserPoolArn', '')
    
    def create_additional_client(self, client_name: str, 
                               callback_urls: Optional[list] = None,
                               logout_urls: Optional[list] = None,
                               generate_secret: bool = False,
                               explicit_auth_flows: Optional[list] = None) -> Dict[str, str]:
        """
        Create an additional client for the shared user pool
        
        Args:
            client_name: Name for the new client
            callback_urls: List of callback URLs (for OAuth flows)
            logout_urls: List of logout URLs (for OAuth flows)
            generate_secret: Whether to generate a client secret
            explicit_auth_flows: List of explicit auth flows to allow
        
        Returns:
            Dictionary with client information
        """
        user_pool_id = self.get_user_pool_id()
        
        client_config = {
            'UserPoolId': user_pool_id,
            'ClientName': client_name,
            'GenerateSecret': generate_secret
        }
        
        if callback_urls:
            client_config['CallbackURLs'] = callback_urls
            client_config['SupportedIdentityProviders'] = ['COGNITO']
            client_config['AllowedOAuthFlows'] = ['code']
            client_config['AllowedOAuthScopes'] = ['email', 'openid', 'profile']
            client_config['AllowedOAuthFlowsUserPoolClient'] = True
        
        if logout_urls:
            client_config['LogoutURLs'] = logout_urls
        
        if explicit_auth_flows:
            client_config['ExplicitAuthFlows'] = explicit_auth_flows
        else:
            client_config['ExplicitAuthFlows'] = [
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ]
        
        try:
            response = self.cognito_client.create_user_pool_client(**client_config)
            client_info = {
                'ClientId': response['UserPoolClient']['ClientId'],
                'ClientName': client_name,
                'UserPoolId': user_pool_id
            }
            
            if generate_secret:
                client_info['ClientSecret'] = response['UserPoolClient']['ClientSecret']
            
            logger.info(f"Created additional client: {client_name}")
            return client_info
            
        except Exception as e:
            logger.error(f"Failed to create additional client: {e}")
            raise
    
    def update_client_callback_urls(self, client_id: str, 
                                  callback_urls: list, 
                                  logout_urls: Optional[list] = None) -> bool:
        """
        Update callback URLs for an existing client
        
        Args:
            client_id: Client ID to update
            callback_urls: New callback URLs
            logout_urls: New logout URLs (optional)
        
        Returns:
            True if successful
        """
        user_pool_id = self.get_user_pool_id()
        
        try:
            # Get current client configuration
            response = self.cognito_client.describe_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            
            client_config = response['UserPoolClient']
            
            # Update URLs
            update_config = {
                'UserPoolId': user_pool_id,
                'ClientId': client_id,
                'ClientName': client_config['ClientName'],
                'CallbackURLs': callback_urls,
                'ExplicitAuthFlows': client_config.get('ExplicitAuthFlows', []),
                'SupportedIdentityProviders': client_config.get('SupportedIdentityProviders', ['COGNITO']),
                'AllowedOAuthFlows': client_config.get('AllowedOAuthFlows', []),
                'AllowedOAuthScopes': client_config.get('AllowedOAuthScopes', []),
                'AllowedOAuthFlowsUserPoolClient': client_config.get('AllowedOAuthFlowsUserPoolClient', False)
            }
            
            if logout_urls:
                update_config['LogoutURLs'] = logout_urls
            elif 'LogoutURLs' in client_config:
                update_config['LogoutURLs'] = client_config['LogoutURLs']
            
            self.cognito_client.update_user_pool_client(**update_config)
            logger.info(f"Updated callback URLs for client: {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update client callback URLs: {e}")
            raise
    
    def get_auth_config_for_agentcore(self) -> Dict[str, Any]:
        """
        Get authentication configuration for AgentCore Runtime
        
        Returns:
            Dictionary with auth configuration for AgentCore
        """
        return {
            "customJWTAuthorizer": {
                "allowedClients": [self.get_mcp_server_client_id()],
                "discoveryUrl": self.get_discovery_url(),
            }
        }
    
    def get_bearer_token(self, username: str, password: str, 
                        client_id: Optional[str] = None) -> str:
        """
        Get a bearer token for a user
        
        Args:
            username: User's username (email)
            password: User's password
            client_id: Client ID to use (defaults to API client)
        
        Returns:
            Bearer token
        """
        if client_id is None:
            client_id = self.get_api_client_id()
        
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            return response['AuthenticationResult']['AccessToken']
            
        except Exception as e:
            logger.error(f"Failed to get bearer token: {e}")
            raise
    
    def get_cognito_config_for_frontend(self, custom_domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Cognito configuration for frontend applications
        
        Args:
            custom_domain: Custom domain for callback URLs (optional)
        
        Returns:
            Dictionary with frontend Cognito configuration
        """
        user_pool_domain = self.get_user_pool_domain()
        
        config = {
            "userPoolId": self.get_user_pool_id(),
            "clientId": self.get_web_app_client_id(),
            "domain": f"{user_pool_domain}.auth.{self.region}.amazoncognito.com",
            "identityPoolId": self.get_identity_pool_id(),
            "region": self.region
        }
        
        if custom_domain:
            config["customDomain"] = custom_domain
        
        return config

def get_shared_cognito_client(region: str = "us-east-1", 
                            shared_stack_name: str = "cloud-optimization-shared-cognito",
                            use_parameter_store: bool = True) -> SharedCognitoClient:
    """
    Factory function to get a shared Cognito client
    
    Args:
        region: AWS region
        shared_stack_name: Name of the shared Cognito stack (fallback)
        use_parameter_store: Whether to use Parameter Store for configuration
    
    Returns:
        SharedCognitoClient instance
    """
    return SharedCognitoClient(region=region, shared_stack_name=shared_stack_name, use_parameter_store=use_parameter_store)

# Convenience functions for common operations
def get_cognito_config_for_cloudformation(region: str = "us-east-1",
                                        shared_stack_name: str = "cloud-optimization-agentflow-cognito") -> Dict[str, Any]:
    """
    Get Cognito configuration for CloudFormation templates
    
    Returns:
        Dictionary with CloudFormation-compatible Cognito references
    """
    return {
        "UserPoolId": {"Fn::ImportValue": f"{shared_stack_name}-UserPoolId"},
        "WebAppClientId": {"Fn::ImportValue": f"{shared_stack_name}-WebAppClientId"},
        "APIClientId": {"Fn::ImportValue": f"{shared_stack_name}-APIClientId"},
        "MCPServerClientId": {"Fn::ImportValue": f"{shared_stack_name}-MCPServerClientId"},
        "IdentityPoolId": {"Fn::ImportValue": f"{shared_stack_name}-IdentityPoolId"},
        "DiscoveryUrl": {"Fn::ImportValue": f"{shared_stack_name}-DiscoveryUrl"},
        "UserPoolDomain": {"Fn::ImportValue": f"{shared_stack_name}-UserPoolDomain"}
    }