#!/usr/bin/env python3
"""
Test script to verify CLI functionality works correctly.
"""

import sys
import subprocess
from pathlib import Path

def test_cli_help():
    """Test CLI help output."""
    print("Testing CLI help output...")
    
    # Test the module CLI
    result = subprocess.run([
        sys.executable, '-m', 'iam_validation.cli', '--help'
    ], cwd='deployment-scripts', capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Module CLI help works")
    else:
        print("❌ Module CLI help failed")
        print(result.stderr)
    
    # Test the standalone script
    result = subprocess.run([
        sys.executable, 'validate_iam_and_update_template.py', '--help'
    ], cwd='deployment-scripts', capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Standalone script help works")
    else:
        print("❌ Standalone script help failed")
        print(result.stderr)

def test_cli_show_config():
    """Test CLI show configuration."""
    print("\nTesting CLI show configuration...")
    
    # Test the module CLI
    result = subprocess.run([
        sys.executable, '-m', 'iam_validation.cli', '--show-config'
    ], cwd='deployment-scripts', capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Module CLI show config works")
        if "Configuration:" in result.stdout:
            print("✅ Configuration output contains expected content")
    else:
        print("❌ Module CLI show config failed")
        print(result.stderr)
    
    # Test the standalone script
    result = subprocess.run([
        sys.executable, 'validate_iam_and_update_template.py', '--show-config'
    ], cwd='deployment-scripts', capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Standalone script show config works")
    else:
        print("❌ Standalone script show config failed")
        print(result.stderr)

def test_cli_validate_prerequisites():
    """Test CLI prerequisites validation."""
    print("\nTesting CLI prerequisites validation...")
    
    # Test the module CLI
    result = subprocess.run([
        sys.executable, '-m', 'iam_validation.cli', '--validate-prerequisites'
    ], cwd='deployment-scripts', capture_output=True, text=True)
    
    # This should fail because files don't exist, but should not crash
    if result.returncode in [0, 1]:  # Either success or expected failure
        print("✅ Module CLI prerequisites validation works")
    else:
        print("❌ Module CLI prerequisites validation crashed")
        print(result.stderr)
    
    # Test the standalone script
    result = subprocess.run([
        sys.executable, 'validate_iam_and_update_template.py', '--validate-prerequisites'
    ], cwd='deployment-scripts', capture_output=True, text=True)
    
    if result.returncode in [0, 1]:  # Either success or expected failure
        print("✅ Standalone script prerequisites validation works")
    else:
        print("❌ Standalone script prerequisites validation crashed")
        print(result.stderr)

def main():
    """Run all CLI tests."""
    print("🧪 Testing CLI functionality...")
    print("=" * 50)
    
    test_cli_help()
    test_cli_show_config()
    test_cli_validate_prerequisites()
    
    print("\n" + "=" * 50)
    print("🎉 CLI testing completed!")

if __name__ == '__main__':
    main()