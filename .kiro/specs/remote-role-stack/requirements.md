# Requirements Document

## Introduction

The Remote Role Stack feature provides a Python script that generates CloudFormation templates for creating IAM roles in target AWS accounts. These roles are designed to be assumed by the AgentCore Runtime Role, enabling MCP servers to perform cross-account operations. The script is executed after the WA Security MCP deployment to create templates that can be deployed to target accounts.

## Requirements

### Requirement 1

**User Story:** As a platform engineer, I want a Python script that generates CloudFormation templates for remote roles, so that I can deploy assumable roles to target accounts after the AgentCore Runtime is deployed.

#### Acceptance Criteria

1. WHEN the script is executed THEN it SHALL generate a valid CloudFormation template in YAML format
2. WHEN the script runs THEN it SHALL retrieve the AgentCore Runtime Role ARN from the deployed infrastructure
3. WHEN generating the template THEN it SHALL create an IAM role with a trust policy allowing the AgentCore Runtime Role to assume it
4. IF the AgentCore Runtime Role ARN cannot be retrieved THEN the script SHALL provide clear error messages and exit gracefully

### Requirement 2

**User Story:** As a security administrator, I want the generated role to have appropriate permissions for MCP server operations, so that cross-account security analysis and AWS operations can be performed safely.

#### Acceptance Criteria

1. WHEN generating the role THEN the script SHALL include permissions for AWS security services (GuardDuty, Security Hub, Inspector, Access Analyzer)
2. WHEN defining permissions THEN the script SHALL include read-only permissions for AWS resources and configuration
3. WHEN creating policies THEN the script SHALL follow least-privilege principles and include only necessary permissions
4. IF custom permissions are specified THEN the script SHALL validate policy syntax before including them in the template

### Requirement 3

**User Story:** As a DevOps engineer, I want the script to support configurable parameters, so that I can customize the remote role for different target accounts and use cases.

#### Acceptance Criteria

1. WHEN running the script THEN it SHALL accept command-line parameters for role name, external ID, and additional permissions
2. WHEN external ID is provided THEN the script SHALL include it as a condition in the trust policy
3. WHEN additional managed policies are specified THEN the script SHALL attach them to the role
4. IF invalid parameters are provided THEN the script SHALL validate inputs and provide helpful error messages

### Requirement 4

**User Story:** As a cloud architect, I want the generated CloudFormation template to include proper outputs and metadata, so that I can easily reference the created role and track deployments.

#### Acceptance Criteria

1. WHEN generating the template THEN it SHALL include outputs for the role ARN and role name
2. WHEN creating the template THEN it SHALL include descriptive metadata and parameter descriptions
3. WHEN the template is generated THEN it SHALL include tags for resource identification and cost tracking
4. IF the template is deployed THEN it SHALL create resources with consistent naming conventions

### Requirement 5

**User Story:** As a system administrator, I want the script to integrate with the existing deployment workflow, so that it can be executed seamlessly after the WA Security MCP deployment.

#### Acceptance Criteria

1. WHEN the script is executed THEN it SHALL locate and read configuration from the deployed WA Security MCP stack
2. WHEN retrieving stack information THEN it SHALL use the same AWS session and region as the parent deployment
3. WHEN generating templates THEN it SHALL save them to a predictable location for subsequent deployment
4. IF the parent stack is not found THEN the script SHALL provide clear instructions for manual configuration