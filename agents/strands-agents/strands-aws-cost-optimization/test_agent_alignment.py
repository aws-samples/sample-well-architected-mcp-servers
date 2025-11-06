#!/usr/bin/env python3
"""
Test script to verify that both aws_api_agent and aws_billing_management_agent 
have aligned configuration structures for handling ARN parameters.
"""

import inspect
from aws_api_agent import aws_api_agent
from aws_billing_management_agent import aws_billing_management_agent
from aws_cross_account_utils import validate_role_arn, get_environment_config


def test_function_signatures():
    """Test that both agent functions have compatible signatures."""
    print("=== Testing Function Signatures ===")
    
    # Get function signatures
    api_sig = inspect.signature(aws_api_agent)
    billing_sig = inspect.signature(aws_billing_management_agent)
    
    print(f"aws_api_agent signature: {api_sig}")
    print(f"aws_billing_management_agent signature: {billing_sig}")
    
    # Check that both have the required parameters
    required_params = ['query', 'env', 'role_arn', 'account_id', 'external_id', 'session_name']
    
    api_params = list(api_sig.parameters.keys())
    billing_params = list(billing_sig.parameters.keys())
    
    print(f"\nAPI agent parameters: {api_params}")
    print(f"Billing agent parameters: {billing_params}")
    
    missing_in_api = [p for p in required_params if p not in api_params]
    missing_in_billing = [p for p in required_params if p not in billing_params]
    
    if missing_in_api:
        print(f"❌ Missing in API agent: {missing_in_api}")
    else:
        print("✅ API agent has all required parameters")
        
    if missing_in_billing:
        print(f"❌ Missing in billing agent: {missing_in_billing}")
    else:
        print("✅ Billing agent has all required parameters")
    
    return len(missing_in_api) == 0 and len(missing_in_billing) == 0


def test_validation_functions():
    """Test that the shared validation function works correctly."""
    print("\n=== Testing Shared Validation Function ===")
    
    test_cases = [
        ("arn:aws:iam::123456789012:role/TestRole", True),
        ("arn:aws:iam::123456789012:role/COAReadOnlyRole", True),
        ("invalid-arn", False),
        ("", False),
        (None, False),
    ]
    
    for arn, expected in test_cases:
        result = validate_role_arn(arn) if arn is not None else False
        
        print(f"ARN: {arn}")
        print(f"  Validation result: {result}")
        print(f"  Expected: {expected}")
        
        if result == expected:
            print("  ✅ Correct")
        else:
            print("  ❌ Incorrect")
            return False
    
    return True


def test_environment_config():
    """Test that the shared environment config function works correctly."""
    print("\n=== Testing Shared Environment Config Function ===")
    
    # Get function signature
    env_sig = inspect.signature(get_environment_config)
    
    print(f"Shared get_environment_config signature: {env_sig}")
    
    # Check parameters
    env_params = list(env_sig.parameters.keys())
    expected_params = ['role_arn', 'external_id', 'session_name', 'custom_env', 'default_session_name', 'working_dir']
    
    print(f"Environment config parameters: {env_params}")
    print(f"Expected parameters: {expected_params}")
    
    if all(param in env_params for param in expected_params[:4]):  # Check core parameters
        print("✅ Shared environment config function has expected parameters")
        return True
    else:
        print("❌ Shared environment config function missing expected parameters")
        return False


def test_cross_account_parameter_handling():
    """Test cross-account parameter handling logic using shared utilities."""
    print("\n=== Testing Cross-Account Parameter Handling ===")
    
    # Import the shared utility functions
    from aws_cross_account_utils import construct_role_arn, resolve_cross_account_parameters
    
    # Test account_id to role_arn construction logic
    test_account_id = "123456789012"
    expected_role_arn = f"arn:aws:iam::{test_account_id}:role/COAReadOnlyRole"
    
    print(f"Test account ID: {test_account_id}")
    print(f"Expected role ARN: {expected_role_arn}")
    
    # Test construction function
    constructed_arn = construct_role_arn(test_account_id)
    print(f"Constructed ARN: {constructed_arn}")
    
    # Test resolution function
    resolved_arn = resolve_cross_account_parameters(account_id=test_account_id)
    print(f"Resolved ARN: {resolved_arn}")
    
    # Validate the constructed ARN
    if (constructed_arn == expected_role_arn and 
        resolved_arn == expected_role_arn and 
        validate_role_arn(expected_role_arn)):
        print("✅ Cross-account parameter handling works correctly")
        return True
    else:
        print("❌ Cross-account parameter handling failed")
        return False


def main():
    """Run all alignment tests."""
    print("Testing Agent Configuration Alignment")
    print("=" * 50)
    
    tests = [
        test_function_signatures,
        test_validation_functions,
        test_environment_config,
        test_cross_account_parameter_handling,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with error: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed! Agent configurations are aligned.")
        return True
    else:
        print("❌ Some tests failed. Agent configurations need alignment.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)