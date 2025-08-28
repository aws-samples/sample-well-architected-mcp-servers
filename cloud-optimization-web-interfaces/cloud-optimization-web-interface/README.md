# AWS Cloud Optimization MCP Web Interface

A modern web interface for AWS cloud optimization assessments using Amazon Bedrock and Model Context Protocol (MCP) integration.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   MCP Server    │
│   (HTML/JS)     │◄──►│   (FastAPI)     │◄──►│  (AgentCore)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AWS Bedrock   │
                       │  (Claude 3.5)   │
                       └─────────────────┘
```

## 🚀 Features

### Real-time Cloud Optimization Assessment
- **Interactive Chat Interface**: Natural language optimization queries
- **WebSocket Communication**: Real-time responses and typing indicators
- **Tool Integration**: Direct access to AWS Well-Architected assessment tools

### AWS Well-Architected Assessment Tools
1. **CheckSecurityServices** - Verify AWS security services status
2. **GetSecurityFindings** - Retrieve security findings and alerts
3. **CheckStorageEncryption** - Analyze data-at-rest encryption
4. **CheckNetworkSecurity** - Review network security configuration
5. **ListServicesInRegion** - Inventory AWS services in use
6. **GetStoredSecurityContext** - Access cached optimization data

*Note: Additional tools for cost optimization, performance efficiency, and operational excellence will be added as the platform expands.*

### Modern Web Interface
- **Responsive Design**: Works on desktop and mobile
- **Service Status Monitoring**: Real-time health indicators
- **Quick Actions**: Pre-built security assessment queries
- **Tool Execution Tracking**: Visual feedback for MCP tool calls

## 📋 Prerequisites

- Python 3.8+
- AWS credentials configured (for Bedrock access)
- Access to deployed MCP server on AgentCore Runtime

## 🛠️ Installation & Setup

### 1. Quick Start
```bash
cd sample-bac-test/cloud-optimization-web-interface
python start_server.py
```

This will:
- Install Python requirements
- Start the FastAPI backend on port 8000
- Open the web interface in your browser

### 2. Manual Setup

#### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### Start Backend Server
```bash
cd backend
python main.py
```

#### Open Frontend
Open `frontend/index.html` in your browser or serve it with a web server.

### 3. Test Integration
```bash
python test_integration.py
```

## 🔧 Configuration

### MCP Server Configuration
Update `backend/services/mcp_client_service.py`:

```python
self.base_url = "https://runtime.agentcore.bedrock.aws.dev"
self.agent_arn = "your-agent-arn-here"
```

### Authentication
The demo uses a simple token-based auth. For production:

1. Configure AWS Cognito
2. Update `backend/services/auth_service.py`
3. Set proper JWT validation

### AWS Credentials
Ensure your environment has AWS credentials:
```bash
aws configure
# or use IAM roles, environment variables, etc.
```

## 📡 API Endpoints

### REST API
- `GET /health` - Service health check
- `POST /api/chat` - Send chat message
- `GET /api/sessions/{id}/history` - Get chat history
- `GET /api/mcp/tools` - List available MCP tools

### WebSocket
- `WS /ws/{session_id}` - Real-time chat communication

### Example API Usage
```bash
# Health check
curl http://localhost:8000/health

# Chat message
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo-token" \
  -d '{"message": "Check my security services"}'
```

## 🎯 Usage Examples

### Cloud Optimization Queries
- "Analyze my cost optimization opportunities"
- "Check my AWS security services status"
- "Review performance efficiency opportunities"
- "Analyze my storage and data management"
- "What improvements should I prioritize?"
- "Perform a comprehensive Well-Architected review"

### Tool-Specific Queries
- "Check GuardDuty status in us-east-1"
- "List all security findings with HIGH severity"
- "Show me unencrypted S3 buckets"
- "Analyze VPC security groups"

## 🔍 Troubleshooting

### Common Issues

#### MCP Connection Failed
```
❌ MCP Service test failed: Failed to initialize MCP session
```
**Solution**: Verify your MCP server ARN and ensure it's deployed and accessible.

#### Bedrock Access Denied
```
❌ Bedrock Service test failed: AccessDenied
```
**Solution**: Ensure your AWS credentials have Bedrock permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
```

#### WebSocket Connection Issues
**Solution**: Check if the backend is running on port 8000 and firewall settings.

### Debug Mode
Enable debug logging in `backend/main.py`:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 🏗️ Development

### Project Structure
```
cloud-optimization-web-interface/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── models/
│   │   └── chat_models.py      # Data models
│   ├── services/
│   │   ├── auth_service.py     # Authentication
│   │   ├── bedrock_chat_service.py  # Bedrock integration
│   │   └── mcp_client_service.py    # MCP client
│   └── requirements.txt
├── frontend/
│   └── index.html              # Web interface
├── start_server.py             # Startup script
├── test_integration.py         # Integration tests
└── README.md
```

### Adding New Features

#### New MCP Tool
1. Add method to `MCPClientService`
2. Update tool conversion in `BedrockChatService`
3. Test with integration script

#### New Frontend Feature
1. Update `frontend/index.html`
2. Add corresponding backend endpoint
3. Test WebSocket communication

## 🚀 Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY backend/ .
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### AWS Deployment Options
- **ECS Fargate**: Container-based deployment
- **Lambda**: Serverless with API Gateway
- **EC2**: Traditional server deployment
- **App Runner**: Fully managed container service

### Security Considerations
- Use proper JWT validation with Cognito
- Enable HTTPS/WSS in production
- Implement rate limiting
- Add request validation and sanitization
- Use AWS IAM roles instead of access keys

## 📊 Monitoring

### Health Checks
The `/health` endpoint provides service status:
```json
{
  "status": "healthy",
  "services": {
    "bedrock": "healthy",
    "mcp": "healthy",
    "auth": "healthy"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Logging
- Backend logs: FastAPI access and error logs
- MCP communication: Tool execution logs
- Frontend: Browser console for WebSocket events

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run integration tests
5. Submit a pull request

## 📄 License

This project is part of the AWS security assessment toolkit and follows AWS sample code guidelines.

---

**☁️ Ready to optimize your AWS infrastructure with AI-powered insights across all Well-Architected pillars!**