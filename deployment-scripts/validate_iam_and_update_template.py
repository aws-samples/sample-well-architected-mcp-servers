#!/usr/bin/env python3
"""
Main execution script for IAM validation and CloudFormation template updates.

This script provides a user-friendly interface for validating IAM policies and updating
CloudFormation templates to support Bedrock AgentCore integration.

Usage:
    python validate_iam_and_update_template.py [options]
    
Examples:
    # Run complete validation and template update
    python validate_iam_and_update_template.py
    
    # Run with custom AWS profile and region
    python validate_iam_and_update_template.py --aws-profile my-profile --aws-region us-west-2
    
    # Run in dry-run mode
    python validate_iam_and_update_template.py --dry-run
    
    # Run with verbose logging
    python validate_iam_and_update_template.py --verbose
"""

import sys
import time
import signal
from pathlib import Path
from typing import Optional

# Add the deployment-scripts directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from iam_validation.cli import main as cli_main, create_parser, setup_logging
from iam_validation.orchestrator import BedrockAgentCoreIntegrator
from iam_validation.config import CONFIG


class ProgressReporter:
    """Provides progress reporting and user-friendly output formatting."""
    
    def __init__(self, verbose: bool = False):
        """Initialize progress reporter.
        
        Args:
            verbose: Enable verbose progress reporting.
        """
        self.verbose = verbose
        self.start_time = None
        self.current_phase = None
        self.phase_start_time = None
        
    def start_process(self, title: str) -> None:
        """Start the overall process.
        
        Args:
            title: Process title to display.
        """
        self.start_time = time.time()
        
        print("=" * 80)
        print(f"🚀 {title}")
        print("=" * 80)
        print()
        
    def start_phase(self, phase_name: str, description: str = "") -> None:
        """Start a new phase of the process.
        
        Args:
            phase_name: Name of the phase.
            description: Optional description of the phase.
        """
        self.current_phase = phase_name
        self.phase_start_time = time.time()
        
        print(f"📋 Phase: {phase_name}")
        if description:
            print(f"   {description}")
        print()
        
    def report_step(self, step_name: str, status: str = "in_progress", details: str = "") -> None:
        """Report progress on a specific step.
        
        Args:
            step_name: Name of the step.
            status: Status of the step ('in_progress', 'success', 'warning', 'error').
            details: Optional details about the step.
        """
        icons = {
            'in_progress': '⏳',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }
        
        icon = icons.get(status, '📝')
        print(f"  {icon} {step_name}")
        
        if details and (self.verbose or status in ['warning', 'error']):
            # Indent details
            for line in details.split('\n'):
                if line.strip():
                    print(f"     {line}")
        
        if status == 'in_progress' and not self.verbose:
            # Add a small delay for visual effect
            time.sleep(0.1)
    
    def complete_phase(self, success: bool = True, summary: str = "") -> None:
        """Complete the current phase.
        
        Args:
            success: Whether the phase completed successfully.
            summary: Optional summary of the phase results.
        """
        if self.phase_start_time:
            duration = time.time() - self.phase_start_time
            status_icon = "✅" if success else "❌"
            status_text = "COMPLETED" if success else "FAILED"
            
            print(f"  {status_icon} Phase {status_text} ({duration:.1f}s)")
            
            if summary:
                print(f"     {summary}")
            
            print()
    
    def complete_process(self, success: bool = True, summary: str = "") -> None:
        """Complete the overall process.
        
        Args:
            success: Whether the process completed successfully.
            summary: Optional summary of the process results.
        """
        if self.start_time:
            total_duration = time.time() - self.start_time
            
            print("=" * 80)
            
            if success:
                print(f"🎉 PROCESS COMPLETED SUCCESSFULLY ({total_duration:.1f}s)")
            else:
                print(f"💥 PROCESS FAILED ({total_duration:.1f}s)")
            
            if summary:
                print()
                print(summary)
            
            print("=" * 80)
    
    def show_configuration(self, integrator: BedrockAgentCoreIntegrator) -> None:
        """Display current configuration.
        
        Args:
            integrator: BedrockAgentCoreIntegrator instance.
        """
        print("📋 Configuration:")
        print(f"   AWS Profile: {integrator.aws_profile or 'default'}")
        print(f"   AWS Region: {integrator.aws_region}")
        print(f"   Input Template: {integrator.input_template_path}")
        print(f"   Output Template: {integrator.output_template_path}")
        print(f"   Policy Directory: {integrator.policy_directory}")
        print()
        
        # Show policy files status
        policy_dir = Path(integrator.policy_directory)
        if policy_dir.exists():
            print("📁 Policy Files:")
            for policy_file in CONFIG['policy_files']:
                policy_path = policy_dir / policy_file
                status = "✅" if policy_path.exists() else "❌"
                print(f"   {status} {policy_file}")
        else:
            print(f"   ❌ Policy directory not found: {integrator.policy_directory}")
        
        print()


def handle_interrupt(signum, frame):
    """Handle keyboard interrupt gracefully."""
    print("\n\n⚠️  Process interrupted by user")
    print("🧹 Performing cleanup...")
    sys.exit(130)  # Standard exit code for SIGINT


def run_with_progress_reporting(args) -> int:
    """Run the IAM validation and template update with progress reporting.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Set up signal handler for graceful interruption
    signal.signal(signal.SIGINT, handle_interrupt)
    
    # Initialize progress reporter
    reporter = ProgressReporter(verbose=args.verbose)
    
    try:
        # Start the process
        process_title = "Bedrock AgentCore IAM Integration"
        if args.dry_run:
            process_title += " (DRY RUN)"
        
        reporter.start_process(process_title)
        
        # Create integrator
        reporter.report_step("Initializing components", "in_progress")
        
        integrator = BedrockAgentCoreIntegrator(
            aws_profile=args.aws_profile,
            aws_region=args.aws_region,
            input_template_path=args.input_template,
            output_template_path=args.output_template,
            policy_directory=args.policy_directory
        )
        
        reporter.report_step("Components initialized", "success")
        
        # Show configuration
        if args.verbose or args.show_config:
            reporter.show_configuration(integrator)
        
        # Validate prerequisites if requested
        if args.validate_prerequisites:
            reporter.start_phase("Prerequisites Validation", "Checking system requirements")
            
            reporter.report_step("Validating prerequisites", "in_progress")
            issues = integrator.validate_prerequisites()
            
            if issues:
                reporter.report_step("Prerequisites validation failed", "error", 
                                   "\n".join(f"- {issue}" for issue in issues))
                reporter.complete_phase(False, f"{len(issues)} issues found")
                reporter.complete_process(False)
                return 1
            else:
                reporter.report_step("All prerequisites validated", "success")
                reporter.complete_phase(True, "All requirements met")
                reporter.complete_process(True)
                return 0
        
        # Phase 1: IAM Policy Validation
        if not args.skip_validation:
            reporter.start_phase("IAM Policy Validation", "Testing policy attachment with temporary role")
            
            reporter.report_step("Loading policy files", "in_progress")
            
            try:
                # Load policies to show what we're validating
                policy_files = list(Path(integrator.policy_directory).glob("*.json"))
                reporter.report_step(f"Found {len(policy_files)} policy files", "success",
                                   "\n".join(f"- {f.name}" for f in policy_files))
                
                reporter.report_step("Creating temporary IAM role", "in_progress")
                reporter.report_step("Attaching policies to role", "in_progress")
                reporter.report_step("Validating policy permissions", "in_progress")
                
                validation_result = integrator.validate_iam_policies()
                
                if validation_result.success:
                    reporter.report_step("IAM validation completed", "success",
                                       f"Validated {len(validation_result.attached_policies)} policies")
                    
                    if validation_result.cleanup_successful:
                        reporter.report_step("Temporary resources cleaned up", "success")
                    else:
                        reporter.report_step("Cleanup completed with warnings", "warning")
                    
                    reporter.complete_phase(True, f"All {len(validation_result.attached_policies)} policies validated")
                else:
                    error_details = "\n".join(validation_result.errors)
                    reporter.report_step("IAM validation failed", "error", error_details)
                    reporter.complete_phase(False, f"{len(validation_result.errors)} validation errors")
                    reporter.complete_process(False)
                    return 1
                    
            except Exception as e:
                reporter.report_step("IAM validation failed", "error", str(e))
                reporter.complete_phase(False, "Unexpected error during validation")
                reporter.complete_process(False)
                return 1
        else:
            print("⏭️  Skipping IAM validation phase")
        
        # Phase 2: CloudFormation Template Update
        if not args.skip_template_update:
            reporter.start_phase("CloudFormation Template Update", "Adding Bedrock AgentCore resources")
            
            reporter.report_step("Loading input template", "in_progress")
            reporter.report_step("Adding Bedrock AgentCore IAM role", "in_progress")
            reporter.report_step("Updating ECS task permissions", "in_progress")
            reporter.report_step("Validating template structure", "in_progress")
            
            try:
                update_result = integrator.update_cloudformation_template(dry_run=args.dry_run)
                
                if update_result.success:
                    if args.dry_run:
                        reporter.report_step("Template validation completed", "success",
                                           "Changes validated but not saved (dry run mode)")
                    else:
                        reporter.report_step("Template updated successfully", "success",
                                           f"Output: {update_result.output_file}")
                    
                    # Report what was added/modified
                    if update_result.new_resources_added:
                        reporter.report_step("New resources added", "success",
                                           "\n".join(f"+ {resource}" for resource in update_result.new_resources_added))
                    
                    if update_result.existing_resources_modified:
                        reporter.report_step("Existing resources modified", "success",
                                           "\n".join(f"~ {resource}" for resource in update_result.existing_resources_modified))
                    
                    summary = f"Added {len(update_result.new_resources_added)} resources, " \
                             f"modified {len(update_result.existing_resources_modified)} resources"
                    reporter.complete_phase(True, summary)
                else:
                    error_details = "\n".join(update_result.errors)
                    reporter.report_step("Template update failed", "error", error_details)
                    reporter.complete_phase(False, f"{len(update_result.errors)} update errors")
                    reporter.complete_process(False)
                    return 1
                    
            except Exception as e:
                reporter.report_step("Template update failed", "error", str(e))
                reporter.complete_phase(False, "Unexpected error during template update")
                reporter.complete_process(False)
                return 1
        else:
            print("⏭️  Skipping template update phase")
        
        # Generate final summary
        result = integrator.run_validation_and_update(
            skip_validation=args.skip_validation,
            skip_template_update=args.skip_template_update,
            dry_run=args.dry_run
        )
        
        if not args.quiet:
            summary = integrator.get_process_summary(result)
            reporter.complete_process(result.overall_success, summary)
        else:
            reporter.complete_process(result.overall_success)
        
        return 0 if result.overall_success else 1
        
    except KeyboardInterrupt:
        reporter.complete_process(False, "Process interrupted by user")
        return 130
    except Exception as e:
        reporter.report_step("Unexpected error", "error", str(e))
        reporter.complete_process(False, f"Unexpected error: {str(e)}")
        return 1


def main() -> int:
    """Main entry point for the standalone execution script.
    
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    # Parse command-line arguments using the existing CLI parser
    parser = create_parser()
    
    # Add some additional help text specific to this script
    parser.description = """
Bedrock AgentCore IAM Integration Tool

This tool validates IAM policies and updates CloudFormation templates to support
Bedrock AgentCore runtime integration. It performs two main phases:

1. IAM Policy Validation: Creates a temporary IAM role and tests policy attachment
2. Template Update: Adds Bedrock AgentCore resources to CloudFormation template

The tool provides detailed progress reporting and user-friendly output formatting.
    """.strip()
    
    args = parser.parse_args()
    
    # Set up logging (but suppress it for clean progress output unless verbose)
    if args.verbose:
        setup_logging(verbose=True, log_file=args.log_file)
    elif args.log_file:
        setup_logging(verbose=False, log_file=args.log_file)
    
    # Handle special cases
    if args.show_config:
        # Use the CLI function for showing configuration
        return cli_main()
    
    if args.security_only:
        # Use the CLI function for security-only validation
        return cli_main()
    
    # Validate arguments
    from iam_validation.cli import validate_arguments
    if not validate_arguments(args):
        return 1
    
    # Run with progress reporting
    return run_with_progress_reporting(args)


if __name__ == '__main__':
    sys.exit(main())