# Cloud Optimization Assistant

A comprehensive platform for AWS security analysis and cloud optimization using Amazon Bedrock agents and Model Context Protocol (MCP) servers.

## 🏗️ **Architecture Overview**

![AWS Architecture Diagram](docs/images/coa-security-assistant-0.1.0.png)

## 🏗️ **System Architecture Components**

The Cloud Optimization Assistant consists of the following key components:

• **🌐 Web Chatbot Interface**
  - Frontend hosted on S3 with CloudFront distribution for global delivery
  - ECS service providing the backend API and business logic
  - Real-time chat interface for user interactions

• **🤖 Amazon Bedrock Agent**
  - AI Agent deployed on Amazon Bedrock Agent service
  - Primary communication endpoint for the ECS backend service
  - Intelligent orchestration of security analysis workflows

• **🧠 LLM Model Integration**
  - Invokes AWS Bedrock models, primarily Anthropic Claude 3.7 Sonnet
  - Configurable model selection for optimal performance and cost
  - Runtime model switching capabilities for different task complexities

• **🔧 MCP Server Architecture**
  - **Self-Maintained MCP Servers**: Deployed in Amazon Bedrock AgentCore Runtime
  - **Remote MCP Servers**: Accessed via streamable-http MCP (Model Context Protocol)
  - Provides specialized tools for AWS security assessments and analysis

• **☁️ AWS Account Integration**
  - Self-maintained MCP servers interact with AWS accounts using IAM role access
  - Cross-account security analysis with read-only permissions
  - Secure, least-privilege access patterns for multi-account environments

• **🔐 Centralized Authentication**
  - Amazon Cognito provides unified authentication across all components
  - Single sign-on experience for users accessing different system parts
  - Secure token-based authentication for API communications



```
/
├── 🌐 cloud-optimization-web-interfaces/    # Web interfaces for user interaction
|
├── 🤖 agents/                               # Agents for specialized assessments
|         ├──bedrock-agents/                 # Bedrock agent set (to be deployed into Bedrock Agent)
|         |        ├──wa-security-agent-multi-mcps/
|         |        |                         # Multi-MCP (WA_SEC + AWS_API + AWS_Knowledge)
|         |        └──wa-security-agent-single-wa-sec-mcp/
|         |                                  # Single-MCP (WA_SEC)
|         |
|         └──strads-agents/                  # Bedrock agent set (to be deployed into Bedrock AgentCore Runtime)
|
├── 🔧 mcp-servers/                          # MCP servers providing assessment tools
|         |
|         └──well-architected-security-mcp-server/
|
└── 🚀 deployment-scripts/                   # Deployment automation scripts
```

## 📁 **Directory Structure**

### 🌐 Cloud Optimization Web Interfaces
Interactive web applications for cloud optimization assessments with automated CI/CD pipeline.

```
cloud-optimization-web-interfaces/
└── cloud-optimization-web-interface/       # Main web interface
    ├── backend/                            # FastAPI backend with health checks
    ├── frontend/                           # HTML/JS frontend
    ├── Dockerfile                          # Production-ready multi-stage container
    └── tests/                              # Integration tests
```

**Features:**
- Real-time chat interface with Claude 3.5 Sonnet
- WebSocket communication for instant responses
- Multi-pillar optimization assessments
- Interactive dashboards and reports
- **🚀 Automated CI/CD Pipeline**: Complete backend deployment automation
- **🐳 Containerized Backend**: Production-ready Docker containers with health checks
- **🔒 Security-First**: VPC endpoints, least-privilege IAM, vulnerability scanning

### 🤖 Bedrock Agents
Specialized AI agents for different aspects of cloud optimization.

```
bedrock-agents/
├── security-assessment-agent/              # ✅ Security pillar assessments
├── resilience-check-agent/                 # 🔄 Reliability pillar (planned)
└── cost-optimization-agent/                # 💰 Cost optimization (planned)
```

**Current Agents:**
- **Security Assessment Agent**: Comprehensive security posture evaluation
- **Resilience Check Agent**: *Planned* - Fault tolerance and disaster recovery
- **Cost Optimization Agent**: *Planned* - Cost analysis and optimization

### 🔧 MCP Servers
Model Context Protocol servers providing specialized assessment tools.

```
mcp-servers/
├── well-architected-security-mcp-server/           # ✅ Security tools
├── well-architected-reliability-mcp-server/        # 🔄 Reliability tools (planned)
└── well-architected-lens-best-practices-mcp-server/ # 🔍 Lens-specific tools (planned)
```

**Available Tools:**
- **Security MCP Server**: 6 security assessment tools (deployed)
- **Reliability MCP Server**: *Planned* - Fault tolerance, backup, monitoring tools
- **Lens Best Practices Server**: *Planned* - Serverless, SaaS, IoT, ML lens tools

### 🚀 Deployment Scripts
Automated deployment scripts for all components with CI/CD pipeline support.

```
deployment-scripts/
├── buildspecs/                              # External BuildSpec files for CI/CD
│   ├── frontend-buildspec.yml               # Frontend build configuration
│   └── backend-buildspec.yml                # Backend Docker build configuration
├── components/                              # Component-specific deployment scripts
│   ├── deploy_component_wa_security_mcp.py  # WA Security MCP Server
│   ├── deploy_component_chatbot_webapp.py   # Chatbot Web Application
│   ├── deploy_component_aws_api_mcp_server.py # AWS API MCP Server
│   └── deploy_shared_cognito.py             # Shared Cognito infrastructure
├── cloud-optimization-assistant-0.1.0.yaml # Enhanced CloudFormation with CI/CD
├── deploy_chatbot_stack.py                  # Main chatbot stack deployment
├── generate_cognito_ssm_parameters.py       # Cognito configuration management
├── generate_remote_role_stack.py            # Cross-account role template generation
└── update_cognito_callbacks.py              # Cognito callback URL updates
```

## 📚 **Complete Documentation**

For comprehensive guides, configuration details, and advanced setup instructions, visit:
**[📖 Documentation Center](docs/README.md)**

Includes detailed guides for:
- Cross-account role setup and security
- Cognito centralization and authentication
- Parameter Store configuration management
- Architecture diagrams and system design

----

## 🎯 **Well-Architected Pillars Coverage**

| Pillar | Status | Components |
|--------|--------|------------|
| 🔒 **Security** | ✅ **Active** | Security Agent + Security MCP Server |
| 🏗️ **Reliability** | 🔄 **Planned** | Resilience Agent + Reliability MCP Server |
| ⚡ **Performance Efficiency** | 🔄 **Planned** | Performance tools integration |
| 💰 **Cost Optimization** | 🔄 **Planned** | Cost Agent + Cost analysis tools |
| 🔧 **Operational Excellence** | 🔄 **Planned** | Operations tools integration |

## 🚀 **Backend CI/CD Pipeline**

The Cloud Optimization Assistant now includes a complete automated CI/CD pipeline for backend deployment, transforming the static public ECR image deployment into a fully automated containerized deployment system.

### **Pipeline Architecture**

```
S3 Source Upload → EventBridge → CodePipeline → CodeBuild → ECR → ECS → ALB
```

### **Key Features**

- **🔄 Automated Triggers**: S3 upload automatically triggers the entire pipeline
- **🐳 Docker Containerization**: Multi-stage builds with production optimizations
- **🔒 Security First**: VPC endpoints, vulnerability scanning, least-privilege IAM
- **📊 Health Monitoring**: FastAPI `/health` endpoint with dependency validation
- **🛡️ Circuit Breaker**: Automatic rollback on deployment failures
- **📋 External BuildSpecs**: Maintainable build configurations in separate files

### **Pipeline Stages**

1. **Source Stage**: S3 event notification triggers CodePipeline
2. **Build Stage**: Parallel frontend and backend builds
   - Frontend: S3 deployment with CloudFront invalidation
   - Backend: Docker build, test, and ECR push
3. **Deploy Stage**: ECS service update with rolling deployment

### **Security Enhancements**

- **VPC Endpoints**: ECR and S3 traffic routed through private endpoints
- **Vulnerability Scanning**: Automatic ECR image scanning on push
- **Least Privilege IAM**: Specific resource ARNs instead of wildcard permissions
- **Parameter Validation**: S3 bucket existence validation before deployment
- **Health Checks**: Container health validation with automatic rollback

### **Deployment Process**

The CI/CD pipeline follows a 3-stage approach:

1. **Stage 1**: S3 bucket setup with EventBridge configuration
2. **Stage 2**: CloudFormation infrastructure deployment
3. **Stage 3**: Source code upload triggers automated pipeline

```bash
# Deploy infrastructure with CI/CD pipeline
./deploy-coa.sh

# Upload backend code to trigger pipeline
aws s3 cp backend.zip s3://your-source-bucket/backend.zip
```

### **Monitoring & Notifications**

- **CloudWatch Alarms**: Pipeline failures, ECS deployment issues, ECR vulnerabilities
- **SNS Notifications**: Structured notifications for pipeline state changes
- **EventBridge Rules**: Automated pipeline triggering and monitoring
- **Health Endpoints**: Real-time application health monitoring

## 🚀 **Quick Start**

### Complete Platform Deployment
```bash
# Deploy the entire Cloud Optimization Assistant platform
./deploy-coa.sh

# Or with custom configuration
./deploy-coa.sh --stack-name my-coa-stack --region us-west-2 --environment prod
```

### Resume Failed Deployments
```bash
# Check deployment progress
./deploy-coa.sh --show-progress

# Resume from specific stage (if deployment failed)
./deploy-coa.sh --resume-from-stage 4

# Reset progress tracking
./deploy-coa.sh --reset-progress
```

### Manual Component Deployment
```bash
# Deploy individual components (advanced users)
cd deployment-scripts

# Deploy MCP servers
python3 components/deploy_component_wa_security_mcp.py --region us-east-1
python3 components/deploy_component_aws_api_mcp_server.py --region us-east-1

# Deploy Bedrock agent
python3 components/deploy_bedrockagent_wa_security_agent.py --region us-east-1
```

## 🎯 **Deploy-COA.sh - Complete Deployment Automation**

The `deploy-coa.sh` script is the primary deployment tool that orchestrates the entire Cloud Optimization Assistant platform deployment in a single command. It provides intelligent progress tracking, error recovery, and resume capabilities.

### **Key Features**

- **🔄 Resume Capability**: Resume deployments from any failed stage without starting over
- **📊 Progress Tracking**: Visual progress indicators and stage completion tracking
- **🛡️ Conflict Detection**: Automatic detection and resolution of conflicting resources
- **🔧 Prerequisite Validation**: Comprehensive checks for required tools and permissions
- **📋 Multi-Stage Deployment**: Organized into 7 logical deployment stages
- **🎛️ Flexible Configuration**: Support for custom stack names, regions, and environments

### **Deployment Stages**

The script executes deployment in 7 carefully orchestrated stages:

1. **Deploy Chatbot Stack & Update Cognito Callbacks**
   - Deploys main CloudFormation stack with web interface
   - Updates Cognito callback URLs for authentication
   - Deploys frontend files to S3 and configures CloudFront

2. **Generate Cognito SSM Parameters**
   - Extracts Cognito configuration from deployed stack
   - Stores centralized parameters in AWS Systems Manager Parameter Store
   - Enables component integration with shared authentication

3. **Deploy MCP Servers**
   - Deploys AWS API MCP Server for AWS CLI operations
   - Deploys Well-Architected Security MCP Server for security assessments
   - Configures AgentCore Runtime integration

4. **Deploy Bedrock Agent**
   - Creates Bedrock agent with Claude 3.5 Sonnet integration
   - Configures MCP tool integrations for security analysis
   - Sets up agent memory and context management

5. **Generate & Upload Remote IAM Role Template**
   - Generates CloudFormation template for cross-account IAM roles
   - Uploads template to S3 for public access
   - Updates web interface with one-click deployment links

6. **Show Deployment Summary**
   - Displays comprehensive deployment information
   - Provides access URLs and next steps
   - Shows cross-account role deployment instructions

7. **Final Completion**
   - Marks deployment as complete
   - Cleans up progress tracking files
   - Provides final success confirmation

### **Command Line Options**

```bash
Usage: ./deploy-coa.sh [OPTIONS]

OPTIONS:
    -n, --stack-name NAME       CloudFormation stack name (default: cloud-optimization-assistant)
    -r, --region REGION         AWS region (default: us-east-1)
    -e, --environment ENV       Environment: dev, staging, prod (default: prod)
    -p, --profile PROFILE       AWS CLI profile name
    -s, --skip-prerequisites    Skip prerequisite checks
    -c, --cleanup               Clean up existing SSM parameters and CloudFormation stacks
    --resume-from-stage N       Resume deployment from stage N (1-7)
    --show-progress             Show current deployment progress and exit
    --reset-progress            Reset deployment progress tracking
    -h, --help                  Show help message
```

### **Usage Examples**

```bash
# Standard deployment with defaults
./deploy-coa.sh

# Deploy with custom configuration
./deploy-coa.sh --stack-name my-coa-stack --region us-west-2 --environment dev

# Deploy using specific AWS profile
./deploy-coa.sh --profile gameday --environment staging

# Check current deployment progress
./deploy-coa.sh --show-progress

# Resume from stage 3 after failure
./deploy-coa.sh --resume-from-stage 3

# Clean up conflicting resources before deployment
./deploy-coa.sh --cleanup

# Reset progress and start fresh
./deploy-coa.sh --reset-progress
./deploy-coa.sh
```

### **Error Recovery & Resume**

The script provides robust error recovery mechanisms:

#### **Automatic Progress Tracking**
- Each completed stage is recorded with timestamp
- Configuration (stack name, region, environment) is preserved
- Progress file (`.coa-deployment-progress`) tracks deployment state

#### **Resume from Failure**
```bash
# If deployment fails at stage 4, resume with:
./deploy-coa.sh --resume-from-stage 4

# Check what stage failed:
./deploy-coa.sh --show-progress
```

#### **Conflict Resolution**
```bash
# Automatically clean up conflicting resources:
./deploy-coa.sh --cleanup

# Then start fresh deployment:
./deploy-coa.sh
```

### **Prerequisites & Validation**

The script automatically validates:

- **System Requirements**: Bash, AWS CLI v2, Python 3.8+, pip3
- **AWS Credentials**: Valid credentials and appropriate permissions
- **Service Access**: Bedrock model access and service availability
- **Resource Conflicts**: Existing SSM parameters and CloudFormation stacks
- **Service Quotas**: AWS service limits and regional availability

### **Troubleshooting Common Issues**

#### **Deployment Stuck or Failed**
```bash
# Check current status
./deploy-coa.sh --show-progress

# Reset and restart if needed
./deploy-coa.sh --reset-progress
./deploy-coa.sh
```

#### **AWS Credential Issues**
```bash
# Verify credentials
aws sts get-caller-identity

# Use specific profile
./deploy-coa.sh --profile your-profile-name
```

#### **Resource Conflicts**
```bash
# Clean up automatically
./deploy-coa.sh --cleanup

# Or manually check conflicts
aws ssm get-parameters-by-path --path /coa/ --recursive
```

#### **Permission Errors**
The script requires these AWS permissions:
- CloudFormation: Full access for stack management
- Cognito: Full access for user pool management
- S3: Full access for frontend deployment
- Bedrock: Full access for agent creation
- AgentCore: Full access for MCP server deployment
- IAM: Role creation and policy attachment
- Systems Manager: Parameter Store access

### **Generated Files & Artifacts**

The deployment creates several important files:

- **`.coa-deployment-progress`**: Progress tracking (auto-managed)
- **`generated-templates/`**: Cross-account role CloudFormation templates
- **Parameter Store**: Centralized configuration at `/coa/*` paths
- **S3 Templates**: Public templates for cross-account role deployment

### **Security Considerations**

- **Cross-account roles**: Use read-only permissions for security analysis
- **Cognito integration**: Centralized authentication across all components
- **Parameter encryption**: Sensitive configuration stored securely in Parameter Store
- **IAM least privilege**: Minimal required permissions for each component

## 🛠️ **Current Capabilities**

### ✅ **Available Now**
- **Web Interface**: Full-featured cloud optimization assistant
- **Security Assessment**: Comprehensive security posture evaluation
- **MCP Integration**: 6 security assessment tools via MCP protocol
- **Real-time Chat**: Natural language interaction with Claude 3.5 Sonnet

### 🔄 **Coming Soon**
- **Cost Optimization**: Automated cost analysis and recommendations
- **Reliability Assessment**: Fault tolerance and disaster recovery evaluation
- **Performance Analysis**: Performance efficiency optimization
- **Multi-Lens Support**: Serverless, SaaS, IoT, ML lens assessments

## 📊 **Assessment Types**

### Security Assessment
- Security services status (GuardDuty, Security Hub, Inspector, Macie)
- Security findings analysis and prioritization
- Encryption configuration review (S3, EBS, RDS)
- Network security assessment (VPC, Security Groups, NACLs)
- Compliance and governance review

### Future Assessments
- **Cost Analysis**: Right-sizing, Reserved Instances, Spot opportunities
- **Reliability Review**: Multi-AZ, backup strategies, monitoring
- **Performance Optimization**: Compute, storage, network efficiency
- **Operational Excellence**: Automation, change management, monitoring

## 🔧 **Technology Stack**

- **Frontend**: HTML5, JavaScript, WebSocket
- **Backend**: FastAPI, Python 3.11+, Docker containers
- **AI/ML**: Amazon Bedrock (Claude 3 Haiku, Claude 3.5 Sonnet)
- **Integration**: Model Context Protocol (MCP)
- **Deployment**: AWS CloudFormation, Bedrock Agents
- **CI/CD Pipeline**: CodePipeline, CodeBuild, ECR, ECS
- **Container Orchestration**: Amazon ECS with Application Load Balancer
- **Authentication**: AWS Cognito (centralized user pool)
- **Configuration**: AWS Systems Manager Parameter Store
- **Cross-Account Access**: IAM roles with read-only permissions
- **Infrastructure**: S3, CloudFront, Lambda, API Gateway, VPC Endpoints
- **Security**: ECR vulnerability scanning, VPC endpoints, least-privilege IAM

## 🛠️ **Troubleshooting**

### Quick Troubleshooting Guide

For comprehensive troubleshooting, see the **Deploy-COA.sh** section above. Here are the most common issues:

#### 1. Deployment Issues
```bash
# Check current status and resume if needed
./deploy-coa.sh --show-progress
./deploy-coa.sh --resume-from-stage N
```

#### 2. Resource Conflicts
```bash
# Clean up conflicting resources automatically
./deploy-coa.sh --cleanup
```

#### 3. AWS Credentials
```bash
# Verify credentials and use specific profile if needed
aws sts get-caller-identity
./deploy-coa.sh --profile your-profile-name
```

#### 4. Cross-Account Role Issues
```bash
# Test and validate remote role generation
python3 deployment-scripts/generate_remote_role_stack.py --role-name CrossAccountMCPRole
aws cloudformation validate-template --template-body file://generated-templates/remote-role-stack/template.yaml
```

### Log Locations
- **CloudFormation Events**: AWS Console → CloudFormation → Stack → Events
- **CloudWatch Logs**: AWS Console → CloudWatch → Log Groups  
- **Deployment Progress**: `.coa-deployment-progress` file

## 🔒 **Security Notes**

### Configuration Files
- **AgentCore configuration files** (`.bedrock_agentcore.yaml`) contain sensitive AWS information and are excluded from version control
- **Deployment scripts** create these files automatically during deployment
- **Never commit** files containing AWS account IDs, ARNs, or authentication details

## 🔄 **Advanced Deployment Features**

### Cross-Account Role Deployment
The platform supports deploying read-only IAM roles to target AWS accounts for security analysis:

```bash
# Generate cross-account role template
python3 deployment-scripts/generate_remote_role_stack.py --role-name CrossAccountMCPRole

# Deploy using one-click links in web interface
# Or manually deploy the generated CloudFormation template
```

### Multi-Environment Support
Deploy to different environments with appropriate configurations:

```bash
# Development environment
./deploy-coa.sh --environment dev --stack-name coa-dev

# Staging environment  
./deploy-coa.sh --environment staging --stack-name coa-staging

# Production environment
./deploy-coa.sh --environment prod --stack-name coa-prod
```

## 📋 **Latest Features & Updates**

### 🚀 **NEW: Backend CI/CD Pipeline** 
- **Automated Container Deployment**: Complete S3 → CodePipeline → CodeBuild → ECR → ECS flow
- **Production-Ready Containers**: Multi-stage Docker builds with security best practices
- **Health Check Integration**: FastAPI `/health` endpoint with dependency validation
- **VPC Security**: ECR and S3 access through VPC endpoints for network isolation
- **Vulnerability Scanning**: Automatic ECR image scanning with lifecycle policies
- **Circuit Breaker Deployment**: ECS deployment with automatic rollback on health check failures
- **Least-Privilege IAM**: Specific resource ARNs instead of wildcard permissions
- **External BuildSpecs**: Maintainable build configurations in separate files

### Enhanced Deployment Automation
- **🚀 One-Command Deployment**: Complete platform deployment with `./deploy-coa.sh`
- **🔄 Intelligent Resume**: Resume from any failed stage without starting over
- **📊 Progress Tracking**: Visual progress indicators and comprehensive status reporting
- **🛡️ Conflict Detection**: Automatic detection and resolution of resource conflicts
- **🎛️ Multi-Environment**: Support for dev, staging, and production environments

### Cross-Account Integration
- **📋 Template Generation**: Automated CloudFormation template creation for target accounts
- **🔗 One-Click Deployment**: Direct deployment links integrated in web interface
- **🔒 Security-First**: Read-only permissions with least privilege access
- **📤 S3 Integration**: Automatic template upload and public access configuration

### Centralized Configuration
- **🗄️ Parameter Store**: Centralized configuration management at `/coa/*` paths
- **🔐 Cognito Integration**: Shared authentication across all components
- **🔧 Component Discovery**: Automatic service discovery and integration
- **📝 Configuration Validation**: Comprehensive validation and error checking

## 📈 **Roadmap**

### Phase 1: Security Foundation ✅
- [x] Security assessment web interface
- [x] Security MCP server with comprehensive tools
- [x] Bedrock agent with multi-MCP integration
- [x] Cross-account role deployment
- [x] Resume-capable deployment system
- [x] Centralized authentication and configuration
- [x] **Backend CI/CD Pipeline**: Complete automated deployment with Docker containers
- [x] **Production Security**: VPC endpoints, vulnerability scanning, health checks

### Phase 2: Enhanced Security & Operations 🔄
- [x] Enhanced cross-account capabilities
- [ ] Advanced security analysis and reporting
- [ ] Automated remediation suggestions

### Phase 3: Multi-Pillar Expansion 🔮
- [ ] Cost optimization analysis
- [ ] Reliability assessment capabilities
- [ ] Operational excellence evaluation (EKS)
- [ ] Multi-lens assessments (Serverless, SaaS, IoT, ML)
- [ ] Performance analysis (RDS - Performance Insight)

## 📁 **Generated Files and Directories**

The deployment process creates several files and directories:

### Deployment Tracking
- **`.coa-deployment-progress`**: Progress tracking file (automatically managed)
- **`generated-templates/`**: CloudFormation templates for cross-account roles
- **`deployment-scripts/logs/`**: Deployment logs and debug information

### Configuration Files
- **Parameter Store**: `/coa/cognito/*`, `/coa/components/*`, `/coa/agent/*` parameters
- **S3 Templates**: Cross-account role templates uploaded to deployment bucket
- **Frontend Updates**: Automatic updates to deployment links in web interface

### Security Considerations
- **AgentCore configuration files** contain sensitive AWS information and are excluded from version control
- **Deployment scripts** create configuration files automatically during deployment
- **Never commit** files containing AWS account IDs, ARNs, or authentication details
- **Cross-account roles** use read-only permissions only for security analysis

## 🤝 **Contributing**

### Development Guidelines
Each component has its own development guidelines:
- **Web interfaces**: See `cloud-optimization-web-interfaces/*/README.md`
- **Bedrock agents**: See `agents/bedrock-agents/*/README.md`
- **MCP servers**: See `mcp-servers/*/README.md`
- **Deployment scripts**: See [deployment-scripts/README.md](deployment-scripts/README.md)

### Documentation
- **Complete guides**: See [Documentation Center](docs/README.md)
- **API documentation**: Component-specific README files
- **Architecture**: Interactive diagram at `docs/architecture_diagram.html`

### Testing
```bash
# Test deployment configuration
./validate-deploy-coa.sh

# Test remote role generation
./test-remote-role-generation.sh

# Run component tests
cd test-files/
python3 test_complete_json_integration.py
```

## 📄 **License**

This project follows AWS sample code guidelines and is provided for educational and demonstration purposes.

---

## 🎯 **Get Started Today**

1. **Deploy the Platform**: `./deploy-coa.sh`
2. **Access the Web Interface**: Use the CloudFront URL from deployment output
3. **Deploy Cross-Account Roles**: Use the one-click deployment link in the web interface
4. **Start Security Analysis**: Begin comprehensive AWS security assessments

For detailed setup instructions, troubleshooting, and advanced configuration, visit the **[📖 Documentation Center](docs/README.md)**.

---

**🛡️ Cloud Optimization Assistant - Secure, Scalable, Intelligent AWS Security Analysis**
