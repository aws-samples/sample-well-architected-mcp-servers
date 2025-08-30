# Unified Cloud Optimization Platform Deployment

This document describes the unified deployment approach for the Cloud Optimization Platform using nested CloudFormation stacks and automated CI/CD pipeline.

## Architecture Overview

The unified deployment creates a complete platform with the following components in the correct sequence:

### 1. Core Infrastructure Stack (Nested Stacks)
- **Cognito Stack**: Shared authentication for all components
- **Build Pipeline Stack**: CodeBuild + ECR for automated Docker builds
- **WebApp Stack**: ECS Fargate backend with ALB
- **Frontend Stack**: CloudFront + S3 for static assets

### 2. MCP Servers
- Well-Architected Security MCP Server
- AWS API MCP Server (optional)

### 3. Bedrock Agents
- WA Security Agent with multi-MCP integration

## Deployment Sequence

The deployment follows this specific sequence to ensure proper dependencies:

```
1. Cognito + Build Pipeline + WebApp + Frontend (Merged Stack)
   ├── Cognito User Pool (shared authentication)
   ├── CodeBuild Pipeline (automated builds)
   ├── ECS Backend (web application)
   └── CloudFront Frontend (static assets)

2. MCP Servers
   ├── WA Security MCP Server
   └── AWS API MCP Server

3. Bedrock Agents
   └── WA Security Agent
```

## Key Features

### Nested Stack Architecture
- **Main Stack**: `cloud-optimization-platform`
- **Nested Stacks**: 
  - `CognitoStack`: Authentication infrastructure
  - `BuildPipelineStack`: CI/CD pipeline
  - `WebAppStack`: Backend application
  - `FrontendStack`: Frontend distribution

### Automated CI/CD Pipeline
- **S3 Source Bucket**: Stores backend source code with versioning
- **CodeBuild**: Automatically builds Docker images on source updates
- **ECR**: Stores Docker images with lifecycle policies
- **ECS**: Automatically deploys new images

### Shared Configuration
- **Parameter Store**: Centralized configuration at `/coa/platform/*`
- **Cross-Stack References**: Proper dependency management
- **Environment Support**: dev, staging, prod environments

## Prerequisites

1. **AWS CLI** configured with appropriate permissions
2. **Python 3.8+** with boto3
3. **Backend source code** in `cloud-optimization-web-interfaces/cloud-optimization-web-interface/backend/`
4. **Frontend assets** in `cloud-optimization-web-interfaces/cloud-optimization-web-interface/frontend/`

## Quick Start

### 1. Deploy the Complete Platform

```bash
# Deploy everything with default settings
python deployment-scripts/deploy_unified_platform.py

# Deploy with custom settings
python deployment-scripts/deploy_unified_platform.py \
  --stack-name my-platform \
  --region us-west-2 \
  --environment staging

# Deploy only infrastructure (skip MCP servers and agents)
python deployment-scripts/deploy_unified_platform.py \
  --skip-mcp-servers \
  --skip-agents
```

### 2. Update Source Code

```bash
# Update backend source code and trigger build
python deployment-scripts/update_source_code.py --wait

# Upload source code without triggering build
python deployment-scripts/update_source_code.py --no-build

# Update for specific stack
python deployment-scripts/update_source_code.py \
  --stack-name my-platform \
  --region us-west-2
```

## Detailed Components

### Cognito Stack
- **Shared User Pool**: Used by all components
- **Multiple Clients**: Web app, API, MCP server clients
- **Parameter Store Integration**: Configuration stored at `/coa/cognito/*`

### Build Pipeline Stack
- **ECR Repository**: Stores Docker images with lifecycle policies
- **CodeBuild Project**: Builds and pushes images automatically
- **S3 Integration**: Triggered by source code updates
- **ECS Integration**: Automatically updates ECS service

### WebApp Stack
- **VPC**: Dedicated VPC with public subnets
- **ECS Fargate**: Serverless container hosting
- **Application Load Balancer**: HTTP/HTTPS traffic routing
- **Security Groups**: Proper network isolation
- **CloudWatch Logs**: Centralized logging

### Frontend Stack
- **S3 Bucket**: Static asset hosting
- **CloudFront**: Global CDN with caching
- **Origin Access Identity**: Secure S3 access
- **API Routing**: Routes `/api/*` to backend ALB

## Configuration Management

### Parameter Store Structure
```
/coa/platform/
├── stack_name              # Main stack name
├── application_url         # CloudFront URL
├── user_pool_id           # Cognito User Pool ID
├── source_bucket          # S3 source bucket
├── ecr_repository         # ECR repository URI
├── region                 # AWS region
└── environment            # Environment name

/coa/cognito/
├── user_pool_id           # Shared across components
├── web_app_client_id      # Frontend client
├── api_client_id          # Backend client
├── mcp_server_client_id   # MCP server client
└── discovery_url          # OIDC discovery URL
```

### Environment Variables (ECS)
- `USER_POOL_ID`: Cognito User Pool ID
- `AWS_REGION`: AWS region
- Additional environment-specific variables

## Source Code Management

### Automatic Builds
1. **Upload**: Source code uploaded to S3 bucket
2. **Trigger**: S3 upload triggers CodeBuild
3. **Build**: CodeBuild creates Docker image
4. **Push**: Image pushed to ECR
5. **Deploy**: ECS service updated automatically

### Manual Updates
```bash
# Update and wait for completion
python deployment-scripts/update_source_code.py --wait

# Check build status in AWS Console
aws codebuild list-builds-for-project \
  --project-name cloud-optimization-platform-build
```

## Monitoring and Troubleshooting

### CloudWatch Logs
- **ECS Logs**: `/ecs/cloud-optimization-platform-webapp`
- **CodeBuild Logs**: `/aws/codebuild/cloud-optimization-platform-build`

### Health Checks
- **ALB Health Check**: `GET /health`
- **ECS Service**: Monitor running tasks
- **CloudFront**: Monitor cache hit rates

### Common Issues

1. **Build Failures**
   - Check CodeBuild logs in CloudWatch
   - Verify Dockerfile syntax
   - Check ECR permissions

2. **ECS Service Issues**
   - Check task definition
   - Verify security groups
   - Check ALB target group health

3. **Frontend Issues**
   - Verify S3 bucket policy
   - Check CloudFront distribution
   - Validate config.js generation

## Security Considerations

### IAM Roles
- **CodeBuild Role**: ECR push, S3 read, ECS update permissions
- **ECS Task Role**: Cognito, SSM parameter access
- **ECS Execution Role**: CloudWatch logs, ECR pull permissions

### Network Security
- **Security Groups**: Restrictive ingress rules
- **VPC**: Isolated network environment
- **ALB**: Public endpoint with security groups

### Data Protection
- **S3 Versioning**: Source code version control
- **ECR Encryption**: Image encryption at rest
- **CloudWatch Logs**: Retention policies

## Cost Optimization

### Resource Sizing
- **ECS Fargate**: 256 CPU, 512 MB memory (adjustable)
- **CodeBuild**: BUILD_GENERAL1_MEDIUM (adjustable)
- **CloudWatch Logs**: 7-day retention (adjustable)

### Lifecycle Policies
- **ECR**: Keep last 10 images
- **S3**: Versioning with lifecycle rules
- **CloudWatch**: Automatic log expiration

## Scaling and Performance

### Auto Scaling
- **ECS Service**: Configure auto scaling based on CPU/memory
- **ALB**: Automatic load distribution
- **CloudFront**: Global edge caching

### Performance Tuning
- **ECS**: Adjust CPU/memory allocation
- **CloudFront**: Configure caching policies
- **ALB**: Health check intervals

## Maintenance

### Regular Tasks
1. **Monitor Costs**: Review AWS Cost Explorer
2. **Update Dependencies**: Keep Docker base images updated
3. **Security Patches**: Regular security updates
4. **Log Review**: Monitor CloudWatch logs

### Backup and Recovery
- **Source Code**: S3 versioning provides backup
- **Configuration**: Parameter Store backup
- **Infrastructure**: CloudFormation templates as code

## Advanced Configuration

### Custom Domains
```bash
# Deploy with custom domain (requires ACM certificate)
python deployment-scripts/deploy_unified_platform.py \
  --domain-name myapp.example.com \
  --certificate-arn arn:aws:acm:us-east-1:123456789012:certificate/...
```

### Multi-Environment
```bash
# Deploy development environment
python deployment-scripts/deploy_unified_platform.py \
  --stack-name cloud-optimization-dev \
  --environment dev

# Deploy staging environment
python deployment-scripts/deploy_unified_platform.py \
  --stack-name cloud-optimization-staging \
  --environment staging
```

### Integration with Existing Infrastructure
- Modify VPC settings in WebApp stack template
- Update security group rules as needed
- Configure custom subnets if required

## Support and Troubleshooting

For issues with the unified deployment:

1. **Check CloudFormation Events**: Review stack events for errors
2. **Monitor CloudWatch Logs**: Check application and build logs
3. **Verify Prerequisites**: Ensure all required files exist
4. **Review IAM Permissions**: Confirm deployment permissions
5. **Test Components**: Use individual deployment scripts for debugging

## Migration from Individual Deployments

If migrating from individual component deployments:

1. **Backup Existing Configuration**: Export Parameter Store values
2. **Deploy New Stack**: Use unified deployment script
3. **Migrate Data**: Transfer any persistent data
4. **Update DNS**: Point domains to new CloudFront distribution
5. **Cleanup**: Remove old individual stacks after verification