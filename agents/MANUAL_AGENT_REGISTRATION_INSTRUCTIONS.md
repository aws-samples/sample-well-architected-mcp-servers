# Manual Agent Registration Instructions

## Overview

This guide provides step-by-step instructions for registering manually deployed agents with the Cloud Optimization Assistant (COA) chatbot system. Use this when you have agents that were deployed outside of the automated deployment scripts but need to be integrated with the COA platform.

## When to Use Manual Registration

- ✅ Agents deployed directly using `agentcore` CLI
- ✅ Agents deployed through custom automation tools
- ✅ Existing agents that predate the automated deployment scripts
- ✅ Agents deployed in different environments or accounts
- ✅ Testing or development agents that need temporary integration

## Prerequisites

### Required Information
Before starting, gather the following information about your agent:

1. **Agent ARN** (Required)
   - Format: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT-ID`
   - Example: `arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-agent-abc123`

2. **Agent Name** (Required)
   - Descriptive name for the agent (used in COA system)
   - Example: `strands-aws-api`, `custom-security-scanner`

3. **AWS Region** (Required)
   - Region where the agent is deployed
   - Example: `us-east-1`, `eu-west-1`

### Optional Information
4. **Agent Type**
   - Type classification for the agent
   - Examples: `strands_agent`, `security_agent`, `cost_optimization`, `custom_agent`

5. **Source Path**
   - Path to agent source code in the project
   - Example: `agents/strands-agents/strands-aws-api`

6. **Execution Role ARN**
   - IAM role used by the agent
   - Example: `arn:aws:iam::123456789012:role/AgentCoreExecutionRole`

7. **Description**
   - Human-readable description of the agent's purpose
   - Example: `AWS API operations and resource management agent`

### Required Permissions
Ensure your AWS credentials have the following permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
                "ssm:DescribeParameters"
            ],
            "Resource": [
                "arn:aws:ssm:*:*:parameter/coa/agent/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## Step-by-Step Registration Process

### Step 1: Discover Existing Agents

First, check what agents are already registered and identify any that need registration:

```bash
cd deployment-scripts/register-agentcore-runtime
python discover_agents.py --region us-east-1
```

This will show you:
- Currently registered agents
- AgentCore configurations found in the project
- Potential agents that need registration
- Registration gaps and recommendations

### Step 2: Prepare Registration Command

Based on the discovery results and your agent information, prepare the registration command:

#### Basic Registration (Minimal Information)
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name my-agent-name \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id
```

#### Full Registration (With All Metadata)
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name strands-aws-api \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/aws-api-agent-123 \
  --agent-type strands_agent \
  --source-path "agents/strands-agents/strands-aws-api" \
  --execution-role-arn arn:aws:iam::123456789012:role/AgentCoreExecutionRole \
  --description "AWS API operations and resource management agent"
```

### Step 3: Execute Registration

Run the registration command from the `deployment-scripts/components` directory:

```bash
cd deployment-scripts/register-agentcore-runtime
# Run your prepared command here
python register_manual_agent.py [your-parameters]
```

The script will:
1. ✅ Validate AWS credentials and permissions
2. ✅ Validate the agent ARN format
3. ✅ Check for existing registrations (prevents overwrites)
4. ✅ Create SSM parameters for chatbot integration
5. ✅ Validate parameter creation
6. ✅ Provide a registration summary

### Step 4: Verify Registration

Confirm the registration was successful:

```bash
# Run discovery again to see the newly registered agent
python discover_agents.py --region us-east-1

# Check specific SSM parameters
aws ssm get-parameters-by-path --path "/coa/agent/your-agent-name" --recursive
```

### Step 5: Test Chatbot Integration

Launch the COA chatbot and verify your agent appears:

```bash
cd ../../cloud-optimization-web-interfaces/cloud-optimization-web-interface
python start_server.py
```

In the web interface, your agent should now be available for use.

## Common Registration Scenarios

### Scenario 1: Strands AWS API Agent

If you have a Strands AWS API agent deployed manually:

```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name strands-aws-api \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/aws-api-agent-123 \
  --agent-type strands_agent \
  --source-path "agents/strands-agents/strands-aws-api" \
  --description "AWS API operations and resource management agent"
```

### Scenario 2: Custom Security Agent

For a custom security assessment agent:

```bash
python register_manual_agent.py \
  --region us-west-2 \
  --agent-name custom-security-scanner \
  --agent-arn arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/security-scanner-456 \
  --agent-type security_agent \
  --execution-role-arn arn:aws:iam::123456789012:role/SecurityScannerRole \
  --description "Custom security scanning and compliance assessment agent"
```

### Scenario 3: Cost Optimization Agent

For a cost optimization agent:

```bash
python register_manual_agent.py \
  --region eu-west-1 \
  --agent-name cost-optimizer \
  --agent-arn arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/cost-opt-789 \
  --agent-type cost_optimization \
  --source-path "agents/strands-agents/strands-aws-cost-optimization" \
  --description "AWS cost analysis and optimization recommendations"
```

### Scenario 4: Overwriting Existing Registration

If you need to update an existing registration:

```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name existing-agent \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/updated-agent-id \
  --agent-type updated_agent \
  --description "Updated agent with new configuration" \
  --overwrite
```

## Interactive Registration

For a guided registration process, use the interactive example script:

```bash
cd deployment-scripts/register-agentcore-runtime
./register_agent.sh
```

This will prompt you for agent information and execute the registration commands.

## Troubleshooting

### Common Issues and Solutions

#### 1. Invalid ARN Format
```
Error: Invalid agent ARN format
```
**Solution**: Ensure your ARN follows the correct format:
`arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT-ID`

#### 2. Agent Already Registered
```
Status: already_registered
```
**Solution**: Use the `--overwrite` flag to replace the existing registration, or choose a different agent name.

#### 3. AWS Credentials Issues
```
Error: AWS credentials not configured or invalid
```
**Solution**: 
- Run `aws configure` to set up credentials
- Ensure your credentials have the required SSM permissions
- Test with `aws sts get-caller-identity`

#### 4. SSM Access Denied
```
Error: SSM access validation failed
```
**Solution**: Verify your IAM user/role has the required SSM permissions listed in the prerequisites.

#### 5. Parameter Creation Failed
```
Error: Failed to create parameter /coa/agent/agent-name/parameter-name
```
**Solution**: 
- Check SSM parameter limits in your account
- Verify parameter path doesn't conflict with existing parameters
- Ensure you have `ssm:PutParameter` permission

### Debug Mode

For detailed troubleshooting, enable debug logging:

```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name my-agent \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id \
  --log-level DEBUG
```

### Getting Help

For additional help:

```bash
# Registration script help
python register_manual_agent.py --help

# Discovery script help
python discover_agents.py --help

# Example script help
./example_register_agents.sh --help
```

## Best Practices

### 1. Naming Conventions
- Use descriptive, consistent agent names
- Follow kebab-case format: `strands-aws-api`, `custom-security-scanner`
- Include the agent type or purpose in the name

### 2. Agent Types
Use consistent agent type classifications:
- `strands_agent` - For Strands framework agents
- `security_agent` - For security assessment agents
- `cost_optimization` - For cost analysis agents
- `reliability_agent` - For reliability assessment agents
- `performance_agent` - For performance optimization agents
- `custom_agent` - For custom or specialized agents

### 3. Documentation
- Always provide meaningful descriptions
- Include source path when available
- Document the agent's purpose and capabilities

### 4. Testing
- Test registration in development environment first
- Verify chatbot integration after registration
- Monitor agent performance after integration

### 5. Maintenance
- Run discovery periodically to identify new agents
- Keep registrations up to date when agents are modified
- Remove registrations for decommissioned agents

## Integration with COA Chatbot

Once registered, your agent will be integrated with the COA chatbot system:

### SSM Parameters Created
The registration creates these parameters under `/coa/agent/{agent-name}/`:
- `agent_arn` - Agent's full ARN
- `agent_id` - Extracted agent ID
- `region` - Deployment region
- `deployment_type` - Set to "manual"
- `agent_type` - Agent classification
- `connection_info` - JSON connection details
- `metadata` - Registration metadata

### Chatbot Discovery
The chatbot automatically discovers registered agents through SSM parameters and makes them available for:
- User interaction and queries
- Automated routing based on agent type
- Display in the agent selection interface
- Integration with multi-agent workflows

### Monitoring
Monitor your registered agent through:
- CloudWatch Logs for agent execution
- SSM Parameter Store for configuration
- COA chatbot interface for usage metrics

## Next Steps

After successful registration:

1. **Test Integration**: Launch the COA chatbot and verify your agent is available
2. **Monitor Performance**: Check CloudWatch logs for agent activity
3. **Update Documentation**: Document your agent's capabilities for users
4. **Share Knowledge**: Update team documentation with registration details
5. **Plan Maintenance**: Schedule regular reviews of agent registrations

## Support

For additional support:
- Review the comprehensive documentation in `deployment-scripts/components/README_manual_agent_registration.md`
- Check the troubleshooting section in the main README
- Run the test suite to validate your environment: `python test_manual_registration.py`
- Use the discovery tool to understand your current agent landscape

---

**🚀 Your manually deployed agents are now ready for COA chatbot integration!**