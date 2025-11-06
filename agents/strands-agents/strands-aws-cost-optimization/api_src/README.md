# AWS API MCP Server (Modified for Cross-Account Support)

## Overview

This directory contains a **modified version** of the [awslabs.aws_api_mcp_server](https://github.com/awslabs/aws-api-mcp-server) that has been enhanced to support cross-account AWS operations through AssumeRole functionality.

## Original Source

- **Original Repository**: [awslabs/aws-api-mcp-server](https://github.com/awslabs/aws-api-mcp-server)
- **License**: Apache License 2.0
- **Purpose**: Model Context Protocol (MCP) server providing AWS CLI functionality

## Modifications Made

This version has been specifically modified for the **Cloud Optimization Assistant (COA)** sample solution to support:

### 1. Cross-Account AssumeRole Support
- Enhanced credential management to support AssumeRole operations
- Environment variable configuration for cross-account access:
  - `AWS_ASSUME_ROLE_ARN`: Target role ARN to assume
  - `AWS_ASSUME_ROLE_SESSION_NAME`: Session name for the assumed role
  - `AWS_ASSUME_ROLE_EXTERNAL_ID`: External ID for enhanced security

### 2. Enhanced Credential Chain
- Improved credential resolution and inheritance
- Support for temporary credentials and session tokens
- Proper credential passing to subprocess environments

### 3. Cross-Account Validation
- Added validation for AssumeRole configuration
- Enhanced error handling for cross-account scenarios
- Improved logging for credential operations

## Key Files Modified

- `server.py`: Enhanced with AssumeRole credential management
- `core/common/credential_utils.py`: Added cross-account credential handling
- Various utility modules for improved cross-account support

## Usage in COA

This modified MCP server is used by the AWS API Strands Agent (`aws_api_agent.py`) to provide:

1. **Same-Account Operations**: Standard AWS CLI operations in the current account
2. **Cross-Account Operations**: AWS CLI operations in target accounts via AssumeRole
3. **Credential Validation**: Verification of cross-account access configuration
4. **Command Suggestions**: AI-powered AWS CLI command recommendations

## Environment Configuration

The server automatically detects and uses AssumeRole configuration when these environment variables are set:

```bash
AWS_ASSUME_ROLE_ARN=arn:aws:iam::TARGET-ACCOUNT:role/ROLE-NAME
AWS_ASSUME_ROLE_SESSION_NAME=session-name
AWS_ASSUME_ROLE_EXTERNAL_ID=external-id  # Optional
```

## Integration with Strands Agent

The modified MCP server integrates seamlessly with the Strands Agent framework:

- **Agent File**: `../aws_api_agent.py`
- **Environment Setup**: Centralized configuration via `get_environment_config()`
- **MCP Client**: Clean initialization pattern for subprocess communication
- **Cross-Account Parameters**: Automatic role ARN construction from account IDs

## Testing

Comprehensive test suite included:

- `../test_credentials.py`: Basic credential validation
- `../test_simple_comparison.py`: Cross-account functionality verification
- `../test_account_verification.py`: Account identity validation
- Additional validation scripts for various scenarios

## Compatibility

- **Original Functionality**: All original awslabs.aws_api_mcp_server features preserved
- **Backward Compatible**: Works with existing MCP clients and configurations
- **Enhanced Features**: Additional cross-account capabilities without breaking changes

## License

This modified version maintains the original Apache License 2.0 from the awslabs project.

## Support

For issues specific to the cross-account modifications, refer to the COA project documentation. For general AWS API MCP server issues, refer to the original [awslabs repository](https://github.com/awslabs/aws-api-mcp-server).

---

**Note**: This is a specialized version for the Cloud Optimization Assistant sample solution. For general use cases, consider using the official awslabs.aws_api_mcp_server package directly.