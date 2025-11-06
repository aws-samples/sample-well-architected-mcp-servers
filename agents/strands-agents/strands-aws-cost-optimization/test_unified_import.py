#!/usr/bin/env python3
"""
Test that both agents can be imported and use shared utilities without conflicts.
"""

def test_imports():
    """Test that all modules can be imported successfully."""
    print("Testing imports...")
    
    try:
        # Test shared utilities import
        from aws_cross_account_utils import (
            validate_role_arn,
            get_environment_config,
            handle_cross_account_parameters
        )
        print("✅ Shared utilities imported successfully")
        
        # Test agent imports
        from aws_api_agent import aws_api_agent
        print("✅ AWS API agent imported successfully")
        
        from aws_billing_management_agent import aws_billing_management_agent
        print("✅ AWS Billing agent imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_shared_utilities_usage():
    """Test that shared utilities work correctly."""
    print("\nTesting shared utilities...")
    
    try:
        from aws_cross_account_utils import validate_role_arn, construct_role_arn
        
        # Test validation
        test_arn = "arn:aws:iam::123456789012:role/TestRole"
        if validate_role_arn(test_arn):
            print("✅ ARN validation works")
        else:
            print("❌ ARN validation failed")
            return False
        
        # Test construction
        constructed = construct_role_arn("123456789012")
        expected = "arn:aws:iam::123456789012:role/COAReadOnlyRole"
        if constructed == expected:
            print("✅ ARN construction works")
        else:
            print(f"❌ ARN construction failed: {constructed} != {expected}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Shared utilities error: {e}")
        return False


def test_agent_signatures():
    """Test that both agents have the expected signatures."""
    print("\nTesting agent signatures...")
    
    try:
        import inspect
        from aws_api_agent import aws_api_agent
        from aws_billing_management_agent import aws_billing_management_agent
        
        # Check signatures
        api_sig = inspect.signature(aws_api_agent)
        billing_sig = inspect.signature(aws_billing_management_agent)
        
        expected_params = ['query', 'env', 'role_arn', 'account_id', 'external_id', 'session_name']
        
        api_params = list(api_sig.parameters.keys())
        billing_params = list(billing_sig.parameters.keys())
        
        if api_params == expected_params and billing_params == expected_params:
            print("✅ Both agents have correct signatures")
            return True
        else:
            print(f"❌ Signature mismatch:")
            print(f"  API agent: {api_params}")
            print(f"  Billing agent: {billing_params}")
            print(f"  Expected: {expected_params}")
            return False
            
    except Exception as e:
        print(f"❌ Signature test error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("UNIFIED IMPORT AND USAGE TEST")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_shared_utilities_usage,
        test_agent_signatures
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
        print("✅ All tests passed! Unified helpers are working correctly.")
        print("\n🎉 Both agents successfully use shared utilities!")
        print("   • No code duplication")
        print("   • Consistent behavior") 
        print("   • Easy maintenance")
        return True
    else:
        print("❌ Some tests failed. Check the unified helper implementation.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)