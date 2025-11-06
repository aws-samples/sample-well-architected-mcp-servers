#!/usr/bin/env python3
"""
Comprehensive validation script for version isolation and functionality.

This script validates that:
1. BedrockAgent version works without any AgentCore dependencies
2. AgentCore version works without any BedrockAgent dependencies  
3. Startup constraint enforcement prevents cross-version imports
4. Shared components work correctly with both versions
"""

import ast
import importlib
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import json


class VersionIsolationValidator:
    """Validates version isolation and dependency constraints."""
    
    def __init__(self, backend_root: str):
        self.backend_root = Path(backend_root)
        self.bedrockagent_path = self.backend_root / "bedrockagent"
        self.agentcore_path = self.backend_root / "agentcore"
        self.shared_path = self.backend_root / "shared"
        
        self.validation_results = {
            "bedrockagent_isolation": {},
            "agentcore_isolation": {},
            "shared_compatibility": {},
            "import_constraints": {},
            "startup_validation": {}
        }
    
    def validate_import_isolation(self) -> Dict[str, Any]:
        """Validate that versions don't import from each other."""
        print("🔍 Validating import isolation...")
        
        results = {
            "bedrockagent_violations": [],
            "agentcore_violations": [],
            "shared_violations": [],
            "success": True
        }
        
        # Check BedrockAgent doesn't import AgentCore
        bedrockagent_violations = self._check_forbidden_imports(
            self.bedrockagent_path,
            forbidden_patterns=["agentcore.", "from agentcore"]
        )
        
        # Check AgentCore doesn't import BedrockAgent
        agentcore_violations = self._check_forbidden_imports(
            self.agentcore_path,
            forbidden_patterns=["bedrockagent.", "from bedrockagent"]
        )
        
        # Check shared doesn't import version-specific modules
        shared_violations = self._check_forbidden_imports(
            self.shared_path,
            forbidden_patterns=["bedrockagent.", "agentcore.", "from bedrockagent", "from agentcore"]
        )
        
        results["bedrockagent_violations"] = bedrockagent_violations
        results["agentcore_violations"] = agentcore_violations
        results["shared_violations"] = shared_violations
        
        total_violations = len(bedrockagent_violations) + len(agentcore_violations) + len(shared_violations)
        results["success"] = total_violations == 0
        
        if results["success"]:
            print("✅ Import isolation validation passed")
        else:
            print(f"❌ Import isolation validation failed ({total_violations} violations)")
            for violation in bedrockagent_violations:
                print(f"  BedrockAgent violation: {violation}")
            for violation in agentcore_violations:
                print(f"  AgentCore violation: {violation}")
            for violation in shared_violations:
                print(f"  Shared violation: {violation}")
        
        return results
    
    def _check_forbidden_imports(self, directory: Path, forbidden_patterns: List[str]) -> List[str]:
        """Check for forbidden import patterns in Python files."""
        violations = []
        
        if not directory.exists():
            return violations
        
        for py_file in directory.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST to find imports
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                import_name = alias.name
                                if any(pattern in import_name for pattern in forbidden_patterns):
                                    violations.append(f"{py_file.relative_to(self.backend_root)}: import {import_name}")
                        
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                import_stmt = f"from {node.module}"
                                if any(pattern in import_stmt for pattern in forbidden_patterns):
                                    violations.append(f"{py_file.relative_to(self.backend_root)}: {import_stmt}")
                
                except SyntaxError:
                    # Skip files with syntax errors
                    continue
                    
            except Exception as e:
                print(f"Warning: Could not analyze {py_file}: {e}")
        
        return violations
    
    def validate_shared_component_compatibility(self) -> Dict[str, Any]:
        """Validate that shared components work with both versions."""
        print("🔍 Validating shared component compatibility...")
        
        results = {
            "bedrockagent_compatibility": {},
            "agentcore_compatibility": {},
            "success": True
        }
        
        # Test shared components with BedrockAgent context
        bedrockagent_compat = self._test_shared_imports("bedrockagent")
        results["bedrockagent_compatibility"] = bedrockagent_compat
        
        # Test shared components with AgentCore context
        agentcore_compat = self._test_shared_imports("agentcore")
        results["agentcore_compatibility"] = agentcore_compat
        
        results["success"] = bedrockagent_compat["success"] and agentcore_compat["success"]
        
        if results["success"]:
            print("✅ Shared component compatibility validation passed")
        else:
            print("❌ Shared component compatibility validation failed")
        
        return results
    
    def _test_shared_imports(self, version_context: str) -> Dict[str, Any]:
        """Test shared component imports in a specific version context."""
        results = {
            "importable_modules": [],
            "failed_imports": [],
            "success": True
        }
        
        # Create a test script to import shared modules
        test_script = f"""
import sys
import os

# Add paths for the specific version context
backend_root = r"{self.backend_root}"
sys.path.insert(0, backend_root)
sys.path.insert(0, os.path.join(backend_root, "{version_context}"))
sys.path.insert(0, os.path.join(backend_root, "shared"))

# Set environment variable to indicate version
os.environ["BACKEND_MODE"] = "{version_context}"

# Test shared module imports
shared_modules = [
    "shared.services.config_service",
    "shared.services.auth_service", 
    "shared.services.aws_config_service",
    "shared.services.bedrock_model_service",
    "shared.models.chat_models",
    "shared.models.exceptions",
    "shared.utils.logging_utils",
    "shared.utils.parameter_manager"
]

importable = []
failed = []

for module in shared_modules:
    try:
        __import__(module)
        importable.append(module)
    except Exception as e:
        failed.append({{
            "module": module,
            "error": str(e)
        }})

print("IMPORTABLE:", importable)
print("FAILED:", failed)
"""
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_script)
                test_file = f.name
            
            # Run the test script
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse output
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if line.startswith("IMPORTABLE:"):
                    importable_str = line.replace("IMPORTABLE:", "").strip()
                    if importable_str:
                        results["importable_modules"] = eval(importable_str)
                elif line.startswith("FAILED:"):
                    failed_str = line.replace("FAILED:", "").strip()
                    if failed_str and failed_str != "[]":
                        results["failed_imports"] = eval(failed_str)
            
            results["success"] = len(results["failed_imports"]) == 0
            
        except Exception as e:
            results["failed_imports"].append({
                "module": "test_execution",
                "error": str(e)
            })
            results["success"] = False
        
        finally:
            # Clean up test file
            try:
                os.unlink(test_file)
            except:
                pass
        
        return results
    
    def validate_startup_constraints(self) -> Dict[str, Any]:
        """Validate startup constraint enforcement."""
        print("🔍 Validating startup constraints...")
        
        results = {
            "bedrockagent_startup": {},
            "agentcore_startup": {},
            "constraint_enforcement": {},
            "success": True
        }
        
        # Test BedrockAgent startup
        bedrockagent_startup = self._test_version_startup("bedrockagent")
        results["bedrockagent_startup"] = bedrockagent_startup
        
        # Test AgentCore startup
        agentcore_startup = self._test_version_startup("agentcore")
        results["agentcore_startup"] = agentcore_startup
        
        # Test constraint enforcement (try to start with wrong mode)
        constraint_test = self._test_constraint_enforcement()
        results["constraint_enforcement"] = constraint_test
        
        results["success"] = (
            bedrockagent_startup["success"] and 
            agentcore_startup["success"] and 
            constraint_test["success"]
        )
        
        if results["success"]:
            print("✅ Startup constraints validation passed")
        else:
            print("❌ Startup constraints validation failed")
        
        return results
    
    def _test_version_startup(self, version: str) -> Dict[str, Any]:
        """Test startup for a specific version."""
        results = {
            "can_import_app": False,
            "can_create_app": False,
            "app_info": {},
            "success": False,
            "error": None
        }
        
        # Create test script for version startup
        test_script = f"""
import sys
import os

# Add paths
backend_root = r"{self.backend_root}"
sys.path.insert(0, backend_root)
sys.path.insert(0, os.path.join(backend_root, "{version}"))
sys.path.insert(0, os.path.join(backend_root, "shared"))

# Set environment variable
os.environ["BACKEND_MODE"] = "{version}"

try:
    # Test app import
    if "{version}" == "bedrockagent":
        from bedrockagent.app import create_bedrockagent_app_minimal, get_bedrockagent_info
        print("IMPORT_SUCCESS: bedrockagent")
        
        # Test app creation (minimal mode to avoid dependencies)
        app = create_bedrockagent_app_minimal()
        print("APP_CREATION_SUCCESS: bedrockagent")
        
        # Get app info
        info = get_bedrockagent_info(minimal_mode=True)
        print("APP_INFO:", info)
        
    elif "{version}" == "agentcore":
        from agentcore.app import create_agentcore_app_minimal, get_agentcore_info
        print("IMPORT_SUCCESS: agentcore")
        
        # Test app creation (minimal mode to avoid dependencies)
        app = create_agentcore_app_minimal()
        print("APP_CREATION_SUCCESS: agentcore")
        
        # Get app info
        info = get_agentcore_info(minimal_mode=True)
        print("APP_INFO:", info)
        
except Exception as e:
    print("ERROR:", str(e))
    import traceback
    traceback.print_exc()
"""
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_script)
                test_file = f.name
            
            # Run the test script
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Parse output
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if line.startswith("IMPORT_SUCCESS:"):
                    results["can_import_app"] = True
                elif line.startswith("APP_CREATION_SUCCESS:"):
                    results["can_create_app"] = True
                elif line.startswith("APP_INFO:"):
                    try:
                        info_str = line.replace("APP_INFO:", "").strip()
                        results["app_info"] = eval(info_str)
                    except:
                        pass
                elif line.startswith("ERROR:"):
                    results["error"] = line.replace("ERROR:", "").strip()
            
            results["success"] = results["can_import_app"] and results["can_create_app"]
            
        except Exception as e:
            results["error"] = str(e)
            results["success"] = False
        
        finally:
            # Clean up test file
            try:
                os.unlink(test_file)
            except:
                pass
        
        return results
    
    def _test_constraint_enforcement(self) -> Dict[str, Any]:
        """Test that constraint enforcement prevents cross-version imports."""
        results = {
            "bedrockagent_prevents_agentcore": False,
            "agentcore_prevents_bedrockagent": False,
            "success": False
        }
        
        # Test that BedrockAgent mode prevents AgentCore imports
        bedrockagent_test = self._test_cross_version_import("bedrockagent", "agentcore")
        results["bedrockagent_prevents_agentcore"] = not bedrockagent_test["import_succeeded"]
        
        # Test that AgentCore mode prevents BedrockAgent imports
        agentcore_test = self._test_cross_version_import("agentcore", "bedrockagent")
        results["agentcore_prevents_bedrockagent"] = not agentcore_test["import_succeeded"]
        
        results["success"] = (
            results["bedrockagent_prevents_agentcore"] and 
            results["agentcore_prevents_bedrockagent"]
        )
        
        return results
    
    def _test_cross_version_import(self, current_mode: str, forbidden_version: str) -> Dict[str, Any]:
        """Test cross-version import prevention."""
        results = {
            "import_succeeded": False,
            "error": None
        }
        
        test_script = f"""
import sys
import os

# Add paths
backend_root = r"{self.backend_root}"
sys.path.insert(0, backend_root)
sys.path.insert(0, os.path.join(backend_root, "{current_mode}"))
sys.path.insert(0, os.path.join(backend_root, "shared"))

# Set environment variable for current mode
os.environ["BACKEND_MODE"] = "{current_mode}"

try:
    # Try to import from forbidden version
    if "{forbidden_version}" == "bedrockagent":
        from bedrockagent.app import create_bedrockagent_app
        print("IMPORT_SUCCEEDED: bedrockagent")
    elif "{forbidden_version}" == "agentcore":
        from agentcore.app import create_agentcore_app
        print("IMPORT_SUCCEEDED: agentcore")
        
except Exception as e:
    print("IMPORT_FAILED:", str(e))
"""
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_script)
                test_file = f.name
            
            # Run the test script
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse output
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if line.startswith("IMPORT_SUCCEEDED:"):
                    results["import_succeeded"] = True
                elif line.startswith("IMPORT_FAILED:"):
                    results["error"] = line.replace("IMPORT_FAILED:", "").strip()
            
        except Exception as e:
            results["error"] = str(e)
        
        finally:
            # Clean up test file
            try:
                os.unlink(test_file)
            except:
                pass
        
        return results
    
    def run_all_validations(self) -> Dict[str, Any]:
        """Run all validation tests."""
        print("🚀 Starting Version Isolation Validation")
        print(f"Backend root: {self.backend_root}")
        
        # Run all validation tests
        import_isolation = self.validate_import_isolation()
        self.validation_results["import_constraints"] = import_isolation
        
        shared_compatibility = self.validate_shared_component_compatibility()
        self.validation_results["shared_compatibility"] = shared_compatibility
        
        startup_validation = self.validate_startup_constraints()
        self.validation_results["startup_validation"] = startup_validation
        
        # Overall success
        overall_success = (
            import_isolation["success"] and
            shared_compatibility["success"] and
            startup_validation["success"]
        )
        
        print(f"\n📊 Validation Summary")
        print(f"Import isolation: {'✅ PASS' if import_isolation['success'] else '❌ FAIL'}")
        print(f"Shared compatibility: {'✅ PASS' if shared_compatibility['success'] else '❌ FAIL'}")
        print(f"Startup validation: {'✅ PASS' if startup_validation['success'] else '❌ FAIL'}")
        print(f"Overall: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        return {
            "success": overall_success,
            "results": self.validation_results
        }
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a detailed validation report."""
        report_lines = [
            "# Version Isolation Validation Report",
            f"Generated: {os.popen('date').read().strip()}",
            f"Backend root: {self.backend_root}",
            "",
            "## Summary",
        ]
        
        # Add summary
        results = self.validation_results
        import_success = results.get("import_constraints", {}).get("success", False)
        shared_success = results.get("shared_compatibility", {}).get("success", False)
        startup_success = results.get("startup_validation", {}).get("success", False)
        
        overall_success = import_success and shared_success and startup_success
        
        report_lines.extend([
            f"- Import isolation: {'PASS' if import_success else 'FAIL'}",
            f"- Shared compatibility: {'PASS' if shared_success else 'FAIL'}",
            f"- Startup validation: {'PASS' if startup_success else 'FAIL'}",
            f"- Overall: {'PASS' if overall_success else 'FAIL'}",
            ""
        ])
        
        # Add detailed results
        if "import_constraints" in results:
            report_lines.extend([
                "## Import Isolation Results",
                f"- BedrockAgent violations: {len(results['import_constraints'].get('bedrockagent_violations', []))}",
                f"- AgentCore violations: {len(results['import_constraints'].get('agentcore_violations', []))}",
                f"- Shared violations: {len(results['import_constraints'].get('shared_violations', []))}",
                ""
            ])
        
        if "shared_compatibility" in results:
            report_lines.extend([
                "## Shared Component Compatibility",
                f"- BedrockAgent context: {'PASS' if results['shared_compatibility'].get('bedrockagent_compatibility', {}).get('success') else 'FAIL'}",
                f"- AgentCore context: {'PASS' if results['shared_compatibility'].get('agentcore_compatibility', {}).get('success') else 'FAIL'}",
                ""
            ])
        
        if "startup_validation" in results:
            report_lines.extend([
                "## Startup Validation",
                f"- BedrockAgent startup: {'PASS' if results['startup_validation'].get('bedrockagent_startup', {}).get('success') else 'FAIL'}",
                f"- AgentCore startup: {'PASS' if results['startup_validation'].get('agentcore_startup', {}).get('success') else 'FAIL'}",
                f"- Constraint enforcement: {'PASS' if results['startup_validation'].get('constraint_enforcement', {}).get('success') else 'FAIL'}",
                ""
            ])
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            print(f"📄 Report saved to: {output_file}")
        
        return report_content


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate version isolation and functionality")
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
    
    # Create validator
    validator = VersionIsolationValidator(args.backend_root)
    
    # Run validations
    results = validator.run_all_validations()
    
    # Generate report if requested
    if args.report:
        validator.generate_report(args.report)
    
    # Save JSON results if requested
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"📄 JSON results saved to: {args.json}")
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()