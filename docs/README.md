# Cloud Optimization Assistant - Documentation

Welcome to the comprehensive documentation for the Cloud Optimization Assistant platform.

## 📚 Documentation Index

### 📋 Core Documentation (This Folder)
- **[Architecture Diagram](architecture_diagram.html)** - Interactive HTML diagram showing system architecture
- **[Cognito Centralization Guide](cognito-centralization-guide.md)** - Complete guide for shared Cognito user pool implementation
- **[Cross-Account Role Setup](cross-account-role-setup.md)** - Comprehensive guide for cross-account IAM role deployment and security
- **[Parameter Store Configuration](parameter-store-configuration.md)** - Complete guide to Parameter Store usage and configuration management

### 🏗️ Architecture & Design
- **[Main README](../README.md)** - Project overview and quick start guide
- **[Deployment Resume Guide](../DEPLOYMENT_RESUME_GUIDE.md)** - Guide for resuming failed deployments
- **[Deployment Updates](../DEPLOYMENT_UPDATES.md)** - Latest deployment improvements and changes

### 🤖 Bedrock Agents
- **[WA Security Agent Multi-MCPs](../agents/bedrock-agents/wa-security-agent-multi-mcps/)** - Enhanced security agent with multiple MCP integrations
- **[Agent Configuration](../agents/bedrock-agents/wa-security-agent-multi-mcps/agent_config/)** - Agent orchestration and integration configurations
- **[Agent Tests](../agents/bedrock-agents/wa-security-agent-multi-mcps/tests/)** - Comprehensive test suite for agent functionality

### 🔧 MCP Servers
- **[Well-Architected Security MCP Server](../mcp-servers/well-architected-security-mcp-server/README.md)** - Security assessment tools and capabilities
- **[MCP Server Implementation](../mcp-servers/well-architected-security-mcp-server/src/)** - Source code and implementation details

### 🌐 Web Interfaces
- **[Cloud Optimization Web Interface](../cloud-optimization-web-interfaces/cloud-optimization-web-interface/README.md)** - Interactive web application
- **[Frontend Interface](../cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend/index.html)** - User interface with deployment links
- **[Backend Services](../cloud-optimization-web-interfaces/cloud-optimization-web-interface/backend/)** - API services and configuration

### 🚀 Deployment & Setup
- **[Main Deployment Script](../deploy-coa.sh)** - Primary deployment script with resume functionality
- **[Deployment Scripts](../deployment-scripts/)** - Automated deployment components and utilities
- **[Component Deployment](../deployment-scripts/components/)** - Individual component deployment scripts
- **[Remote Role Generation](../deployment-scripts/generate_remote_role_stack.py)** - Cross-account role template generator

### 🧪 Testing & Validation
- **[Test Files](../test-files/)** - Development and integration test files
- **[Validation Scripts](../validate-deploy-coa.sh)** - Deployment validation utilities

## 🎯 Quick Navigation

### For Developers
1. **Getting Started**: [Main README](../README.md) → [Architecture Diagram](architecture_diagram.html)
2. **Configuration**: [Parameter Store Guide](parameter-store-configuration.md) → [Cognito Setup](cognito-centralization-guide.md)
3. **Implementation**: Component-specific documentation in respective directories

### For Security Teams
1. **Security Agent**: [WA Security Agent](../agents/bedrock-agents/wa-security-agent-multi-mcps/)
2. **MCP Tools**: [Security MCP Server](../mcp-servers/well-architected-security-mcp-server/README.md)
3. **Cross-Account Access**: [Cross-Account Role Setup](cross-account-role-setup.md)
4. **Web Interface**: [Cloud Optimization Interface](../cloud-optimization-web-interfaces/cloud-optimization-web-interface/README.md)

### For DevOps/Deployment
1. **Primary Deployment**: [Main Deployment Script](../deploy-coa.sh) → [Resume Guide](../DEPLOYMENT_RESUME_GUIDE.md)
2. **Cross-Account Setup**: [Cross-Account Role Setup](cross-account-role-setup.md)
3. **Configuration Management**: [Parameter Store Guide](parameter-store-configuration.md)
4. **Authentication**: [Cognito Centralization](cognito-centralization-guide.md)
5. **Component Deployment**: [Deployment Scripts](../deployment-scripts/)

### For System Administrators
1. **Authentication Setup**: [Cognito Centralization Guide](cognito-centralization-guide.md)
2. **Configuration Management**: [Parameter Store Configuration](parameter-store-configuration.md)
3. **Cross-Account Security**: [Cross-Account Role Setup](cross-account-role-setup.md)
4. **Troubleshooting**: [Deployment Resume Guide](../DEPLOYMENT_RESUME_GUIDE.md)

## 📊 Component Overview

| Component | Status | Documentation | Purpose |
|-----------|--------|---------------|---------|
| **Web Interface** | ✅ Active | [Frontend](../cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend/index.html) | User interaction and visualization |
| **WA Security Agent** | ✅ Active | [Multi-MCP Agent](../agents/bedrock-agents/wa-security-agent-multi-mcps/) | AI-powered security assessments with multiple MCP integrations |
| **Security MCP Server** | ✅ Active | [MCP Server](../mcp-servers/well-architected-security-mcp-server/README.md) | Security assessment tools and capabilities |
| **Deployment System** | ✅ Active | [Main Script](../deploy-coa.sh) | Automated deployment with resume functionality |
| **Cross-Account Roles** | ✅ Active | [Setup Guide](cross-account-role-setup.md) | Read-only IAM roles for cross-account analysis |
| **Authentication** | ✅ Active | [Cognito Guide](cognito-centralization-guide.md) | Centralized user authentication |
| **Configuration** | ✅ Active | [Parameter Store](parameter-store-configuration.md) | Centralized configuration management |

## 🔄 Recent Updates

### Deployment System Enhancements (Latest)
- **Resume Functionality**: Resume deployments from specific stages after failures
- **Progress Tracking**: Visual progress indicators and stage completion tracking
- **Parameter Store Integration**: Centralized configuration management across all components
- **Cross-Account Role Generation**: Automated CloudFormation template generation for target accounts

### Authentication & Configuration
- **Centralized Cognito**: Shared user pool across all components with automatic Parameter Store integration
- **Multi-Namespace Parameters**: Organized parameter hierarchy for different component types
- **Configuration Discovery**: Automatic configuration discovery without manual setup

### Security & Cross-Account Access
- **Read-Only Cross-Account Roles**: Secure, auditable access to target AWS accounts
- **Data Privacy Protection**: No data access permissions, only metadata and configuration analysis
- **MCP Server Integration**: Enhanced cross-account capabilities for security analysis

### Web Interface & User Experience
- **One-Click Deployment**: Direct CloudFormation deployment links for cross-account roles
- **Enhanced UI**: Improved user interface with better navigation and status indicators
- **Real-time Integration**: Seamless integration with backend services and Bedrock agents

## 🎉 Getting Started

1. **Explore Architecture**: Open [Architecture Diagram](architecture_diagram.html) in your browser
2. **Read Overview**: Start with [Main README](../README.md)
3. **Deploy the Platform**: Use [Main Deployment Script](../deploy-coa.sh) for complete setup
4. **Choose Your Focus**:
   - **Security Analysis**: [Cross-Account Role Setup](cross-account-role-setup.md) → [WA Security Agent](../agents/bedrock-agents/wa-security-agent-multi-mcps/)
   - **Configuration Management**: [Parameter Store Guide](parameter-store-configuration.md) → [Cognito Setup](cognito-centralization-guide.md)
   - **Development**: Component-specific documentation in respective directories
   - **Troubleshooting**: [Deployment Resume Guide](../DEPLOYMENT_RESUME_GUIDE.md)

## 📖 Documentation Quick Reference

### Essential Guides
- **[Cross-Account Role Setup](cross-account-role-setup.md)** - Complete guide for secure cross-account access
- **[Cognito Centralization Guide](cognito-centralization-guide.md)** - Shared authentication setup and migration
- **[Parameter Store Configuration](parameter-store-configuration.md)** - Centralized configuration management

### Architecture & Deployment
- **[Architecture Diagram](architecture_diagram.html)** - Interactive system architecture visualization
- **[Main Deployment Script](../deploy-coa.sh)** - Primary deployment with resume functionality
- **[Deployment Resume Guide](../DEPLOYMENT_RESUME_GUIDE.md)** - Handling deployment failures and recovery

## 📞 Support & Troubleshooting

For questions, issues, or contributions:

### Documentation Resources
- **Configuration Issues**: [Parameter Store Configuration](parameter-store-configuration.md)
- **Authentication Problems**: [Cognito Centralization Guide](cognito-centralization-guide.md)
- **Cross-Account Access**: [Cross-Account Role Setup](cross-account-role-setup.md)
- **Deployment Failures**: [Deployment Resume Guide](../DEPLOYMENT_RESUME_GUIDE.md)

### Technical Resources
- **Architecture Understanding**: [Architecture Diagram](architecture_diagram.html)
- **Component Documentation**: Component-specific READMEs in respective directories
- **Test Examples**: [Test Files](../test-files/) for usage examples
- **Deployment Scripts**: [Deployment Scripts](../deployment-scripts/) for automation details

### Common Issues
1. **Deployment Failures**: Use `./deploy-coa.sh --show-progress` and `--resume-from-stage N`
2. **Authentication Issues**: Check [Cognito Centralization Guide](cognito-centralization-guide.md)
3. **Cross-Account Access**: Verify roles using [Cross-Account Role Setup](cross-account-role-setup.md)
4. **Configuration Problems**: Review [Parameter Store Configuration](parameter-store-configuration.md)

---

**🛡️ Cloud Optimization Assistant - Secure, Scalable, Intelligent AWS Security Analysis**
