# Implementation Plan

- [ ] 1. Enhance environment detection capabilities in credential utilities
  - Create environment detection service that identifies EC2, ECS, EKS, Lambda, Bedrock AgentCore Runtime, Fargate, and local environments
  - Implement metadata service clients for retrieving IAM role information from all AWS compute services
  - Add comprehensive error handling for metadata service failures and missing IAM roles across different compute platforms
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 1.1 Create environment detection data models and interfaces
  - Write EnvironmentInfo dataclass with comprehensive environment types (ec2, ecs, eks, lambda, bedrock-agentcore, fargate, local)
  - Add environment-specific metadata fields for Kubernetes service accounts, Bedrock runtime contexts, and container orchestration details
  - Create ValidationResult dataclass for consistent error reporting across validation functions
  - Implement RoleConfiguration dataclass for managing cross-account role settings
  - Write unit tests for data model validation and serialization covering all compute service types
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 1.2 Implement metadata service clients for AWS environments
  - Create EC2MetadataClient class to retrieve instance profile and role information
  - Implement ECSMetadataClient class to get task role ARN from ECS metadata endpoint
  - Add EKSMetadataClient class to handle Kubernetes service account token projection and IRSA (IAM Roles for Service Accounts)
  - Create LambdaContextClient class to extract execution role from Lambda context
  - Implement BedrockAgentCoreClient class to retrieve runtime role from Bedrock AgentCore environment
  - Add FargateMetadataClient class for Fargate-specific metadata service endpoints
  - Write comprehensive unit tests with mocked metadata service responses for all compute services
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 1.3 Build environment detection service with automatic discovery
  - Implement EnvironmentDetector class that automatically identifies hosting environment across all AWS compute services
  - Add logic to detect EC2 by checking for instance metadata service availability
  - Implement ECS detection using task metadata endpoint and ECS_CONTAINER_METADATA_URI environment variables
  - Create EKS detection using Kubernetes service account token files and AWS_ROLE_ARN environment variable
  - Add Lambda detection using AWS_LAMBDA_FUNCTION_NAME and AWS_EXECUTION_ENV environment variables
  - Implement Bedrock AgentCore Runtime detection using BEDROCK_AGENTCORE_RUNTIME_ID and runtime-specific environment variables
  - Create Fargate detection by checking for Fargate-specific metadata endpoints and environment markers
  - Add fallback detection logic with priority ordering for environments that share similar characteristics
  - Write unit tests covering all environment detection scenarios, edge cases, and environment precedence rules
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Extend existing credential chain to leverage hosting environment roles
  - Modify create_aws_session() function to automatically detect and use hosting environment credentials
  - Add fallback logic to maintain compatibility with existing AssumeRole environment variables
  - Implement credential validation to ensure hosting role has necessary permissions
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [ ] 2.1 Enhance create_aws_session() with environment-aware credential selection
  - Modify existing create_aws_session() function to detect hosting environment first across all compute services
  - Add logic to use hosting environment credentials (EC2 instance profiles, ECS task roles, EKS IRSA, Lambda execution roles, Bedrock AgentCore runtime roles)
  - Implement special handling for Kubernetes environments with service account token projection
  - Add support for Bedrock AgentCore Runtime credential chain and runtime-specific authentication
  - Maintain backward compatibility with existing AWS_ASSUME_ROLE_ARN environment variable
  - Implement comprehensive logging for credential source selection and validation across all environments
  - Write unit tests covering all credential selection scenarios, compute service types, and fallback logic
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 2.2 Add hosting role validation and permission checking
  - Create validate_hosting_role_permissions() function to check sts:AssumeRole permissions
  - Implement get_hosting_role_arn() function that retrieves role ARN from detected environment
  - Add validate_cross_account_access() function to test actual role assumption
  - Create comprehensive error messages with specific remediation guidance for permission issues
  - Write unit tests with mocked STS calls and permission validation scenarios
  - _Requirements: 2.2, 2.3, 2.4, 2.5_

- [ ] 2.3 Implement enhanced session management with automatic refresh
  - Add session caching to avoid repeated metadata service calls during MCP server operation
  - Implement credential refresh logic that handles temporary credential expiration
  - Create session validation that checks credential validity before use
  - Add monitoring and logging for credential refresh operations and failures
  - Write unit tests for session lifecycle management and refresh scenarios
  - _Requirements: 2.1, 2.2, 2.3, 2.5_

- [ ] 3. Create cross-account role management and template generation
  - Build CloudFormation template generators for hosting environment IAM roles
  - Implement cross-account role template generation with proper trust policies
  - Add validation tools for generated templates and role configurations
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3.1 Implement CloudFormation template generators for hosting roles
  - Create generate_ec2_instance_role_template() function with MCP-specific permissions and instance profile
  - Implement generate_ecs_task_role_template() function with container-appropriate policies and task role configuration
  - Add generate_eks_service_account_template() function with IRSA configuration and Kubernetes service account setup
  - Create generate_lambda_execution_role_template() function with Lambda-specific permissions and VPC configuration
  - Implement generate_bedrock_agentcore_runtime_role_template() function with Bedrock-specific permissions and runtime policies
  - Add generate_fargate_task_role_template() function with Fargate-appropriate policies and networking configuration
  - Include all necessary permissions for MCP security assessment operations in each template
  - Write unit tests validating generated template structure, policy correctness, and compute service compatibility
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [ ] 3.2 Build cross-account role template generator with trust policy management
  - Create generate_cross_account_role_template() function that accepts source role ARN
  - Implement trust policy generation that allows hosting role to assume target role
  - Add external ID support for enhanced cross-account security
  - Include comprehensive MCP permissions for security assessment operations
  - Write unit tests for trust policy generation and template validation
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3.3 Add template validation and deployment helpers
  - Create validate_cloudformation_template() function to check template syntax and policies
  - Implement check_role_permissions() function to validate that roles have minimum required permissions
  - Add generate_deployment_instructions() function that creates account-specific deployment guides
  - Create template customization functions for different organizational requirements
  - Write integration tests that validate templates can be successfully deployed
  - _Requirements: 3.2, 3.3, 3.4, 3.5_

- [ ] 4. Integrate enhanced credential functionality with existing MCP server
  - Update existing MCP server tools to use enhanced credential chain
  - Add new MCP tools for environment validation and role management
  - Ensure backward compatibility with existing AssumeRole configurations
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 4.1 Update existing MCP tools to use enhanced credential chain
  - Modify CheckSecurityServices tool to use new environment-aware session creation
  - Update all security assessment tools to leverage enhanced credential validation
  - Add environment information to debug output in existing tools
  - Ensure all existing functionality continues to work with new credential chain
  - Write integration tests validating existing tools work with enhanced credentials
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 4.2 Create new MCP tools for environment and role management
  - Implement ValidateHostingEnvironment tool that checks environment configuration
  - Add GenerateDeploymentTemplates tool that creates CloudFormation templates for target accounts
  - Create TestCrossAccountAccess tool that validates cross-account role assumption
  - Implement GetEnvironmentInfo tool that returns detailed hosting environment information
  - Write comprehensive unit tests for all new MCP tools
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 4.3 Add enhanced error handling and diagnostic capabilities
  - Update error messages throughout credential utilities to include specific remediation steps
  - Add diagnostic information to help troubleshoot common configuration issues
  - Implement comprehensive logging for credential operations and environment detection
  - Create troubleshooting guide with common issues and solutions
  - Write tests covering error scenarios and validation of error messages
  - _Requirements: 4.3, 4.4, 4.5_

- [ ] 5. Create comprehensive documentation and examples
  - Write deployment guides for each hosting environment (EC2, ECS, Lambda)
  - Create example CloudFormation templates with complete IAM role configurations
  - Add troubleshooting documentation for common setup issues
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 5.1 Create environment-specific deployment documentation
  - Write EC2 deployment guide with instance profile setup and MCP server installation
  - Create ECS deployment guide with task role configuration and container deployment
  - Add EKS deployment guide with IRSA setup, service account configuration, and Kubernetes deployment manifests
  - Create Lambda deployment guide with execution role setup and function packaging
  - Write Bedrock AgentCore Runtime deployment guide with runtime role configuration and MCP server integration
  - Add Fargate deployment guide with task role setup and serverless container deployment
  - Include step-by-step instructions for cross-account role setup in target accounts for each compute service
  - Write troubleshooting sections for each deployment type with common issues, environment-specific gotchas, and solutions
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 5.2 Generate example CloudFormation templates and configurations
  - Create complete EC2 deployment template with instance profile, security groups, and user data scripts
  - Build ECS deployment template with task definition, service, cluster, and IAM roles
  - Add EKS deployment template with cluster, node groups, IRSA configuration, and Kubernetes manifests
  - Create Lambda deployment template with function, execution role, VPC configuration, and trigger setup
  - Build Bedrock AgentCore Runtime deployment template with runtime configuration, IAM roles, and MCP integration
  - Add Fargate deployment template with task definition, service, and serverless networking configuration
  - Include cross-account role templates for target accounts with proper trust policies for each compute service
  - Write validation scripts to test example templates in different AWS environments and compute services
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 5.3 Update existing documentation with enhanced credential capabilities
  - Update README.md with new environment detection and automatic credential features
  - Modify assume-role-configuration.md to include hosting environment setup instructions
  - Add migration guide for users moving from manual credential configuration
  - Create FAQ section addressing common questions about environment detection and role setup
  - Write integration examples showing how to use enhanced credentials with different MCP clients
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 6. Add comprehensive testing and validation
  - Create integration tests that validate functionality across different AWS environments
  - Add performance tests for credential operations and environment detection
  - Implement end-to-end tests with actual AWS resources and cross-account scenarios
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6.1 Build integration test suite for cross-account scenarios
  - Create test framework that can deploy temporary roles in multiple AWS accounts
  - Implement tests that validate actual cross-account AssumeRole operations
  - Add tests for external ID validation and trust policy enforcement
  - Create cleanup procedures to remove test resources after integration tests complete
  - Write tests covering permission validation and error scenarios
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 6.2 Add performance and reliability testing
  - Create performance tests for environment detection and metadata service calls
  - Implement load tests for credential refresh and session management
  - Add reliability tests that simulate metadata service failures and network issues
  - Create monitoring tests that validate logging and error reporting functionality
  - Write stress tests for concurrent credential operations and session management
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6.3 Implement end-to-end validation with real AWS environments
  - Create test scenarios that deploy MCP server in actual EC2, ECS, EKS, Lambda, Bedrock AgentCore Runtime, and Fargate environments
  - Add validation tests that perform real security assessments using enhanced credentials across all compute services
  - Implement tests that validate CloudFormation template deployment in target accounts for each hosting environment
  - Create monitoring and alerting tests for production deployment scenarios across different compute platforms
  - Add specific tests for Kubernetes IRSA functionality and Bedrock AgentCore Runtime integration
  - Write comprehensive test documentation with setup instructions, environment prerequisites, and expected results for each compute service
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6.4 Create comprehensive cross-account ECS deployment test
  - Build standalone ECS service deployment using "default" AWS profile with dedicated IAM task role
  - Create CloudFormation template for ECS cluster, service, and task definition with MCP server container
  - Implement dedicated ECS task role with sts:AssumeRole permissions for cross-account access
  - Deploy read-only IAM role in "coa" AWS profile with trust policy allowing ECS task role assumption
  - Configure ECS service with proper networking, security groups, and load balancer for MCP API access
  - Create automated deployment script that sets up both source and target account roles
  - Write integration test that sends MCP requests to deployed ECS service endpoint
  - Validate that MCP server can successfully assume role in "coa" account and fetch security data
  - Implement test cleanup procedures to remove all created resources after validation
  - Document complete deployment process with step-by-step instructions and troubleshooting guide
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 6.5 Implement detailed ECS cross-account test components
  - Create CloudFormation template for ECS cluster with Fargate capacity providers and networking configuration
  - Build ECS task definition with MCP server container image, resource requirements, and environment variables
  - Implement ECS task role with minimum required permissions for MCP operations and cross-account AssumeRole
  - Create Application Load Balancer with target group and health checks for MCP server HTTP endpoint
  - Build CloudFormation template for "coa" account read-only role with comprehensive security assessment permissions
  - Configure trust policy in "coa" role to allow assumption by ECS task role from "default" account
  - Create deployment automation script that handles both accounts and validates cross-account trust setup
  - Write MCP client test script that calls CheckSecurityServices and other tools via HTTP API
  - Implement validation logic that confirms successful cross-account data retrieval and proper error handling
  - Add comprehensive logging and monitoring for both deployment process and runtime MCP operations
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_