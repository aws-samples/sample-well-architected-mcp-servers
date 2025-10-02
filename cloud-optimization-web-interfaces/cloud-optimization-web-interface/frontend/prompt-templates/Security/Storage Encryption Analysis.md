# Storage Encryption and Data Protection Assessment

Analyze the encryption status and data protection mechanisms for all storage services in my AWS account to ensure compliance with security best practices.

## Storage Services to Analyze

### Amazon S3
- **Bucket Encryption**: Default encryption settings and KMS key usage
- **Bucket Policies**: Encryption enforcement policies
- **Access Logging**: CloudTrail and S3 access logging configuration
- **Versioning and MFA Delete**: Data protection mechanisms

### Amazon EBS
- **Volume Encryption**: Encryption status for all EBS volumes
- **Snapshot Encryption**: Encrypted snapshots and cross-region copying
- **Default Encryption**: Account-level default encryption settings

### Amazon RDS
- **Database Encryption**: Encryption at rest for RDS instances
- **Backup Encryption**: Automated backup and snapshot encryption
- **Performance Insights**: Encryption for performance monitoring data

### Amazon DynamoDB
- **Table Encryption**: Encryption at rest configuration
- **Point-in-Time Recovery**: Backup encryption settings
- **Global Tables**: Cross-region encryption consistency

### Amazon EFS
- **File System Encryption**: Encryption in transit and at rest
- **Access Points**: Encryption enforcement for access points

### Amazon ElastiCache
- **Cluster Encryption**: Redis and Memcached encryption settings
- **Backup Encryption**: Snapshot encryption configuration

## Key Management Analysis

- **AWS KMS**: Customer-managed vs AWS-managed keys usage
- **Key Rotation**: Automatic key rotation configuration
- **Key Policies**: Access control and permissions review
- **Cross-Account Access**: Key sharing and external access

## Compliance Framework

Evaluate against these security standards:
- **AWS Well-Architected Security Pillar**: Data protection at rest
- **SOC 2 Type II**: Encryption requirements
- **PCI DSS**: Data encryption standards (if applicable)
- **HIPAA**: Healthcare data protection (if applicable)

## Account Details

- AWS Account ID: {{account_id}}
- Primary Region: {{region}}
- Compliance Requirements: {{compliance_framework}}

Please provide a comprehensive report with encryption status, compliance gaps, and remediation recommendations.