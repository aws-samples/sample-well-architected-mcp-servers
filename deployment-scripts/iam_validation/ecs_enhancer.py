"""
ECS permission enhancer for adding Bedrock AgentCore invoke permissions.
"""

import logging
from typing import Dict, List, Optional, Any
from copy import deepcopy

from .config import ECS_BEDROCK_PERMISSION
from .error_handling import TemplateException

logger = logging.getLogger(__name__)


class ECSPermissionEnhancer:
    """Enhances ECS task roles with Bedrock AgentCore invoke permissions."""
    
    def __init__(self):
        """Initialize the ECS permission enhancer."""
        pass
    
    def enhance_ecs_task_role(self, template: Dict, role_name: Optional[str] = None) -> Dict:
        """Add Bedrock AgentCore invoke permissions to ECS task role.
        
        Args:
            template: CloudFormation template dictionary.
            role_name: Specific role name to enhance. If None, auto-detect ECS task role.
            
        Returns:
            Updated template with enhanced ECS permissions.
            
        Raises:
            TemplateException: If ECS role cannot be found or enhanced.
        """
        # Create a deep copy to avoid modifying the original
        updated_template = deepcopy(template)
        
        # Find ECS task role if not specified
        if not role_name:
            role_name = self.find_ecs_task_role(updated_template)
            if not role_name:
                raise TemplateException(
                    "Could not find ECS task role in template. "
                    "Please specify role_name parameter or ensure template contains an ECS task role."
                )
        
        logger.info(f"Enhancing ECS task role: {role_name}")
        
        # Validate role exists in template
        if role_name not in updated_template.get('Resources', {}):
            raise TemplateException(f"Role {role_name} not found in template resources")
        
        role_resource = updated_template['Resources'][role_name]
        
        # Validate it's an IAM role
        if role_resource.get('Type') != 'AWS::IAM::Role':
            raise TemplateException(f"Resource {role_name} is not an IAM role")
        
        # Add Bedrock AgentCore permissions
        self._add_bedrock_permissions(role_resource)
        
        logger.info(f"Successfully enhanced ECS task role {role_name} with Bedrock AgentCore permissions")
        return updated_template
    
    def find_ecs_task_role(self, template: Dict) -> Optional[str]:
        """Find ECS task role in CloudFormation template.
        
        Args:
            template: CloudFormation template dictionary.
            
        Returns:
            Name of ECS task role resource, or None if not found.
        """
        resources = template.get('Resources', {})
        
        # Strategy 1: Look for role with ECS tasks service principal
        for resource_name, resource in resources.items():
            if self._is_ecs_task_role_by_service(resource):
                logger.info(f"Found ECS task role by service principal: {resource_name}")
                return resource_name
        
        # Strategy 2: Look for role with ECS-related naming
        for resource_name, resource in resources.items():
            if self._is_ecs_task_role_by_name(resource_name, resource):
                logger.info(f"Found ECS task role by naming convention: {resource_name}")
                return resource_name
        
        # Strategy 3: Look for role with ECS-related policies
        for resource_name, resource in resources.items():
            if self._is_ecs_task_role_by_policies(resource):
                logger.info(f"Found ECS task role by policies: {resource_name}")
                return resource_name
        
        logger.warning("No ECS task role found in template")
        return None
    
    def _is_ecs_task_role_by_service(self, resource: Dict) -> bool:
        """Check if resource is ECS task role by service principal.
        
        Args:
            resource: CloudFormation resource dictionary.
            
        Returns:
            True if resource is ECS task role based on service principal.
        """
        if resource.get('Type') != 'AWS::IAM::Role':
            return False
        
        properties = resource.get('Properties', {})
        assume_policy = properties.get('AssumeRolePolicyDocument', {})
        statements = assume_policy.get('Statement', [])
        
        if not isinstance(statements, list):
            statements = [statements]
        
        for statement in statements:
            principal = statement.get('Principal', {})
            if isinstance(principal, dict):
                service = principal.get('Service', '')
                if isinstance(service, str):
                    if 'ecs-tasks.amazonaws.com' in service:
                        return True
                elif isinstance(service, list):
                    if any('ecs-tasks.amazonaws.com' in s for s in service):
                        return True
        
        return False
    
    def _is_ecs_task_role_by_name(self, resource_name: str, resource: Dict) -> bool:
        """Check if resource is ECS task role by naming convention.
        
        Args:
            resource_name: Name of the resource.
            resource: CloudFormation resource dictionary.
            
        Returns:
            True if resource appears to be ECS task role based on name.
        """
        if resource.get('Type') != 'AWS::IAM::Role':
            return False
        
        name_lower = resource_name.lower()
        
        # Common ECS task role naming patterns
        ecs_patterns = [
            'ecs' in name_lower and 'task' in name_lower,
            'ecstask' in name_lower,
            'task' in name_lower and 'role' in name_lower,
            name_lower.endswith('taskrole'),
            'container' in name_lower and 'task' in name_lower
        ]
        
        return any(ecs_patterns)
    
    def _is_ecs_task_role_by_policies(self, resource: Dict) -> bool:
        """Check if resource is ECS task role by examining policies.
        
        Args:
            resource: CloudFormation resource dictionary.
            
        Returns:
            True if resource appears to be ECS task role based on policies.
        """
        if resource.get('Type') != 'AWS::IAM::Role':
            return False
        
        properties = resource.get('Properties', {})
        
        # Check managed policy ARNs
        managed_policies = properties.get('ManagedPolicyArns', [])
        for policy_arn in managed_policies:
            if 'ECSTaskRolePolicy' in policy_arn or 'ecs-tasks' in policy_arn.lower():
                return True
        
        # Check inline policies
        policies = properties.get('Policies', [])
        for policy in policies:
            policy_doc = policy.get('PolicyDocument', {})
            statements = policy_doc.get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            
            for statement in statements:
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                
                # Look for ECS-related actions
                for action in actions:
                    if any(service in action.lower() for service in ['ecs:', 'ecr:', 'logs:']):
                        return True
        
        return False
    
    def _add_bedrock_permissions(self, role_resource: Dict) -> None:
        """Add Bedrock AgentCore permissions to IAM role resource.
        
        Args:
            role_resource: IAM role resource dictionary to modify.
        """
        properties = role_resource.get('Properties', {})
        
        # Ensure Policies section exists
        if 'Policies' not in properties:
            properties['Policies'] = []
        
        policies = properties['Policies']
        
        # Check if Bedrock permission already exists
        existing_policy = self._find_bedrock_policy(policies)
        
        if existing_policy:
            logger.info("Bedrock AgentCore permission already exists, updating...")
            self._update_bedrock_policy(existing_policy)
        else:
            logger.info("Adding new Bedrock AgentCore permission policy...")
            self._create_bedrock_policy(policies)
    
    def _find_bedrock_policy(self, policies: List[Dict]) -> Optional[Dict]:
        """Find existing Bedrock policy in role policies.
        
        Args:
            policies: List of policy dictionaries.
            
        Returns:
            Bedrock policy dictionary if found, None otherwise.
        """
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
    
    def _update_bedrock_policy(self, policy: Dict) -> None:
        """Update existing Bedrock policy to ensure correct permissions.
        
        Args:
            policy: Existing policy dictionary to update.
        """
        policy_doc = policy.get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        # Find and update Bedrock statement
        bedrock_statement_found = False
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            
            if 'bedrock-agentcore:InvokeAgent' in actions:
                bedrock_statement_found = True
                # Ensure correct resource pattern
                resources = statement.get('Resource', [])
                if isinstance(resources, str):
                    resources = [resources]
                
                expected_resource = ECS_BEDROCK_PERMISSION['Resource'][0]
                if expected_resource not in resources:
                    resources.append(expected_resource)
                    statement['Resource'] = resources
                    logger.info("Updated Bedrock policy resource pattern")
                break
        
        # Add the statement if it doesn't exist
        if not bedrock_statement_found:
            statements.append(ECS_BEDROCK_PERMISSION)
            policy_doc['Statement'] = statements
            logger.info("Added Bedrock AgentCore invoke statement to existing policy")
    
    def _create_bedrock_policy(self, policies: List[Dict]) -> None:
        """Create new Bedrock policy and add to policies list.
        
        Args:
            policies: List of policies to append new Bedrock policy to.
        """
        bedrock_policy = {
            'PolicyName': 'BedrockAgentCoreInvokePolicy',
            'PolicyDocument': {
                'Version': '2012-10-17',
                'Statement': [ECS_BEDROCK_PERMISSION]
            }
        }
        
        policies.append(bedrock_policy)
        logger.info("Created new Bedrock AgentCore invoke policy")
    
    def validate_bedrock_permissions(self, template: Dict, role_name: str) -> Dict:
        """Validate that Bedrock permissions are correctly configured.
        
        Args:
            template: CloudFormation template dictionary.
            role_name: Name of the role to validate.
            
        Returns:
            Validation result dictionary.
        """
        validation_result = {
            'valid': False,
            'has_bedrock_permission': False,
            'has_correct_action': False,
            'has_correct_resource': False,
            'issues': []
        }
        
        # Check if role exists
        if role_name not in template.get('Resources', {}):
            validation_result['issues'].append(f"Role {role_name} not found in template")
            return validation_result
        
        role_resource = template['Resources'][role_name]
        
        # Check if it's an IAM role
        if role_resource.get('Type') != 'AWS::IAM::Role':
            validation_result['issues'].append(f"Resource {role_name} is not an IAM role")
            return validation_result
        
        # Check policies
        properties = role_resource.get('Properties', {})
        policies = properties.get('Policies', [])
        
        for policy in policies:
            policy_doc = policy.get('PolicyDocument', {})
            statements = policy_doc.get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            
            for statement in statements:
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                
                # Check for Bedrock AgentCore action
                if 'bedrock-agentcore:InvokeAgent' in actions:
                    validation_result['has_bedrock_permission'] = True
                    validation_result['has_correct_action'] = True
                    
                    # Check resource pattern
                    resources = statement.get('Resource', [])
                    if isinstance(resources, str):
                        resources = [resources]
                    
                    expected_resource = ECS_BEDROCK_PERMISSION['Resource'][0]
                    if expected_resource in resources:
                        validation_result['has_correct_resource'] = True
                    else:
                        validation_result['issues'].append(
                            f"Bedrock permission has incorrect resource pattern. "
                            f"Expected: {expected_resource}"
                        )
        
        if not validation_result['has_bedrock_permission']:
            validation_result['issues'].append("No Bedrock AgentCore invoke permission found")
        
        validation_result['valid'] = (
            validation_result['has_bedrock_permission'] and
            validation_result['has_correct_action'] and
            validation_result['has_correct_resource']
        )
        
        return validation_result
    
    def get_enhancement_summary(self, original_template: Dict, enhanced_template: Dict, role_name: str) -> Dict:
        """Get summary of ECS permission enhancements made.
        
        Args:
            original_template: Original CloudFormation template.
            enhanced_template: Enhanced CloudFormation template.
            role_name: Name of the enhanced role.
            
        Returns:
            Summary dictionary of changes made.
        """
        summary = {
            'role_name': role_name,
            'enhancement_applied': False,
            'policies_added': 0,
            'statements_added': 0,
            'existing_bedrock_policy_updated': False,
            'new_bedrock_policy_created': False
        }
        
        # Get original and enhanced role resources
        original_role = original_template.get('Resources', {}).get(role_name, {})
        enhanced_role = enhanced_template.get('Resources', {}).get(role_name, {})
        
        if not original_role or not enhanced_role:
            return summary
        
        # Compare policies
        original_policies = original_role.get('Properties', {}).get('Policies', [])
        enhanced_policies = enhanced_role.get('Properties', {}).get('Policies', [])
        
        summary['policies_added'] = len(enhanced_policies) - len(original_policies)
        
        # Check if Bedrock policy was added or updated
        original_bedrock_policy = self._find_bedrock_policy(original_policies)
        enhanced_bedrock_policy = self._find_bedrock_policy(enhanced_policies)
        
        if not original_bedrock_policy and enhanced_bedrock_policy:
            summary['new_bedrock_policy_created'] = True
            summary['enhancement_applied'] = True
        elif original_bedrock_policy and enhanced_bedrock_policy:
            # Compare policy content to see if it was updated
            if original_bedrock_policy != enhanced_bedrock_policy:
                summary['existing_bedrock_policy_updated'] = True
                summary['enhancement_applied'] = True
        
        # Count statements added
        original_statements = 0
        enhanced_statements = 0
        
        for policy in original_policies:
            statements = policy.get('PolicyDocument', {}).get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            original_statements += len(statements)
        
        for policy in enhanced_policies:
            statements = policy.get('PolicyDocument', {}).get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            enhanced_statements += len(statements)
        
        summary['statements_added'] = enhanced_statements - original_statements
        
        return summary