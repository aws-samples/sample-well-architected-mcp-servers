#!/usr/bin/env python3
"""
Manual Agent Registration Script

This script handles agents that have been manually deployed and creates the necessary
SSM parameters for chatbot integration. It's designed to work with agents that were
deployed outside of the automated deployment process but need to be integrated
with the COA chatbot system.

Usage:
    python register_manual_agent.py --region us-east-1 --agent-name my-manual-agent --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


# Core Data Classes
@dataclass
class ManualAgentInfo:
    """Information about a manually deployed agent."""
    agent_name: str
    agent_arn: str
    agent_id: Optional[str] = None
    region: str = None
    agent_type: str = "manual"
    deployment_type: str = "manual"
    source_path: Optional[str] = None
    execution_role_arn: Optional[str] = None
    description: Optional[str] = None
    stack_prefix: str = None
    
    def __post_init__(self):
        """Extract agent ID and region from ARN if not provided."""
        if self.agent_arn and not self.agent_id:
            # Extract agent ID from ARN: arn:aws:bedrock-agentcore:region:account:runtime/agent-id
            arn_parts = self.agent_arn.split(':')
            if len(arn_parts) >= 6 and 'runtime/' in arn_parts[5]:
                self.agent_id = arn_parts[5].split('/')[-1]
        
        if self.agent_arn and not self.region:
            # Extract region from ARN
            arn_parts = self.agent_arn.split(':')
            if len(arn_parts) >= 4:
                self.region = arn_parts[3]
        
        # Use environment variable or default if stack_prefix is None
        if self.stack_prefix is None:
            self.stack_prefix = os.environ.get('PARAM_PREFIX', 'coa')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RegistrationResult:
    """Result of the agent registration process."""
    agent_name: str
    agent_arn: str
    agent_id: Optional[str] = None
    region: Optional[str] = None
    registration_timestamp: Optional[str] = None
    status: str = "pending"
    ssm_parameters_created: List[str] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.ssm_parameters_created is None:
            self.ssm_parameters_created = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class ProgressReporter:
    """Utility class for reporting registration progress with visual indicators."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.start_time = time.time()
    
    def report_start(self, message: str) -> None:
        """Report the start of the registration process."""
        self.logger.info(f"🚀 {message}")
        print(f"🚀 {message}")
    
    def report_step(self, message: str) -> None:
        """Report a registration step in progress."""
        self.logger.info(f"📋 {message}")
        print(f"📋 {message}")
    
    def report_success(self, message: str) -> None:
        """Report a successful step."""
        self.logger.info(f"✓ {message}")
        print(f"✓ {message}")
    
    def report_warning(self, message: str) -> None:
        """Report a warning."""
        self.logger.warning(f"⚠️ {message}")
        print(f"⚠️ {message}")
    
    def report_error(self, message: str) -> None:
        """Report an error."""
        self.logger.error(f"❌ {message}")
        print(f"❌ {message}")
    
    def report_info(self, message: str) -> None:
        """Report informational message."""
        self.logger.info(f"ℹ️ {message}")
        print(f"ℹ️ {message}")
    
    def report_completion(self, message: str) -> None:
        """Report successful completion."""
        elapsed = time.time() - self.start_time
        completion_msg = f"{message} (completed in {elapsed:.1f}s)"
        self.logger.info(f"🎉 {completion_msg}")
        print(f"🎉 {completion_msg}")


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration for the registration script.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"manual_agent_registration_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger("manual_agent_registration")
    logger.info(f"Logging initialized. Log file: {log_file}")
    
    return logger


def validate_aws_credentials() -> bool:
    """
    Validate that AWS credentials are properly configured.
    
    Returns:
        True if credentials are valid, False otherwise
    """
    try:
        # Try to get caller identity to validate credentials
        sts_client = boto3.client('sts')
        response = sts_client.get_caller_identity()
        return True
    except (NoCredentialsError, ClientError) as e:
        return False


def validate_agent_arn(agent_arn: str) -> bool:
    """
    Validate that the agent ARN has the correct format.
    
    Args:
        agent_arn: The agent ARN to validate
        
    Returns:
        True if ARN format is valid, False otherwise
    """
    if not agent_arn:
        return False
    
    # Expected format: arn:aws:bedrock-agentcore:region:account:runtime/agent-id
    arn_parts = agent_arn.split(':')
    
    if len(arn_parts) != 6:
        return False
    
    if arn_parts[0] != 'arn':
        return False
    
    if arn_parts[1] != 'aws':
        return False
    
    if arn_parts[2] != 'bedrock-agentcore':
        return False
    
    if not arn_parts[3]:  # region
        return False
    
    if not arn_parts[4]:  # account
        return False
    
    if not arn_parts[5].startswith('runtime/'):
        return False
    
    return True


class AgentValidator:
    """Validates manually deployed agents."""
    
    def __init__(self, bedrock_agentcore_client, logger, progress_reporter):
        self.bedrock_agentcore_client = bedrock_agentcore_client
        self.logger = logger
        self.progress = progress_reporter
    
    def validate_agent_exists(self, agent_info: ManualAgentInfo) -> bool:
        """
        Validate that the agent actually exists and is accessible.
        
        Args:
            agent_info: Information about the agent to validate
            
        Returns:
            True if agent exists and is accessible, False otherwise
        """
        try:
            # Note: This is a placeholder for actual agent validation
            # The exact API call depends on the Bedrock AgentCore service
            # For now, we'll assume the agent exists if the ARN format is valid
            
            if not validate_agent_arn(agent_info.agent_arn):
                self.progress.report_error(f"Invalid agent ARN format: {agent_info.agent_arn}")
                return False
            
            self.progress.report_success(f"Agent ARN format validated: {agent_info.agent_arn}")
            
            # TODO: Add actual agent existence check when API is available
            # Example:
            # response = self.bedrock_agentcore_client.describe_agent(AgentArn=agent_info.agent_arn)
            # return response['Agent']['Status'] in ['ACTIVE', 'AVAILABLE']
            
            return True
            
        except ClientError as e:
            self.logger.error(f"Error validating agent: {e}")
            self.progress.report_error(f"Failed to validate agent: {str(e)}")
            return False
    
    def get_agent_details(self, agent_info: ManualAgentInfo) -> Dict[str, Any]:
        """
        Get additional details about the agent if available.
        
        Args:
            agent_info: Information about the agent
            
        Returns:
            Dictionary with additional agent details
        """
        details = {
            'agent_name': agent_info.agent_name,
            'agent_arn': agent_info.agent_arn,
            'agent_id': agent_info.agent_id,
            'region': agent_info.region,
            'status': 'unknown'  # Would be populated from actual API call
        }
        
        # TODO: Add actual agent details retrieval when API is available
        # Example:
        # try:
        #     response = self.bedrock_agentcore_client.describe_agent(AgentArn=agent_info.agent_arn)
        #     details.update({
        #         'status': response['Agent']['Status'],
        #         'created_at': response['Agent']['CreatedAt'],
        #         'updated_at': response['Agent']['UpdatedAt'],
        #         'execution_role_arn': response['Agent']['ExecutionRoleArn']
        #     })
        # except ClientError as e:
        #     self.logger.warning(f"Could not retrieve agent details: {e}")
        
        return details


class SSMParameterManager:
    """Creates and manages SSM parameters for manual agent integration."""
    
    def __init__(self, ssm_client, logger, progress_reporter):
        self.ssm_client = ssm_client
        self.logger = logger
        self.progress = progress_reporter
    
    def create_agent_parameters(self, agent_info: ManualAgentInfo) -> List[str]:
        """
        Create SSM parameters for the manually deployed agent.
        
        Args:
            agent_info: Information about the agent
            
        Returns:
            List of created parameter paths
        """
        self.progress.report_step("Creating SSM parameters for manual agent...")
        
        created_parameters = []
        base_path = f"/{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}"
        
        # Basic agent parameters
        parameters = {
            'agent_arn': agent_info.agent_arn,
            'agent_id': agent_info.agent_id,
            'region': agent_info.region,
            'deployment_type': agent_info.deployment_type,
            'agent_type': agent_info.agent_type
        }
        
        # Optional parameters
        if agent_info.execution_role_arn:
            parameters['execution_role_arn'] = agent_info.execution_role_arn
        
        if agent_info.source_path:
            parameters['source_path'] = agent_info.source_path
        
        if agent_info.description:
            parameters['description'] = agent_info.description
        
        # Create each parameter
        for param_name, param_value in parameters.items():
            if param_value:
                param_path = f"{base_path}/{param_name}"
                try:
                    self.ssm_client.put_parameter(
                        Name=param_path,
                        Value=str(param_value),
                        Type='String',
                        Overwrite=True,
                        Description=f"Manual agent {agent_info.agent_name} - {param_name}"
                    )
                    created_parameters.append(param_path)
                    self.logger.debug(f"Created parameter: {param_path}")
                except ClientError as e:
                    self.logger.error(f"Failed to create parameter {param_path}: {e}")
        
        return created_parameters
    
    def create_connection_info(self, agent_info: ManualAgentInfo) -> Optional[str]:
        """
        Create connection information parameter for chatbot integration.
        
        Args:
            agent_info: Information about the agent
            
        Returns:
            Parameter path if created successfully, None otherwise
        """
        connection_info = {
            "agent_arn": agent_info.agent_arn,
            "agent_id": agent_info.agent_id,
            "region": agent_info.region,
            "deployment_type": agent_info.deployment_type,
            "agent_type": agent_info.agent_type,
            "registration_timestamp": datetime.now().isoformat(),
            "status": "registered"
        }
        
        # Add optional fields
        if agent_info.execution_role_arn:
            connection_info["execution_role_arn"] = agent_info.execution_role_arn
        
        if agent_info.description:
            connection_info["description"] = agent_info.description
        
        param_path = f"/{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/connection_info"
        
        try:
            self.ssm_client.put_parameter(
                Name=param_path,
                Value=json.dumps(connection_info, indent=2),
                Type='String',
                Overwrite=True,
                Description=f"Manual agent {agent_info.agent_name} connection information"
            )
            self.logger.debug(f"Created connection info parameter: {param_path}")
            return param_path
        except ClientError as e:
            self.logger.error(f"Failed to create connection info parameter: {e}")
            return None
    
    def create_metadata_parameters(self, agent_info: ManualAgentInfo) -> Optional[str]:
        """
        Create metadata parameter for the agent.
        
        Args:
            agent_info: Information about the agent
            
        Returns:
            Parameter path if created successfully, None otherwise
        """
        metadata = {
            "registration_timestamp": datetime.now().isoformat(),
            "registration_version": "1.0.0",
            "agent_type": agent_info.agent_type,
            "deployment_type": agent_info.deployment_type,
            "registration_method": "manual_script"
        }
        
        if agent_info.description:
            metadata["description"] = agent_info.description
        
        if agent_info.source_path:
            metadata["source_path"] = agent_info.source_path
        
        param_path = f"/{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/metadata"
        
        try:
            self.ssm_client.put_parameter(
                Name=param_path,
                Value=json.dumps(metadata, indent=2),
                Type='String',
                Overwrite=True,
                Description=f"Manual agent {agent_info.agent_name} metadata"
            )
            self.logger.debug(f"Created metadata parameter: {param_path}")
            return param_path
        except ClientError as e:
            self.logger.error(f"Failed to create metadata parameter: {e}")
            return None
    
    def validate_parameter_creation(self, parameter_paths: List[str]) -> bool:
        """
        Verify that parameters were created successfully.
        
        Args:
            parameter_paths: List of parameter paths to validate
            
        Returns:
            True if all parameters exist, False otherwise
        """
        self.progress.report_step("Validating parameter creation...")
        
        validated_params = []
        for param_path in parameter_paths:
            try:
                self.ssm_client.get_parameter(Name=param_path)
                validated_params.append(param_path)
            except ClientError:
                self.logger.warning(f"Parameter not found: {param_path}")
        
        if validated_params:
            self.progress.report_success(f"Validated {len(validated_params)} SSM parameters")
            return len(validated_params) == len(parameter_paths)
        else:
            self.progress.report_error("No SSM parameters were validated successfully")
            return False
    
    def list_existing_agent_parameters(self, agent_name: str, stack_prefix: str = None) -> List[str]:
        """
        List existing parameters for an agent.
        
        Args:
            agent_name: Name of the agent
            stack_prefix: Stack prefix for parameter path
            
        Returns:
            List of existing parameter paths
        """
        if stack_prefix is None:
            stack_prefix = os.environ.get('PARAM_PREFIX', 'coa')
        base_path = f"/{stack_prefix}/agentcore/{agent_name}"
        existing_params = []
        
        try:
            response = self.ssm_client.get_parameters_by_path(
                Path=base_path,
                Recursive=True
            )
            
            for param in response.get('Parameters', []):
                existing_params.append(param['Name'])
                
        except ClientError as e:
            self.logger.debug(f"No existing parameters found for {agent_name}: {e}")
        
        return existing_params


class ManualAgentRegistrar:
    """
    Main class for registering manually deployed agents.
    
    This class handles the complete registration process including:
    - Agent validation
    - SSM parameter creation
    - Integration setup for chatbot
    """
    
    def __init__(self, region: str):
        """
        Initialize the registrar.
        
        Args:
            region: AWS region for the agent
        """
        self.region = region
        self.logger = setup_logging()
        self.progress = ProgressReporter(self.logger)
        
        # Initialize AWS clients
        self.session = boto3.Session(region_name=region)
        self.ssm_client = self.session.client('ssm')
        
        # Note: bedrock-agentcore client may not be available yet
        # self.bedrock_agentcore_client = self.session.client('bedrock-agentcore')
        self.bedrock_agentcore_client = None
        
        # Initialize component classes
        self.agent_validator = AgentValidator(self.bedrock_agentcore_client, self.logger, self.progress)
        self.ssm_manager = SSMParameterManager(self.ssm_client, self.logger, self.progress)
    
    def validate_prerequisites(self) -> bool:
        """
        Validate prerequisites for registration.
        
        Returns:
            True if prerequisites are met, False otherwise
        """
        self.progress.report_step("Validating prerequisites...")
        
        # Check AWS credentials
        if not validate_aws_credentials():
            self.progress.report_error("AWS credentials not configured or invalid")
            return False
        
        self.progress.report_success("AWS credentials validated")
        
        # Check SSM access
        try:
            self.ssm_client.describe_parameters(MaxResults=1)
            self.progress.report_success("SSM access validated")
        except ClientError as e:
            self.progress.report_error(f"SSM access validation failed: {e}")
            return False
        
        return True
    
    def check_existing_registration(self, agent_name: str, stack_prefix: str = None) -> bool:
        """
        Check if the agent is already registered.
        
        Args:
            agent_name: Name of the agent to check
            stack_prefix: Stack prefix for parameter path
            
        Returns:
            True if agent is already registered, False otherwise
        """
        if stack_prefix is None:
            stack_prefix = os.environ.get('PARAM_PREFIX', 'coa')
        existing_params = self.ssm_manager.list_existing_agent_parameters(agent_name, stack_prefix)
        
        if existing_params:
            self.progress.report_warning(f"Agent '{agent_name}' appears to be already registered")
            self.progress.report_info(f"Existing parameters: {len(existing_params)}")
            for param in existing_params[:5]:  # Show first 5 parameters
                self.progress.report_info(f"  - {param}")
            if len(existing_params) > 5:
                self.progress.report_info(f"  ... and {len(existing_params) - 5} more")
            return True
        
        return False
    
    def register_agent(self, agent_info: ManualAgentInfo, overwrite: bool = False) -> RegistrationResult:
        """
        Register a manually deployed agent.
        
        Args:
            agent_info: Information about the agent to register
            overwrite: Whether to overwrite existing registration
            
        Returns:
            RegistrationResult with registration status and details
        """
        self.progress.report_start(f"Registering manual agent: {agent_info.agent_name}")
        
        result = RegistrationResult(
            agent_name=agent_info.agent_name,
            agent_arn=agent_info.agent_arn,
            agent_id=agent_info.agent_id,
            region=agent_info.region,
            registration_timestamp=datetime.now().isoformat()
        )
        
        try:
            # Step 1: Validate prerequisites
            if not self.validate_prerequisites():
                result.status = "failed"
                result.error_message = "Prerequisites validation failed"
                return result
            
            # Step 2: Check for existing registration
            if not overwrite and self.check_existing_registration(agent_info.agent_name, agent_info.stack_prefix):
                result.status = "already_registered"
                result.error_message = "Agent already registered (use --overwrite to replace)"
                return result
            
            # Step 3: Validate agent
            if not self.agent_validator.validate_agent_exists(agent_info):
                result.status = "failed"
                result.error_message = "Agent validation failed"
                return result
            
            # Step 4: Create SSM parameters
            created_params = self.ssm_manager.create_agent_parameters(agent_info)
            
            # Step 5: Create connection info
            connection_param = self.ssm_manager.create_connection_info(agent_info)
            if connection_param:
                created_params.append(connection_param)
            
            # Step 6: Create metadata
            metadata_param = self.ssm_manager.create_metadata_parameters(agent_info)
            if metadata_param:
                created_params.append(metadata_param)
            
            result.ssm_parameters_created = created_params
            
            # Step 7: Validate parameter creation
            if self.ssm_manager.validate_parameter_creation(created_params):
                result.status = "completed"
                self.progress.report_success(f"Successfully registered agent: {agent_info.agent_name}")
            else:
                result.status = "completed_with_warnings"
                result.error_message = "Some parameters may not have been created successfully"
                self.progress.report_warning("Registration completed with warnings")
            
            return result
            
        except Exception as e:
            self.logger.exception("Unexpected error during registration")
            self.progress.report_error(f"Registration failed: {str(e)}")
            result.status = "failed"
            result.error_message = str(e)
            return result
    
    def generate_registration_summary(self, result: RegistrationResult) -> str:
        """
        Generate a summary of the registration process.
        
        Args:
            result: Registration result
            
        Returns:
            Formatted summary string
        """
        summary = f"""
🎉 Manual Agent Registration Summary
{'=' * 40}

Agent Information:
  Name: {result.agent_name}
  ARN: {result.agent_arn}
  ID: {result.agent_id or 'N/A'}
  Region: {result.region or 'N/A'}

Registration Status: {result.status.upper()}
Registration Time: {result.registration_timestamp}

SSM Parameters Created ({len(result.ssm_parameters_created)}):
"""
        
        for param_path in result.ssm_parameters_created:
            summary += f"  - {param_path}\n"
        
        if result.status == "completed":
            summary += """
✅ Registration completed successfully!

Next Steps:
1. The agent is now available for use in the COA chatbot
2. Test the agent through the web interface
3. Monitor agent performance in CloudWatch Logs
4. Update agent configuration as needed

Integration:
The chatbot will automatically discover this agent via the SSM parameters.
No additional configuration is required for basic usage.
"""
        elif result.status == "failed":
            summary += f"""
❌ Registration failed: {result.error_message}

Please check the logs for more details and resolve any issues before retrying.
"""
        elif result.status == "already_registered":
            summary += """
⚠️ Agent already registered

Use the --overwrite flag if you want to replace the existing registration.
"""
        
        return summary.strip()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Register manually deployed agents for COA chatbot integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Register a basic manual agent
  python register_manual_agent.py --region us-east-1 --agent-name my-manual-agent --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id
  
  # Register with additional information
  python register_manual_agent.py --region us-east-1 --agent-name my-agent --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id --agent-type custom --description "My custom agent"
  
  # Register with custom stack prefix
  python register_manual_agent.py --region us-east-1 --agent-name my-agent --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id --stack-prefix "my-stack"
  
  # Overwrite existing registration
  python register_manual_agent.py --region us-east-1 --agent-name my-agent --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id --overwrite
        """
    )
    
    parser.add_argument(
        "--region",
        required=True,
        help="AWS region where the agent is deployed"
    )
    
    parser.add_argument(
        "--agent-name",
        required=True,
        help="Name for the agent (used for SSM parameter organization)"
    )
    
    parser.add_argument(
        "--agent-arn",
        required=True,
        help="ARN of the manually deployed agent"
    )
    
    parser.add_argument(
        "--agent-type",
        default="manual",
        help="Type of agent (default: manual)"
    )
    
    parser.add_argument(
        "--source-path",
        help="Source path of the agent code (optional)"
    )
    
    parser.add_argument(
        "--execution-role-arn",
        help="ARN of the execution role used by the agent (optional)"
    )
    
    parser.add_argument(
        "--description",
        help="Description of the agent (optional)"
    )
    
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing registration if it exists"
    )
    
    parser.add_argument(
        "--stack-prefix",
        default="coa",
        help="Stack prefix for SSM parameter paths (default: coa)"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the registration script."""
    try:
        args = parse_arguments()
        
        # Set up logging level
        if hasattr(args, 'log_level'):
            logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
        
        # Create agent info from arguments
        agent_info = ManualAgentInfo(
            agent_name=args.agent_name,
            agent_arn=args.agent_arn,
            region=args.region,
            agent_type=args.agent_type,
            source_path=getattr(args, 'source_path', None),
            execution_role_arn=getattr(args, 'execution_role_arn', None),
            description=getattr(args, 'description', None),
            stack_prefix=getattr(args, 'stack_prefix', 'coa')
        )
        
        # Initialize registrar
        registrar = ManualAgentRegistrar(region=args.region)
        
        # Execute registration
        result = registrar.register_agent(
            agent_info=agent_info,
            overwrite=getattr(args, 'overwrite', False)
        )
        
        # Generate and display summary
        summary = registrar.generate_registration_summary(result)
        print(summary)
        
        # Exit with appropriate code
        if result.status == "failed":
            sys.exit(1)
        elif result.status == "already_registered" and not args.overwrite:
            sys.exit(2)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n❌ Registration interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()