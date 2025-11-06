# EC2 Instance Rightsizing Analysis

Analyze my EC2 instances for rightsizing opportunities and provide cost optimization recommendations.

## Analysis Request

Please analyze my EC2 infrastructure for cost optimization:

1. **Get EC2 rightsizing recommendations** from AWS Compute Optimizer
   - Show current instance configurations and recommended sizes
   - Calculate potential cost savings from rightsizing
   - Identify underutilized instances with low CPU usage

2. **Analyze EC2 costs and usage patterns**
   - Show EC2 spending by instance type and region over the last 30 days
   - Identify highest cost instances for optimization priority
   - Compare costs between instance families and generations

3. **Check for optimization opportunities**
   - Find instances with consistently low utilization (< 40% CPU)
   - Identify candidates for newer generation instances (M5→M6i, C5→C6i)
   - Suggest Graviton-based instances for compatible workloads

## Expected Deliverables

- List of specific EC2 instances with rightsizing recommendations
- Estimated monthly cost savings from implementing recommendations
- Priority ranking based on potential savings and implementation effort
- Specific next steps for each optimization opportunity

Focus on actionable recommendations with clear cost impact and implementation guidance.