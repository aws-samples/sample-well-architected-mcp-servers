#!/usr/bin/env python3
"""
Integration test for IAM validation functionality in deployment script.
Tests the integration without actually creating AWS resources.
"""

import subprocess
import sys
from pathlib import Path


def test_cli_import():
    """Test that the CLI module can be imported successfully."""
    print("Testing CLI module import...")
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from iam_validation.cli import main
        print("✅ CLI module import successful")
        return True
    except ImportError as e:
        print(f"❌ CLI module import failed: {e}")
        return False


def test_cli_help():
    """Test that the CLI help command works."""
    print("Testing CLI help command...")
    try:
        # Set up environment with correct Python path
        env = {'PYTHONPATH': str(Path(__file__).parent)}
        
        result = subprocess.run([
            sys.executable, '-m', 'iam_validation.cli', '--help'
        ], capture_output=True, text=True, env=env, cwd=Path(__file__).parent)
        
        if result.returncode == 0 and 'IAM validation and CloudFormation template update tool' in result.stdout:
            print("✅ CLI help command successful")
            return True
        else:
            print(f"❌ CLI help command failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI help command failed: {e}")
        return False


def test_cli_show_config():
    """Test that the CLI show-config command works."""
    print("Testing CLI show-config command...")
    try:
        # Set up environment with correct Python path
        env = {'PYTHONPATH': str(Path(__file__).parent)}
        
        result = subprocess.run([
            sys.executable, '-m', 'iam_validation.cli', '--show-config'
        ], capture_output=True, text=True, env=env, cwd=Path(__file__).parent)
        
        if result.returncode == 0 and 'Current Configuration:' in result.stdout:
            print("✅ CLI show-config command successful")
            return True
        else:
            print(f"❌ CLI show-config command failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI show-config command failed: {e}")
        return False


def test_deployment_script_help():
    """Test that the deployment script help includes new options."""
    print("Testing deployment script help...")
    try:
        # Get the parent directory (project root)
        project_root = Path(__file__).parent.parent
        deploy_script = project_root / 'deploy-coa.sh'
        
        result = subprocess.run([
            str(deploy_script), '--help'
        ], capture_output=True, text=True)
        
        if (result.returncode == 0 and 
            '--validate-iam' in result.stdout and 
            '--template-version' in result.stdout):
            print("✅ Deployment script help includes new options")
            return True
        else:
            print(f"❌ Deployment script help missing new options")
            return False
    except Exception as e:
        print(f"❌ Deployment script help test failed: {e}")
        return False


def test_required_files():
    """Test that all required files exist."""
    print("Testing required files...")
    
    # Get the deployment-scripts directory
    deployment_dir = Path(__file__).parent
    
    required_files = [
        'cloud-optimization-assistant-0.1.0.yaml',
        'policies/agentCore-runtime-coa-mcp-sts-policy.json',
        'policies/agentCore-runtime-coa-ssm-policy.json',
        'policies/agentCore-runtime-execution-role-plicy.json',
        'iam_validation/cli.py',
        'iam_validation/orchestrator.py',
        'iam_validation/template_manager.py',
    ]
    
    all_exist = True
    for file_path in required_files:
        path = deployment_dir / file_path
        if path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - NOT FOUND")
            all_exist = False
    
    return all_exist


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("IAM VALIDATION INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        test_required_files,
        test_cli_import,
        test_cli_help,
        test_cli_show_config,
        test_deployment_script_help,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        print(f"\n{test.__name__.replace('_', ' ').title()}:")
        print("-" * 40)
        
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! IAM validation integration is working correctly.")
        return 0
    else:
        print(f"\n💥 {failed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())