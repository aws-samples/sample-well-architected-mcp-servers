# Technology Stack & Build System

## Core Technologies

### Backend & API
- **Python 3.8+**: Primary backend language
- **FastAPI**: Web framework for REST APIs and WebSocket communication
- **Uvicorn**: ASGI server for FastAPI applications
- **Pydantic**: Data validation and serialization
- **Boto3**: AWS SDK for Python

### AI & ML Integration
- **Amazon Bedrock**: AI/ML service with Claude 3 Haiku and Claude 3.5 Sonnet models
- **Model Context Protocol (MCP)**: Protocol for AI tool integration
- **Bedrock AgentCore Runtime**: Runtime environment for MCP servers

### Frontend
- **HTML5/JavaScript**: Web interface with WebSocket communication
- **No framework dependencies**: Vanilla JavaScript for simplicity

### AWS Services
- **CloudFormation**: Infrastructure as Code
- **S3 + CloudFront**: Static website hosting and CDN
- **Amazon Cognito**: Authentication and user management
- **Systems Manager Parameter Store**: Configuration management
- **IAM**: Cross-account role management

## Development Tools

### Code Quality
- **Ruff**: Python linting and formatting (line-length: 99)
- **Pytest**: Testing framework with asyncio support
- **Coverage**: Code coverage reporting
- **Pre-commit hooks**: Automated code quality checks

### Package Management
- **pip3**: Python package management
- **Virtual environments**: Isolated Python environments
- **pyproject.toml**: Modern Python project configuration

## Common Commands

### Development Setup
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Install development dependencies (for MCP servers)
pip3 install -e ".[dev]"
```

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_security_services.py

# Run tests excluding live API calls
pytest -m "not live"
```

### Code Quality
```bash
# Run linting
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
ruff format .

# Run pre-commit hooks
pre-commit run --all-files
```

### Deployment
```bash
# Complete platform deployment
./deploy-coa.sh

# Deploy with custom configuration
./deploy-coa.sh --stack-name my-coa-stack --region us-west-2 --environment prod

# Resume failed deployment
./deploy-coa.sh --resume-from-stage 3

# Check deployment progress
./deploy-coa.sh --show-progress

# Clean up conflicting resources
./deploy-coa.sh --cleanup
```

### MCP Server Development
```bash
# Run MCP server locally
python3 -m src.server

# Test MCP server tools
python3 -c "from src.server import mcp; print(mcp.list_tools())"

# Install MCP server for testing
pip3 install -e .
```

### Web Interface Development
```bash
# Start backend server
cd cloud-optimization-web-interfaces/cloud-optimization-web-interface/backend
python3 main.py

# Serve frontend locally
cd ../frontend
python3 -m http.server 8080
```

## Configuration Files

- **pyproject.toml**: Python project configuration, dependencies, and tool settings
- **requirements.txt**: Python dependencies for deployment scripts
- **.ruff.toml**: Ruff linting and formatting configuration
- **.pre-commit-config.yaml**: Pre-commit hook configuration
- **deploy-coa.sh**: Main deployment automation script
- **.bedrock_agentcore.yaml**: AgentCore configuration (auto-generated, not committed)

## Environment Variables

### AWS Configuration
- `AWS_PROFILE`: AWS CLI profile name
- `AWS_REGION`: Target AWS region
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`: AWS credentials

### Application Configuration
- `ENVIRONMENT`: Deployment environment (dev, staging, prod)
- `STACK_NAME`: CloudFormation stack name
- `BEDROCK_MODEL_ID`: Bedrock model identifier
- `USE_ENHANCED_AGENT`: Enable enhanced agent features