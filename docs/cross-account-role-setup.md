Deploy this policy in the account to assume other ReadOnly role.

```
  "CrossAccountAssumeRolePolicy": {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "sts:AssumeRole",
        "Resource": [
          "arn:aws:iam::*:role/ReadOnly"
        ],
        "Condition": {
          "StringEquals": {
            "sts:ExternalId": "CloudOptimizationAssistant"
          }
        }
      }
    ]
  }
```

Deploy this policy in the target account to allow the agent/MCP to access.
Also, replace the XXXXXXXXXXXXX with the account number of the source account.
```
  "TargetRoleTrustPolicy": {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "AWS": "arn:aws:iam::XXXXXXXXXXXXXXXXXX:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-0a5c2f9775"
        },
        "Action": "sts:AssumeRole",
        "Condition": {
          "StringEquals": {
            "sts:ExternalId": "CloudOptimizationAssistant"
          }
        }
      }
    ]
  }
```