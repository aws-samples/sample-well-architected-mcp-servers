#!/usr/bin/env python3
"""
Comprehensive integration test runner for COA Backend versions.

This script runs all integration tests to validate version isolation,
graceful degradation, and functionality preservation.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

# Test configuration
DEFAULT_BEDROCKAGENT_URL = "http://localhost:8000"
DEFAULT_AGENTCORE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 300  # 5 minutes


class IntegrationTestRunner:
    """Integration test runner for COA Backend versions."""
    
    def __init__(self, 
                 bedrockagent_url: str = DEFAULT_BEDROCKAGENT_URL,
                 agentcore_url: str = DEFAULT_AGENTCORE_URL,
                 timeout: int = DEFAULT_TIMEOUT,
                 verbose: bool = False):
        self.bedrockagent_url = bedrockagent_url
        self.agentcore_url = agentcore_url
        self.timeout = timeout
        self.verbose = verbose
        self.test_results = {}
        
        # Set environment variables for tests
        os.environ["BEDROCKAGENT_URL"] = bedrockagent_url
        os.environ["AGENTCORE_URL"] = agentcore_url
    
    def check_services_availability(self) -> Dict[str, bool]:
        """Check if both services are available before running tests."""
        import requests
        
        availability = {
            "bedrockagent": False,
            "agentcore": False
        }
        
        try:
            bedrockagent_response = requests.get(f"{self.bedrockagent_url}/health", timeout=10)
            availability["bedrockagent"] = bedrockagent_response.status_code == 200
        except Exception as e:
            if self.verbose:
                print(f"BedrockAgent service check failed: {e}")
        
        try:
            agentcore_response = requests.get(f"{self.agentcore_url}/health", timeout=10)
            availability["agentcore"] = agentcore_response.status_code == 200
        except Exception as e:
            if self.verbose:
                print(f"AgentCore service check failed: {e}")
        
        return availability
    
    def run_test_suite(self, test_file: str, test_name: str) -> Dict[str, Any]:
        """Run a specific test suite."""
        print(f"\n🧪 Running {test_name}...")
        
        start_time = time.time()
        
        # Prepare pytest command
        cmd = [
            "python", "-m", "pytest",
            test_file,
            "-v",
            "--tb=short",
            "--json-report",
            f"--json-report-file=/tmp/pytest_report_{test_name.lower().replace(' ', '_')}.json",
            f"--timeout={self.timeout}"
        ]
        
        if self.verbose:
            cmd.append("-s")
        
        try:
            # Run the test
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            success = result.returncode == 0
            
            # Try to load JSON report
            json_report_file = f"/tmp/pytest_report_{test_name.lower().replace(' ', '_')}.json"
            test_details = {}
            
            try:
                if os.path.exists(json_report_file):
                    with open(json_report_file, 'r') as f:
                        json_report = json.load(f)
                        test_details = {
                            "total": json_report.get("summary", {}).get("total", 0),
                            "passed": json_report.get("summary", {}).get("passed", 0),
                            "failed": json_report.get("summary", {}).get("failed", 0),
                            "skipped": json_report.get("summary", {}).get("skipped", 0),
                            "errors": json_report.get("summary", {}).get("error", 0)
                        }
            except Exception as e:
                if self.verbose:
                    print(f"Failed to parse JSON report: {e}")
            
            # Print results
            if success:
                print(f"✅ {test_name} passed ({duration:.1f}s)")
                if test_details:
                    print(f"   Tests: {test_details['passed']}/{test_details['total']} passed")
            else:
                print(f"❌ {test_name} failed ({duration:.1f}s)")
                if test_details:
                    print(f"   Tests: {test_details['passed']}/{test_details['total']} passed, {test_details['failed']} failed")
                
                if self.verbose:
                    print("STDOUT:")
                    print(result.stdout)
                    print("STDERR:")
                    print(result.stderr)
            
            return {
                "success": success,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "details": test_details
            }
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_name} timed out after {self.timeout}s")
            return {
                "success": False,
                "duration": self.timeout,
                "stdout": "",
                "stderr": f"Test timed out after {self.timeout}s",
                "details": {}
            }
        except Exception as e:
            print(f"💥 {test_name} failed with exception: {e}")
            return {
                "success": False,
                "duration": 0,
                "stdout": "",
                "stderr": str(e),
                "details": {}
            }
    
    def run_all_tests(self, test_suites: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run all integration tests."""
        print("🚀 Starting COA Backend Integration Tests")
        print(f"BedrockAgent URL: {self.bedrockagent_url}")
        print(f"AgentCore URL: {self.agentcore_url}")
        print(f"Timeout: {self.timeout}s")
        
        # Check service availability
        print("\n🔍 Checking service availability...")
        availability = self.check_services_availability()
        
        if not availability["bedrockagent"]:
            print("⚠️  BedrockAgent service not available")
        else:
            print("✅ BedrockAgent service available")
        
        if not availability["agentcore"]:
            print("⚠️  AgentCore service not available")
        else:
            print("✅ AgentCore service available")
        
        if not any(availability.values()):
            print("❌ No services available. Cannot run integration tests.")
            return {"success": False, "error": "No services available"}
        
        # Define test suites
        all_test_suites = {
            "Version Isolation": "integration/test_version_isolation.py",
            "Graceful Degradation": "integration/test_graceful_degradation.py",
            "Functionality Preservation": "integration/test_functionality_preservation.py"
        }
        
        # Filter test suites if specified
        if test_suites:
            test_suites_to_run = {k: v for k, v in all_test_suites.items() if k in test_suites}
        else:
            test_suites_to_run = all_test_suites
        
        # Run tests
        overall_start_time = time.time()
        results = {}
        
        for test_name, test_file in test_suites_to_run.items():
            result = self.run_test_suite(test_file, test_name)
            results[test_name] = result
            self.test_results[test_name] = result
        
        overall_end_time = time.time()
        overall_duration = overall_end_time - overall_start_time
        
        # Generate summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"\n📊 Test Summary")
        print(f"Total test suites: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Overall duration: {overall_duration:.1f}s")
        
        # Detailed results
        for test_name, result in results.items():
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            duration = result["duration"]
            print(f"  {status} {test_name} ({duration:.1f}s)")
            
            if result["details"]:
                details = result["details"]
                print(f"    Tests: {details.get('passed', 0)}/{details.get('total', 0)} passed")
        
        overall_success = failed_tests == 0
        
        if overall_success:
            print("\n🎉 All integration tests passed!")
        else:
            print(f"\n💥 {failed_tests} test suite(s) failed")
        
        return {
            "success": overall_success,
            "total_suites": total_tests,
            "passed_suites": passed_tests,
            "failed_suites": failed_tests,
            "duration": overall_duration,
            "results": results,
            "availability": availability
        }
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a detailed test report."""
        if not self.test_results:
            return "No test results available"
        
        report_lines = [
            "# COA Backend Integration Test Report",
            f"Generated: {datetime.now().isoformat()}",
            f"BedrockAgent URL: {self.bedrockagent_url}",
            f"AgentCore URL: {self.agentcore_url}",
            "",
            "## Summary",
        ]
        
        total_suites = len(self.test_results)
        passed_suites = sum(1 for r in self.test_results.values() if r["success"])
        failed_suites = total_suites - passed_suites
        
        report_lines.extend([
            f"- Total test suites: {total_suites}",
            f"- Passed: {passed_suites}",
            f"- Failed: {failed_suites}",
            f"- Success rate: {(passed_suites/total_suites)*100:.1f}%",
            ""
        ])
        
        # Detailed results
        report_lines.append("## Detailed Results")
        
        for test_name, result in self.test_results.items():
            status = "PASS" if result["success"] else "FAIL"
            duration = result["duration"]
            
            report_lines.extend([
                f"### {test_name}",
                f"- Status: {status}",
                f"- Duration: {duration:.1f}s",
            ])
            
            if result["details"]:
                details = result["details"]
                report_lines.extend([
                    f"- Total tests: {details.get('total', 0)}",
                    f"- Passed: {details.get('passed', 0)}",
                    f"- Failed: {details.get('failed', 0)}",
                    f"- Skipped: {details.get('skipped', 0)}",
                ])
            
            if not result["success"] and result["stderr"]:
                report_lines.extend([
                    "- Error output:",
                    "```",
                    result["stderr"][:1000] + ("..." if len(result["stderr"]) > 1000 else ""),
                    "```"
                ])
            
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            print(f"📄 Report saved to: {output_file}")
        
        return report_content


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run COA Backend integration tests")
    
    parser.add_argument(
        "--bedrockagent-url",
        default=DEFAULT_BEDROCKAGENT_URL,
        help=f"BedrockAgent service URL (default: {DEFAULT_BEDROCKAGENT_URL})"
    )
    
    parser.add_argument(
        "--agentcore-url",
        default=DEFAULT_AGENTCORE_URL,
        help=f"AgentCore service URL (default: {DEFAULT_AGENTCORE_URL})"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Test timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )
    
    parser.add_argument(
        "--test-suites",
        nargs="+",
        choices=["Version Isolation", "Graceful Degradation", "Functionality Preservation"],
        help="Specific test suites to run (default: all)"
    )
    
    parser.add_argument(
        "--report",
        help="Generate report and save to file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Create test runner
    runner = IntegrationTestRunner(
        bedrockagent_url=args.bedrockagent_url,
        agentcore_url=args.agentcore_url,
        timeout=args.timeout,
        verbose=args.verbose
    )
    
    # Run tests
    results = runner.run_all_tests(args.test_suites)
    
    # Generate report if requested
    if args.report:
        runner.generate_report(args.report)
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()