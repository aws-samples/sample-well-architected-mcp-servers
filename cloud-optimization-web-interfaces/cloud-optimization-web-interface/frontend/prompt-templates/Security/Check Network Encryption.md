# Network Security and Encryption Analysis

Perform a comprehensive analysis of network security configurations and data-in-transit encryption across my AWS infrastructure.

## Network Security Assessment

Please evaluate the following network security components:

### Load Balancers and Traffic Encryption
- **Application Load Balancers (ALB)**: SSL/TLS configuration and cipher suites
- **Network Load Balancers (NLB)**: TLS termination and security groups
- **Classic Load Balancers**: HTTPS listeners and SSL policies

### API Gateway Security
- **REST APIs**: TLS configuration and custom domain certificates
- **WebSocket APIs**: Secure connection protocols
- **API Keys and Authentication**: Security mechanisms in place

### CloudFront Distributions
- **SSL/TLS Configuration**: Certificate management and security policies
- **Origin Access Control**: Secure communication with origins
- **Security Headers**: HSTS, CSP, and other security headers

### VPC Network Security
- **Security Groups**: Ingress/egress rules analysis
- **Network ACLs**: Layer 4 security controls
- **VPC Flow Logs**: Network traffic monitoring and analysis

## Compliance Requirements

Check compliance with the following standards:
- **TLS 1.2+ Only**: Ensure deprecated protocols are disabled
- **Strong Cipher Suites**: Verify use of secure encryption algorithms
- **Certificate Management**: Valid certificates and proper rotation
- **Network Segmentation**: Proper isolation between environments

## Account Information

- AWS Account ID: {{account_id}}
- Target Region: {{region}}
- Environment Type: {{environment}}

Please provide detailed findings with specific recommendations for any security gaps identified.