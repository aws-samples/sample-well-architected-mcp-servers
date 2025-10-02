#!/usr/bin/env python3
"""
Example script demonstrating AssumeRole functionality in the Well-Architected Security MCP Server.

This script shows how to configure and use AssumeRole for cross-account security assessments.
"""

import os


def validate_assume_role_config():
    """Validate AssumeRole configuration from environment variables."""
    assume_role_arn = os.environ.get("AWS_ASSUME_ROLE_ARN")
    
    if not assume_role_arn:
        return {
            "configured": False,
            "valid": True,
            "message": "No AssumeRole configuration found. Using default credentials chain.",
        }
    
    issues = []
    
    # Validate ARN format
    if not assume_role_arn.startswith("arn:aws:iam::"):
        issues.append("AWS_ASSUME_ROLE_ARN does not appear to be a valid IAM role ARN")
    
    # Check session name
    session_name = os.environ.get("AWS_ASSUME_ROLE_SESSION_NAME", "mcp-server-session")
    if len(session_name) < 2 or len(session_name) > 64:
        issues.append("AWS_ASSUME_ROLE_SESSION_NAME must be between 2 and 64 characters")
    
    # Check external ID if provided
    external_id = os.environ.get("AWS_ASSUME_ROLE_EXTERNAL_ID")
    if external_id and (len(external_id) < 2 or len(external_id) > 1224):
        issues.append("AWS_ASSUME_ROLE_EXTERNAL_ID must be between 2 and 1224 characters")
    
    return {
        "configured": True,
        "valid": len(issues) == 0,
        "role_arn": assume_role_arn,
        "session_name": session_name,
        "external_id_configured": bool(external_id),
        "issues": issues,
        "message": "AssumeRole configuration is valid" if len(issues) == 0 else f"Configuration issues: {'; '.join(issues)}",
    }


def demonstrate_assume_role():
    """Demonstrate AssumeRole functionality with different configurations."""
    
    print("=== AWS Well-Architected Security MCP Server - AssumeRole Demo ===\n")
    
    # Test 1: Default credentials (no AssumeRole)
    print("1. Testing default AWS credentials chain...")
    
    # Clear any existing AssumeRole environment variables
    for key in ["AWS_ASSUME_ROLE_ARN", "AWS_ASSUME_ROLE_SESSION_NAME", "AWS_ASSUME_ROLE_EXTERNAL_ID"]:
        if key in os.environ:
            del os.environ[key]
    
    config = validate_assume_role_config()
    print(f"   Configuration: {config['message']}")
    
    print("   Note: Session creation skipped in this demo")
    
    print()
    
    # Test 2: AssumeRole configuration (simulated)
    print("2. Testing AssumeRole configuration (simulated)...")
    
    # Set up AssumeRole environment variables (example values)
    os.environ["AWS_ASSUME_ROLE_ARN"] = "arn:aws:iam::123456789012:role/SecurityAuditRole"
    os.environ["AWS_ASSUME_ROLE_SESSION_NAME"] = "mcp-demo-session"
    os.environ["AWS_ASSUME_ROLE_EXTERNAL_ID"] = "demo-external-id-2024"
    
    config = validate_assume_role_config()
    print(f"   Configuration: {config['message']}")
    print(f"   Role ARN: {config.get('role_arn', 'Not configured')}")
    print(f"   Session Name: {config.get('session_name', 'Not configured')}")
    print(f"   External ID Configured: {config.get('external_id_configured', False)}")
    
    # Note: We won't actually try to assume the role since it's just an example
    print("   Note: Actual AssumeRole operation skipped (example role ARN)")
    
    print()
    
    # Test 3: Invalid configuration
    print("3. Testing invalid AssumeRole configuration...")
    
    os.environ["AWS_ASSUME_ROLE_ARN"] = "invalid-arn-format"
    
    config = validate_assume_role_config()
    print(f"   Configuration: {config['message']}")
    if config.get('issues'):
        for issue in config['issues']:
            print(f"   Issue: {issue}")
    
    print()
    
    # Clean up
    for key in ["AWS_ASSUME_ROLE_ARN", "AWS_ASSUME_ROLE_SESSION_NAME", "AWS_ASSUME_ROLE_EXTERNAL_ID"]:
        if key in os.environ:
            del os.environ[key]
    
    print("=== Demo Complete ===")
    print("\nTo use AssumeRole in production:")
    print("1. Set AWS_ASSUME_ROLE_ARN to your target role ARN")
    print("2. Optionally set AWS_ASSUME_ROLE_SESSION_NAME and AWS_ASSUME_ROLE_EXTERNAL_ID")
    print("3. Ensure your current credentials can assume the target role")
    print("4. Run the MCP server - it will automatically use AssumeRole")


def main():
    """Main function to run the demonstration."""
    demonstrate_assume_role()


if __name__ == "__main__":
    main()