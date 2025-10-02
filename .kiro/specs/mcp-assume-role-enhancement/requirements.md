# Requirements Document

## Introduction

This feature enhances the existing MCP AssumeRole functionality to seamlessly integrate with AWS's native credential chain and IAM roles for services (EC2, ECS, Lambda, etc.). The system will automatically leverage the IAM role of the hosting AWS resource, eliminating the need for manual credential management while providing comprehensive cross-account access capabilities. This approach follows AWS security best practices by using temporary credentials and avoiding credential exposure through environment variables or configuration files.

## Requirements

### Requirement 1

**User Story:** As a security engineer, I want the MCP server to automatically use the IAM role of its hosting AWS resource, so that I can deploy it securely without managing credentials.

#### Acceptance Criteria

1. WHEN the MCP server starts on an EC2 instance THEN the system SHALL automatically use the EC2 instance's IAM role credentials
2. WHEN the MCP server runs in an ECS task THEN the system SHALL automatically use the ECS task's IAM role credentials
3. WHEN the MCP server runs in a Lambda function THEN the system SHALL automatically use the Lambda execution role credentials
4. WHEN no explicit AssumeRole configuration is provided THEN the system SHALL fall back to the AWS default credential chain
5. WHEN the hosting resource has no IAM role THEN the system SHALL provide clear error messages with setup guidance

### Requirement 2

**User Story:** As a DevOps engineer, I want automated setup of cross-account IAM roles that trust the hosting resource's IAM role, so that I can enable secure cross-account access without credential management.

#### Acceptance Criteria

1. WHEN setting up cross-account access THEN the system SHALL generate CloudFormation templates that trust the hosting resource's IAM role
2. WHEN the MCP server is deployed on EC2 THEN the generated trust policies SHALL reference the EC2 instance role ARN
3. WHEN the MCP server is deployed on ECS THEN the generated trust policies SHALL reference the ECS task role ARN
4. WHEN the hosting role ARN changes THEN the system SHALL provide tools to update trust policies in target accounts
5. WHEN deploying to multiple target accounts THEN the system SHALL generate account-specific templates with appropriate role ARNs

### Requirement 3

**User Story:** As a platform architect, I want the MCP server to automatically discover its hosting environment and configure appropriate cross-account access, so that deployment is seamless across different AWS services.

#### Acceptance Criteria

1. WHEN the MCP server starts THEN the system SHALL automatically detect whether it's running on EC2, ECS, Lambda, or other AWS services
2. WHEN running on EC2 THEN the system SHALL retrieve the instance's IAM role ARN using the EC2 metadata service
3. WHEN running on ECS THEN the system SHALL retrieve the task's IAM role ARN using the ECS metadata service
4. WHEN running on Lambda THEN the system SHALL retrieve the execution role ARN from the Lambda context
5. WHEN the hosting environment is detected THEN the system SHALL configure AssumeRole operations to use the appropriate source role

### Requirement 4

**User Story:** As a security administrator, I want validation that the hosting resource's IAM role has the necessary permissions for cross-account operations, so that I can ensure proper access without credential exposure.

#### Acceptance Criteria

1. WHEN the MCP server starts THEN the system SHALL validate that the hosting resource's IAM role has sts:AssumeRole permissions
2. WHEN validating permissions THEN the system SHALL check that the role can assume the configured target roles
3. WHEN permission validation fails THEN the system SHALL provide specific error messages indicating which permissions are missing
4. WHEN the hosting role lacks permissions THEN the system SHALL suggest the minimum required policy statements
5. WHEN validation succeeds THEN the system SHALL log the successful configuration with source and target role details

### Requirement 5

**User Story:** As a developer, I want the MCP server to work seamlessly with AWS's native credential chain, so that I can deploy it anywhere without credential configuration.

#### Acceptance Criteria

1. WHEN no AssumeRole configuration is provided THEN the system SHALL use the default AWS credential chain
2. WHEN AssumeRole is configured THEN the system SHALL use the hosting resource's credentials as the source for assuming target roles
3. WHEN credentials are refreshed THEN the system SHALL automatically handle credential rotation without service interruption
4. WHEN deployed in different environments THEN the system SHALL adapt to the available credential sources (instance profile, task role, etc.)
5. WHEN credential issues occur THEN the system SHALL provide clear diagnostic information about the credential chain and available options

### Requirement 6

**User Story:** As a cloud architect, I want deployment templates that properly configure IAM roles for hosting resources, so that MCP servers can be deployed with appropriate cross-account permissions.

#### Acceptance Criteria

1. WHEN deploying MCP servers on EC2 THEN the system SHALL provide CloudFormation templates with properly configured EC2 instance roles
2. WHEN deploying MCP servers on ECS THEN the system SHALL provide CloudFormation templates with properly configured ECS task roles
3. WHEN deploying MCP servers on Lambda THEN the system SHALL provide CloudFormation templates with properly configured Lambda execution roles
4. WHEN configuring hosting roles THEN the system SHALL include the minimum required permissions for MCP operations and cross-account access
5. WHEN generating deployment templates THEN the system SHALL include example configurations for common cross-account scenarios