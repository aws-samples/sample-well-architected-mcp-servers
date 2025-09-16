# AWS API MCP Server Runtime

This AgentCore runtime hosts the `awslabs.aws-api-mcp-server` as an MCP server, providing AWS CLI tools and capabilities through the Model Context Protocol.

## Overview

This runtime deploys the AWS API MCP server to Amazon Bedrock AgentCore Runtime, making AWS CLI commands and operations available as MCP tools that can be consumed by other agents and applications.

### Architecture

```
┌─────────────────────────────────────┐
│     AgentCore Runtime               │
│  ┌─────────────────────────────────┐│
│  │   AWS API MCP Server            ││
│  │                                 ││
│  │  ┌─────────────────────────────┐││
│  │  │  AWS CLI Tools              │││
│  │  │  - EC2 operations           │││
│  │  │  - S3 operations            │││
│  │  │  - Lambda operations        │││
│  │  │  - IAM operations           │││
│  │  │  - And more...              │││
│  │  └─────────────────────────────┘││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
```

### Features

- **AWS CLI Integration**: Full access to AWS CLI commands through MCP tools
- **IAM Authentication**: Native AWS IAM-based access control
- **Stateless Operation**: Supports session isolation for multiple clients
- **Production Ready**: Deployed on AgentCore Runtime with proper monitoring
- **Fine-grained Access**: Control access at the IAM principal level

## Files

- `mcp_server.py`: Main MCP server implementation
- `requirements.txt`: Python dependencies
- `test_client.py`: Local testing client
- `remote_client.py`: Remote testing client for deployed server
- `deploy.ipynb`: Jupyter notebook for deployment

## Usage

1. **Local Testing**: Run the server locally and test with the local client
2. **Deploy**: Use the deployment notebook to deploy to AgentCore Runtime with IAM auth
3. **Remote Testing**: Test the deployed server with IAM authentication

## Next Steps

Once deployed, this MCP server can be consumed by other agents or applications that need AWS operations capabilities.