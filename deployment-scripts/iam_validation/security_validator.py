"""
Security validator for ensuring least privilege and security best practices.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .config import CONFIG, POLICY_NAME_MAPPING, BEDROCK_ASSUME_ROLE_POLICY
from .error_handling import ValidationException

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    """Represents a security issue found during validation."""
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'
    category: str  # 'OVERPRIVILEGED', 'WILDCARD_RESOURCE', 'BROAD_ACTION', etc.
    message: str
    resource_name: Optional[str] = None
    policy_name: Optional[str] = None
    statement_index: Optional[int] = None
    recommendation: Optional[str] = None


@dataclass
class SecurityValidationResult:
    """Result of security validation."""
    passed: bool
    issues: List[SecurityIssue]
    summary: Dict[str, int]  # Count by severity
    
    def __post_init__(self):
        """Calculate summary after initialization."""
        if not self.summary:
            self.summary = {
                'HIGH': len([i for i in self.issues if i.severity == 'HIGH']),
                'MEDIUM': len([i for i in self.issues if i.severity == 'MEDIUM']),
                'LOW': len([i for i in self.issues if i.severity == 'LOW'])
            }


class SecurityValidator:
    """Validates IAM policies and CloudFormation templates for security best practices."""
    
    def __init__(self):
        """Initialize the security validator."""
        # Define dangerous actions that should be avoided
        self.dangerous_actions = {
            '*',  # All actions
            'iam:*',  # All IAM actions
            'sts:AssumeRole',  # Can assume any role (when used with *)
            'ec2:*',  # All EC2 actions
            's3:*',  # All S3 actions
        }
        
        # Define sensitive resources that require specific scoping
        self.sensitive_resource_patterns = [
            r'arn:aws:iam::\*:role/\*',  # All IAM roles
            r'arn:aws:iam::\*:user/\*',  # All IAM users
            r'arn:aws:s3:::\*',  # All S3 buckets
            r'\*',  # Wildcard resource
        ]
        
        # Define expected actions for Bedrock AgentCore
        self.expected_bedrock_actions = {
            'bedrock-agentcore:InvokeAgent',
            'bedrock:InvokeModel',
            'bedrock:InvokeModelWithResponseStream'
        }
        
        # Define expected AWS services for the policies
        self.expected_services = {
            'sts', 'ec2', 's3', 'lambda', 'iam', 'rds', 'cloudformation',
            'cloudwatch', 'logs', 'support', 'ecr', 'bedrock-agentcore', 'bedrock'
        }
    
    def validate_bedrock_agentcore_role(self, template: Dict, role_name: str = None) -> SecurityValidationResult:
        """Validate Bedrock AgentCore IAM role for security best practices.
        
        Args:
            template: CloudFormation template containing the role.
            role_name: Name of the Bedrock AgentCore role to validate.
            
        Returns:
            SecurityValidationResult with validation findings.
        """
        if not role_name:
            role_name = CONFIG['bedrock_role_resource_name']
        
        logger.info(f"Validating security of Bedrock AgentCore role: {role_name}")
        
        issues = []
        
        # Check if role exists
        resources = template.get('Resources', {})
        if role_name not in resources:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_RESOURCE',
                message=f"Bedrock AgentCore role {role_name} not found in template",
                resource_name=role_name,
                recommendation="Ensure the Bedrock AgentCore role is properly added to the template"
            ))
            return SecurityValidationResult(passed=False, issues=issues, summary={})
        
        role_resource = resources[role_name]
        
        # Validate role type
        if role_resource.get('Type') != 'AWS::IAM::Role':
            issues.append(SecurityIssue(
                severity='HIGH',
                category='INVALID_RESOURCE_TYPE',
                message=f"Resource {role_name} is not an IAM role",
                resource_name=role_name,
                recommendation="Ensure the resource type is AWS::IAM::Role"
            ))
            return SecurityValidationResult(passed=False, issues=issues, summary={})
        
        properties = role_resource.get('Properties', {})
        
        # Validate assume role policy
        assume_policy_issues = self._validate_assume_role_policy(
            properties.get('AssumeRolePolicyDocument', {}),
            role_name
        )
        issues.extend(assume_policy_issues)
        
        # Validate inline policies
        policies = properties.get('Policies', [])
        policy_issues = self._validate_bedrock_policies(policies, role_name)
        issues.extend(policy_issues)
        
        # Check for managed policies (should not be used for Bedrock AgentCore)
        managed_policies = properties.get('ManagedPolicyArns', [])
        if managed_policies:
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='MANAGED_POLICIES',
                message=f"Bedrock AgentCore role uses managed policies: {managed_policies}",
                resource_name=role_name,
                recommendation="Use inline policies for better security control"
            ))
        
        # Validate tags
        tag_issues = self._validate_role_tags(properties.get('Tags', []), role_name)
        issues.extend(tag_issues)
        
        # Determine overall pass/fail
        high_severity_count = len([i for i in issues if i.severity == 'HIGH'])
        passed = high_severity_count == 0
        
        logger.info(f"Security validation completed: {len(issues)} issues found")
        return SecurityValidationResult(passed=passed, issues=issues, summary={})
    
    def validate_ecs_permissions(self, template: Dict, ecs_role_name: str) -> SecurityValidationResult:
        """Validate ECS task role permissions for Bedrock AgentCore access.
        
        Args:
            template: CloudFormation template containing the ECS role.
            ecs_role_name: Name of the ECS task role to validate.
            
        Returns:
            SecurityValidationResult with validation findings.
        """
        logger.info(f"Validating ECS role permissions: {ecs_role_name}")
        
        issues = []
        
        # Check if role exists
        resources = template.get('Resources', {})
        if ecs_role_name not in resources:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_RESOURCE',
                message=f"ECS role {ecs_role_name} not found in template",
                resource_name=ecs_role_name
            ))
            return SecurityValidationResult(passed=False, issues=issues, summary={})
        
        role_resource = resources[ecs_role_name]
        properties = role_resource.get('Properties', {})
        policies = properties.get('Policies', [])
        
        # Find Bedrock-related policies
        bedrock_policies = []
        for i, policy in enumerate(policies):
            if self._policy_contains_bedrock_actions(policy):
                bedrock_policies.append((i, policy))
        
        if not bedrock_policies:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_PERMISSION',
                message=f"ECS role {ecs_role_name} missing Bedrock AgentCore invoke permissions",
                resource_name=ecs_role_name,
                recommendation="Add bedrock-agentcore:InvokeAgent permission to ECS task role"
            ))
        else:
            # Validate each Bedrock policy
            for policy_index, policy in bedrock_policies:
                policy_issues = self._validate_ecs_bedrock_policy(
                    policy, ecs_role_name, policy_index
                )
                issues.extend(policy_issues)
        
        # Check for overly broad permissions
        broad_permission_issues = self._check_for_broad_permissions(policies, ecs_role_name)
        issues.extend(broad_permission_issues)
        
        high_severity_count = len([i for i in issues if i.severity == 'HIGH'])
        passed = high_severity_count == 0
        
        return SecurityValidationResult(passed=passed, issues=issues, summary={})
    
    def validate_policy_documents(self, policies: List[Dict]) -> SecurityValidationResult:
        """Validate individual policy documents for security best practices.
        
        Args:
            policies: List of policy documents to validate.
            
        Returns:
            SecurityValidationResult with validation findings.
        """
        logger.info(f"Validating {len(policies)} policy documents")
        
        issues = []
        
        for policy in policies:
            policy_name = policy.get('file_name', 'Unknown')
            policy_doc = policy.get('policy_document', {})
            
            # Validate policy structure
            structure_issues = self._validate_policy_structure(policy_doc, policy_name)
            issues.extend(structure_issues)
            
            # Validate statements
            statements = policy_doc.get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            
            for i, statement in enumerate(statements):
                statement_issues = self._validate_policy_statement(
                    statement, policy_name, i
                )
                issues.extend(statement_issues)
        
        high_severity_count = len([i for i in issues if i.severity == 'HIGH'])
        passed = high_severity_count == 0
        
        return SecurityValidationResult(passed=passed, issues=issues, summary={})
    
    def _validate_assume_role_policy(self, assume_policy: Dict, role_name: str) -> List[SecurityIssue]:
        """Validate assume role policy document."""
        issues = []
        
        if not assume_policy:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_ASSUME_POLICY',
                message=f"Role {role_name} missing assume role policy",
                resource_name=role_name
            ))
            return issues
        
        statements = assume_policy.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        # Check for Bedrock AgentCore service principal
        has_bedrock_principal = False
        for statement in statements:
            principal = statement.get('Principal', {})
            if isinstance(principal, dict):
                service = principal.get('Service', '')
                if 'bedrock-agentcore.amazonaws.com' in str(service):
                    has_bedrock_principal = True
                    break
        
        if not has_bedrock_principal:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='INVALID_PRINCIPAL',
                message=f"Role {role_name} assume policy missing bedrock-agentcore.amazonaws.com principal",
                resource_name=role_name,
                recommendation="Add bedrock-agentcore.amazonaws.com as trusted service"
            ))
        
        # Check for overly broad principals
        for i, statement in enumerate(statements):
            principal = statement.get('Principal', {})
            if principal == '*' or (isinstance(principal, dict) and principal.get('AWS') == '*'):
                issues.append(SecurityIssue(
                    severity='HIGH',
                    category='OVERPRIVILEGED',
                    message=f"Role {role_name} allows assumption by any principal (*)",
                    resource_name=role_name,
                    statement_index=i,
                    recommendation="Restrict principal to specific services or accounts"
                ))
        
        return issues
    
    def _validate_bedrock_policies(self, policies: List[Dict], role_name: str) -> List[SecurityIssue]:
        """Validate Bedrock AgentCore role policies."""
        issues = []
        
        if not policies:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_POLICIES',
                message=f"Bedrock AgentCore role {role_name} has no policies",
                resource_name=role_name
            ))
            return issues
        
        # Check that we have the expected policies
        expected_policy_names = set(POLICY_NAME_MAPPING.values())
        actual_policy_names = {p.get('PolicyName', '') for p in policies}
        
        missing_policies = expected_policy_names - actual_policy_names
        if missing_policies:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_POLICIES',
                message=f"Bedrock AgentCore role missing expected policies: {missing_policies}",
                resource_name=role_name,
                recommendation=f"Add missing policies: {', '.join(missing_policies)}"
            ))
        
        # Validate each policy
        for i, policy in enumerate(policies):
            policy_name = policy.get('PolicyName', f'Policy{i}')
            policy_doc = policy.get('PolicyDocument', {})
            
            policy_issues = self._validate_policy_document_security(
                policy_doc, role_name, policy_name
            )
            issues.extend(policy_issues)
        
        return issues
    
    def _validate_ecs_bedrock_policy(self, policy: Dict, role_name: str, policy_index: int) -> List[SecurityIssue]:
        """Validate ECS Bedrock policy for proper scoping."""
        issues = []
        
        policy_doc = policy.get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        for i, statement in enumerate(statements):
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            
            # Check if this statement has Bedrock actions
            has_bedrock_action = any('bedrock-agentcore' in action for action in actions)
            if not has_bedrock_action:
                continue
            
            # Validate Bedrock actions are properly scoped
            if 'bedrock-agentcore:InvokeAgent' not in actions:
                issues.append(SecurityIssue(
                    severity='MEDIUM',
                    category='MISSING_ACTION',
                    message=f"ECS role {role_name} Bedrock policy missing InvokeAgent action",
                    resource_name=role_name,
                    policy_name=policy.get('PolicyName'),
                    statement_index=i
                ))
            
            # Validate resources are properly scoped
            resources = statement.get('Resource', [])
            if isinstance(resources, str):
                resources = [resources]
            
            has_proper_resource = False
            for resource in resources:
                if 'bedrock-agentcore' in resource and 'runtime' in resource:
                    has_proper_resource = True
                    break
            
            if not has_proper_resource:
                issues.append(SecurityIssue(
                    severity='HIGH',
                    category='IMPROPER_RESOURCE_SCOPE',
                    message=f"ECS role {role_name} Bedrock policy has improper resource scope",
                    resource_name=role_name,
                    policy_name=policy.get('PolicyName'),
                    statement_index=i,
                    recommendation="Scope resource to bedrock-agentcore runtime ARN pattern"
                ))
        
        return issues
    
    def _validate_policy_structure(self, policy_doc: Dict, policy_name: str) -> List[SecurityIssue]:
        """Validate basic policy document structure."""
        issues = []
        
        # Check version
        version = policy_doc.get('Version')
        if version != '2012-10-17':
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='OUTDATED_VERSION',
                message=f"Policy {policy_name} uses outdated version: {version}",
                policy_name=policy_name,
                recommendation="Use version 2012-10-17"
            ))
        
        # Check for statements
        if 'Statement' not in policy_doc:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='MISSING_STATEMENTS',
                message=f"Policy {policy_name} has no statements",
                policy_name=policy_name
            ))
        
        return issues
    
    def _validate_policy_statement(self, statement: Dict, policy_name: str, statement_index: int) -> List[SecurityIssue]:
        """Validate individual policy statement."""
        issues = []
        
        # Check effect
        effect = statement.get('Effect')
        if effect not in ['Allow', 'Deny']:
            issues.append(SecurityIssue(
                severity='HIGH',
                category='INVALID_EFFECT',
                message=f"Policy {policy_name} statement {statement_index} has invalid effect: {effect}",
                policy_name=policy_name,
                statement_index=statement_index
            ))
        
        # Check for dangerous actions
        actions = statement.get('Action', [])
        if isinstance(actions, str):
            actions = [actions]
        
        for action in actions:
            if action in self.dangerous_actions:
                issues.append(SecurityIssue(
                    severity='HIGH',
                    category='DANGEROUS_ACTION',
                    message=f"Policy {policy_name} contains dangerous action: {action}",
                    policy_name=policy_name,
                    statement_index=statement_index,
                    recommendation="Use more specific actions instead of wildcards"
                ))
        
        # Check for wildcard resources
        resources = statement.get('Resource', [])
        if isinstance(resources, str):
            resources = [resources]
        
        for resource in resources:
            if resource == '*':
                # Check if this is acceptable for the specific action
                if not self._is_wildcard_resource_acceptable(actions):
                    issues.append(SecurityIssue(
                        severity='MEDIUM',
                        category='WILDCARD_RESOURCE',
                        message=f"Policy {policy_name} uses wildcard resource with actions: {actions}",
                        policy_name=policy_name,
                        statement_index=statement_index,
                        recommendation="Use specific resource ARNs when possible"
                    ))
        
        return issues
    
    def _validate_policy_document_security(self, policy_doc: Dict, role_name: str, policy_name: str) -> List[SecurityIssue]:
        """Validate policy document for security issues."""
        issues = []
        
        statements = policy_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        # Track all actions and resources
        all_actions = set()
        all_resources = set()
        
        for i, statement in enumerate(statements):
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            
            resources = statement.get('Resource', [])
            if isinstance(resources, str):
                resources = [resources]
            
            all_actions.update(actions)
            all_resources.update(resources)
            
            # Validate statement
            statement_issues = self._validate_policy_statement(statement, policy_name, i)
            issues.extend(statement_issues)
        
        # Check for service scope
        services_used = set()
        for action in all_actions:
            if ':' in action:
                service = action.split(':')[0]
                services_used.add(service)
        
        unexpected_services = services_used - self.expected_services
        if unexpected_services:
            issues.append(SecurityIssue(
                severity='MEDIUM',
                category='UNEXPECTED_SERVICE',
                message=f"Policy {policy_name} uses unexpected services: {unexpected_services}",
                resource_name=role_name,
                policy_name=policy_name,
                recommendation="Verify these services are necessary for Bedrock AgentCore"
            ))
        
        return issues
    
    def _validate_role_tags(self, tags: List[Dict], role_name: str) -> List[SecurityIssue]:
        """Validate role tags for compliance."""
        issues = []
        
        if not tags:
            issues.append(SecurityIssue(
                severity='LOW',
                category='MISSING_TAGS',
                message=f"Role {role_name} has no tags",
                resource_name=role_name,
                recommendation="Add tags for Environment, Component, and Project"
            ))
            return issues
        
        # Check for required tags
        tag_dict = {tag.get('Key'): tag.get('Value') for tag in tags}
        required_tags = ['Environment', 'Component', 'Project']
        
        for required_tag in required_tags:
            if required_tag not in tag_dict:
                issues.append(SecurityIssue(
                    severity='LOW',
                    category='MISSING_TAG',
                    message=f"Role {role_name} missing required tag: {required_tag}",
                    resource_name=role_name,
                    recommendation=f"Add {required_tag} tag"
                ))
        
        # Validate Component tag value for Bedrock role
        if 'Component' in tag_dict and tag_dict['Component'] != 'BedrockAgentCore':
            issues.append(SecurityIssue(
                severity='LOW',
                category='INCORRECT_TAG_VALUE',
                message=f"Role {role_name} Component tag should be 'BedrockAgentCore', got: {tag_dict['Component']}",
                resource_name=role_name
            ))
        
        return issues
    
    def _policy_contains_bedrock_actions(self, policy: Dict) -> bool:
        """Check if policy contains Bedrock-related actions."""
        policy_doc = policy.get('PolicyDocument', {})
        statements = policy_doc.get('Statement', [])
        if not isinstance(statements, list):
            statements = [statements]
        
        for statement in statements:
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]
            
            for action in actions:
                if 'bedrock' in action.lower():
                    return True
        
        return False
    
    def _check_for_broad_permissions(self, policies: List[Dict], role_name: str) -> List[SecurityIssue]:
        """Check for overly broad permissions in policies."""
        issues = []
        
        for policy in policies:
            policy_name = policy.get('PolicyName', 'Unknown')
            policy_doc = policy.get('PolicyDocument', {})
            statements = policy_doc.get('Statement', [])
            if not isinstance(statements, list):
                statements = [statements]
            
            for i, statement in enumerate(statements):
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                
                resources = statement.get('Resource', [])
                if isinstance(resources, str):
                    resources = [resources]
                
                # Check for admin-level permissions
                admin_actions = [a for a in actions if a.endswith(':*') or a == '*']
                if admin_actions and '*' in resources:
                    issues.append(SecurityIssue(
                        severity='HIGH',
                        category='ADMIN_PERMISSIONS',
                        message=f"ECS role {role_name} has admin-level permissions: {admin_actions}",
                        resource_name=role_name,
                        policy_name=policy_name,
                        statement_index=i,
                        recommendation="Use specific actions and resources instead of wildcards"
                    ))
        
        return issues
    
    def _is_wildcard_resource_acceptable(self, actions: List[str]) -> bool:
        """Check if wildcard resource is acceptable for given actions."""
        # Some actions legitimately require wildcard resources
        acceptable_wildcard_actions = {
            'sts:GetCallerIdentity',
            'ec2:Describe*',
            'ec2:List*',
            'iam:List*',
            'iam:Get*',
            's3:ListAllMyBuckets',
            'ecr:GetAuthorizationToken'
        }
        
        for action in actions:
            # Check exact matches
            if action in acceptable_wildcard_actions:
                return True
            
            # Check pattern matches
            for acceptable_action in acceptable_wildcard_actions:
                if acceptable_action.endswith('*'):
                    prefix = acceptable_action[:-1]
                    if action.startswith(prefix):
                        return True
        
        return False
    
    def generate_security_report(self, validation_results: List[SecurityValidationResult]) -> str:
        """Generate a comprehensive security validation report.
        
        Args:
            validation_results: List of validation results to include in report.
            
        Returns:
            Formatted security report string.
        """
        report_lines = []
        
        # Header
        report_lines.append("=" * 60)
        report_lines.append("SECURITY VALIDATION REPORT")
        report_lines.append("=" * 60)
        
        # Overall summary
        total_issues = sum(len(result.issues) for result in validation_results)
        passed_validations = sum(1 for result in validation_results if result.passed)
        
        report_lines.append(f"Validations: {len(validation_results)}")
        report_lines.append(f"Passed: {passed_validations}")
        report_lines.append(f"Failed: {len(validation_results) - passed_validations}")
        report_lines.append(f"Total Issues: {total_issues}")
        report_lines.append("")
        
        # Issue summary by severity
        severity_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for result in validation_results:
            for severity in severity_counts:
                severity_counts[severity] += result.summary.get(severity, 0)
        
        report_lines.append("Issues by Severity:")
        for severity, count in severity_counts.items():
            icon = "🔴" if severity == 'HIGH' else "🟡" if severity == 'MEDIUM' else "🟢"
            report_lines.append(f"  {icon} {severity}: {count}")
        report_lines.append("")
        
        # Detailed issues
        if total_issues > 0:
            report_lines.append("Detailed Issues:")
            report_lines.append("-" * 40)
            
            for i, result in enumerate(validation_results):
                if result.issues:
                    report_lines.append(f"Validation {i + 1}:")
                    
                    for issue in result.issues:
                        icon = "🔴" if issue.severity == 'HIGH' else "🟡" if issue.severity == 'MEDIUM' else "🟢"
                        report_lines.append(f"  {icon} [{issue.severity}] {issue.category}: {issue.message}")
                        
                        if issue.resource_name:
                            report_lines.append(f"      Resource: {issue.resource_name}")
                        if issue.policy_name:
                            report_lines.append(f"      Policy: {issue.policy_name}")
                        if issue.statement_index is not None:
                            report_lines.append(f"      Statement: {issue.statement_index}")
                        if issue.recommendation:
                            report_lines.append(f"      Recommendation: {issue.recommendation}")
                        
                        report_lines.append("")
        else:
            report_lines.append("✅ No security issues found!")
        
        report_lines.append("=" * 60)
        
        return "\n".join(report_lines)