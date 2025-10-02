# Changelog

## [Unreleased] - AssumeRole Support Enhancement

### Added
- **AssumeRole Support**: Extended AWS credential handling to support AssumeRole via environment variables
  - `AWS_ASSUME_ROLE_ARN`: The ARN of the IAM role to assume (required)
  - `AWS_ASSUME_ROLE_SESSION_NAME`: Custom session name (optional, defaults to "mcp-server-session")
  - `AWS_ASSUME_ROLE_EXTERNAL_ID`: External ID for enhanced security (optional)

- **New Utility Module**: `src/util/credential_utils.py`
  - `create_aws_session()`: Enhanced session creation with AssumeRole support
  - `validate_assume_role_config()`: Configuration validation for AssumeRole setup
  - `get_session_info()`: Session information retrieval for debugging

- **New MCP Tool**: `ValidateCredentialConfiguration`
  - Validates current AWS credential configuration
  - Provides troubleshooting information for authentication issues
  - Displays session information and credential source details

- **Comprehensive Documentation**:
  - `docs/assume-role-configuration.md`: Detailed AssumeRole configuration guide
  - Updated README.md with authentication methods and examples
  - Example script: `examples/assume_role_example.py`

- **Test Coverage**: `tests/test_credential_utils.py`
  - Unit tests for all credential utility functions
  - Mock-based testing to avoid actual AWS API calls
  - Validation testing for various configuration scenarios

### Changed
- **Enhanced Credential Chain**: All MCP tools now use the enhanced credential chain that supports AssumeRole
- **Improved Debug Output**: Added credential source information to debug logs
- **Updated Documentation**: README.md now includes comprehensive authentication section

### Technical Details
- **Backward Compatibility**: Maintains full compatibility with existing authentication methods
- **Security**: Supports external ID for enhanced cross-account security
- **Error Handling**: Comprehensive error handling and validation for AssumeRole operations
- **Logging**: Enhanced logging for credential operations and troubleshooting

### Use Cases
- **Cross-Account Security Assessments**: Assess security posture across multiple AWS accounts
- **Centralized Security Operations**: Use a single MCP server to assess multiple accounts
- **Enhanced Security**: Use external IDs for secure cross-account access
- **Compliance Auditing**: Perform compliance checks across organizational boundaries

### Migration Guide
Existing users can continue using their current authentication methods. To enable AssumeRole:

1. Set environment variables:
   ```bash
   export AWS_ASSUME_ROLE_ARN="arn:aws:iam::TARGET-ACCOUNT:role/SecurityAuditRole"
   export AWS_ASSUME_ROLE_EXTERNAL_ID="unique-external-id"
   ```

2. Ensure IAM permissions for AssumeRole operation

3. Run the MCP server - AssumeRole will be used automatically

### Breaking Changes
None. This is a backward-compatible enhancement.

### Dependencies
No new dependencies added. Uses existing boto3 and botocore libraries.