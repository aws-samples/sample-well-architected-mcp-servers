#!/usr/bin/env python3
"""
Agent Discovery Utility

This script helps discover manually deployed agents that may need registration
with the COA system. It can scan for:
- Existing SSM parameters that indicate registered agents
- AgentCore configurations in the project
- Potential agents that need registration

Usage:
    python discover_agents.py --region us-east-1
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger("agent_discovery")


class AgentDiscovery:
    """Discovers existing agents and their registration status."""
    
    def __init__(self, region: str, logger: logging.Logger, stack_prefix: str = "coa"):
        self.region = region
        self.logger = logger
        self.stack_prefix = stack_prefix
        self.session = boto3.Session(region_name=region)
        self.ssm_client = self.session.client('ssm')
    
    def discover_registered_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Discover agents that are already registered via SSM parameters.
        
        Returns:
            Dictionary of registered agents with their information
        """
        self.logger.info("Discovering registered agents from SSM parameters...")
        
        registered_agents = {}
        
        try:
            # Get all parameters under /{stack_prefix}/agentcore/
            paginator = self.ssm_client.get_paginator('get_parameters_by_path')
            
            for page in paginator.paginate(Path=f'/{self.stack_prefix}/agentcore', Recursive=True):
                for param in page.get('Parameters', []):
                    param_name = param['Name']
                    param_value = param['Value']
                    
                    # Extract agent name from parameter path
                    # Format: /{stack_prefix}/agentcore/{agent_name}/{parameter_name}
                    path_parts = param_name.split('/')
                    if len(path_parts) >= 5:
                        agent_name = path_parts[3]
                        param_type = path_parts[4] if len(path_parts) > 4 else 'unknown'
                        
                        if agent_name not in registered_agents:
                            registered_agents[agent_name] = {
                                'agent_name': agent_name,
                                'parameters': {},
                                'registration_complete': False
                            }
                        
                        # Store parameter value
                        registered_agents[agent_name]['parameters'][param_type] = param_value
                        
                        # Try to parse JSON parameters
                        if param_type in ['connection_info', 'metadata']:
                            try:
                                registered_agents[agent_name]['parameters'][param_type] = json.loads(param_value)
                            except json.JSONDecodeError:
                                pass
            
            # Analyze completeness of registrations
            for agent_name, agent_info in registered_agents.items():
                params = agent_info['parameters']
                required_params = ['agent_arn', 'agent_id', 'region', 'deployment_type']
                
                has_required = all(param in params for param in required_params)
                has_connection_info = 'connection_info' in params
                
                agent_info['registration_complete'] = has_required and has_connection_info
                agent_info['missing_params'] = [p for p in required_params if p not in params]
                
        except ClientError as e:
            self.logger.error(f"Error discovering registered agents: {e}")
        
        return registered_agents
    
    def discover_agentcore_configs(self) -> List[Dict[str, Any]]:
        """
        Discover AgentCore configurations in the project.
        
        Returns:
            List of discovered AgentCore configurations
        """
        self.logger.info("Discovering AgentCore configurations in project...")
        
        configs = []
        project_root = Path(__file__).parent.parent.parent
        
        # Search for .bedrock_agentcore.yaml files
        for config_file in project_root.rglob('.bedrock_agentcore.yaml'):
            try:
                # Read the configuration file
                import yaml
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                config_info = {
                    'config_file': str(config_file),
                    'relative_path': str(config_file.relative_to(project_root)),
                    'directory': str(config_file.parent),
                    'config_data': config_data
                }
                
                # Extract agent information if available
                if isinstance(config_data, dict):
                    if 'agents' in config_data:
                        for agent_name, agent_config in config_data['agents'].items():
                            config_info['agent_name'] = agent_name
                            config_info['agent_config'] = agent_config
                            break
                    elif 'name' in config_data:
                        config_info['agent_name'] = config_data['name']
                
                configs.append(config_info)
                
            except Exception as e:
                self.logger.warning(f"Error reading config file {config_file}: {e}")
                configs.append({
                    'config_file': str(config_file),
                    'relative_path': str(config_file.relative_to(project_root)),
                    'directory': str(config_file.parent),
                    'error': str(e)
                })
        
        return configs
    
    def discover_agent_directories(self) -> List[Dict[str, Any]]:
        """
        Discover potential agent directories in the project.
        
        Returns:
            List of potential agent directories
        """
        self.logger.info("Discovering potential agent directories...")
        
        agent_dirs = []
        project_root = Path(__file__).parent.parent.parent
        
        # Look in common agent directories
        agent_paths = [
            project_root / "agents" / "strands-agents",
            project_root / "agents" / "bedrock-agents"
        ]
        
        for base_path in agent_paths:
            if base_path.exists():
                for item in base_path.iterdir():
                    if item.is_dir():
                        # Check if it looks like an agent directory
                        has_main = (item / "main.py").exists()
                        has_requirements = (item / "requirements.txt").exists()
                        has_config = (item / ".bedrock_agentcore.yaml").exists()
                        has_agent_py = any(item.glob("*agent*.py"))
                        
                        if has_main or has_requirements or has_config or has_agent_py:
                            agent_info = {
                                'directory': str(item),
                                'relative_path': str(item.relative_to(project_root)),
                                'name': item.name,
                                'has_main': has_main,
                                'has_requirements': has_requirements,
                                'has_config': has_config,
                                'has_agent_py': has_agent_py,
                                'likely_agent': has_main and has_requirements
                            }
                            
                            # Try to extract agent type from directory structure
                            if "strands" in str(item):
                                agent_info['suggested_type'] = 'strands_agent'
                            elif "bedrock" in str(item):
                                agent_info['suggested_type'] = 'bedrock_agent'
                            else:
                                agent_info['suggested_type'] = 'custom_agent'
                            
                            agent_dirs.append(agent_info)
        
        return agent_dirs
    
    def analyze_registration_gaps(self, registered_agents: Dict[str, Dict], 
                                agent_dirs: List[Dict]) -> List[Dict[str, Any]]:
        """
        Analyze gaps between discovered agents and registered agents.
        
        Args:
            registered_agents: Dictionary of registered agents
            agent_dirs: List of agent directories
            
        Returns:
            List of agents that may need registration
        """
        self.logger.info("Analyzing registration gaps...")
        
        gaps = []
        
        # Check if agent directories have corresponding registrations
        for agent_dir in agent_dirs:
            agent_name = agent_dir['name']
            
            # Check various possible registration names
            possible_names = [
                agent_name,
                agent_name.replace('-', '_'),
                agent_name.replace('_', '-'),
                agent_name.replace('strands-', ''),
                agent_name.replace('strands_', '')
            ]
            
            is_registered = any(name in registered_agents for name in possible_names)
            
            if not is_registered and agent_dir['likely_agent']:
                gap_info = {
                    'type': 'unregistered_agent_directory',
                    'agent_name': agent_name,
                    'directory': agent_dir['directory'],
                    'relative_path': agent_dir['relative_path'],
                    'suggested_type': agent_dir['suggested_type'],
                    'has_config': agent_dir['has_config'],
                    'registration_command': self._generate_registration_command(agent_dir)
                }
                gaps.append(gap_info)
        
        # Check for incomplete registrations
        for agent_name, agent_info in registered_agents.items():
            if not agent_info['registration_complete']:
                gap_info = {
                    'type': 'incomplete_registration',
                    'agent_name': agent_name,
                    'missing_params': agent_info['missing_params'],
                    'existing_params': list(agent_info['parameters'].keys())
                }
                gaps.append(gap_info)
        
        return gaps
    
    def _generate_registration_command(self, agent_dir: Dict[str, Any]) -> str:
        """Generate a registration command for an agent directory."""
        agent_name = agent_dir['name']
        agent_type = agent_dir['suggested_type']
        source_path = agent_dir['relative_path']
        
        cmd = f"python register_manual_agent.py \\\n"
        cmd += f"  --region {self.region} \\\n"
        cmd += f"  --agent-name {agent_name} \\\n"
        cmd += f"  --agent-arn REPLACE_WITH_ACTUAL_ARN \\\n"
        cmd += f"  --agent-type {agent_type} \\\n"
        cmd += f"  --source-path \"{source_path}\" \\\n"
        cmd += f"  --description \"REPLACE_WITH_DESCRIPTION\""
        
        return cmd
    
    def generate_report(self) -> str:
        """Generate a comprehensive discovery report."""
        self.logger.info("Generating discovery report...")
        
        # Discover all components
        registered_agents = self.discover_registered_agents()
        agentcore_configs = self.discover_agentcore_configs()
        agent_dirs = self.discover_agent_directories()
        gaps = self.analyze_registration_gaps(registered_agents, agent_dirs)
        
        # Generate report
        report = f"""
🔍 Agent Discovery Report
========================
Generated: {datetime.now().isoformat()}
Region: {self.region}

📊 Summary
----------
Registered Agents: {len(registered_agents)}
AgentCore Configs: {len(agentcore_configs)}
Agent Directories: {len(agent_dirs)}
Registration Gaps: {len(gaps)}

"""
        
        # Registered Agents Section
        if registered_agents:
            report += "✅ Registered Agents\n"
            report += "-------------------\n"
            for agent_name, agent_info in registered_agents.items():
                status = "✓ Complete" if agent_info['registration_complete'] else "⚠️ Incomplete"
                report += f"• {agent_name}: {status}\n"
                
                if 'agent_arn' in agent_info['parameters']:
                    report += f"  ARN: {agent_info['parameters']['agent_arn']}\n"
                
                if not agent_info['registration_complete']:
                    report += f"  Missing: {', '.join(agent_info['missing_params'])}\n"
                
                report += "\n"
        else:
            report += "❌ No registered agents found\n\n"
        
        # AgentCore Configurations Section
        if agentcore_configs:
            report += "⚙️ AgentCore Configurations\n"
            report += "---------------------------\n"
            for config in agentcore_configs:
                report += f"• {config['relative_path']}\n"
                if 'agent_name' in config:
                    report += f"  Agent: {config['agent_name']}\n"
                if 'error' in config:
                    report += f"  Error: {config['error']}\n"
                report += "\n"
        
        # Agent Directories Section
        if agent_dirs:
            report += "📁 Agent Directories\n"
            report += "-------------------\n"
            for agent_dir in agent_dirs:
                likely = "✓ Likely Agent" if agent_dir['likely_agent'] else "? Possible Agent"
                report += f"• {agent_dir['relative_path']}: {likely}\n"
                report += f"  Type: {agent_dir['suggested_type']}\n"
                
                features = []
                if agent_dir['has_main']:
                    features.append("main.py")
                if agent_dir['has_requirements']:
                    features.append("requirements.txt")
                if agent_dir['has_config']:
                    features.append("agentcore config")
                if agent_dir['has_agent_py']:
                    features.append("agent script")
                
                if features:
                    report += f"  Features: {', '.join(features)}\n"
                report += "\n"
        
        # Registration Gaps Section
        if gaps:
            report += "⚠️ Registration Gaps\n"
            report += "-------------------\n"
            
            unregistered = [g for g in gaps if g['type'] == 'unregistered_agent_directory']
            incomplete = [g for g in gaps if g['type'] == 'incomplete_registration']
            
            if unregistered:
                report += "Unregistered Agents:\n"
                for gap in unregistered:
                    report += f"• {gap['agent_name']} ({gap['relative_path']})\n"
                    report += f"  Suggested command:\n"
                    for line in gap['registration_command'].split('\n'):
                        report += f"    {line}\n"
                    report += "\n"
            
            if incomplete:
                report += "Incomplete Registrations:\n"
                for gap in incomplete:
                    report += f"• {gap['agent_name']}\n"
                    report += f"  Missing: {', '.join(gap['missing_params'])}\n"
                    report += f"  Has: {', '.join(gap['existing_params'])}\n"
                    report += "\n"
        else:
            report += "✅ No registration gaps found\n\n"
        
        # Recommendations Section
        report += "💡 Recommendations\n"
        report += "-----------------\n"
        
        if not registered_agents:
            report += "• No agents are currently registered with the COA system\n"
            report += "• Consider registering existing agents for chatbot integration\n"
        
        if gaps:
            unregistered_count = len([g for g in gaps if g['type'] == 'unregistered_agent_directory'])
            incomplete_count = len([g for g in gaps if g['type'] == 'incomplete_registration'])
            
            if unregistered_count > 0:
                report += f"• {unregistered_count} agent(s) found that may need registration\n"
                report += "• Use the suggested commands above to register them\n"
            
            if incomplete_count > 0:
                report += f"• {incomplete_count} agent(s) have incomplete registrations\n"
                report += "• Re-run registration with --overwrite to complete them\n"
        else:
            report += "• All discovered agents appear to be properly registered\n"
        
        report += "• Run this discovery script regularly to identify new agents\n"
        report += "• Use 'python register_manual_agent.py --help' for registration help\n"
        
        return report.strip()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Discover manually deployed agents and their registration status",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--region",
        required=True,
        help="AWS region to check for registered agents"
    )
    
    parser.add_argument(
        "--output-file",
        help="Save report to file (optional)"
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
    """Main entry point for the discovery script."""
    try:
        args = parse_arguments()
        
        # Set up logging
        logger = setup_logging(args.log_level)
        
        # Validate AWS credentials
        try:
            sts_client = boto3.client('sts')
            sts_client.get_caller_identity()
        except Exception as e:
            logger.error(f"AWS credentials not configured or invalid: {e}")
            sys.exit(1)
        
        # Run discovery
        discovery = AgentDiscovery(args.region, logger, args.stack_prefix)
        report = discovery.generate_report()
        
        # Output report
        print(report)
        
        # Save to file if requested
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to: {args.output_file}")
        
    except KeyboardInterrupt:
        print("\n❌ Discovery interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()