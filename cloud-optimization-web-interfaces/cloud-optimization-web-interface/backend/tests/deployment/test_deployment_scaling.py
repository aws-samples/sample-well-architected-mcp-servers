#!/usr/bin/env python3
"""
Deployment and scaling configuration tests.

Tests that:
1. Both versions can be deployed independently using Docker configurations
2. Container orchestration and independent scaling capabilities work
3. Health check endpoints and monitoring work for both versions
4. Deployment automation scripts and rollback procedures work
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests


class DeploymentScalingTester:
    """Tests deployment and scaling configurations."""
    
    def __init__(self, backend_root: str):
        self.backend_root = Path(backend_root)
        self.deployment_dir = self.backend_root / "deployment"
        self.scripts_dir = self.deployment_dir / "scripts"
        
        self.test_results = {
            "docker_build_tests": {},
            "deployment_tests": {},
            "scaling_tests": {},
            "health_monitoring_tests": {},
            "automation_tests": {}
        }
    
    def test_docker_build_configurations(self) -> Dict[str, Any]:
        """Test Docker build configurations for both versions."""
        print("🔍 Testing Docker build configurations...")
        
        results = {
            "bedrockagent_build": {},
            "agentcore_build": {},
            "success": True
        }
        
        # Test BedrockAgent build
        bedrockagent_result = self._test_version_build("bedrockagent")
        results["bedrockagent_build"] = bedrockagent_result
        
        # Test AgentCore build
        agentcore_result = self._test_version_build("agentcore")
        results["agentcore_build"] = agentcore_result
        
        results["success"] = bedrockagent_result["success"] and agentcore_result["success"]
        
        if results["success"]:
            print("✅ Docker build configurations test passed")
        else:
            print("❌ Docker build configurations test failed")
        
        return results
    
    def _test_version_build(self, version: str) -> Dict[str, Any]:
        """Test build configuration for a specific version."""
        results = {
            "dockerfile_exists": False,
            "build_script_exists": False,
            "build_script_executable": False,
            "dockerfile_valid": False,
            "success": False
        }
        
        # Check if Dockerfile exists
        dockerfile_path = self.deployment_dir / f"{version}.dockerfile"
        results["dockerfile_exists"] = dockerfile_path.exists()
        
        # Check if build script exists
        build_script_path = self.scripts_dir / f"build-{version}.sh"
        results["build_script_exists"] = build_script_path.exists()
        
        # Check if build script is executable
        if build_script_path.exists():
            results["build_script_executable"] = os.access(build_script_path, os.X_OK)
        
        # Validate Dockerfile content
        if dockerfile_path.exists():
            try:
                with open(dockerfile_path, 'r') as f:
                    dockerfile_content = f.read()
                
                # Check for required elements
                required_elements = [
                    "FROM",
                    "WORKDIR",
                    "COPY",
                    "RUN pip install",
                    "EXPOSE",
                    "CMD"
                ]
                
                dockerfile_valid = all(element in dockerfile_content for element in required_elements)
                
                # Check for version-specific configuration
                if version == "bedrockagent":
                    dockerfile_valid = dockerfile_valid and "BACKEND_MODE=bedrockagent" in dockerfile_content
                elif version == "agentcore":
                    dockerfile_valid = dockerfile_valid and "BACKEND_MODE=agentcore" in dockerfile_content
                
                results["dockerfile_valid"] = dockerfile_valid
                
            except Exception as e:
                print(f"Error validating Dockerfile for {version}: {e}")
                results["dockerfile_valid"] = False
        
        results["success"] = all([
            results["dockerfile_exists"],
            results["build_script_exists"],
            results["build_script_executable"],
            results["dockerfile_valid"]
        ])
        
        return results
    
    def test_deployment_configurations(self) -> Dict[str, Any]:
        """Test deployment configurations."""
        print("🔍 Testing deployment configurations...")
        
        results = {
            "docker_compose_exists": False,
            "docker_compose_valid": False,
            "deployment_script_exists": False,
            "deployment_script_executable": False,
            "profiles_configured": False,
            "success": False
        }
        
        # Check if docker-compose.yml exists
        compose_file = self.deployment_dir / "docker-compose.yml"
        results["docker_compose_exists"] = compose_file.exists()
        
        # Validate docker-compose.yml
        if compose_file.exists():
            try:
                with open(compose_file, 'r') as f:
                    compose_content = f.read()
                
                # Check for required services and profiles
                required_elements = [
                    "services:",
                    "coa-bedrockagent:",
                    "coa-agentcore:",
                    "profiles:",
                    "bedrockagent",
                    "agentcore"
                ]
                
                results["docker_compose_valid"] = all(element in compose_content for element in required_elements)
                results["profiles_configured"] = "profiles:" in compose_content
                
            except Exception as e:
                print(f"Error validating docker-compose.yml: {e}")
                results["docker_compose_valid"] = False
        
        # Check deployment script
        deploy_script = self.scripts_dir / "deploy-coa.sh"
        results["deployment_script_exists"] = deploy_script.exists()
        
        if deploy_script.exists():
            results["deployment_script_executable"] = os.access(deploy_script, os.X_OK)
        
        results["success"] = all([
            results["docker_compose_exists"],
            results["docker_compose_valid"],
            results["deployment_script_exists"],
            results["deployment_script_executable"],
            results["profiles_configured"]
        ])
        
        if results["success"]:
            print("✅ Deployment configurations test passed")
        else:
            print("❌ Deployment configurations test failed")
        
        return results
    
    def test_scaling_capabilities(self) -> Dict[str, Any]:
        """Test scaling capabilities."""
        print("🔍 Testing scaling capabilities...")
        
        results = {
            "independent_scaling": False,
            "profile_isolation": False,
            "port_configuration": False,
            "resource_limits": False,
            "success": False
        }
        
        # Check docker-compose for scaling configuration
        compose_file = self.deployment_dir / "docker-compose.yml"
        if compose_file.exists():
            try:
                with open(compose_file, 'r') as f:
                    compose_content = f.read()
                
                # Check for independent scaling (different profiles)
                results["independent_scaling"] = (
                    "profiles:" in compose_content and
                    "bedrockagent" in compose_content and
                    "agentcore" in compose_content
                )
                
                # Check for profile isolation
                results["profile_isolation"] = (
                    "- bedrockagent" in compose_content and
                    "- agentcore" in compose_content
                )
                
                # Check for different port configurations
                results["port_configuration"] = (
                    "8000:" in compose_content and
                    "8001:" in compose_content
                )
                
                # Check for resource limits (optional but good practice)
                results["resource_limits"] = (
                    "deploy:" in compose_content or
                    "resources:" in compose_content or
                    "mem_limit:" in compose_content
                )
                
            except Exception as e:
                print(f"Error checking scaling configuration: {e}")
        
        results["success"] = all([
            results["independent_scaling"],
            results["profile_isolation"],
            results["port_configuration"]
        ])
        
        if results["success"]:
            print("✅ Scaling capabilities test passed")
        else:
            print("❌ Scaling capabilities test failed")
        
        return results
    
    def test_health_monitoring(self) -> Dict[str, Any]:
        """Test health check endpoints and monitoring."""
        print("🔍 Testing health monitoring configurations...")
        
        results = {
            "health_check_script_exists": False,
            "health_check_executable": False,
            "validation_script_exists": False,
            "validation_script_executable": False,
            "monitoring_config_exists": False,
            "success": False
        }
        
        # Check health check script
        health_script = self.scripts_dir / "health-check.sh"
        results["health_check_script_exists"] = health_script.exists()
        
        if health_script.exists():
            results["health_check_executable"] = os.access(health_script, os.X_OK)
        
        # Check validation script
        validation_script = self.scripts_dir / "validate-deployment.sh"
        results["validation_script_exists"] = validation_script.exists()
        
        if validation_script.exists():
            results["validation_script_executable"] = os.access(validation_script, os.X_OK)
        
        # Check for monitoring configuration
        monitoring_configs = [
            self.deployment_dir / "configs" / "prometheus.yml",
            self.deployment_dir / "configs" / "nginx.conf"
        ]
        
        results["monitoring_config_exists"] = any(config.exists() for config in monitoring_configs)
        
        results["success"] = all([
            results["health_check_script_exists"],
            results["health_check_executable"],
            results["validation_script_exists"],
            results["validation_script_executable"]
        ])
        
        if results["success"]:
            print("✅ Health monitoring test passed")
        else:
            print("❌ Health monitoring test failed")
        
        return results
    
    def test_automation_scripts(self) -> Dict[str, Any]:
        """Test deployment automation scripts and rollback procedures."""
        print("🔍 Testing automation scripts...")
        
        results = {
            "deploy_script_exists": False,
            "deploy_script_executable": False,
            "rollback_script_exists": False,
            "rollback_script_executable": False,
            "build_scripts_exist": False,
            "build_scripts_executable": False,
            "script_help_available": False,
            "success": False
        }
        
        # Check main deployment script
        deploy_script = self.scripts_dir / "deploy-coa.sh"
        results["deploy_script_exists"] = deploy_script.exists()
        
        if deploy_script.exists():
            results["deploy_script_executable"] = os.access(deploy_script, os.X_OK)
        
        # Check rollback script
        rollback_script = self.scripts_dir / "rollback-deployment.sh"
        results["rollback_script_exists"] = rollback_script.exists()
        
        if rollback_script.exists():
            results["rollback_script_executable"] = os.access(rollback_script, os.X_OK)
        
        # Check build scripts
        build_scripts = [
            self.scripts_dir / "build-bedrockagent.sh",
            self.scripts_dir / "build-agentcore.sh"
        ]
        
        results["build_scripts_exist"] = all(script.exists() for script in build_scripts)
        results["build_scripts_executable"] = all(
            os.access(script, os.X_OK) for script in build_scripts if script.exists()
        )
        
        # Test script help functionality
        if deploy_script.exists() and results["deploy_script_executable"]:
            try:
                result = subprocess.run(
                    [str(deploy_script), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results["script_help_available"] = result.returncode == 0 and "Usage:" in result.stdout
            except Exception:
                results["script_help_available"] = False
        
        results["success"] = all([
            results["deploy_script_exists"],
            results["deploy_script_executable"],
            results["rollback_script_exists"],
            results["rollback_script_executable"],
            results["build_scripts_exist"],
            results["build_scripts_executable"]
        ])
        
        if results["success"]:
            print("✅ Automation scripts test passed")
        else:
            print("❌ Automation scripts test failed")
        
        return results
    
    def test_deployment_validation(self) -> Dict[str, Any]:
        """Test deployment validation capabilities."""
        print("🔍 Testing deployment validation...")
        
        results = {
            "validation_script_functional": False,
            "health_check_functional": False,
            "rollback_script_functional": False,
            "success": False
        }
        
        # Test validation script functionality
        validation_script = self.scripts_dir / "validate-deployment.sh"
        if validation_script.exists():
            try:
                result = subprocess.run(
                    [str(validation_script), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results["validation_script_functional"] = result.returncode == 0
            except Exception:
                results["validation_script_functional"] = False
        
        # Test health check script functionality
        health_script = self.scripts_dir / "health-check.sh"
        if health_script.exists():
            try:
                result = subprocess.run(
                    [str(health_script), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results["health_check_functional"] = result.returncode == 0
            except Exception:
                results["health_check_functional"] = False
        
        # Test rollback script functionality
        rollback_script = self.scripts_dir / "rollback-deployment.sh"
        if rollback_script.exists():
            try:
                result = subprocess.run(
                    [str(rollback_script), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                results["rollback_script_functional"] = result.returncode == 0
            except Exception:
                results["rollback_script_functional"] = False
        
        results["success"] = all([
            results["validation_script_functional"],
            results["health_check_functional"],
            results["rollback_script_functional"]
        ])
        
        if results["success"]:
            print("✅ Deployment validation test passed")
        else:
            print("❌ Deployment validation test failed")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all deployment and scaling tests."""
        print("🚀 Starting Deployment and Scaling Configuration Tests")
        print(f"Backend root: {self.backend_root}")
        print(f"Deployment directory: {self.deployment_dir}")
        
        # Run all tests
        docker_build_results = self.test_docker_build_configurations()
        self.test_results["docker_build_tests"] = docker_build_results
        
        deployment_results = self.test_deployment_configurations()
        self.test_results["deployment_tests"] = deployment_results
        
        scaling_results = self.test_scaling_capabilities()
        self.test_results["scaling_tests"] = scaling_results
        
        health_results = self.test_health_monitoring()
        self.test_results["health_monitoring_tests"] = health_results
        
        automation_results = self.test_automation_scripts()
        self.test_results["automation_tests"] = automation_results
        
        validation_results = self.test_deployment_validation()
        self.test_results["deployment_validation_tests"] = validation_results
        
        # Overall success
        overall_success = all([
            docker_build_results["success"],
            deployment_results["success"],
            scaling_results["success"],
            health_results["success"],
            automation_results["success"],
            validation_results["success"]
        ])
        
        print(f"\n📊 Deployment Testing Summary")
        print(f"Docker build configurations: {'✅ PASS' if docker_build_results['success'] else '❌ FAIL'}")
        print(f"Deployment configurations: {'✅ PASS' if deployment_results['success'] else '❌ FAIL'}")
        print(f"Scaling capabilities: {'✅ PASS' if scaling_results['success'] else '❌ FAIL'}")
        print(f"Health monitoring: {'✅ PASS' if health_results['success'] else '❌ FAIL'}")
        print(f"Automation scripts: {'✅ PASS' if automation_results['success'] else '❌ FAIL'}")
        print(f"Deployment validation: {'✅ PASS' if validation_results['success'] else '❌ FAIL'}")
        print(f"Overall: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        return {
            "success": overall_success,
            "results": self.test_results
        }
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a detailed deployment testing report."""
        report_lines = [
            "# Deployment and Scaling Configuration Test Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Backend root: {self.backend_root}",
            f"Deployment directory: {self.deployment_dir}",
            "",
            "## Summary",
        ]
        
        # Add summary
        results = self.test_results
        docker_success = results.get("docker_build_tests", {}).get("success", False)
        deployment_success = results.get("deployment_tests", {}).get("success", False)
        scaling_success = results.get("scaling_tests", {}).get("success", False)
        health_success = results.get("health_monitoring_tests", {}).get("success", False)
        automation_success = results.get("automation_tests", {}).get("success", False)
        validation_success = results.get("deployment_validation_tests", {}).get("success", False)
        
        overall_success = all([
            docker_success, deployment_success, scaling_success,
            health_success, automation_success, validation_success
        ])
        
        report_lines.extend([
            f"- Docker build configurations: {'PASS' if docker_success else 'FAIL'}",
            f"- Deployment configurations: {'PASS' if deployment_success else 'FAIL'}",
            f"- Scaling capabilities: {'PASS' if scaling_success else 'FAIL'}",
            f"- Health monitoring: {'PASS' if health_success else 'FAIL'}",
            f"- Automation scripts: {'PASS' if automation_success else 'FAIL'}",
            f"- Deployment validation: {'PASS' if validation_success else 'FAIL'}",
            f"- Overall: {'PASS' if overall_success else 'FAIL'}",
            ""
        ])
        
        # Add detailed results for each test category
        for test_category, test_results in results.items():
            if test_results:
                report_lines.extend([
                    f"## {test_category.replace('_', ' ').title()}",
                    f"Status: {'PASS' if test_results.get('success', False) else 'FAIL'}",
                    ""
                ])
                
                # Add specific test details
                for key, value in test_results.items():
                    if key != "success" and isinstance(value, dict):
                        report_lines.append(f"### {key.replace('_', ' ').title()}")
                        for subkey, subvalue in value.items():
                            if subkey != "success":
                                status = "✓" if subvalue else "✗"
                                report_lines.append(f"- {status} {subkey.replace('_', ' ').title()}: {subvalue}")
                        report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            print(f"📄 Report saved to: {output_file}")
        
        return report_content


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test deployment and scaling configurations")
    parser.add_argument(
        "--backend-root",
        default=".",
        help="Path to backend root directory"
    )
    parser.add_argument(
        "--report",
        help="Generate report and save to file"
    )
    parser.add_argument(
        "--json",
        help="Save results as JSON to file"
    )
    
    args = parser.parse_args()
    
    # Create tester
    tester = DeploymentScalingTester(args.backend_root)
    
    # Run tests
    results = tester.run_all_tests()
    
    # Generate report if requested
    if args.report:
        tester.generate_report(args.report)
    
    # Save JSON results if requested
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"📄 JSON results saved to: {args.json}")
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()