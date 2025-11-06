#!/usr/bin/env python3
"""
Interactive Agent Registration Tool

This script provides a one-click interactive way to:
1. List available Bedrock AgentCore runtimes
2. Allow users to select agents to register
3. Guide through the registration process
4. Verify integration with COA chatbot

Usage:
    python interactive_agent_registration.py --region us-east-1
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def _load_param_prefix_from_config() -> str:
    """Load parameter prefix from deployment-config.json"""
    try:
        config_file = "deployment-config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
            return config.get('deployment', {}).get('param_prefix', 'coa')
    except Exception:
        pass
    return 'coa'


# Import our registration modules
try:
    from register_manual_agent import (
        ManualAgentInfo, 
        ManualAgentRegistrar,
        validate_agent_arn,
        validate_aws_credentials
    )
    from discover_agents import AgentDiscovery
except ImportError as e:
    print(f"❌ Failed to import registration modules: {e}")
    print("Make sure you're running this from the deployment-scripts/components directory")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


class InteractiveUI:
    """Interactive user interface for agent registration."""
    
    def __init__(self):
        self.colors = Colors()
    
    def print_header(self, title: str) -> None:
        """Print a formatted header."""
        print(f"\n{self.colors.BOLD}{self.colors.BLUE}{'=' * 60}{self.colors.NC}")
        print(f"{self.colors.BOLD}{self.colors.WHITE}{title:^60}{self.colors.NC}")
        print(f"{self.colors.BOLD}{self.colors.BLUE}{'=' * 60}{self.colors.NC}\n")
    
    def print_success(self, message: str) -> None:
        """Print a success message."""
        print(f"{self.colors.GREEN}✅ {message}{self.colors.NC}")
    
    def print_error(self, message: str) -> None:
        """Print an error message."""
        print(f"{self.colors.RED}❌ {message}{self.colors.NC}")
    
    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        print(f"{self.colors.YELLOW}⚠️ {message}{self.colors.NC}")
    
    def print_info(self, message: str) -> None:
        """Print an info message."""
        print(f"{self.colors.CYAN}ℹ️ {message}{self.colors.NC}")
    
    def print_step(self, step: int, message: str) -> None:
        """Print a step message."""
        print(f"{self.colors.PURPLE}{self.colors.BOLD}Step {step}:{self.colors.NC} {message}")
    
    def get_user_input(self, prompt: str, default: str = None) -> str:
        """Get user input with optional default."""
        if default:
            full_prompt = f"{prompt} [{default}]: "
        else:
            full_prompt = f"{prompt}: "
        
        response = input(full_prompt).strip()
        return response if response else (default or "")
    
    def get_user_choice(self, prompt: str, choices: List[str], default: int = None) -> int:
        """Get user choice from a list of options."""
        print(f"\n{prompt}")
        for i, choice in enumerate(choices, 1):
            marker = " (default)" if default == i else ""
            print(f"  {i}. {choice}{marker}")
        
        while True:
            try:
                choice_input = input(f"\nEnter choice (1-{len(choices)}): ").strip()
                if not choice_input and default:
                    return default
                
                choice = int(choice_input)
                if 1 <= choice <= len(choices):
                    return choice
                else:
                    self.print_error(f"Please enter a number between 1 and {len(choices)}")
            except ValueError:
                self.print_error("Please enter a valid number")
    
    def confirm_action(self, message: str, default: bool = True) -> bool:
        """Get user confirmation."""
        default_text = "Y/n" if default else "y/N"
        response = input(f"{message} ({default_text}): ").strip().lower()
        
        if not response:
            return default
        
        return response in ['y', 'yes', 'true', '1']
    
    def display_table(self, headers: List[str], rows: List[List[str]], title: str = None) -> None:
        """Display data in a formatted table."""
        if title:
            print(f"\n{self.colors.BOLD}{title}{self.colors.NC}")
        
        if not rows:
            self.print_warning("No data to display")
            return
        
        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print header
        header_row = " | ".join(header.ljust(col_widths[i]) for i, header in enumerate(headers))
        print(f"{self.colors.BOLD}{header_row}{self.colors.NC}")
        print("-" * len(header_row))
        
        # Print rows
        for row in rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            print(row_str)
        print()


class AgentCoreRuntimeDiscovery:
    """Discovers available Bedrock AgentCore runtimes using AWS APIs."""
    
    def __init__(self, region: str, logger: logging.Logger, ui: InteractiveUI):
        self.region = region
        self.logger = logger
        self.ui = ui
        self.session = boto3.Session(region_name=region)
        
        # Initialize AWS clients
        try:
            # Use bedrock-agentcore-control service for listing runtimes
            self.bedrock_agentcore_client = self.session.client('bedrock-agentcore-control')
        except Exception as e:
            self.logger.debug(f"Bedrock AgentCore Control client not available: {e}")
            self.bedrock_agentcore_client = None
        
        # Alternative clients for discovery
        self.logs_client = self.session.client('logs')
        self.iam_client = self.session.client('iam')
    
    def discover_runtimes_from_aws_api(self) -> List[Dict[str, Any]]:
        """
        Discover AgentCore runtimes using AWS APIs.
        
        Returns:
            List of discovered runtime configurations from AWS
        """
        self.ui.print_step(1, "Discovering AgentCore runtimes via AWS APIs...")
        
        runtimes = []
        
        # Method 1: Try bedrock-agentcore API if available
        if self.bedrock_agentcore_client:
            try:
                runtimes.extend(self._discover_via_bedrock_agentcore_api())
            except Exception as e:
                self.logger.debug(f"Bedrock AgentCore API discovery failed: {e}")
        
        # Method 2: Discover via CloudWatch Logs (AgentCore creates log groups)
        try:
            log_runtimes = self._discover_via_cloudwatch_logs()
            runtimes.extend(log_runtimes)
        except Exception as e:
            self.logger.debug(f"CloudWatch Logs discovery failed: {e}")
        
        # Method 3: Discover via IAM roles (AgentCore creates execution roles)
        # Note: Disabled for now as it adds incomplete entries without agent ARNs
        # try:
        #     iam_runtimes = self._discover_via_iam_roles()
        #     runtimes.extend(iam_runtimes)
        # except Exception as e:
        #     self.logger.debug(f"IAM roles discovery failed: {e}")
        
        # Method 4: Discover via Bedrock model usage (if agents have been invoked)
        # Note: Not implemented yet
        # try:
        #     usage_runtimes = self._discover_via_bedrock_usage()
        #     runtimes.extend(usage_runtimes)
        # except Exception as e:
        #     self.logger.debug(f"Bedrock usage discovery failed: {e}")
        
        # Deduplicate and enrich runtime information
        unique_runtimes = self._deduplicate_runtimes(runtimes)
        
        self.ui.print_success(f"Discovered {len(unique_runtimes)} AgentCore runtimes via AWS APIs")
        
        return unique_runtimes
    
    def _discover_via_bedrock_agentcore_api(self) -> List[Dict[str, Any]]:
        """Discover runtimes using Bedrock AgentCore Control API calls."""
        runtimes = []
        
        try:
            # List all agent runtimes using bedrock-agentcore-control service
            response = self.bedrock_agentcore_client.list_agent_runtimes()
            
            for runtime_summary in response.get('agentRuntimes', []):
                runtime_id = runtime_summary.get('agentRuntimeId')
                
                try:
                    # Get detailed runtime information if available
                    if runtime_id:
                        runtime_details = self.bedrock_agentcore_client.get_agent_runtime(agentRuntimeId=runtime_id)
                        # Remove ResponseMetadata and use the rest as runtime info
                        runtime = {k: v for k, v in runtime_details.items() if k != 'ResponseMetadata'}
                    else:
                        runtime = runtime_summary
                    
                    runtime_info = {
                        'agent_arn': runtime.get('agentRuntimeArn'),
                        'agent_id': runtime.get('agentRuntimeId'),
                        'agent_name': runtime.get('agentRuntimeName') or f"runtime-{runtime.get('agentRuntimeId', 'unknown')[:8]}",
                        'status': runtime.get('status'),
                        'created_at': runtime.get('createdAt'),
                        'updated_at': runtime.get('lastUpdatedAt'),
                        'source': 'bedrock_agentcore_api',
                        'runtime_status': 'deployed',
                        'execution_role_arn': runtime.get('roleArn'),
                        'description': '',
                        'runtime_version': runtime.get('agentRuntimeVersion'),
                        'network_configuration': runtime.get('networkConfiguration', {}),
                        'lifecycle_configuration': runtime.get('lifecycleConfiguration', {}),
                        'environment_variables': runtime.get('environmentVariables', {})
                    }
                    
                    runtimes.append(runtime_info)
                    
                except ClientError as e:
                    self.logger.debug(f"Error getting runtime details for {runtime_arn}: {e}")
                    # Use summary information if detailed call fails
                    runtime_info = {
                        'agent_arn': runtime_summary.get('agentRuntimeArn'),
                        'agent_id': runtime_summary.get('agentRuntimeId'),
                        'agent_name': runtime_summary.get('agentRuntimeName') or f"runtime-{runtime_summary.get('agentRuntimeId', 'unknown')[:8]}",
                        'status': runtime_summary.get('status'),
                        'created_at': None,
                        'updated_at': runtime_summary.get('lastUpdatedAt'),
                        'source': 'bedrock_agentcore_api',
                        'runtime_status': 'deployed',
                        'execution_role_arn': '',
                        'description': '',
                        'runtime_version': runtime_summary.get('agentRuntimeVersion')
                    }
                    runtimes.append(runtime_info)
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['UnauthorizedOperation', 'AccessDenied']:
                self.logger.warning("Insufficient permissions for Bedrock AgentCore Control API")
            else:
                self.logger.warning(f"Bedrock AgentCore Control API error: {e}")
        except Exception as e:
            self.logger.debug(f"Bedrock AgentCore Control API discovery error: {e}")
        
        return runtimes
    
    def _discover_via_cloudwatch_logs(self) -> List[Dict[str, Any]]:
        """Discover runtimes by looking for AgentCore CloudWatch log groups."""
        runtimes = []
        
        try:
            # AgentCore typically creates log groups with specific patterns
            log_group_patterns = [
                '/aws/bedrock/agentcore/',
                '/aws/lambda/bedrock-agentcore-',
                '/bedrock/agentcore/'
            ]
            
            paginator = self.logs_client.get_paginator('describe_log_groups')
            
            for pattern in log_group_patterns:
                try:
                    for page in paginator.paginate(logGroupNamePrefix=pattern):
                        for log_group in page.get('logGroups', []):
                            log_group_name = log_group['logGroupName']
                            
                            # Extract agent information from log group name
                            agent_info = self._extract_agent_info_from_log_group(log_group_name)
                            
                            if agent_info:
                                runtime_info = {
                                    'agent_name': agent_info.get('agent_name'),
                                    'agent_id': agent_info.get('agent_id'),
                                    'log_group_name': log_group_name,
                                    'created_at': log_group.get('creationTime'),
                                    'source': 'cloudwatch_logs',
                                    'runtime_status': 'active'
                                }
                                
                                # Try to construct ARN from log group information
                                if agent_info.get('agent_id'):
                                    runtime_info['agent_arn'] = f"arn:aws:bedrock-agentcore:{self.region}:{self._get_account_id()}:runtime/{agent_info['agent_id']}"
                                
                                runtimes.append(runtime_info)
                                
                except ClientError as e:
                    self.logger.debug(f"Error checking log group pattern {pattern}: {e}")
                    
        except Exception as e:
            self.logger.debug(f"CloudWatch Logs discovery error: {e}")
        
        return runtimes
    
    def _discover_via_iam_roles(self) -> List[Dict[str, Any]]:
        """Discover runtimes by looking for AgentCore IAM execution roles."""
        runtimes = []
        
        try:
            # AgentCore creates IAM roles with specific patterns
            role_patterns = [
                'AmazonBedrockAgentCoreSDKRuntime',
                'bedrock-agentcore-runtime',
                'agentcore-execution-role'
            ]
            
            paginator = self.iam_client.get_paginator('list_roles')
            
            for page in paginator.paginate():
                for role in page.get('Roles', []):
                    role_name = role['RoleName']
                    
                    # Check if role matches AgentCore patterns
                    if any(pattern.lower() in role_name.lower() for pattern in role_patterns):
                        # Extract agent information from role name or tags
                        agent_info = self._extract_agent_info_from_iam_role(role)
                        
                        if agent_info:
                            runtime_info = {
                                'agent_name': agent_info.get('agent_name'),
                                'execution_role_arn': role['Arn'],
                                'role_name': role_name,
                                'created_at': role.get('CreateDate'),
                                'source': 'iam_roles',
                                'runtime_status': 'configured'
                            }
                            
                            runtimes.append(runtime_info)
                            
        except ClientError as e:
            if e.response['Error']['Code'] in ['UnauthorizedOperation', 'AccessDenied']:
                self.logger.debug("Insufficient permissions for IAM role discovery")
            else:
                self.logger.debug(f"IAM role discovery error: {e}")
        
        return runtimes
    
    def _discover_via_bedrock_usage(self) -> List[Dict[str, Any]]:
        """Discover runtimes by looking at Bedrock model usage patterns."""
        runtimes = []
        
        try:
            # This would involve checking CloudTrail or CloudWatch metrics
            # for Bedrock model invocations that might be from AgentCore
            
            # For now, we'll implement a basic check for recent Bedrock activity
            # that might indicate AgentCore usage
            
            # Note: This is a placeholder for more sophisticated discovery
            # Real implementation would analyze CloudTrail logs or metrics
            
            pass
            
        except Exception as e:
            self.logger.debug(f"Bedrock usage discovery error: {e}")
        
        return runtimes
    
    def _extract_agent_info_from_log_group(self, log_group_name: str) -> Optional[Dict[str, str]]:
        """Extract agent information from CloudWatch log group name."""
        import re
        
        # Common patterns for AgentCore log groups
        patterns = [
            r'/aws/bedrock/agentcore/([^/]+)/([^/]+)',  # /aws/bedrock/agentcore/agent-name/agent-id
            r'/aws/lambda/bedrock-agentcore-([^-]+)-([^/]+)',  # /aws/lambda/bedrock-agentcore-name-id
            r'/bedrock/agentcore/([^/]+)',  # /bedrock/agentcore/agent-id
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_group_name)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return {
                        'agent_name': groups[0],
                        'agent_id': groups[1]
                    }
                elif len(groups) == 1:
                    return {
                        'agent_id': groups[0],
                        'agent_name': f"agent-{groups[0][:8]}"  # Generate name from ID
                    }
        
        return None
    
    def _extract_agent_info_from_iam_role(self, role: Dict) -> Optional[Dict[str, str]]:
        """Extract agent information from IAM role."""
        role_name = role['RoleName']
        
        # Try to extract agent name from role name
        import re
        
        # Look for patterns in role name
        patterns = [
            r'agentcore-([^-]+)-role',
            r'bedrock-agentcore-([^-]+)',
            r'AmazonBedrockAgentCoreSDKRuntime-([^-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, role_name, re.IGNORECASE)
            if match:
                agent_name = match.group(1)
                return {
                    'agent_name': agent_name
                }
        
        # Check role tags for agent information
        try:
            tags_response = self.iam_client.list_role_tags(RoleName=role_name)
            tags = tags_response.get('Tags', [])
            
            for tag in tags:
                if tag['Key'].lower() in ['agentname', 'agent-name', 'agent_name']:
                    return {
                        'agent_name': tag['Value']
                    }
                    
        except ClientError:
            pass
        
        return None
    
    def _deduplicate_runtimes(self, runtimes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate and merge runtime information from different sources."""
        # Group runtimes by agent_arn or agent_id
        runtime_groups = {}
        
        for runtime in runtimes:
            # Use agent_arn as primary key, fall back to agent_id or agent_name
            key = runtime.get('agent_arn') or runtime.get('agent_id') or runtime.get('agent_name')
            
            if key:
                if key not in runtime_groups:
                    runtime_groups[key] = runtime
                else:
                    # Merge information from multiple sources
                    existing = runtime_groups[key]
                    
                    # Prefer more complete information
                    for field in ['agent_arn', 'agent_id', 'agent_name', 'execution_role_arn']:
                        if field in runtime and field not in existing:
                            existing[field] = runtime[field]
                    
                    # Combine sources
                    existing_sources = existing.get('sources', [existing.get('source')])
                    new_source = runtime.get('source')
                    if new_source and new_source not in existing_sources:
                        existing_sources.append(new_source)
                    existing['sources'] = existing_sources
        
        return list(runtime_groups.values())
    
    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        try:
            sts_client = self.session.client('sts')
            response = sts_client.get_caller_identity()
            return response['Account']
        except Exception:
            return 'unknown'
    
    def _get_arn_from_agentcore_status(self, directory: Path) -> Optional[str]:
        """
        Try to get agent ARN by running agentcore status in the directory.
        
        Args:
            directory: Directory to run agentcore status in
            
        Returns:
            Agent ARN if found, None otherwise
        """
        try:
            import subprocess
            import os
            
            original_cwd = os.getcwd()
            os.chdir(directory)
            
            result = subprocess.run(
                ['agentcore', 'status'], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            os.chdir(original_cwd)
            
            if result.returncode == 0:
                output = result.stdout
                # Look for agent ARN in the status output
                import re
                arn_match = re.search(r'Agent ARN:\s*(arn:aws:bedrock-agentcore:[^:]+:[^:]+:runtime/[^\s]+)', output)
                if arn_match:
                    return arn_match.group(1)
                
                # Alternative pattern
                arn_match = re.search(r'(arn:aws:bedrock-agentcore:[^:]+:[^:]+:runtime/[^\s]+)', output)
                if arn_match:
                    return arn_match.group(1)
            
        except Exception as e:
            self.logger.debug(f"Could not get ARN from agentcore status in {directory}: {e}")
        
        return None
    
    def discover_runtimes_from_ssm(self) -> List[Dict[str, Any]]:
        """
        Discover already registered runtimes from SSM parameters.
        
        Returns:
            List of registered runtimes
        """
        self.ui.print_step(2, "Checking for already registered agents in SSM...")
        
        try:
            # Use the stack prefix from the interactive session
            stack_prefix = getattr(self, 'stack_prefix', os.environ.get('PARAM_PREFIX') or self._load_param_prefix_from_config())
            discovery = AgentDiscovery(self.region, self.logger, stack_prefix)
            registered_agents = discovery.discover_registered_agents()
            
            runtimes = []
            for agent_name, agent_info in registered_agents.items():
                if 'agent_arn' in agent_info['parameters']:
                    runtime_info = {
                        'agent_name': agent_name,
                        'agent_arn': agent_info['parameters']['agent_arn'],
                        'source': 'ssm_registered',
                        'registration_complete': agent_info['registration_complete'],
                        'parameters': agent_info['parameters']
                    }
                    runtimes.append(runtime_info)
            
            return runtimes
            
        except Exception as e:
            self.logger.warning(f"Error discovering registered agents: {e}")
            return []
    
    def discover_all_runtimes(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Discover all available runtimes from AWS APIs and SSM.
        
        Returns:
            Tuple of (aws_runtimes, registered_runtimes)
        """
        aws_runtimes = self.discover_runtimes_from_aws_api()
        registered_runtimes = self.discover_runtimes_from_ssm()
        
        return aws_runtimes, registered_runtimes


class InteractiveAgentRegistration:
    """Main interactive agent registration class."""
    
    def __init__(self, region: str, stack_prefix: str = None):
        self.region = region
        self.stack_prefix = stack_prefix or os.environ.get('PARAM_PREFIX') or self._load_param_prefix_from_config()
        self.ui = InteractiveUI()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger("interactive_registration")
        
        # Initialize components
        self.discovery = AgentCoreRuntimeDiscovery(region, self.logger, self.ui)
        self.registrar = ManualAgentRegistrar(region)
    
    def _load_param_prefix_from_config(self) -> str:
        """Load parameter prefix from deployment-config.json"""
        return _load_param_prefix_from_config()
    
    def validate_prerequisites(self) -> bool:
        """Validate prerequisites for registration."""
        self.ui.print_step(0, "Validating prerequisites...")
        
        # Check AWS credentials
        if not validate_aws_credentials():
            self.ui.print_error("AWS credentials not configured or invalid")
            self.ui.print_info("Please run 'aws configure' to set up your credentials")
            return False
        
        self.ui.print_success("AWS credentials validated")
        
        # Check region
        try:
            sts_client = boto3.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            account_id = identity['Account']
            self.ui.print_success(f"Using AWS account: {account_id} in region: {self.region}")
        except Exception as e:
            self.ui.print_error(f"Error validating AWS setup: {e}")
            return False
        
        return True
    
    def display_discovered_runtimes(self, aws_runtimes: List[Dict], registered_runtimes: List[Dict]) -> None:
        """Display discovered runtimes in a user-friendly format."""
        
        # Display AWS-discovered runtimes
        if aws_runtimes:
            self.ui.print_header("Deployed AgentCore Runtimes (from AWS)")
            
            aws_rows = []
            for i, runtime in enumerate(aws_runtimes, 1):
                agent_name = runtime.get('agent_name', 'Unknown')
                agent_id = runtime.get('agent_id', 'N/A')
                source = runtime.get('source', 'unknown')
                status = runtime.get('runtime_status', 'unknown')
                has_arn = '✅' if 'agent_arn' in runtime else '❌'
                
                # Truncate long agent IDs for display
                display_id = agent_id[:12] + '...' if len(agent_id) > 15 else agent_id
                
                aws_rows.append([str(i), agent_name, display_id, source, has_arn, status])
            
            self.ui.display_table(
                ['#', 'Agent Name', 'Agent ID', 'Source', 'Has ARN', 'Status'],
                aws_rows,
                "Discovered AgentCore Runtimes:"
            )
        else:
            self.ui.print_warning("No AgentCore runtimes found via AWS APIs")
            self.ui.print_info("Make sure agents are deployed and you have appropriate permissions")
        
        # Display registered runtimes
        if registered_runtimes:
            self.ui.print_header("Already Registered Agents")
            
            registered_rows = []
            for i, runtime in enumerate(registered_runtimes, 1):
                agent_name = runtime['agent_name']
                complete = '✅' if runtime['registration_complete'] else '⚠️'
                status = 'Complete' if runtime['registration_complete'] else 'Incomplete'
                
                registered_rows.append([str(i), agent_name, complete, status])
            
            self.ui.display_table(
                ['#', 'Agent Name', 'Complete', 'Status'],
                registered_rows,
                "Already Registered Agents:"
            )
        else:
            self.ui.print_info("No agents currently registered with COA system")
    
    def select_runtime_for_registration(self, aws_runtimes: List[Dict], registered_runtimes: List[Dict]) -> Optional[Dict]:
        """Allow user to select a runtime for registration."""
        
        if not aws_runtimes:
            self.ui.print_warning("No AgentCore runtimes discovered via AWS APIs")
            self.ui.print_info("Make sure agents are deployed and you have appropriate permissions")
            
            # Offer custom ARN entry as fallback
            if self.ui.confirm_action("Would you like to enter a custom agent ARN?"):
                return self.get_custom_agent_info()
            return None
        
        # Filter out already registered runtimes
        registered_arns = set()
        for reg_runtime in registered_runtimes:
            if 'agent_arn' in reg_runtime.get('parameters', {}):
                registered_arns.add(reg_runtime['parameters']['agent_arn'])
        
        available_runtimes = []
        for runtime in aws_runtimes:
            runtime_arn = runtime.get('agent_arn')
            # Only include runtimes that have ARNs and are not already registered
            if runtime_arn and runtime_arn not in registered_arns:
                available_runtimes.append(runtime)
        
        if not available_runtimes:
            self.ui.print_warning("All discovered runtimes are already registered")
            
            # Show option to re-register or enter custom ARN
            choices = ["Re-register an existing agent", "Enter custom agent ARN", "Cancel"]
            choice = self.ui.get_user_choice("What would you like to do?", choices)
            
            if choice == 1:  # Re-register existing
                available_runtimes = aws_runtimes  # Allow selection from all
            elif choice == 2:  # Custom ARN
                return self.get_custom_agent_info()
            else:  # Cancel
                return None
        
        # Create choices from available runtimes
        choices = []
        for runtime in available_runtimes:
            agent_name = runtime.get('agent_name', 'Unknown')
            agent_id = runtime.get('agent_id', 'N/A')
            source = runtime.get('source', 'unknown')
            
            # Create descriptive choice text
            display_id = agent_id[:8] + '...' if len(agent_id) > 12 else agent_id
            choice_text = f"{agent_name} (ID: {display_id}, Source: {source})"
            choices.append(choice_text)
        
        choices.append("Enter custom agent ARN")
        choices.append("Cancel")
        
        choice = self.ui.get_user_choice(
            "Select an agent to register:",
            choices
        )
        
        if choice == len(choices):  # Cancel
            return None
        elif choice == len(choices) - 1:  # Custom ARN
            return self.get_custom_agent_info()
        else:
            return available_runtimes[choice - 1]
    
    def get_custom_agent_info(self) -> Optional[Dict]:
        """Get custom agent information from user input."""
        self.ui.print_header("Custom Agent Registration")
        
        agent_arn = self.ui.get_user_input("Enter agent ARN")
        if not agent_arn:
            self.ui.print_error("Agent ARN is required")
            return None
        
        if not validate_agent_arn(agent_arn):
            self.ui.print_error("Invalid agent ARN format")
            self.ui.print_info("Expected format: arn:aws:bedrock-agentcore:region:account:runtime/agent-id")
            return None
        
        agent_name = self.ui.get_user_input("Enter agent name")
        if not agent_name:
            self.ui.print_error("Agent name is required")
            return None
        
        return {
            'agent_arn': agent_arn,
            'agent_name': agent_name,
            'source': 'custom_input'
        }
    
    def collect_registration_details(self, runtime: Dict) -> ManualAgentInfo:
        """Collect additional registration details from user."""
        self.ui.print_header("Registration Details")
        
        agent_name = runtime.get('agent_name', '')
        agent_arn = runtime.get('agent_arn', '')
        
        # Get or confirm agent name
        if agent_name:
            confirmed_name = self.ui.get_user_input(
                "Agent name", 
                default=agent_name
            )
        else:
            confirmed_name = self.ui.get_user_input("Agent name")
        
        # Get agent type
        type_choices = [
            "strands_agent",
            "security_agent", 
            "cost_optimization",
            "reliability_agent",
            "performance_agent",
            "custom_agent"
        ]
        
        print(f"\n{self.ui.colors.BOLD}Select agent type:{self.ui.colors.NC}")
        for i, agent_type in enumerate(type_choices, 1):
            print(f"  {i}. {agent_type}")
        
        type_choice = self.ui.get_user_choice("", type_choices, default=1)
        selected_type = type_choices[type_choice - 1]
        
        # Get optional details
        source_path = self.ui.get_user_input("Source path (optional)")
        execution_role = self.ui.get_user_input("Execution role ARN (optional)")
        description = self.ui.get_user_input("Description (optional)")
        
        # Create agent info
        agent_info = ManualAgentInfo(
            agent_name=confirmed_name,
            agent_arn=agent_arn,
            agent_type=selected_type,
            source_path=source_path if source_path else None,
            execution_role_arn=execution_role if execution_role else None,
            description=description if description else None,
            stack_prefix=self.stack_prefix
        )
        
        return agent_info
    
    def confirm_registration(self, agent_info: ManualAgentInfo) -> bool:
        """Show registration summary and get confirmation."""
        self.ui.print_header("Registration Summary")
        
        print(f"{self.ui.colors.BOLD}Agent Details:{self.ui.colors.NC}")
        print(f"  Name: {agent_info.agent_name}")
        print(f"  ARN: {agent_info.agent_arn}")
        print(f"  Type: {agent_info.agent_type}")
        print(f"  Region: {agent_info.region}")
        
        if agent_info.source_path:
            print(f"  Source Path: {agent_info.source_path}")
        if agent_info.execution_role_arn:
            print(f"  Execution Role: {agent_info.execution_role_arn}")
        if agent_info.description:
            print(f"  Description: {agent_info.description}")
        
        print(f"\n{self.ui.colors.BOLD}SSM Parameters to be created:{self.ui.colors.NC}")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/agent_arn")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/agent_id")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/region")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/deployment_type")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/agent_type")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/connection_info")
        print(f"  /{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}/metadata")
        
        return self.ui.confirm_action("\nProceed with registration?")
    
    def perform_registration(self, agent_info: ManualAgentInfo) -> bool:
        """Perform the actual registration."""
        self.ui.print_header("Performing Registration")
        
        try:
            result = self.registrar.register_agent(agent_info)
            
            if result.status == "completed":
                self.ui.print_success("Registration completed successfully!")
                
                # Show created parameters
                if result.ssm_parameters_created:
                    print(f"\n{self.ui.colors.BOLD}Created SSM Parameters:{self.ui.colors.NC}")
                    for param in result.ssm_parameters_created:
                        print(f"  ✅ {param}")
                
                return True
                
            elif result.status == "already_registered":
                self.ui.print_warning("Agent is already registered")
                
                if self.ui.confirm_action("Overwrite existing registration?"):
                    result = self.registrar.register_agent(agent_info, overwrite=True)
                    if result.status == "completed":
                        self.ui.print_success("Registration updated successfully!")
                        return True
                
                return False
                
            else:
                self.ui.print_error(f"Registration failed: {result.error_message}")
                return False
                
        except Exception as e:
            self.ui.print_error(f"Registration error: {str(e)}")
            return False
    
    def verify_integration(self, agent_info: ManualAgentInfo) -> None:
        """Verify the agent is properly integrated."""
        self.ui.print_header("Verifying Integration")
        
        try:
            # Check SSM parameters
            ssm_client = boto3.client('ssm', region_name=self.region)
            base_path = f"/{agent_info.stack_prefix}/agentcore/{agent_info.agent_name}"
            
            response = ssm_client.get_parameters_by_path(
                Path=base_path,
                Recursive=True
            )
            
            if response['Parameters']:
                self.ui.print_success(f"Found {len(response['Parameters'])} SSM parameters")
                
                # Show key parameters
                for param in response['Parameters']:
                    param_name = param['Name'].split('/')[-1]
                    if param_name in ['agent_arn', 'agent_type', 'deployment_type']:
                        print(f"  {param_name}: {param['Value']}")
            else:
                self.ui.print_error("No SSM parameters found")
                return
            
            self.ui.print_success("Agent is ready for COA chatbot integration!")
            self.ui.print_info("Launch the COA chatbot to see your registered agent")
            
        except Exception as e:
            self.ui.print_error(f"Verification error: {str(e)}")
    
    def run_interactive_session(self) -> None:
        """Run the complete interactive registration session."""
        self.ui.print_header("🚀 Interactive Agent Registration Tool")
        
        print(f"{self.ui.colors.BOLD}Welcome to the COA Agent Registration Tool!{self.ui.colors.NC}")
        print("This tool will help you register manually deployed agents with the COA chatbot system.\n")
        
        # Step 0: Validate prerequisites
        if not self.validate_prerequisites():
            return
        
        # Step 1-2: Discover runtimes
        aws_runtimes, registered_runtimes = self.discovery.discover_all_runtimes()
        
        # Step 3: Display discovered runtimes
        self.display_discovered_runtimes(aws_runtimes, registered_runtimes)
        
        # Step 4: Select runtime for registration
        selected_runtime = self.select_runtime_for_registration(aws_runtimes, registered_runtimes)
        if not selected_runtime:
            self.ui.print_info("Registration cancelled")
            return
        
        # Step 5: Collect registration details
        agent_info = self.collect_registration_details(selected_runtime)
        
        # Step 6: Confirm registration
        if not self.confirm_registration(agent_info):
            self.ui.print_info("Registration cancelled")
            return
        
        # Step 7: Perform registration
        if self.perform_registration(agent_info):
            # Step 8: Verify integration
            self.verify_integration(agent_info)
            
            self.ui.print_header("🎉 Registration Complete!")
            print(f"{self.ui.colors.GREEN}Your agent '{agent_info.agent_name}' is now registered with the COA system!{self.ui.colors.NC}")
            print(f"\n{self.ui.colors.BOLD}Next Steps:{self.ui.colors.NC}")
            print("1. Launch the COA chatbot web interface")
            print("2. Verify your agent appears in the available agents list")
            print("3. Test agent functionality through the chatbot")
        else:
            self.ui.print_error("Registration failed. Please check the logs and try again.")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Interactive tool for registering Bedrock AgentCore runtimes with COA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This interactive tool will:
1. Discover available Bedrock AgentCore runtimes
2. Show already registered agents
3. Guide you through registering new agents
4. Verify integration with COA chatbot

Examples:
  python interactive_agent_registration.py --region us-east-1
  python interactive_agent_registration.py --region eu-west-1 --log-level DEBUG
        """
    )
    
    parser.add_argument(
        "--region",
        required=True,
        help="AWS region to search for agents and create registrations"
    )
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--stack-prefix",
        help="Stack prefix for SSM parameter paths (default: from PARAM_PREFIX env var or 'coa')"
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the interactive registration tool."""
    try:
        args = parse_arguments()
        
        # Set up logging level
        logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
        
        # Run interactive session
        tool = InteractiveAgentRegistration(args.region, args.stack_prefix)
        tool.run_interactive_session()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️ Registration interrupted by user{Colors.NC}")
        sys.exit(130)
    except Exception as e:
        print(f"{Colors.RED}❌ Unexpected error: {str(e)}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()