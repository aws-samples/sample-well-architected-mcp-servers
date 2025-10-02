# Implementation Plan

- [x] 1. Set up project structure and core data models
  - Create directory structure for IAM validation components
  - Define data classes for ValidationResult, UpdateResult, and IntegrationResult
  - Create configuration constants and error handling base classes
  - _Requirements: 1.1, 4.1, 4.2_

- [x] 2. Implement policy document processor
  - Create PolicyDocumentProcessor class to load JSON policy files from directory
  - Implement policy syntax validation using boto3 IAM policy validation
  - Add method to convert policy documents to CloudFormation inline policy format
  - Write unit tests for policy loading and validation functionality
  - _Requirements: 2.2, 4.4, 5.1_

- [x] 3. Implement IAM role validator core functionality
  - Create IAMRoleValidator class with temporary role creation method
  - Implement policy attachment logic with error handling for each policy file
  - Add comprehensive cleanup method that handles partial failures
  - Write unit tests with mocked AWS IAM API responses
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.3_

- [x] 4. Implement CloudFormation template manager
  - Create CloudFormationTemplateManager class to parse YAML templates
  - Implement method to add new Bedrock AgentCore IAM role resource to template
  - Add functionality to locate and update existing ECS task role with new permissions
  - Write unit tests for template parsing and modification operations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.4_

- [x] 5. Implement ECS permission enhancement logic
  - Create method to find existing ECS task role in CloudFormation template
  - Implement logic to add bedrock-agentcore:InvokeAgent permission to ECS task role
  - Ensure new permission uses account-specific ARN pattern with wildcard for runtimes
  - Write unit tests to verify permission addition without affecting existing permissions
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Create main orchestrator with error handling
  - Implement BedrockAgentCoreIntegrator class to coordinate validation and update phases
  - Add comprehensive error handling for AWS API errors, file system errors, and validation errors
  - Implement cleanup-on-failure logic that ensures temporary resources are removed
  - Create detailed logging and summary reporting functionality
  - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [x] 7. Implement security validation and least privilege checks
  - Add validation to ensure Bedrock AgentCore role only includes specified policies
  - Implement checks for account-specific and region-specific ARN patterns
  - Add validation to ensure ECS permissions are scoped to bedrock-agentcore service only
  - Create security audit functionality to verify no overly broad permissions
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 8. Create comprehensive test suite
  - Write integration tests that validate complete end-to-end workflow
  - Create test fixtures with sample CloudFormation templates and policy files
  - Implement mock AWS responses for various success and failure scenarios
  - Add tests for error handling and cleanup behavior
  - _Requirements: 1.5, 4.3, 4.5_

- [x] 9. Create command-line interface and main execution script
  - Implement CLI script that accepts configuration parameters and executes validation
  - Add command-line options for dry-run mode and verbose logging
  - Create main execution function that orchestrates the entire process
  - Add progress reporting and user-friendly output formatting
  - _Requirements: 1.5, 4.5_

- [x] 10. Integrate with existing deployment infrastructure
  - Update deployment scripts to optionally run IAM validation before template deployment
  - Add the new CloudFormation template version to deployment script options
  - Create documentation for using the new IAM validation and template update functionality
  - Test integration with existing deploy-coa.sh script
  - _Requirements: 2.6, 3.5_