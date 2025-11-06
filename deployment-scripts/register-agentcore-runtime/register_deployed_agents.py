#!/usr/bin/env python3
"""
Register Deployed Agents Script

This script registers deployed AgentCore agents with the COA system
by creating the necessary SSM parameters for agent discovery.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DeployedAgentRegistrar:
    """Registers deployed AgentCore agents with COA system."""
    
    def __init__(self, region: str, stack_prefix: str, profile: Optional[str] = None):
        """
        Initialize the registrar.
        
        Args:
            region: AWS region
            stack_prefix: Parameter prefix for SSM parameters
            profile: AWS profile name (optional)
        """
        self.region = region
        self.stack_prefix = stack_prefix
        self.profile = profile
        
        # Create session with profile if specified
        if profile:
            session = boto3.Session(profile_name=profile)
            logger.info(f"Using AWS profile: {profile}")
        else:
            session = boto3.Session()
            logger.info("Using default AWS credentials")
        
        # Initialize AWS clients
        self.ssm_client = session.client("ssm", region_name=region)
        self.sts_client = session.client("sts", region_name=region)
        
        # Get account ID
        self.account_id = self.sts_client.get_caller_identity()["Account"]
        
        logger.info(f"Initialized registrar for account {self.account_id} in region {region}")
        logger.info(f"Using parameter prefix: {stack_prefix}")
    
    def register_agent(
        self, 
        agent_name: str, 
        runtime_id: str, 
        target_account_id: str,
        stack_name: str,
        environment: str
    ) -> bool:
        """
        Register a deployed agent with the COA system.
        
        Args:
            agent_name: Name of the agent
            runtime_id: AgentCore runtime ID
            target_account_id: Target account ID for cross-account access
            stack_name: CloudFormation stack name
            environment: Deployment environment
            
        Returns:
            True if registration successful, False otherwise
        """
        logger.info(f"Registering agent: {agent_name}")
        
        # Construct agent ARN from runtime ID
        agent_arn = f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/{runtime_id}"
        
        # Extract agent ID from runtime ID
        agent_id = runtime_id
        
        # Create SSM parameters for agent registration
        agent_path = f"/{self.stack_prefix}/agentcore/agents/{agent_name}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Define parameters to create
        parameters = {
            f"{agent_path}/agent_arn": agent_arn,
            f"{agent_path}/agent_id": agent_id,
            f"{agent_path}/name": agent_name,
            f"{agent_path}/runtime_id": runtime_id,
            f"{agent_path}/region": self.region,
            f"{agent_path}/deployment_type": "agentcore",
            f"{agent_path}/agent_type": self._determine_agent_type(agent_name),
            f"{agent_path}/status": "deployed",
            f"{agent_path}/deployment_timestamp": timestamp,
            f"{agent_path}/target_account_id": target_account_id,
            f"{agent_path}/stack_name": stack_name,
            f"{agent_path}/environment": environment,
            f"{agent_path}/endpoint_url": f"arn-based-invocation://{agent_arn}",
            f"{agent_path}/health_check_url": f"arn-based-invocation://{agent_arn}/health",
            f"{agent_path}/connection_info": json.dumps({
                "runtime_id": runtime_id,
                "region": self.region,
                "account_id": self.account_id
            }),
            f"{agent_path}/metadata": json.dumps({
                "deployment_method": "deploy-coa-agentcore.sh",
                "registered_at": timestamp,
                "version": "1.0"
            })
        }
        
        # Register parameters
        registered_count = 0
        failed_count = 0
        
        for param_name, param_value in parameters.items():
            try:
                self.ssm_client.put_parameter(
                    Name=param_name,
                    Value=param_value,
                    Type="String",
                    Overwrite=True
                )
                registered_count += 1
                logger.debug(f"Registered parameter: {param_name}")
                
            except ClientError as e:
                logger.error(f"Failed to register parameter {param_name}: {e}")
                failed_count += 1
        
        # Summary
        logger.info(f"Registration summary for {agent_name}:")
        logger.info(f"  Successful parameters: {registered_count}")
        logger.info(f"  Failed parameters: {failed_count}")
        
        if registered_count > 0:
            logger.info(f"Agent registered successfully: {agent_name}")
            
            # Verify registration
            if self._verify_registration(agent_name):
                logger.info("Registration verified: agent discoverable in Parameter Store")
                return True
            else:
                logger.warning("Registration verification failed")
                return False
        else:
            logger.error(f"Agent registration failed: {agent_name}")
            return False
    
    def _determine_agent_type(self, agent_name: str) -> str:
        """
        Determine agent type based on agent name.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent type string
        """
        name_lower = agent_name.lower()
        
        if "aws-api" in name_lower:
            return "aws_api_agent"
        elif "cost" in name_lower or "billing" in name_lower:
            return "cost_optimization"
        elif "security" in name_lower or "wa-sec" in name_lower:
            return "security_agent"
        elif "reliability" in name_lower:
            return "reliability_agent"
        elif "performance" in name_lower:
            return "performance_agent"
        else:
            return "strands_agent"
    
    def _verify_registration(self, agent_name: str) -> bool:
        """
        Verify agent registration by checking key parameters.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            True if verification successful, False otherwise
        """
        try:
            agent_path = f"/{self.stack_prefix}/agentcore/agents/{agent_name}"
            
            # Check if key parameters exist
            key_params = [
                f"{agent_path}/agent_arn",
                f"{agent_path}/name",
                f"{agent_path}/runtime_id"
            ]
            
            for param_name in key_params:
                self.ssm_client.get_parameter(Name=param_name)
            
            return True
            
        except ClientError as e:
            logger.error(f"Registration verification failed: {e}")
            return False
    
    def list_registered_agents(self) -> List[str]:
        """
        List all registered agents.
        
        Returns:
            List of registered agent names
        """
        try:
            agent_path = f"/{self.stack_prefix}/agentcore/agents"
            
            response = self.ssm_client.get_parameters_by_path(
                Path=agent_path,
                Recursive=True
            )
            
            # Extract agent names from parameter paths
            agent_names = set()
            for param in response.get('Parameters', []):
                path_parts = param['Name'].split('/')
                if len(path_parts) >= 5:  # /{prefix}/agentcore/agents/{name}/{param}
                    agent_name = path_parts[4]
                    agent_names.add(agent_name)
            
            return sorted(list(agent_names))
            
        except ClientError as e:
            logger.error(f"Failed to list registered agents: {e}")
            return []


def main():
    """Main entry point for the registration script."""
    parser = argparse.ArgumentParser(
        description="Register deployed AgentCore agents with COA system"
    )
    parser.add_argument(
        "--region",
        required=True,
        help="AWS region"
    )
    parser.add_argument(
        "--stack-prefix",
        required=True,
        help="Parameter prefix for SSM parameters"
    )
    parser.add_argument(
        "--profile",
        help="AWS CLI profile name"
    )
    parser.add_argument(
        "--agent-name",
        required=True,
        help="Name of the agent to register"
    )
    parser.add_argument(
        "--runtime-id",
        required=True,
        help="AgentCore runtime ID"
    )
    parser.add_argument(
        "--target-account-id",
        required=True,
        help="Target account ID for cross-account access"
    )
    parser.add_argument(
        "--stack-name",
        required=True,
        help="CloudFormation stack name"
    )
    parser.add_argument(
        "--environment",
        required=True,
        help="Deployment environment"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    try:
        # Create registrar
        registrar = DeployedAgentRegistrar(
            region=args.region,
            stack_prefix=args.stack_prefix,
            profile=args.profile
        )
        
        # Register agent
        success = registrar.register_agent(
            agent_name=args.agent_name,
            runtime_id=args.runtime_id,
            target_account_id=args.target_account_id,
            stack_name=args.stack_name,
            environment=args.environment
        )
        
        if success:
            print(f"✅ Agent '{args.agent_name}' registered successfully")
            return 0
        else:
            print(f"❌ Failed to register agent '{args.agent_name}'")
            return 1
            
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())