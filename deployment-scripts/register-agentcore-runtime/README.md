# AgentCore Runtime Registration Tools

This directory contains comprehensive tools for registering manually deployed Bedrock AgentCore runtimes with the COA (Cloud Optimization Assistant) chatbot system.

## 🚀 Quick Start

### One-Click Registration (Recommended)
```bash
cd deployment-scripts/register-agentcore-runtime
./register_agent.sh
```

This interactive tool will:
- ✅ Auto-discover deployed AgentCore runtimes
- ✅ Show registration status
- ✅ Guide you through registration
- ✅ Verify integration with COA chatbot

## 📁 Available Tools

### 🌟 **Interactive Tools**
- **`register_agent.sh`** - One-click interactive registration launcher
- **`interactive_agent_registration.py`** - Python-based interactive registration tool

### 🔧 **Command-Line Tools**
- **`register_manual_agent.py`** - Command-line registration script for automation
- **`discover_agents.py`** - Agent discovery and status utility

## 🎯 Usage Scenarios

### Scenario 1: Interactive Registration (Recommended)
```bash
./register_agent.sh --region us-east-1
```

### Scenario 2: Command-Line Registration
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name my-agent \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id
```

### Scenario 3: Discovery Only
```bash
python discover_agents.py --region us-east-1
```

## 🔧 Prerequisites

### Required Software
- **AWS CLI** configured with valid credentials
- **Python 3.8+** with boto3 installed
- **Bedrock AgentCore runtimes** already deployed
- **AgentCore CLI** (optional, for enhanced discovery)

### Required Permissions
Your AWS credentials need these permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:ListAgentRuntimes",
                "bedrock-agentcore:GetAgentRuntime",
                "bedrock-agentcore:DescribeAgentRuntime"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "iam:ListRoles",
                "iam:ListRoleTags"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
                "ssm:DescribeParameters"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/*/agentcore/*"
        },
        {
            "Effect": "Allow",
            "Action": "sts:GetCallerIdentity",
            "Resource": "*"
        }
    ]
}
```

## �  Interactive Registration Features

The interactive registration tool provides a comprehensive experience:

### Auto-Discovery Process
1. **AWS API Discovery**: Direct calls to Bedrock AgentCore service APIs
2. **CloudWatch Logs Analysis**: Scans log groups for AgentCore activity patterns
3. **IAM Role Discovery**: Finds AgentCore execution roles and extracts agent info
4. **SSM Parameter Check**: Queries existing registrations in Parameter Store
5. **Gap Analysis**: Identifies deployed but unregistered agents

### User Interface Features
- **Color-Coded Output**: Green for success, red for errors, yellow for warnings
- **Interactive Tables**: Formatted display of agents and status
- **Step-by-Step Guidance**: Clear progress indicators and confirmations
- **Safety Features**: Prevents overwrites and validates inputs

### Example Interactive Display
```
Deployed AgentCore Runtimes (from AWS):
# | Agent Name      | Agent ID     | Source           | Has ARN | Status   
--------------------------------------------------------------------------
1 | strands-aws-api | abc123def456 | cloudwatch_logs  | ✅       | active    
2 | strands-wa-sec  | def456ghi789 | iam_roles        | ✅       | deployed  
3 | cost-optimizer  | ghi789jkl012 | bedrock_agentcore_api | ✅  | deployed

Already Registered Agents:
# | Agent Name              | Complete | Status  
-------------------------------------------------
1 | existing-security-agent | ✅        | Complete
```

## 🔧 Command-Line Registration

For automation and scripting, use the command-line tool:

### Basic Registration
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name my-manual-agent \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id
```

### Full Registration with Metadata
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name strands-aws-api \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/abc123def456 \
  --agent-type strands_agent \
  --source-path "agents/strands-agents/strands-aws-api" \
  --execution-role-arn arn:aws:iam::123456789012:role/AgentCoreExecutionRole \
  --description "AWS API operations agent for COA system"
```

### Command Line Arguments

#### Required Arguments
- `--region`: AWS region where the agent is deployed
- `--agent-name`: Name for the agent (used for SSM parameter organization)
- `--agent-arn`: ARN of the manually deployed agent

#### Optional Arguments
- `--agent-type`: Type of agent (default: "manual")
- `--source-path`: Source path of the agent code
- `--execution-role-arn`: ARN of the execution role used by the agent
- `--description`: Description of the agent
- `--stack-prefix`: Stack prefix for SSM parameter paths (default: "coa")
- `--overwrite`: Overwrite existing registration if it exists
- `--log-level`: Logging level (DEBUG, INFO, WARNING, ERROR)

## 🔍 What Gets Registered

The registration process creates SSM parameters under `/{stack-prefix}/agentcore/{agent-name}/` (default: `/coa/agentcore/{agent-name}/`):

### Basic Parameters
- `agent_arn` - Full AgentCore runtime ARN
- `agent_id` - Runtime ID extracted from ARN
- `region` - AWS region
- `deployment_type` - Set to "manual"
- `agent_type` - Agent classification (e.g., "cost_optimization", "security_agent")

### Optional Parameters (if provided)
- `execution_role_arn` - IAM role used by the agent
- `source_path` - Path to agent source code
- `description` - Agent description

### Special Parameters
- `connection_info` - JSON connection details for chatbot integration
- `metadata` - Registration metadata and timestamps

## 🎯 Integration with COA Chatbot

Once registered, agents are automatically available in the COA chatbot through SSM parameter discovery:

1. **Auto-Discovery**: Chatbot scans SSM parameters for registered agents
2. **Agent Selection**: Users can select from available agents
3. **Routing**: Requests are routed to appropriate agents based on type
4. **Monitoring**: Agent usage is tracked and logged

## 📋 Common Registration Examples

### Registering a Strands AWS API Agent
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name strands-aws-api \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/aws-api-agent-123 \
  --agent-type strands_agent \
  --source-path "agents/strands-agents/strands-aws-api" \
  --description "AWS API operations and resource management agent"
```

### Registering with Custom Stack Prefix
```bash
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name strands-aws-api \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/aws-api-agent-123 \
  --stack-prefix "my-stack" \
  --agent-type strands_agent \
  --description "AWS API operations agent for my-stack deployment"
```

### Registering a Custom Security Agent
```bash
python register_manual_agent.py \
  --region us-west-2 \
  --agent-name custom-security-scanner \
  --agent-arn arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/security-scanner-456 \
  --agent-type security_agent \
  --execution-role-arn arn:aws:iam::123456789012:role/SecurityScannerRole \
  --description "Custom security scanning and compliance agent"
```

### Registering a Cost Optimization Agent
```bash
python register_manual_agent.py \
  --region eu-west-1 \
  --agent-name cost-optimizer \
  --agent-arn arn:aws:bedrock-agentcore:eu-west-1:123456789012:runtime/cost-opt-789 \
  --agent-type cost_optimization \
  --source-path "agents/strands-agents/strands-aws-cost-optimization" \
  --description "AWS cost analysis and optimization recommendations"
```

## 🆘 Troubleshooting

### Common Issues

#### "No AgentCore runtimes found via AWS APIs"
- **Cause**: No deployed agents or insufficient permissions
- **Solution**: 
  - Verify agents are deployed to Bedrock AgentCore Runtime
  - Check IAM permissions for bedrock-agentcore, logs, and iam actions
  - Ensure you're checking the correct AWS region

#### "Insufficient permissions for Bedrock AgentCore API"
- **Cause**: Missing bedrock-agentcore permissions
- **Solution**: Add bedrock-agentcore:ListAgents and related permissions to your IAM user/role

#### "AWS credentials not configured"
- **Cause**: Missing or invalid AWS credentials
- **Solution**: Run `aws configure` or check IAM permissions

#### "SSM access denied"
- **Cause**: Insufficient IAM permissions
- **Solution**: Add required SSM permissions to your IAM user/role

#### "Invalid ARN Format"
- **Cause**: Incorrect agent ARN format
- **Solution**: Ensure ARN follows format: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT-ID`

#### "Agent Already Registered"
- **Cause**: Agent name already exists in SSM parameters
- **Solution**: Use `--overwrite` flag or choose a different agent name

### Debug Logging

Enable debug logging for detailed troubleshooting:

```bash
# Interactive tool
./register_agent.sh --region us-east-1 --log-level DEBUG

# Command-line tool
python register_manual_agent.py \
  --region us-east-1 \
  --agent-name my-agent \
  --agent-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/agent-id \
  --log-level DEBUG
```

Log files are created in the `logs/` directory with timestamps.

## 🎯 Best Practices

### Before Registration
1. Deploy agents using `agentcore` CLI
2. Verify agents are working with `agentcore status`
3. Ensure AWS credentials have required permissions
4. Run discovery to understand current state

### During Registration
1. Use descriptive agent names
2. Provide meaningful descriptions
3. Select appropriate agent types
4. Include source paths when available

### After Registration
1. Test agents in COA chatbot
2. Monitor agent performance
3. Update registrations when agents change
4. Document agent capabilities for users

## 🔗 Related Documentation

- **Main deployment scripts**: `../components/`
- **Agent instructions**: `../../agents/MANUAL_AGENT_REGISTRATION_INSTRUCTIONS.md`
- **Project documentation**: `../../docs/`

---

**🚀 Ready to register your AgentCore runtimes? Start with `./register_agent.sh`!**