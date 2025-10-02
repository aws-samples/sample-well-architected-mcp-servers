# AWS Compute Optimizer Analysis and Rightsizing Recommendations

Analyze AWS Compute Optimizer recommendations and provide comprehensive rightsizing guidance for optimal performance and cost efficiency.

## Compute Optimizer Analysis

### EC2 Instance Recommendations
- **Rightsizing Opportunities**: Analyze over-provisioned and under-provisioned instances
- **Instance Family Optimization**: Recommendations for newer generation instances
- **Performance Impact**: Assess performance implications of recommended changes
- **Cost Savings**: Calculate potential monthly and annual savings

### Auto Scaling Group Analysis
- **Scaling Policies**: Review current scaling configurations
- **Instance Mix**: Optimize instance types within ASGs
- **Capacity Planning**: Right-size minimum, maximum, and desired capacity

### EBS Volume Optimization
- **Volume Type Recommendations**: gp2 to gp3 migration opportunities
- **IOPS and Throughput**: Optimize provisioned IOPS and throughput settings
- **Volume Sizing**: Identify oversized volumes and storage waste

### Lambda Function Analysis
- **Memory Allocation**: Optimize memory settings for cost and performance
- **Execution Duration**: Identify functions that could benefit from different configurations
- **Provisioned Concurrency**: Analyze cost vs performance trade-offs

## Performance Metrics Analysis

### CPU Utilization Patterns
- **Peak Usage**: Identify peak usage periods and patterns
- **Average Utilization**: Long-term utilization trends
- **Idle Resources**: Resources with consistently low utilization

### Memory and Network Analysis
- **Memory Pressure**: Identify memory-constrained workloads
- **Network Utilization**: Bandwidth usage patterns and optimization opportunities
- **Storage Performance**: Disk I/O patterns and optimization needs

## Implementation Strategy

### Phased Approach
- **Phase 1**: Low-risk, high-impact changes (oversized instances)
- **Phase 2**: Medium-risk optimizations (instance family changes)
- **Phase 3**: Architecture-level optimizations (workload modernization)

### Risk Mitigation
- **Testing Strategy**: Recommended testing approach for each change
- **Rollback Plans**: Procedures for reverting changes if needed
- **Monitoring**: Key metrics to monitor post-implementation

## Business Impact Analysis

- **Cost Savings**: Detailed breakdown of potential savings
- **Performance Impact**: Expected performance changes (positive/negative)
- **Operational Overhead**: Additional management complexity
- **Compliance Considerations**: Impact on compliance and security posture

## Account Context

- AWS Account ID: {{account_id}}
- Environment Type: {{environment}}
- Workload Characteristics: {{workload_type}}
- Performance Requirements: {{performance_sla}}

Please provide prioritized recommendations with implementation timelines, expected savings, and risk assessments for each optimization opportunity.