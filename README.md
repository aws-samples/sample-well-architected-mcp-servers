# AWS Well-Architected Cloud Optimization Suite

A comprehensive suite of tools for AWS cloud optimization assessments using Amazon Bedrock and Model Context Protocol (MCP) integration.

## 🏗️ **Architecture Overview**

```
/
├── 🌐 cloud-optimization-web-interfaces/    # Web interfaces for user interaction
├── 🤖 bedrock-agents/                       # Bedrock agents for specialized assessments
├── 🔧 mcp-servers/                          # MCP servers providing assessment tools
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

### 1. Launch Web Interface
```bash
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface
python3 start_server.py
```

### 2. Deploy Security Assessment Agent
```bash
cd deployment-scripts
python3 deploy_security_agent.py
```

### 3. Deploy Security MCP Server
```bash
cd deployment-scripts
python3 deploy_wa_security_mcp.py
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
- **AI/ML**: Amazon Bedrock (Claude 3.5 Sonnet)
- **Integration**: Model Context Protocol (MCP)
- **Deployment**: AWS AgentCore Runtime
- **Authentication**: AWS Cognito (JWT tokens)

## 🔒 **Security Notes**

### Configuration Files
- **AgentCore configuration files** (`.bedrock_agentcore.yaml`) contain sensitive AWS information and are excluded from version control
- **Deployment scripts** create these files automatically during deployment
- **Never commit** files containing AWS account IDs, ARNs, or authentication details

## 📈 **Roadmap**

### Phase 1: Security Foundation ✅
- [x] Security assessment web interface
- [x] Security MCP server with 6 tools
- [x] Bedrock agent integration
- [x] Real-time chat capabilities

### Phase 2: Multi-Pillar Expansion 🔄
- [ ] Cost optimization agent and tools
- [ ] Reliability assessment capabilities
- [ ] Performance efficiency analysis
- [ ] Operational excellence evaluation

### Phase 3: Advanced Features 🔮
- [ ] Multi-lens assessments (Serverless, SaaS, IoT, ML)
- [ ] Automated remediation suggestions
- [ ] Integration with AWS Config and Systems Manager
- [ ] Advanced reporting and dashboards

## 🤝 **Contributing**

Each component has its own development guidelines:
- Web interfaces: See `cloud-optimization-web-interfaces/*/README.md`
- Bedrock agents: See `bedrock-agents/*/README.md`
- MCP servers: See `mcp-servers/*/README.md`

## 📄 **License**

This project follows AWS sample code guidelines and is provided for educational and demonstration purposes.

---

**🎯 Ready to optimize your AWS infrastructure with AI-powered insights across all Well-Architected pillars!**
