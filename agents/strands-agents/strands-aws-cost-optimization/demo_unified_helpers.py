#!/usr/bin/env python3
"""
Demonstration of unified helper utilities shared between AWS agents.

This script shows how both aws_api_agent and aws_billing_management_agent
now use the same shared utilities for cross-account configuration.
"""

from aws_cross_account_utils import (
    validate_role_arn,
    validate_account_id,
    construct_role_arn,
    resolve_cross_account_parameters,
    handle_cross_account_parameters,
    get_environment_config
)


def demo_shared_utilities():
    """Demonstrate the shared utility functions."""
    
    print("=" * 60)
    print("UNIFIED HELPER UTILITIES DEMONSTRATION")
    print("=" * 60)
    
    # Demo 1: ARN Validation
    print("\n1. ARN Validation")
    print("-" * 20)
    
    test_arns = [
        "arn:aws:iam::123456789012:role/COAReadOnlyRole",
        "arn:aws:iam::987654321098:role/TestRole",
        "invalid-arn-format",
        ""
    ]
    
    for arn in test_arns:
        is_valid = validate_role_arn(arn)
        print(f"  {arn:<50} → {'✅ Valid' if is_valid else '❌ Invalid'}")
    
    # Demo 2: Account ID Validation and Role Construction
    print("\n2. Account ID Validation and Role Construction")
    print("-" * 45)
    
    test_account_ids = [
        "123456789012",
        "987654321098",
        "invalid-id",
        "12345"  # Too short
    ]
    
    for account_id in test_account_ids:
        is_valid = validate_account_id(account_id)
        print(f"  Account ID: {account_id:<15} → {'✅ Valid' if is_valid else '❌ Invalid'}")
        
        if is_valid:
            try:
                role_arn = construct_role_arn(account_id)
                print(f"    Constructed ARN: {role_arn}")
            except Exception as e:
                print(f"    Construction failed: {e}")
    
    # Demo 3: Cross-Account Parameter Resolution
    print("\n3. Cross-Account Parameter Resolution")
    print("-" * 35)
    
    test_scenarios = [
        {
            "name": "Role ARN provided",
            "role_arn": "arn:aws:iam::123456789012:role/CustomRole",
            "account_id": None
        },
        {
            "name": "Account ID provided",
            "role_arn": None,
            "account_id": "987654321098"
        },
        {
            "name": "Both provided (role_arn wins)",
            "role_arn": "arn:aws:iam::111111111111:role/WinningRole",
            "account_id": "222222222222"
        },
        {
            "name": "Neither provided",
            "role_arn": None,
            "account_id": None
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n  Scenario: {scenario['name']}")
        print(f"    Input - role_arn: {scenario['role_arn']}")
        print(f"    Input - account_id: {scenario['account_id']}")
        
        try:
            resolved = resolve_cross_account_parameters(
                role_arn=scenario['role_arn'],
                account_id=scenario['account_id']
            )
            print(f"    Result: {resolved or 'None (same-account)'}")
        except Exception as e:
            print(f"    Error: {e}")
    
    # Demo 4: Complete Parameter Handling
    print("\n4. Complete Parameter Handling")
    print("-" * 30)
    
    config = handle_cross_account_parameters(
        role_arn=None,
        account_id="123456789012",
        external_id="my-external-id",
        session_name="demo-session",
        default_session_name="default-agent"
    )
    
    print("  Input parameters:")
    print("    account_id: 123456789012")
    print("    external_id: my-external-id")
    print("    session_name: demo-session")
    
    print("\n  Resolved configuration:")
    for key, value in config.items():
        if key == 'current_identity':
            print(f"    {key}: {type(value).__name__} (identity info)")
        else:
            print(f"    {key}: {value}")
    
    # Demo 5: Environment Configuration
    print("\n5. Environment Configuration")
    print("-" * 28)
    
    try:
        env_config = get_environment_config(
            role_arn="arn:aws:iam::123456789012:role/COAReadOnlyRole",
            external_id="demo-external-id",
            session_name="demo-session",
            default_session_name="demo-agent",
            working_dir="/tmp/demo-workdir"
        )
        
        print("  Generated environment variables:")
        important_vars = [
            'AWS_ASSUME_ROLE_ARN',
            'AWS_ASSUME_ROLE_SESSION_NAME', 
            'AWS_ASSUME_ROLE_EXTERNAL_ID',
            'AWS_REGION',
            'AWS_API_MCP_WORKING_DIR',
            'FASTMCP_LOG_LEVEL'
        ]
        
        for var in important_vars:
            if var in env_config:
                print(f"    {var}: {env_config[var]}")
        
        print(f"\n  Total environment variables: {len(env_config)}")
        
    except Exception as e:
        print(f"  Environment config error: {e}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✅ Both aws_api_agent and aws_billing_management_agent now use:")
    print("   • Shared ARN validation")
    print("   • Shared environment configuration")
    print("   • Shared cross-account parameter handling")
    print("   • Shared error formatting")
    print("   • Consistent logging and debugging")
    print("\n✅ This eliminates code duplication and ensures consistency!")
    print("=" * 60)


if __name__ == "__main__":
    demo_shared_utilities()