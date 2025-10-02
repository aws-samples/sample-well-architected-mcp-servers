# Cloud Optimization Assistant - Component Architecture

This document describes the key components of the Cloud Optimization Assistant (COA) platform and their interactions.

## Architecture Overview

The COA platform consists of four main component types that work together to provide comprehensive AWS security analysis and optimization:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│   Web Chatbot   │    │  Bedrock Agents  │    │  Strands Agents     │    │   MCP Servers    │
│   (ECS Service) │◄──►│  (Bedrock Agent) │◄──►│ (AgentCore Runtime) │◄──►│ (AgentCore       │
│                 │    │                  │    │                     │    │  Runtime)        │
└─────────────────┘    └──────────────────┘    └─────────────────────┘    └──────────────────┘
```

## Component Details

### 1. Web Chatbot (ECS Service)

**Location**: `cloud-optimization-web-interfaces/cloud-optimization-web-interface/`
**Deployment**: Amazon ECS with Fargate
**Purpose**: User-facing web interface for interactive conversations

**Key Features**:
- FastAPI backend with WebSocket support for real-time chat
- Vanilla JavaScript frontend with template-based prompts
- Amazon Cognito authentication integration
- Direct integration with Bedrock models (Claude 3.5 Sonnet, Claude 3 Haiku)
- Template processor for structured prompts and workflows

**Configuration**:
- **Backend**: `backend/main.py` - FastAPI application with WebSocket endpoints
- **Frontend**: `frontend/index.html` - Single-page application with chat interface
- **Templates**: `frontend/prompt-templates/` - Structured prompts for different use cases
- **Deployment**: Deployed via CloudFormation as ECS service with ALB

### 2. Bedrock Agents (Amazon Bedrock Agent Service)

**Location**: `agents/bedrock-agents/`
**Deployment**: Amazon Bedrock Agent Service
**Purpose**: AI agents with multi-MCP integration for complex workflows

**Available Agents**:
- **Multi-MCP Agent**: `wa-security-agent-multi-mcps/` - Integrates WA Security + AWS API + AWS Knowledge MCPs
- **Single-MCP Agent**: `wa-security-agent-single-mcp/` - Uses only Well-Architected Security MCP

**Key Features**:
- Model switching between Claude 3.5 Sonnet and Claude 3 Haiku
- Orchestrated workflows across multiple MCP servers
- Advanced reasoning and analysis capabilities
- Integration with AWS services through MCP tools

**Configuration**:
- **Agent Config**: `agent_config/` - Agent definitions and model configurations
- **Integrations**: `integrations/` - MCP server integration logic
- **Orchestration**: `orchestration/` - Multi-MCP workflow coordination

### 3. Strands Agents (AgentCore Runtime)

**Location**: `agents/strands-agents/`
**Deployment**: Amazon Bedrock AgentCore Runtime
**Purpose**: Specialized agents for specific assessment domains

**Available Strands Agents**:
- **WA Security Agent**: `strands-wa-sec/` - Well-Architected security assessments
- **AWS API Agent**: `strands-aws-api/` - AWS API operations and resource management
- **Cost Optimization Agent**: `strands-aws-cost-optimization/` - Cost analysis and optimization

**Key Features**:
- Lightweight, focused agents for specific use cases
- Direct MCP server integration
- Optimized for AgentCore Runtime environment
- Streamlined deployment and scaling

**Configuration**:
- **Main Entry**: `main.py` - Agent entry point and configuration
- **Agent Logic**: `*_agent.py` - Core agent implementation
- **Requirements**: `requirements.txt` - Python dependencies
- **Config**: `config.py` - Agent-specific configuration

### 4. MCP Servers (AgentCore Runtime)

**Location**: `mcp-servers/`
**Deployment**: Amazon Bedrock AgentCore Runtime
**Purpose**: Specialized tools providing AWS service integration

**Available MCP Servers**:
- **Well-Architected Security MCP**: `well-architected-security-mcp-server/` - Security assessment tools
- **AWS API MCP**: `aws-api-mcp-server/` - AWS CLI and API operations
- **AWS Knowledge MCP**: `aws-knowledge-mcp-server/` - AWS documentation and knowledge
- **Billing Cost MCP**: `billing-cost-mcp-server/` - Cost analysis and billing tools

**Key Features**:
- FastMCP framework for rapid tool development
- Comprehensive AWS service integration
- Enhanced credential management with AssumeRole support
- Stateless HTTP mode for AgentCore Runtime compatibility

**Configuration**:
- **Server**: `src/server.py` - MCP server implementation with tool definitions
- **Utils**: `src/util/` - Utility modules for AWS service interactions
- **Tests**: `tests/` - Comprehensive test coverage
- **Docs**: `docs/` - Server-specific documentation

## Component Interactions

### 1. User Interaction Flow
```
User → Web Chatbot → Bedrock Agent → Strands Agent → MCP Server → AWS Services
```

### 2. Authentication & Authorization
- **Web Chatbot**: Amazon Cognito for user authentication
- **Bedrock Agents**: IAM roles with Bedrock service permissions
- **Strands Agents**: AgentCore Runtime roles with cross-account access
- **MCP Servers**: Enhanced credential chain with AssumeRole support

### 3. Cross-Account Access Pattern
```
Source Account (Default Profile):
├── ECS Task Role (Web Chatbot)
├── Bedrock Agent Role
├── AgentCore Runtime Role (Strands Agents)
└── AgentCore Runtime Role (MCP Servers)
    └── AssumeRole → Target Account (COA Profile)
                    └── ReadOnly Assessment Role
```

## Deployment Architecture

### Infrastructure Components
- **VPC**: Dedicated VPC with public/private subnets
- **ECS Cluster**: Fargate-based cluster for web chatbot
- **Application Load Balancer**: HTTPS termination and routing
- **CloudFront**: CDN for frontend assets
- **S3 Buckets**: Static assets and artifacts storage
- **ECR Repository**: Container image storage

### Security Components
- **IAM Roles**: Least-privilege roles for each component
- **Security Groups**: Network-level access controls
- **VPC Endpoints**: Secure AWS service access
- **CloudTrail**: Audit logging for all operations
- **Parameter Store**: Secure configuration management

## Development Workflow

### Local Development
1. **Web Chatbot**: Run FastAPI backend + serve frontend locally
2. **Bedrock Agents**: Test with example scripts and model switching
3. **Strands Agents**: Local testing with mock MCP servers
4. **MCP Servers**: pytest with live/mock AWS API calls

### Deployment Process
1. **Source Upload**: Code uploaded to S3 source bucket
2. **Pipeline Trigger**: EventBridge triggers CodePipeline
3. **Build Phase**: CodeBuild builds containers and packages agents
4. **Deploy Phase**: CloudFormation updates infrastructure
5. **Validation**: Automated tests verify deployment success

### Testing Strategy
- **Unit Tests**: Individual component testing with mocks
- **Integration Tests**: Cross-component interaction testing
- **End-to-End Tests**: Full workflow validation with real AWS resources
- **Performance Tests**: Load testing and credential refresh validation

## Configuration Management

### Environment Variables
- **AWS_REGION**: Target AWS region for operations
- **AWS_ASSUME_ROLE_ARN**: Cross-account role for MCP servers
- **BEDROCK_MODEL_ID**: Default model for agent operations
- **ENVIRONMENT**: Deployment environment (dev/staging/prod)

### Parameter Store Paths
- `/coa/cognito/*`: Authentication configuration
- `/coa/components/*`: Component-specific settings
- `/coa/agent/*`: Agent configuration and model settings

### Secrets Management
- **External IDs**: Stored in Parameter Store for cross-account access
- **API Keys**: Managed through IAM roles (no static keys)
- **Session Tokens**: Temporary credentials via AssumeRole

## Monitoring and Observability

### Logging
- **CloudWatch Logs**: Centralized logging for all components
- **Structured Logging**: JSON format with correlation IDs
- **Log Groups**: Component-specific log group organization

### Metrics
- **CloudWatch Metrics**: Custom metrics for agent performance
- **X-Ray Tracing**: Distributed tracing across components
- **Health Checks**: Component health monitoring

### Alerting
- **SNS Topics**: Notification channels for alerts
- **CloudWatch Alarms**: Threshold-based alerting
- **EventBridge Rules**: Event-driven notifications

## Security Considerations

### Network Security
- **Private Subnets**: Sensitive components in private subnets
- **Security Groups**: Restrictive ingress/egress rules
- **VPC Endpoints**: Private AWS service access

### Identity and Access Management
- **Least Privilege**: Minimal required permissions for each role
- **Cross-Account Trust**: Secure trust relationships with external IDs
- **Temporary Credentials**: No long-lived access keys

### Data Protection
- **Encryption in Transit**: HTTPS/TLS for all communications
- **Encryption at Rest**: S3 and EBS encryption enabled
- **Audit Logging**: Comprehensive CloudTrail coverage

## Troubleshooting Common Issues

### Component Communication
- **Network Connectivity**: Check security groups and VPC configuration
- **Authentication**: Verify IAM roles and trust policies
- **Cross-Account Access**: Validate AssumeRole permissions and external IDs

### Performance Issues
- **Credential Refresh**: Monitor credential refresh latency
- **Agent Response Time**: Check model selection and MCP server performance
- **Resource Limits**: Verify ECS task and Lambda resource allocation

### Deployment Problems
- **Pipeline Failures**: Check CodeBuild logs and IAM permissions
- **Stack Updates**: Verify CloudFormation template syntax and dependencies
- **Container Issues**: Check ECR repository access and image builds

This architecture provides a scalable, secure, and maintainable platform for AWS optimization and security assessment across multiple accounts and environments.