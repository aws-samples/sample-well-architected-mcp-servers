# AWS Savings Plans and Cost Optimization Analysis

Analyze my AWS usage patterns and provide recommendations for Savings Plans, Reserved Instances, and other cost optimization opportunities.

## Cost Analysis Scope

### Compute Savings Opportunities
- **EC2 Savings Plans**: Analyze EC2 usage patterns for 1-year and 3-year commitments
- **Compute Savings Plans**: Cross-service savings for EC2, Fargate, and Lambda
- **Reserved Instances**: Traditional RI recommendations for predictable workloads
- **Spot Instances**: Opportunities to use Spot for fault-tolerant workloads

### Service-Specific Analysis
- **Amazon RDS**: Reserved Instance opportunities for database workloads
- **Amazon ElastiCache**: Reserved Node recommendations
- **Amazon Redshift**: Reserved Node analysis for data warehouse workloads
- **Amazon OpenSearch**: Reserved Instance opportunities

### Usage Pattern Analysis
- **Historical Usage**: Analyze last 12 months of usage data
- **Seasonal Patterns**: Identify seasonal variations in resource usage
- **Growth Trends**: Factor in projected growth for sizing recommendations
- **Utilization Metrics**: Current resource utilization and rightsizing opportunities

## Cost Optimization Recommendations

### Immediate Opportunities
- **Rightsizing**: Oversized instances and underutilized resources
- **Storage Optimization**: S3 storage class analysis and lifecycle policies
- **Data Transfer**: Optimize data transfer costs and CloudFront usage
- **Unused Resources**: Identify and eliminate unused resources

### Long-term Strategies
- **Architecture Optimization**: Serverless vs container vs EC2 cost analysis
- **Multi-Region Strategy**: Cost implications of multi-region deployments
- **Backup and Disaster Recovery**: Cost-effective backup strategies

## Financial Analysis

Please provide:
- **Current Monthly Spend**: Breakdown by service and resource type
- **Potential Savings**: Estimated savings from each recommendation
- **Payback Period**: Time to recover any upfront costs
- **Risk Assessment**: Impact of commitment-based savings plans

## Account Information

- AWS Account ID: {{account_id}}
- Primary Region: {{region}}
- Monthly Budget Range: {{budget_range}}
- Business Criticality: {{criticality_level}}

Provide detailed recommendations with specific actions, expected savings amounts, and implementation timelines.