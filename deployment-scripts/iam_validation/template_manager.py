"""
CloudFormation template manager for updating templates with Bedrock AgentCore resources.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from copy import deepcopy


def load_cloudformation_yaml(file_path):
    """Load CloudFormation YAML file with proper handling of intrinsic functions."""
    import re
    
    # Read the file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace CloudFormation intrinsic functions with standard YAML
    # This is a simple approach that converts !Ref to a string format
    content = re.sub(r'!Ref\s+([\w:]+)', r'"CF_REF_\1"', content)
    content = re.sub(r'!Sub\s+(\'[^\']*\')', r'"CF_SUB_\1"', content)
    content = re.sub(r'!Sub\s+("([^"]*)")', r'"CF_SUB_\1"', content)
    content = re.sub(r'!Sub\s+([^\s\'"]+)', r'"CF_SUB_\1"', content)
    content = re.sub(r'!GetAtt\s+([^\s]+)', r'"CF_GETATT_\1"', content)
    content = re.sub(r'!Join\s*\[', r'"CF_JOIN" [', content)
    content = re.sub(r'!Split\s*\[', r'"CF_SPLIT" [', content)
    content = re.sub(r'!Select\s*\[', r'"CF_SELECT" [', content)
    content = re.sub(r'!Base64\s+([^\s]+)', r'"CF_BASE64_\1"', content)
    content = re.sub(r'!If\s*\[', r'"CF_IF" [', content)
    content = re.sub(r'!Not\s*\[', r'"CF_NOT" [', content)
    content = re.sub(r'!Equals\s*\[', r'"CF_EQUALS" [', content)
    content = re.sub(r'!And\s*\[', r'"CF_AND" [', content)
    content = re.sub(r'!Or\s*\[', r'"CF_OR" [', content)
    content = re.sub(r'!FindInMap\s*\[', r'"CF_FINDINMAP" [', content)
    content = re.sub(r'!ImportValue\s+([^\s]+)', r'"CF_IMPORTVALUE_\1"', content)
    
    # Load the modified YAML
    template = yaml.safe_load(content)
    
    # Debug: Check what we loaded
    print(f"DEBUG: Loaded template type: {type(template)}")
    if hasattr(template, 'keys'):
        print(f"DEBUG: Template keys: {list(template.keys())}")
    
    # Post-process to convert string representations back to proper format
    def process_value(obj):
        if isinstance(obj, dict):
            return {k: process_value(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [process_value(item) for item in obj]
        elif isinstance(obj, str):
            if obj.startswith('CF_REF_'):
                return {'Ref': obj[7:]}
            elif obj.startswith('CF_SUB_'):
                value = obj[7:]
                # Remove quotes if present
                if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
                    value = value[1:-1]
                return {'Fn::Sub': value}
            elif obj.startswith('CF_GETATT_'):
                parts = obj[10:].split('.')
                return {'Fn::GetAtt': parts}
            elif obj.startswith('CF_BASE64_'):
                return {'Fn::Base64': obj[10:]}
            elif obj.startswith('CF_IMPORTVALUE_'):
                return {'Fn::ImportValue': obj[15:]}
            elif obj == 'CF_JOIN':
                return 'Fn::Join'
            elif obj == 'CF_SPLIT':
                return 'Fn::Split'
            elif obj == 'CF_SELECT':
                return 'Fn::Select'
            elif obj == 'CF_IF':
                return 'Fn::If'
            elif obj == 'CF_NOT':
                return 'Fn::Not'
            elif obj == 'CF_EQUALS':
                return 'Fn::Equals'
            elif obj == 'CF_AND':
                return 'Fn::And'
            elif obj == 'CF_OR':
                return 'Fn::Or'
            elif obj == 'CF_FINDINMAP':
                return 'Fn::FindInMap'
        return obj
    
    return process_value(template)

from .config import CONFIG, POLICY_NAME_MAPPING, BEDROCK_ASSUME_ROLE_POLICY, ECS_BEDROCK_PERMISSION
from .data_models import UpdateResult
from .error_handling import ErrorHandler, TemplateException
from .policy_processor import PolicyDocumentProcessor

logger = logging.getLogger(__name__)


class CloudFormationTemplateManager:
    """Manages CloudFormation template loading, modification, and saving."""
    
    def __init__(self, input_template_path: Optional[str] = None, output_template_path: Optional[str] = None):
        """Initialize the template manager.
        
        Args:
            input_template_path: Path to input CloudFormation template.
            output_template_path: Path for output CloudFormation template.
        """
        self.input_template_path = Path(input_template_path or CONFIG['template_input'])
        self.output_template_path = Path(output_template_path or CONFIG['template_output'])
        self.policy_processor = PolicyDocumentProcessor()
        
    def load_template(self, file_path: Optional[str] = None) -> Dict:
        """Load and parse CloudFormation template from YAML file.
        
        Args:
            file_path: Path to template file. Defaults to input_template_path.
            
        Returns:
            Parsed CloudFormation template as dictionary.
            
        Raises:
            TemplateException: If template cannot be loaded or parsed.
        """
        template_path = Path(file_path) if file_path else self.input_template_path
        
        if not template_path.exists():
            raise TemplateException(
                f"Template file not found: {template_path}",
                template_path=str(template_path)
            )
        
        try:
            template = load_cloudformation_yaml(template_path)
            
            # Debug: Check what type we got
            logger.debug(f"Loaded template type: {type(template)}")
            logger.debug(f"Template keys: {list(template.keys()) if hasattr(template, 'keys') else 'No keys method'}")
            
            # Validate basic CloudFormation structure
            if not isinstance(template, dict):
                raise TemplateException(
                    f"Template must be a YAML object, got {type(template)}",
                    template_path=str(template_path)
                )
            
            required_sections = ['AWSTemplateFormatVersion', 'Resources']
            for section in required_sections:
                if section not in template:
                    raise TemplateException(
                        f"Template missing required section: {section}",
                        template_path=str(template_path)
                    )
            
            logger.info(f"Successfully loaded template: {template_path}")
            logger.info(f"Template contains {len(template.get('Resources', {}))} resources")
            
            return template
            
        except yaml.YAMLError as e:
            raise TemplateException(
                f"Invalid YAML syntax in template: {str(e)}",
                template_path=str(template_path),
                line_number=getattr(e, 'problem_mark', {}).get('line')
            )
        except Exception as e:
            raise TemplateException(
                f"Failed to load template: {str(e)}",
                template_path=str(template_path)
            )
    
    def add_bedrock_agentcore_role(self, template: Dict) -> Dict:
        """Add Bedrock AgentCore IAM role to CloudFormation template.
        
        Args:
            template: CloudFormation template dictionary.
            
        Returns:
            Updated template with new Bedrock AgentCore role.
            
        Raises:
            TemplateException: If role cannot be added to template.
        """
        # Create a deep copy to avoid modifying the original
        updated_template = deepcopy(template)
        
        try:
            # Load policy documents
            policies = self.policy_processor.load_policy_files()
            logger.info(f"Loaded {len(policies)} policies for Bedrock AgentCore role")
            
            # Convert policies to CloudFormation inline policy format
            inline_policies = []
            for policy in policies:
                inline_policy = self.policy_processor.convert_to_inline_policy(
                    policy, 
                    policy['cloudformation_name']
                )
                inline_policies.append(inline_policy)
            
            # Create the Bedrock AgentCore role resource
            bedrock_role = {
                'Type': 'AWS::IAM::Role',
                'Properties': {
                    'RoleName': '!Sub \'${AWS::StackName}-bedrock-agentcore-runtime-role\'',
                    'AssumeRolePolicyDocument': BEDROCK_ASSUME_ROLE_POLICY,
                    'Policies': inline_policies,
                    'Tags': [
                        {
                            'Key': 'Environment',
                            'Value': '!Ref Environment'
                        },
                        {
                            'Key': 'Component',
                            'Value': 'BedrockAgentCore'
                        },
                        {
                            'Key': 'Project',
                            'Value': 'CloudOptimization'
                        }
                    ]
                }
            }
            
            # Add role to template resources
            resource_name = CONFIG['bedrock_role_resource_name']
            updated_template['Resources'][resource_name] = bedrock_role
            
            logger.info(f"Added Bedrock AgentCore role: {resource_name}")
            
            return updated_template
            
        except Exception as e:
            raise TemplateException(
                f"Failed to add Bedrock AgentCore role: {str(e)}",
                template_path=str(self.input_template_path)
            )
    
    def update_ecs_permissions(self, template: Dict) -> Dict:
        """Update ECS task role with Bedrock AgentCore invoke permissions.
        
        Args:
            template: CloudFormation template dictionary.
            
        Returns:
            Updated template with enhanced ECS permissions.
            
        Raises:
            TemplateException: If ECS role cannot be found or updated.
        """
        # Create a deep copy to avoid modifying the original
        updated_template = deepcopy(template)
        
        try:
            # Find ECS task role in template
            ecs_role_name = self._find_ecs_task_role(updated_template)
            if not ecs_role_name:
                raise TemplateException(
                    "Could not find ECS task role in template",
                    template_path=str(self.input_template_path)
                )
            
            logger.info(f"Found ECS task role: {ecs_role_name}")
            
            # Get the ECS role resource
            ecs_role = updated_template['Resources'][ecs_role_name]
            
            # Ensure Policies section exists
            if 'Policies' not in ecs_role['Properties']:
                ecs_role['Properties']['Policies'] = []
            
            # Check if Bedrock permission already exists
            existing_policy = self._find_bedrock_policy_in_role(ecs_role)
            
            if existing_policy:
                logger.info("Bedrock AgentCore permission already exists in ECS role")
                # Update existing policy to ensure it has the correct permissions
                self._update_existing_bedrock_policy(existing_policy)
            else:
                # Add new policy for Bedrock AgentCore permissions
                bedrock_policy = {
                    'PolicyName': 'BedrockAgentCoreInvokePolicy',
                    'PolicyDocument': {
                        'Version': '2012-10-17',
                        'Statement': [ECS_BEDROCK_PERMISSION]
                    }
                }
                
                ecs_role['Properties']['Policies'].append(bedrock_policy)
                logger.info("Added Bedrock AgentCore invoke permission to ECS task role")
            
            return updated_template
            
        except Exception as e:
            if isinstance(e, TemplateException):
                raise
            raise TemplateException(
                f"Failed to update ECS permissions: {str(e)}",
                template_path=str(self.input_template_path)
            )
    
    def save_template(self, template: Dict, output_path: Optional[str] = None) -> bool:
        """Save CloudFormation template to YAML file.
        
        Args:
            template: CloudFormation template dictionary.
            output_path: Path for output file. Defaults to output_template_path.
            
        Returns:
            True if template was saved successfully.
            
        Raises:
            TemplateException: If template cannot be saved.
        """
        save_path = Path(output_path) if output_path else self.output_template_path
        
        try:
            # Ensure output directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Configure YAML output formatting
            yaml.add_representer(type(None), lambda dumper, value: dumper.represent_scalar('tag:yaml.org,2002:null', ''))
            
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    template,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                    width=120,
                    allow_unicode=True
                )
            
            logger.info(f"Successfully saved template: {save_path}")
            return True
            
        except Exception as e:
            raise TemplateException(
                f"Failed to save template: {str(e)}",
                template_path=str(save_path)
            )
    
    def _find_ecs_task_role(self, template: Dict) -> Optional[str]:
        """Find ECS task role in CloudFormation template.
        
        Args:
            template: CloudFormation template dictionary.
            
        Returns:
            Name of ECS task role resource, or None if not found.
        """
        resources = template.get('Resources', {})
        
        # Look for role with ECS task role characteristics
        for resource_name, resource in resources.items():
            if resource.get('Type') == 'AWS::IAM::Role':
                properties = resource.get('Properties', {})
                assume_policy = properties.get('AssumeRolePolicyDocument', {})
                
                # Check if role can be assumed by ECS tasks
                statements = assume_policy.get('Statement', [])
                if not isinstance(statements, list):
                    statements = [statements]
                
                for statement in statements:
                    principal = statement.get('Principal', {})
                    if isinstance(principal, dict):
                        service = principal.get('Service', '')
                        if 'ecs-tasks.amazonaws.com' in service:
                            return resource_name
                
                # Also check by naming convention
                if 'ecs' in resource_name.lower() and 'task' in resource_name.lower():
                    return resource_name
        
        return None
    
    def _find_bedrock_policy_in_role(self, role_resource: Dict) -> Optional[Dict]:
        """Find existing Bedrock policy in IAM role.
        
        Args:
            role_resource: IAM role resource dictionary.
            
        Returns:
            Bedrock policy dictionary if found, None otherwise.
        """
        policies = role_resource.get('Properties', {}).get('Policies', [])
        
        for policy in policies:
            policy_doc = policy.get('PolicyDocument', {})
            statements = policy_doc.get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            
            for statement in statements:
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                
                # Check if any action is related to bedrock-agentcore
                for action in actions:
                    if 'bedrock-agentcore' in action:
                        return policy
        
        return None
    
    def _update_existing_bedrock_policy(self, policy: Dict) -> None:
        """Update existing Bedrock policy to ensure correct permissions.
        
        Args:
            policy: Existing policy dictionary to update.
        """
        policy_doc = policy.get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        # Check if the correct permission already exists
        bedrock_statement_exists = False
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            
            if 'bedrock-agentcore:InvokeAgent' in actions:
                bedrock_statement_exists = True
                # Update resource if needed
                resources = statement.get('Resource', [])
                if isinstance(resources, str):
                    resources = [resources]
                
                expected_resource = ECS_BEDROCK_PERMISSION['Resource'][0]
                if expected_resource not in resources:
                    resources.append(expected_resource)
                    statement['Resource'] = resources
                break
        
        # Add the statement if it doesn't exist
        if not bedrock_statement_exists:
            statements.append(ECS_BEDROCK_PERMISSION)
            policy_doc['Statement'] = statements
    
    def get_template_summary(self, template: Dict) -> Dict:
        """Get summary information about CloudFormation template.
        
        Args:
            template: CloudFormation template dictionary.
            
        Returns:
            Summary dictionary with template statistics.
        """
        resources = template.get('Resources', {})
        parameters = template.get('Parameters', {})
        outputs = template.get('Outputs', {})
        
        # Count resources by type
        resource_types = {}
        for resource in resources.values():
            resource_type = resource.get('Type', 'Unknown')
            resource_types[resource_type] = resource_types.get(resource_type, 0) + 1
        
        # Find IAM roles
        iam_roles = []
        for name, resource in resources.items():
            if resource.get('Type') == 'AWS::IAM::Role':
                iam_roles.append(name)
        
        return {
            'total_resources': len(resources),
            'total_parameters': len(parameters),
            'total_outputs': len(outputs),
            'resource_types': resource_types,
            'iam_roles': iam_roles,
            'template_version': template.get('AWSTemplateFormatVersion'),
            'description': template.get('Description', 'No description')
        }
    
    def validate_template_structure(self, template: Dict) -> List[str]:
        """Validate CloudFormation template structure and return any issues.
        
        Args:
            template: CloudFormation template dictionary.
            
        Returns:
            List of validation issues (empty if valid).
        """
        issues = []
        
        # Check required top-level sections
        if 'AWSTemplateFormatVersion' not in template:
            issues.append("Missing AWSTemplateFormatVersion")
        
        if 'Resources' not in template:
            issues.append("Missing Resources section")
        elif not isinstance(template['Resources'], dict):
            issues.append("Resources section must be an object")
        elif len(template['Resources']) == 0:
            issues.append("Resources section is empty")
        
        # Validate resource structure
        resources = template.get('Resources', {})
        for resource_name, resource in resources.items():
            if not isinstance(resource, dict):
                issues.append(f"Resource {resource_name} must be an object")
                continue
            
            if 'Type' not in resource:
                issues.append(f"Resource {resource_name} missing Type")
            
            if resource.get('Type') == 'AWS::IAM::Role':
                if 'Properties' not in resource:
                    issues.append(f"IAM Role {resource_name} missing Properties")
                else:
                    properties = resource['Properties']
                    if 'AssumeRolePolicyDocument' not in properties:
                        issues.append(f"IAM Role {resource_name} missing AssumeRolePolicyDocument")
        
        return issues