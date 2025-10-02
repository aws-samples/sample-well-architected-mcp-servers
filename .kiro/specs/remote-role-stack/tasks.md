# Implementation Plan

- [x] 1. Set up project structure and core script foundation
  - Create `deployment-scripts/generate_remote_role_stack.py` with main entry point
  - Add command-line argument parsing for role configuration options
  - Set up logging configuration for deployment workflow integration
  - _Requirements: 1.1, 5.1_

- [x] 2. Implement configuration retrieval from Parameter Store
  - Create function to retrieve AgentCore Runtime Role ARN from `/coa/components/wa_security_mcp/agent_arn`
  - Add error handling for missing or invalid parameter store values
  - Implement AWS session management using same region as parent deployment
  - _Requirements: 1.2, 1.4, 5.2_

- [x] 3. Create CloudFormation template generation core
  - Implement `generate_cloudformation_template()` function that creates template dictionary
  - Add CloudFormation template structure with Parameters, Resources, and Outputs sections
  - Create template metadata and description fields
  - _Requirements: 1.1, 4.2_

- [x] 4. Implement IAM role resource generation
  - Create IAM role resource with configurable role name parameter
  - Generate trust policy allowing AgentCore Runtime Role to assume the remote role
  - Add conditional external ID requirement in trust policy when specified
  - _Requirements: 1.3, 3.2, 3.3_

- [x] 5. Add security service permissions to role
  - Create custom inline policy with permissions for GuardDuty, Security Hub, Inspector, Access Analyzer
  - Add Macie and Trusted Advisor permissions to the policy statements
  - Include read-only permissions for AWS resource discovery and configuration
  - _Requirements: 2.1, 2.3_

- [x] 6. Implement managed policy attachments
  - Add SecurityAudit managed policy attachment to the role
  - Support additional managed policies through command-line parameters
  - Validate managed policy ARNs before including in template
  - _Requirements: 2.2, 3.4_

- [x] 7. Create template outputs and metadata
  - Add CloudFormation outputs for role ARN, role name, and external ID
  - Include resource tags for environment, component, and cost tracking
  - Add template description and parameter descriptions
  - _Requirements: 4.1, 4.3_

- [x] 8. Implement YAML template serialization and file output
  - Create function to convert template dictionary to YAML format
  - Implement file saving with timestamp-based naming convention
  - Create output directory structure if it doesn't exist
  - _Requirements: 1.1, 5.3_

- [x] 9. Add command-line interface and parameter validation
  - Implement argument parser for role name, external ID, and additional policies
  - Add input validation for role names, external IDs, and policy ARNs
  - Create help text and usage examples for the script
  - _Requirements: 3.1, 3.4_

- [x] 10. Implement comprehensive error handling
  - Add error handling for AWS API failures and permission issues
  - Create user-friendly error messages with remediation suggestions
  - Handle file system errors and directory creation failures
  - _Requirements: 1.4, 2.4, 5.4_

- [x] 11. Create unit tests for core functionality
  - Write tests for configuration retrieval and parameter store integration
  - Test CloudFormation template generation with various input combinations
  - Add tests for policy validation and error handling scenarios
  - _Requirements: 1.1, 2.2, 3.1_

- [x] 12. Add integration tests and end-to-end validation
  - Create integration tests with mock AWS services
  - Test complete workflow from parameter retrieval to template generation
  - Validate generated templates can be successfully deployed to AWS
  - _Requirements: 5.2, 4.4_