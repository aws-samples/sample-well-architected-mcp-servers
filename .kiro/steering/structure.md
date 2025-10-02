# Project Structure & Organization

## Root Directory Layout

```
/
├── 🌐 cloud-optimization-web-interfaces/    # Web interfaces for user interaction
├── 🤖 agents/                               # AI agents for specialized assessments
├── 🔧 mcp-servers/                          # MCP servers providing assessment tools
├── 🚀 deployment-scripts/                   # Deployment automation scripts
├── 📚 docs/                                 # Documentation and guides
├── deploy-coa.sh                            # Main deployment script
└── .kiro/                                   # Kiro IDE configuration
```

## Component Structure

### Web Interfaces (`cloud-optimization-web-interfaces/`)
```
cloud-optimization-web-interface/
├── backend/                    # FastAPI backend service
│   ├── main.py                # FastAPI application entry point
│   ├── models/                # Pydantic data models
│   ├── services/              # Business logic services
│   └── requirements.txt       # Backend dependencies
├── frontend/                  # Static web frontend
│   ├── index.html            # Main web interface
│   ├── config.js             # Frontend configuration
│   └── local-test.html       # Local testing interface
└── serve_frontend.py         # Development server
```

### Bedrock Agents (`agents/bedrock-agents/`)
```
wa-security-agent-multi-mcps/
├── agent_config/              # Agent configuration modules
│   ├── config.py             # Main configuration
│   ├── model_config.py       # Model configuration
│   ├── model_switcher.py     # Runtime model switching
│   ├── wa_security_agent.py  # Main agent implementation
│   ├── integrations/         # MCP integrations
│   ├── orchestration/        # MCP orchestration logic
│   └── utils/                # Utility functions
├── example_usage.py          # Usage examples
├── test_model_switching.py   # Model switching tests
└── requirements.txt          # Agent dependencies
```

### MCP Servers (`mcp-servers/`)
```
well-architected-security-mcp-server/
├── src/                      # Source code
│   ├── server.py            # Main MCP server
│   ├── consts.py            # Constants and configuration
│   └── util/                # Utility modules
│       ├── security_services.py    # Security service checks
│       ├── storage_security.py     # Storage encryption checks
│       ├── network_security.py     # Network security checks
│       └── resource_utils.py       # AWS resource utilities
├── tests/                    # Comprehensive test suite
├── pyproject.toml           # Python project configuration
└── README.md                # Server documentation
```

### Deployment Scripts (`deployment-scripts/`)
```
deployment-scripts/
├── components/               # Component-specific deployments
│   ├── deploy_component_wa_security_mcp.py
│   ├── deploy_component_chatbot_webapp.py
│   ├── deploy_component_aws_api_mcp_server.py
│   └── deploy_shared_cognito.py
├── deploy_chatbot_stack.py   # Main chatbot deployment
├── generate_cognito_ssm_parameters.py
├── generate_remote_role_stack.py
└── requirements.txt          # Deployment dependencies
```

## File Naming Conventions

### Python Files
- **snake_case**: All Python files and modules use snake_case naming
- **Descriptive names**: Files clearly indicate their purpose (e.g., `security_services.py`, `model_switcher.py`)
- **Test files**: Prefixed with `test_` (e.g., `test_security_services.py`)

### Configuration Files
- **pyproject.toml**: Modern Python project configuration
- **requirements.txt**: Dependency specifications
- **.ruff.toml**: Linting configuration
- **.bedrock_agentcore.yaml**: AgentCore configuration (auto-generated, excluded from git)

### Documentation
- **README.md**: Component-specific documentation
- **Markdown files**: All documentation in Markdown format
- **UPPERCASE**: Important project files (LICENSE, CONTRIBUTING.md)

## Key Directories to Understand

### `/agents/bedrock-agents/`
Contains AI agents deployed to Amazon Bedrock Agent service:
- **Multi-MCP agents**: Integrate multiple MCP servers (WA Security + AWS API + AWS Knowledge)
- **Single-MCP agents**: Use only Well-Architected Security MCP server
- **Agent configuration**: Model selection, orchestration, and integration logic

### `/mcp-servers/`
Contains Model Context Protocol servers providing specialized tools:
- **Self-contained servers**: Each server is independently deployable
- **Utility modules**: Shared functionality for AWS service interactions
- **Comprehensive testing**: Each server has extensive test coverage

### `/cloud-optimization-web-interfaces/`
Web-based user interfaces for the platform:
- **Backend**: FastAPI service handling WebSocket communication and Bedrock integration
- **Frontend**: Vanilla JavaScript interface with real-time chat capabilities
- **Configuration**: Environment-specific settings and authentication

### `/deployment-scripts/`
Automated deployment and configuration management:
- **Component deployment**: Individual component deployment scripts
- **Infrastructure**: CloudFormation stack management
- **Configuration**: SSM Parameter Store management and Cognito setup

## Important Files

### Root Level
- **deploy-coa.sh**: Primary deployment automation script with resume capabilities
- **README.md**: Comprehensive project documentation and quick start guide

### Configuration Management
- **Parameter Store paths**: `/coa/cognito/*`, `/coa/components/*`, `/coa/agent/*`
- **Environment variables**: Defined in deployment scripts and backend services
- **AWS credentials**: Managed through IAM roles and profiles

### Generated Files (Excluded from Git)
- **.bedrock_agentcore.yaml**: Contains sensitive AWS configuration
- **.coa-deployment-progress**: Deployment progress tracking
- **generated-templates/**: CloudFormation templates for cross-account roles

## Development Workflow

### Working with Components
1. **MCP Servers**: Develop in `mcp-servers/*/src/`, test with `pytest`
2. **Bedrock Agents**: Configure in `agents/*/agent_config/`, test with example scripts
3. **Web Interface**: Backend in `backend/`, frontend in `frontend/`
4. **Deployment**: Use `deployment-scripts/` for infrastructure changes

### Testing Strategy
- **Unit tests**: Each component has comprehensive test coverage
- **Integration tests**: Cross-component testing in deployment scripts
- **Live tests**: Marked with `@pytest.mark.live` for actual AWS API calls
- **Mock tests**: Default testing mode using mocked AWS responses

### Configuration Hierarchy
1. **Environment variables**: Runtime configuration
2. **Parameter Store**: Centralized configuration management
3. **pyproject.toml**: Project-level settings
4. **Component configs**: Service-specific configuration files