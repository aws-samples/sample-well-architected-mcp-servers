# Enhanced Security Agent with Multi-MCP Integration

The Enhanced Security Agent represents a significant evolution of AWS security assessment capabilities, combining multiple Model Context Protocol (MCP) servers to provide comprehensive, intelligent security guidance.

## Overview

This enhanced agent orchestrates three specialized MCP servers to deliver the most comprehensive AWS security assessments possible:

1. **Security MCP Server** - Real-time AWS security data and assessments
2. **AWS Knowledge MCP Server** - Official AWS documentation and best practices
3. **AWS API MCP Server** - Direct AWS service interactions and detailed resource analysis

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                Enhanced Security Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ MCP Orchestrator│  │ Response Engine │  │ Session Manager │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Security MCP   │  │AWS Knowledge MCP│  │  AWS API MCP    │  │
│  │     Server      │  │     Server      │  │     Server      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 🔄 Multi-MCP Orchestration
- Intelligent routing of queries to appropriate MCP servers
- Parallel execution for optimal performance
- Graceful degradation when servers are unavailable
- Circuit breaker patterns for resilience

### 🧠 Enhanced Intelligence
- Combines real-time security data with authoritative AWS documentation
- Context-aware recommendations based on session history
- Risk-based prioritization aligned with AWS Well-Architected principles
- Executive summaries with business impact analysis

### 🛡️ Comprehensive Security Coverage
- Real-time security service status and findings
- Storage and network encryption analysis
- Compliance framework alignment
- Automated remediation guidance with safety checks

### 📚 Knowledge Integration
- Automatic reference to official AWS documentation
- Best practices guidance for every recommendation
- Implementation steps with detailed AWS guidance
- Links to relevant compliance and security frameworks

## Directory Structure

```
bedrock-agents/enhanced-security-agent/
├── agent_config/
│   ├── __init__.py                    # Package initialization
│   ├── enhanced_security_agent.py     # Main agent implementation
│   ├── interfaces.py                  # Core interfaces and data models
│   ├── config.py                      # Configuration management
│   ├── orchestration/                 # MCP orchestration layer
│   │   └── __init__.py
│   ├── integrations/                  # MCP server integrations
│   │   └── __init__.py
│   ├── response/                      # Response processing
│   │   └── __init__.py
│   ├── session/                       # Session management
│   │   └── __init__.py
│   └── utils/                         # Utility functions
│       ├── __init__.py
│       ├── error_handling.py          # Error handling and recovery
│       └── logging_utils.py           # Structured logging
├── requirements.txt                   # Python dependencies
├── deploy_enhanced_security_agent.py # Deployment script
└── README.md                         # This file
```

## Core Interfaces

### MCPOrchestrator
Manages connections and interactions with multiple MCP servers:
- `initialize_connections()` - Set up all MCP server connections
- `execute_parallel_calls()` - Execute multiple tool calls in parallel
- `discover_all_tools()` - Discover tools across all MCP servers
- `health_check_all()` - Monitor health of all MCP servers

### DataSynthesizer
Intelligently combines data from multiple sources:
- `synthesize_security_assessment()` - Combine multi-source security data
- `resolve_conflicts()` - Handle conflicting information
- `prioritize_recommendations()` - Risk-based recommendation prioritization
- `generate_executive_summary()` - Business-focused summaries

### ResponseEngine
Transforms raw data into intelligent responses:
- `transform_multi_source_response()` - Create coherent responses from multiple sources
- `create_contextual_analysis()` - Add session context to responses
- `generate_action_plan()` - Create actionable implementation plans
- `format_with_documentation_links()` - Integrate AWS documentation references

## Configuration Management

The enhanced agent uses a sophisticated configuration system supporting:

- **Environment-specific configurations** (development, staging, production)
- **Dynamic MCP server discovery** and connection management
- **Feature flags** for enabling/disabling capabilities
- **Secure credential management** through AWS Secrets Manager
- **Health monitoring** and automatic recovery

### Key Configuration Components

```python
@dataclass
class EnhancedMCPServerConfig:
    name: str
    server_type: MCPServerType
    connection_type: str
    auth_config: AuthConfig
    retry_config: RetryConfig
    health_check_config: HealthCheckConfig
    feature_flags: Dict[str, bool]
    region_specific: Dict[str, Any]
```

## Error Handling and Resilience

### Circuit Breaker Pattern
- Automatically disables failing MCP servers
- Implements recovery mechanisms with health checks
- Provides graceful degradation with fallback responses

### Retry Logic
- Exponential backoff with jitter
- Configurable retry attempts per MCP server
- Smart retry logic based on error types

### Comprehensive Error Types
- Connection errors with network troubleshooting
- Authentication errors with credential guidance
- Rate limiting with intelligent queuing
- Timeout errors with performance optimization
- Permission errors with IAM guidance

## Deployment

### Prerequisites
1. AWS CLI configured with appropriate permissions
2. Python 3.9+ with required dependencies
3. Existing Security MCP Server deployment (optional but recommended)

### Quick Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Deploy the enhanced agent
python deploy_enhanced_security_agent.py --region us-east-1

# Validate deployment
python deploy_enhanced_security_agent.py --validate --agent-id <agent-id>
```

### Configuration Parameters

The deployment script automatically configures:
- IAM roles with least-privilege permissions
- SSM parameters for feature flags and MCP server settings
- Secrets Manager integration for secure credential storage
- CloudWatch logging for monitoring and debugging

## Usage Examples

### Comprehensive Security Assessment
```
"Perform a comprehensive security assessment of my AWS environment"
```
**Response includes:**
- Real-time security service status
- Storage encryption analysis
- Network security configuration
- AWS documentation references
- Prioritized remediation plan

### Service-Specific Analysis
```
"Analyze my S3 bucket security configuration"
```
**Response includes:**
- Current S3 encryption status
- Bucket policy analysis
- AWS S3 security best practices
- Step-by-step remediation guide
- Links to official AWS S3 security documentation

### Compliance Guidance
```
"Help me align with AWS Well-Architected Security Pillar"
```
**Response includes:**
- Current security posture assessment
- Well-Architected Framework alignment
- Gap analysis with official AWS guidance
- Implementation roadmap with documentation links
- Executive summary for stakeholders

## Monitoring and Observability

### Structured Logging
- All MCP interactions logged with performance metrics
- Error tracking with context and recovery suggestions
- Session-based analytics for user behavior insights

### Performance Metrics
- Response time tracking across all MCP servers
- Success/failure rates for each integration
- Resource utilization and optimization recommendations

### Health Monitoring
- Continuous health checks for all MCP servers
- Automatic recovery mechanisms
- Alert generation for service degradation

## Development and Testing

### Running Tests
```bash
# Install test dependencies
pip install -r requirements.txt

# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=agent_config tests/
```

### Local Development
1. Set up local MCP server connections
2. Configure test credentials and permissions
3. Use mock implementations for external dependencies
4. Enable debug logging for detailed troubleshooting

## Security Considerations

### Authentication and Authorization
- IAM role-based access with least privilege
- Secure credential storage in AWS Secrets Manager
- Automatic token refresh mechanisms
- Audit logging for all security-related operations

### Data Protection
- Encryption in transit for all MCP communications
- Sensitive data masking in logs and responses
- Appropriate data retention policies
- Access controls for configuration and credentials

## Troubleshooting

### Common Issues

1. **MCP Server Connection Failures**
   - Check network connectivity and security groups
   - Verify authentication credentials
   - Review CloudWatch logs for detailed error information

2. **Performance Issues**
   - Monitor parallel execution efficiency
   - Check MCP server response times
   - Review caching configuration

3. **Authentication Errors**
   - Verify IAM role permissions
   - Check Secrets Manager credential validity
   - Ensure proper cross-account access if applicable

### Debug Mode
Enable detailed logging by setting environment variables:
```bash
export LOG_LEVEL=DEBUG
export MCP_DEBUG=true
```

## Contributing

1. Follow the established code structure and interfaces
2. Add comprehensive tests for new functionality
3. Update documentation for any interface changes
4. Ensure security best practices in all implementations

## License

MIT No Attribution - See LICENSE file for details.

## Support

For issues and questions:
1. Check CloudWatch logs for detailed error information
2. Review the troubleshooting section above
3. Consult AWS documentation for service-specific guidance
4. Contact your AWS support team for infrastructure issues