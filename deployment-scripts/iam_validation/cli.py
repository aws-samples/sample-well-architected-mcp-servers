"""
Command-line interface for IAM validation and CloudFormation template updates.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .orchestrator import BedrockAgentCoreIntegrator
from .security_validator import SecurityValidator
from .config import CONFIG


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """Set up logging configuration.
    
    Args:
        verbose: Enable verbose logging.
        log_file: Optional log file path.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)
    
    # Reduce noise from boto3/botocore
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser.
    
    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description='IAM validation and CloudFormation template update tool for Bedrock AgentCore integration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete validation and template update
  python -m iam_validation.cli
  
  # Run with custom AWS profile and region
  python -m iam_validation.cli --aws-profile my-profile --aws-region us-west-2
  
  # Run in dry-run mode (validate but don't create output)
  python -m iam_validation.cli --dry-run
  
  # Skip IAM validation (only update template)
  python -m iam_validation.cli --skip-validation
  
  # Run with custom file paths
  python -m iam_validation.cli \\
    --input-template /path/to/input.yaml \\
    --output-template /path/to/output.yaml \\
    --policy-directory /path/to/policies
  
  # Run with verbose logging
  python -m iam_validation.cli --verbose --log-file validation.log
  
  # Run security validation only
  python -m iam_validation.cli --security-only --input-template template.yaml
        """
    )
    
    # AWS Configuration
    aws_group = parser.add_argument_group('AWS Configuration')
    aws_group.add_argument(
        '--aws-profile',
        help='AWS profile to use for authentication (default: use default profile)'
    )
    aws_group.add_argument(
        '--aws-region',
        default=CONFIG['aws_region'],
        help=f'AWS region for operations (default: {CONFIG["aws_region"]})'
    )
    
    # File Paths
    paths_group = parser.add_argument_group('File Paths')
    paths_group.add_argument(
        '--input-template',
        default=CONFIG['template_input'],
        help=f'Path to input CloudFormation template (default: {CONFIG["template_input"]})'
    )
    paths_group.add_argument(
        '--output-template',
        default=CONFIG['template_output'],
        help=f'Path for output CloudFormation template (default: {CONFIG["template_output"]})'
    )
    paths_group.add_argument(
        '--policy-directory',
        default=CONFIG['policy_directory'],
        help=f'Directory containing policy JSON files (default: {CONFIG["policy_directory"]})'
    )
    
    # Execution Options
    execution_group = parser.add_argument_group('Execution Options')
    execution_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate changes but do not create output files'
    )
    execution_group.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip IAM policy validation phase'
    )
    execution_group.add_argument(
        '--skip-template-update',
        action='store_true',
        help='Skip CloudFormation template update phase'
    )
    execution_group.add_argument(
        '--security-only',
        action='store_true',
        help='Run security validation only (requires --input-template)'
    )
    
    # Logging Options
    logging_group = parser.add_argument_group('Logging Options')
    logging_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    logging_group.add_argument(
        '--log-file',
        help='Write logs to specified file'
    )
    logging_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    # Validation Options
    validation_group = parser.add_argument_group('Validation Options')
    validation_group.add_argument(
        '--validate-prerequisites',
        action='store_true',
        help='Only validate prerequisites and exit'
    )
    validation_group.add_argument(
        '--show-config',
        action='store_true',
        help='Show configuration and exit'
    )
    
    return parser


def validate_arguments(args: argparse.Namespace) -> bool:
    """Validate command-line arguments.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        True if arguments are valid, False otherwise.
    """
    errors = []
    
    # Check file paths exist
    if not args.skip_validation and not args.security_only:
        policy_dir = Path(args.policy_directory)
        if not policy_dir.exists():
            errors.append(f"Policy directory not found: {args.policy_directory}")
    
    if not args.skip_template_update or args.security_only:
        input_template = Path(args.input_template)
        if not input_template.exists():
            errors.append(f"Input template not found: {args.input_template}")
    
    # Check conflicting options
    if args.skip_validation and args.skip_template_update:
        errors.append("Cannot skip both validation and template update")
    
    if args.security_only and (args.skip_validation or args.skip_template_update):
        errors.append("--security-only cannot be used with --skip-validation or --skip-template-update")
    
    if args.quiet and args.verbose:
        errors.append("Cannot use both --quiet and --verbose")
    
    # Print errors if any
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return False
    
    return True


def run_security_validation(args: argparse.Namespace) -> int:
    """Run security validation only.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        from .template_manager import CloudFormationTemplateManager
        
        print("Running security validation...")
        
        # Load template
        template_manager = CloudFormationTemplateManager(args.input_template)
        template = template_manager.load_template()
        
        # Run security validation
        validator = SecurityValidator()
        
        # Validate Bedrock AgentCore role if it exists
        bedrock_role_name = CONFIG['bedrock_role_resource_name']
        validation_results = []
        
        if bedrock_role_name in template.get('Resources', {}):
            print(f"Validating Bedrock AgentCore role: {bedrock_role_name}")
            bedrock_result = validator.validate_bedrock_agentcore_role(template, bedrock_role_name)
            validation_results.append(bedrock_result)
        else:
            print(f"Bedrock AgentCore role '{bedrock_role_name}' not found in template")
        
        # Find and validate ECS role
        from .ecs_enhancer import ECSPermissionEnhancer
        enhancer = ECSPermissionEnhancer()
        ecs_role_name = enhancer.find_ecs_task_role(template)
        
        if ecs_role_name:
            print(f"Validating ECS task role: {ecs_role_name}")
            ecs_result = validator.validate_ecs_permissions(template, ecs_role_name)
            validation_results.append(ecs_result)
        else:
            print("No ECS task role found in template")
        
        # Generate and display report
        if validation_results:
            report = validator.generate_security_report(validation_results)
            print("\n" + report)
            
            # Determine exit code based on results
            overall_passed = all(result.passed for result in validation_results)
            return 0 if overall_passed else 1
        else:
            print("No security validations performed")
            return 0
            
    except Exception as e:
        print(f"Security validation failed: {str(e)}", file=sys.stderr)
        return 1


def run_main_workflow(args: argparse.Namespace) -> int:
    """Run the main IAM validation and template update workflow.
    
    Args:
        args: Parsed command-line arguments.
        
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    try:
        # Create integrator
        if not args.quiet:
            print("🔧 Initializing Bedrock AgentCore integrator...")
        
        integrator = BedrockAgentCoreIntegrator(
            aws_profile=args.aws_profile,
            aws_region=args.aws_region,
            input_template_path=args.input_template,
            output_template_path=args.output_template,
            policy_directory=args.policy_directory
        )
        
        # Validate prerequisites if requested
        if args.validate_prerequisites:
            if not args.quiet:
                print("🔍 Validating prerequisites...")
            
            issues = integrator.validate_prerequisites()
            
            if issues:
                print("❌ Prerequisites validation failed:")
                for issue in issues:
                    print(f"  - {issue}")
                return 1
            else:
                print("✅ All prerequisites validated successfully")
                return 0
        
        # Show progress for main workflow
        if not args.quiet:
            print("🚀 Starting Bedrock AgentCore integration process...")
            
            if args.dry_run:
                print("🔍 Running in DRY RUN mode - no files will be modified")
            
            if args.skip_validation:
                print("⏭️  Skipping IAM validation phase")
            
            if args.skip_template_update:
                print("⏭️  Skipping template update phase")
        
        # Run main workflow
        result = integrator.run_validation_and_update(
            skip_validation=args.skip_validation,
            skip_template_update=args.skip_template_update,
            dry_run=args.dry_run
        )
        
        # Display results
        if not args.quiet:
            summary = integrator.get_process_summary(result)
            print("\n" + summary)
            
            # Add final status message
            if result.overall_success:
                print("🎉 Integration process completed successfully!")
            else:
                print("💥 Integration process failed!")
        
        # Return appropriate exit code
        return 0 if result.overall_success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user", file=sys.stderr)
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        print(f"💥 Unexpected error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def show_configuration(args: argparse.Namespace) -> None:
    """Display current configuration.
    
    Args:
        args: Parsed command-line arguments.
    """
    print("Current Configuration:")
    print("=" * 50)
    print(f"AWS Profile: {args.aws_profile or 'default'}")
    print(f"AWS Region: {args.aws_region}")
    print(f"Input Template: {args.input_template}")
    print(f"Output Template: {args.output_template}")
    print(f"Policy Directory: {args.policy_directory}")
    print(f"Dry Run: {args.dry_run}")
    print(f"Skip Validation: {args.skip_validation}")
    print(f"Skip Template Update: {args.skip_template_update}")
    print(f"Security Only: {args.security_only}")
    print(f"Verbose: {args.verbose}")
    print(f"Log File: {args.log_file or 'None'}")
    print("=" * 50)
    
    # Show policy files
    policy_dir = Path(args.policy_directory)
    if policy_dir.exists():
        print(f"\nPolicy Files in {args.policy_directory}:")
        for policy_file in CONFIG['policy_files']:
            policy_path = policy_dir / policy_file
            status = "✓" if policy_path.exists() else "✗"
            print(f"  {status} {policy_file}")
    else:
        print(f"\nPolicy directory does not exist: {args.policy_directory}")
    
    # Show template file status
    input_template = Path(args.input_template)
    template_status = "✓" if input_template.exists() else "✗"
    print(f"\nInput Template: {template_status} {args.input_template}")


def main() -> int:
    """Main entry point for the CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Set up logging
    if not args.quiet:
        setup_logging(verbose=args.verbose, log_file=args.log_file)
    
    # Show configuration if requested
    if args.show_config:
        show_configuration(args)
        return 0
    
    # Validate arguments
    if not validate_arguments(args):
        return 1
    
    # Run appropriate workflow
    if args.security_only:
        return run_security_validation(args)
    else:
        return run_main_workflow(args)


if __name__ == '__main__':
    sys.exit(main())