# Cloud Optimization Assistant

A comprehensive platform for AWS security analysis and cloud optimization using Amazon Bedrock agents and Model Context Protocol (MCP) servers.

## 📚 **Complete Documentation**

For comprehensive guides, configuration details, and advanced setup instructions, visit:
**[📖 Documentation Center](docs/README.md)**

Includes detailed guides for:
- Cross-account role setup and security
- Cognito centralization and authentication
- Parameter Store configuration management
- Architecture diagrams and system design

## 🏗️ **Architecture Overview**

```
/
├── 🌐 cloud-optimization-web-interfaces/    # Web interfaces for user interaction
├── 🤖 agents/                               # Agents for specialized assessments
|         ├──bedrock-agents/                 # Bedrock agent set (to be deployed into Bedrock Agent)
|         |   ├──wa-security-agent-multi-mcps/
|         |   |                              # Multi-MCP (WA_SEC + AWS_API + AWS_Knowledge)
|         |   ├──wa-security-agent-single-wa-sec-mcp/
|         |   |                              # Single-MCP (WA_SEC)
|         |   └──examples/
|         └──strads-agents/                  # Bedrock agent set (to be deployed into Bedrock AgentCore Runtime)
├── 🔧 mcp-servers/                          # MCP servers providing assessment tools
|         └──well-architected-security-mcp-server/
└── 🚀 deployment-scripts/                   # Deployment automation scripts
```

## 📁 **Directory Structure**

### 🌐 Cloud Optimization Web Interfaces
Interactive web applications for cloud optimization assessments.

```
cloud-optimization-web-interfaces/
└── cloud-optimization-web-interface/       # Main web interface
    ├── backend/                            # FastAPI backend
    ├── frontend/                           # HTML/JS frontend
    └── tests/                              # Integration tests
```

**Features:**
- Real-time chat interface with Claude 3.5 Sonnet
- WebSocket communication for instant responses
- Multi-pillar optimization assessments
- Interactive dashboards and reports

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
Automated deployment scripts for all components.

```
deployment-scripts/
├── deploy_wa_security_direct.py            # Direct MCP server deployment
├── deploy_wa_security_mcp.py               # AgentCore MCP deployment
├── deploy_mcp_server.py                    # Generic MCP server deployment
└── deploy_security_agent.py                # Bedrock agent deployment
```

## 🎯 **Well-Architected Pillars Coverage**

| Pillar | Status | Components |
|--------|--------|------------|
| 🔒 **Security** | ✅ **Active** | Security Agent + Security MCP Server |
| 🏗️ **Reliability** | 🔄 **Planned** | Resilience Agent + Reliability MCP Server |
| ⚡ **Performance Efficiency** | 🔄 **Planned** | Performance tools integration |
| 💰 **Cost Optimization** | 🔄 **Planned** | Cost Agent + Cost analysis tools |
| 🔧 **Operational Excellence** | 🔄 **Planned** | Operations tools integration |

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
- **Backend**: FastAPI, Python 3.8+
- **AI/ML**: Amazon Bedrock (Claude 3 Haiku, Claude 3.5 Sonnet)
- **Integration**: Model Context Protocol (MCP)
- **Deployment**: AWS CloudFormation, Bedrock Agents
- **Authentication**: AWS Cognito (centralized user pool)
- **Configuration**: AWS Systems Manager Parameter Store
- **Cross-Account Access**: IAM roles with read-only permissions
- **Infrastructure**: S3, CloudFront, Lambda, API Gateway

## 🛠️ **Troubleshooting**

### Common Deployment Issues

#### 1. Deployment Progress Issues
```bash
# Check current deployment status
./deploy-coa.sh --show-progress

# If no progress found, start fresh deployment
./deploy-coa.sh

# If deployment stuck, reset and restart
./deploy-coa.sh --reset-progress
./deploy-coa.sh
```

#### 2. AWS Credential Problems
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check AWS profile (if using profiles)
aws sts get-caller-identity --profile your-profile-name

# Configure credentials if needed
aws configure
```

#### 3. Parameter Store Configuration Issues
```bash
# Validate Cognito parameters
python3 deployment-scripts/generate_cognito_ssm_parameters.py --validate

# Check all COA parameters
aws ssm get-parameters-by-path --path /coa/ --recursive

# Regenerate parameters if needed
python3 deployment-scripts/generate_cognito_ssm_parameters.py --stack-name your-stack-name
```

#### 4. Cross-Account Role Deployment
```bash
# Test remote role generation
./test-remote-role-generation.sh

# Manually generate template
python3 deployment-scripts/generate_remote_role_stack.py --role-name CrossAccountMCPRole

# Validate CloudFormation template
aws cloudformation validate-template --template-body file://generated-templates/remote-role-stack/template.yaml
```

### Error Recovery

#### Stage-Specific Recovery
- **Stage 1 Failure**: Check CloudFormation stack status and IAM permissions
- **Stage 2 Failure**: Verify Parameter Store access permissions
- **Stage 3 Failure**: Check MCP server deployment logs
- **Stage 4 Failure**: Verify Bedrock service access and model permissions
- **Stage 5 Failure**: Check S3 bucket permissions and template generation

#### Log Locations
- **CloudFormation Events**: AWS Console → CloudFormation → Stack → Events
- **CloudWatch Logs**: AWS Console → CloudWatch → Log Groups
- **Deployment Logs**: Local terminal output and `.coa-deployment-progress` file

### Best Practices for Troubleshooting

1. **Always check progress first**: `./deploy-coa.sh --show-progress`
2. **Review AWS permissions**: Ensure adequate IAM permissions for all services
3. **Check service quotas**: Verify AWS service limits haven't been exceeded
4. **Monitor CloudFormation**: Watch stack events for detailed error information
5. **Use resume functionality**: Don't restart from scratch unless necessary

## 🔒 **Security Notes**

### Configuration Files
- **AgentCore configuration files** (`.bedrock_agentcore.yaml`) contain sensitive AWS information and are excluded from version control
- **Deployment scripts** create these files automatically during deployment
- **Never commit** files containing AWS account IDs, ARNs, or authentication details

## 🔄 **Deployment Resume Functionality**

The deployment script supports resuming from specific stages when failures occur, saving time and avoiding re-running successful steps.

### Deployment Stages

The deployment is divided into 7 stages:

1. **Deploy chatbot stack and update Cognito callbacks**
   - Deploys the main CloudFormation stack
   - Updates Cognito callback URLs
   - Deploys frontend files to S3

2. **Generate Cognito SSM parameters**
   - Extracts Cognito configuration from the deployed stack
   - Stores parameters in AWS Systems Manager Parameter Store

3. **Deploy MCP servers**
   - Deploys AWS API MCP Server
   - Deploys WA Security MCP Server

4. **Deploy Bedrock agent**
   - Deploys the Bedrock agent with MCP integrations

5. **Generate and upload remote IAM role template**
   - Generates CloudFormation template for cross-account IAM roles
   - Uploads template to S3 for public access

6. **Show deployment summary**
   - Displays deployment information and next steps

7. **Final completion**
   - Marks deployment as complete and cleans up progress tracking

### Resume Commands

```bash
# Check current deployment status
./deploy-coa.sh --show-progress

# Resume from stage 4 (if deployment failed at stage 4)
./deploy-coa.sh --resume-from-stage 4

# Reset progress tracking to start fresh
./deploy-coa.sh --reset-progress
```

### Progress Tracking Features

- **Automatic Progress Saving**: Each completed stage is recorded with timestamp
- **Configuration Preservation**: Stack name, region, environment, and AWS profile are preserved
- **Error Recovery**: Clear instructions provided when stages fail
- **Validation**: Prevents resuming from invalid stages

## 📋 **Recent Deployment Updates**

### Enhanced Deployment Process
- **Resume Functionality**: Resume deployments from specific stages after failures
- **Progress Tracking**: Visual progress indicators and stage completion tracking
- **Cross-Account Role Generation**: Automated CloudFormation template generation for target accounts
- **One-Click Deployment**: Direct CloudFormation deployment links in web interface

### New Helper Scripts
- **`test-remote-role-generation.sh`**: Test remote role template generation
- **`update-template-url.sh`**: Manually update deployment links in frontend
- **`validate-deploy-coa.sh`**: Validate deployment configuration

### Automated Features
- **S3 Template Upload**: Automatic upload of cross-account role templates
- **Frontend Integration**: Automatic update of deployment links in web interface
- **Parameter Store Integration**: Centralized configuration management
- **Error Handling**: Comprehensive error checking and recovery options

## 📈 **Roadmap**

### Phase 1: Security Foundation ✅
- [x] Security assessment web interface
- [x] Security MCP server with comprehensive tools
- [x] Bedrock agent with multi-MCP integration
- [x] Cross-account role deployment
- [x] Resume-capable deployment system
- [x] Centralized authentication and configuration

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
