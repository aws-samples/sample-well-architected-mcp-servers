# Design Document

## Overview

The Remote Role Stack feature consists of a Python script (`generate_remote_role_stack.py`) that creates CloudFormation templates for deploying IAM roles in target AWS accounts. These roles are designed to be assumed by the AgentCore Runtime Role, enabling MCP servers to perform cross-account operations. The script integrates with the existing deployment workflow and retrieves configuration from the deployed WA Security MCP stack.

## Architecture

### High-Level Flow
1. **Post-Deployment Execution**: Script runs after `deploy_component_wa_security_mcp.py` completes
2. **Configuration Retrieval**: Extracts AgentCore Runtime Role ARN from AWS Parameter Store
3. **Template Generation**: Creates CloudFormation template with IAM role and trust policy
4. **Output Generation**: Saves template to predictable location for deployment to target accounts

### Integration Points
- **Parameter Store**: Reads configuration from `/coa/components/wa_security_mcp/*` paths
- **AWS Session**: Uses same boto3 session and region as parent deployment
- **File System**: Outputs templates to `deployment-scripts/generated-templates/` directory

## Components and Interfaces

### Core Script (`generate_remote_role_stack.py`)

#### Main Functions
```python
def get_agentcore_runtime_role_arn(region: str) -> str
def generate_cloudformation_template(
    runtime_role_arn: str,
    role_name: str = "CrossAccountMCPRole",
    external_id: Optional[str] = None,
    additional_policies: List[str] = None
) -> dict
def save_template(template: dict, output_path: str) -> None
def main()
```

#### Configuration Class
```python
@dataclass
class RemoteRoleConfig:
    runtime_role_arn: str
    role_name: str
    external_id: Optional[str]
    additional_managed_policies: List[str]
    custom_policy_statements: List[dict]
    tags: Dict[str, str]
```

### CloudFormation Template Structure

#### Parameters
- `RoleName`: Name for the IAM role (default: CrossAccountMCPRole)
- `ExternalId`: Optional external ID for additional security
- `Environment`: Environment tag (dev/staging/prod)

#### Resources
- **IAM Role**: Cross-account assumable role with trust policy
- **Managed Policy Attachments**: AWS managed policies for security services
- **Custom Inline Policy**: Additional permissions for MCP operations

#### Outputs
- `RoleArn`: ARN of the created role
- `RoleName`: Name of the created role
- `ExternalId`: External ID used (if provided)

## Data Models

### Trust Policy Structure
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE_ACCOUNT:role/AgentCoreRuntimeRole"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "EXTERNAL_ID"
        }
      }
    }
  ]
}
```

### Permission Policy Structure
The role will include permissions for:
- **Security Services**: GuardDuty, Security Hub, Inspector, Access Analyzer, Macie, Trusted Advisor
- **Resource Discovery**: Resource Explorer, Config, CloudTrail
- **Read-Only Access**: EC2, S3, RDS, Lambda, VPC for security analysis
- **Tagging Operations**: Resource tagging for compliance tracking

### Default Managed Policies
- `SecurityAudit` - AWS managed policy for security auditing
- `ReadOnlyAccess` - Read-only access to AWS services (optional, can be replaced with more specific policies)

### Custom Policy Statements
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "guardduty:GetDetector",
        "guardduty:ListDetectors",
        "guardduty:GetFindings",
        "securityhub:DescribeHub",
        "securityhub:GetFindings",
        "inspector2:GetStatus",
        "inspector2:ListFindings",
        "access-analyzer:ListAnalyzers",
        "access-analyzer:ListFindings",
        "macie2:GetMacieSession",
        "macie2:ListFindings",
        "support:DescribeTrustedAdvisorChecks",
        "support:DescribeTrustedAdvisorCheckResult"
      ],
      "Resource": "*"
    }
  ]
}
```

## Error Handling

### Configuration Retrieval Errors
- **Missing Parameter Store Values**: Provide clear error message with setup instructions
- **Invalid Role ARN Format**: Validate ARN format and provide correction guidance
- **AWS Permission Issues**: Handle access denied errors with permission requirements

### Template Generation Errors
- **Invalid Policy Syntax**: Validate JSON policy documents before inclusion
- **Parameter Validation**: Check role name format, external ID requirements
- **Resource Limits**: Handle IAM policy size limits and role attachment limits

### File System Errors
- **Directory Creation**: Create output directories if they don't exist
- **File Permissions**: Handle write permission issues gracefully
- **Disk Space**: Check available disk space before writing large templates

## Testing Strategy

### Unit Tests
- **Configuration Parsing**: Test parameter store value retrieval and parsing
- **Template Generation**: Validate generated CloudFormation template structure
- **Policy Validation**: Test IAM policy syntax and permission validation
- **Error Handling**: Test all error conditions and edge cases

### Integration Tests
- **AWS Integration**: Test with real AWS Parameter Store and IAM services
- **End-to-End Flow**: Test complete workflow from deployment to template generation
- **Cross-Account Testing**: Validate role assumption across different AWS accounts

### Test Data
- **Mock Parameter Store**: Simulated parameter store responses
- **Sample Configurations**: Various role configurations for testing
- **Invalid Inputs**: Test cases for error handling validation

### Test Environment Setup
```python
@pytest.fixture
def mock_parameter_store():
    # Mock AWS Parameter Store responses
    
@pytest.fixture
def sample_runtime_role_arn():
    return "arn:aws:iam::123456789012:role/AgentCoreRuntimeRole"

@pytest.fixture
def expected_template_structure():
    # Expected CloudFormation template structure
```

## Security Considerations

### Least Privilege Access
- Role permissions limited to security analysis and read-only operations
- No administrative or destructive permissions included by default
- Custom policies validated for overly permissive access

### Trust Relationship Security
- External ID requirement for additional security layer
- Trust policy limited to specific AgentCore Runtime Role ARN
- No wildcard principals or overly broad trust relationships

### Credential Management
- No long-term credentials stored or generated
- Role assumption uses temporary credentials only
- Session duration limits enforced through trust policy

### Audit and Compliance
- All role assumptions logged through CloudTrail
- Role usage tracked through AWS access logs
- Template generation logged for audit purposes

## Deployment Integration

### Execution Context
- Script executed from `deployment-scripts/` directory
- Uses same AWS profile and region as parent deployment
- Inherits environment variables and configuration

### Output Location
- Templates saved to `deployment-scripts/generated-templates/remote-role-stack/`
- Filename format: `remote-role-{timestamp}.yaml`
- Includes metadata file with generation parameters

### Usage Instructions
```bash
# After WA Security MCP deployment
cd deployment-scripts
python generate_remote_role_stack.py --role-name MyRemoteRole --external-id my-unique-id

# Deploy to target account
aws cloudformation deploy \
  --template-file generated-templates/remote-role-stack/remote-role-20240829.yaml \
  --stack-name remote-mcp-role \
  --capabilities CAPABILITY_IAM \
  --profile target-account-profile
```