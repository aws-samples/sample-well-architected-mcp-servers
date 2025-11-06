# AWS API Agent with Intelligent Prompt Preprocessing

This enhanced AWS API agent includes intelligent prompt preprocessing capabilities that can analyze complex user inputs and automatically split them into multiple targeted AWS operations.

## Key Features

### 1. Intelligent Complexity Analysis
- **Single Operation Detection**: Identifies simple, focused AWS requests
- **Multi-Operation Detection**: Recognizes complex workflows requiring multiple AWS operations
- **Cross-Service Dependencies**: Handles operations that depend on outputs from other operations

### 2. Cross-Account Parameter Extraction
Automatically extracts and manages cross-account parameters:
- `account_id`: 12-digit AWS account numbers
- `role_arn`: Complete IAM role ARNs
- `external_id`: External IDs for enhanced security
- `region`: AWS regions mentioned in requests

### 3. Workflow Orchestration
- **Sequential Execution**: Operations executed in order with dependency management
- **Parallel Execution**: Independent operations can run concurrently
- **Conditional Execution**: Operations can be conditional based on previous results

## Architecture

```
User Input → Preprocessing → Complexity Analysis → Execution Routing
                                    ↓
                            Single Operation → aws_api_agent
                                    ↓
                            Multi Operation → execute_aws_operations_workflow
```

## Available Tools

### 1. `preprocess_complex_prompt`
Analyzes user input and creates structured execution plan:
```python
preprocess_complex_prompt("Analyze my security posture across all AWS services")
```

Returns JSON with:
- Complexity analysis (single/multi)
- Detected AWS services and actions
- Cross-account parameters
- Structured operation breakdown
- Execution strategy recommendation

### 2. `execute_aws_operations_workflow`
Orchestrates multi-operation workflows:
```python
execute_aws_operations_workflow(preprocessed_analysis)
```

Features:
- Sequential/parallel execution
- Dependency management
- Cross-account parameter propagation
- Comprehensive result compilation

### 3. `aws_api_agent`
Direct AWS operations for simple requests:
```python
aws_api_agent("List EC2 instances", account_id="123456789012")
```

## Usage Examples

### Simple Request (Single Operation)
```
Input: "List all EC2 instances in us-east-1"
Flow: preprocess → aws_api_agent (direct execution)
```

### Complex Request (Multi-Operation)
```
Input: "Analyze my complete security posture"
Flow: preprocess → execute_aws_operations_workflow
Operations:
1. Check IAM users and policies
2. Analyze EC2 security groups
3. Review S3 bucket encryption
4. Examine VPC configurations
5. Compile security recommendations
```

### Cross-Account Request
```
Input: "Audit account 123456789012 for compliance violations"
Flow: preprocess (extracts account_id) → execute_aws_operations_workflow
Parameters: account_id="123456789012" passed to all operations
```

## Preprocessing Analysis Format

The preprocessing tool returns structured JSON:

```json
{
    "analysis": {
        "complexity": "single|multi",
        "reasoning": "Why this complexity was chosen",
        "detected_services": ["EC2", "S3", "IAM"],
        "detected_actions": ["list", "describe", "analyze"],
        "cross_account_params": {
            "account_id": "123456789012",
            "role_arn": "arn:aws:iam::123456789012:role/ReadOnlyRole",
            "external_id": "secure-external-id",
            "region": "us-east-1"
        }
    },
    "operations": [
        {
            "sequence": 1,
            "description": "Check IAM security configuration",
            "query": "List all IAM users and their attached policies",
            "dependencies": [],
            "estimated_complexity": "medium"
        }
    ],
    "execution_strategy": "sequential|parallel|conditional"
}
```

## Benefits

### For Users
- **Natural Language**: Use natural language for complex AWS operations
- **Automatic Breakdown**: Complex requests automatically split into manageable operations
- **Cross-Account Support**: Seamless cross-account operations with parameter extraction
- **Comprehensive Results**: Get complete analysis across multiple AWS services

### For Developers
- **Intelligent Routing**: Automatic routing between simple and complex execution paths
- **Dependency Management**: Automatic handling of operation dependencies
- **Error Handling**: Graceful fallback when preprocessing fails
- **Extensible**: Easy to add new operation types and execution strategies

## Testing

Run the test script to see preprocessing in action:

```bash
python test_preprocessing.py
```

This will demonstrate:
- Single vs multi-operation detection
- Cross-account parameter extraction
- Workflow structure generation
- Complete execution flow

## Integration

The enhanced agent integrates seamlessly with existing COA components:
- **Web Chatbot**: Natural language interface for complex AWS operations
- **Bedrock Agents**: Multi-MCP orchestration with preprocessing
- **MCP Servers**: Direct tool access through structured workflows

## Future Enhancements

- **Learning Capabilities**: Learn from user patterns to improve preprocessing
- **Custom Workflows**: User-defined workflow templates
- **Performance Optimization**: Parallel execution optimization
- **Advanced Dependencies**: Complex conditional logic between operations