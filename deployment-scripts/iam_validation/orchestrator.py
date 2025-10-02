"""
Main orchestrator for IAM validation and CloudFormation template updates.
"""

import logging
from typing import Optional, List
from pathlib import Path

from .config import CONFIG
from .data_models import ValidationResult, UpdateResult, IntegrationResult, FailureContext
from .error_handling import ErrorHandler, ValidationException, TemplateException
from .validator import IAMRoleValidator
from .template_manager import CloudFormationTemplateManager
from .ecs_enhancer import ECSPermissionEnhancer
from .policy_processor import PolicyDocumentProcessor

logger = logging.getLogger(__name__)


class BedrockAgentCoreIntegrator:
    """Main orchestrator for Bedrock AgentCore IAM integration."""
    
    def __init__(self, 
                 aws_profile: Optional[str] = None,
                 aws_region: Optional[str] = None,
                 input_template_path: Optional[str] = None,
                 output_template_path: Optional[str] = None,
                 policy_directory: Optional[str] = None):
        """Initialize the Bedrock AgentCore integrator.
        
        Args:
            aws_profile: AWS profile for authentication.
            aws_region: AWS region for operations.
            input_template_path: Path to input CloudFormation template.
            output_template_path: Path for output CloudFormation template.
            policy_directory: Directory containing policy JSON files.
        """
        self.aws_profile = aws_profile or CONFIG.get('aws_profile')
        self.aws_region = aws_region or CONFIG['aws_region']
        self.input_template_path = input_template_path or CONFIG['template_input']
        self.output_template_path = output_template_path or CONFIG['template_output']
        self.policy_directory = policy_directory or CONFIG['policy_directory']
        
        # Initialize components
        self.validator = IAMRoleValidator(
            aws_profile=self.aws_profile,
            aws_region=self.aws_region
        )
        
        self.template_manager = CloudFormationTemplateManager(
            input_template_path=self.input_template_path,
            output_template_path=self.output_template_path
        )
        
        self.ecs_enhancer = ECSPermissionEnhancer()
        self.policy_processor = PolicyDocumentProcessor(self.policy_directory)
        
        # Track overall process state
        self.failure_context = FailureContext()
        
    def run_validation_and_update(self, 
                                 skip_validation: bool = False,
                                 skip_template_update: bool = False,
                                 dry_run: bool = False,
                                 progress_callback: Optional[callable] = None) -> IntegrationResult:
        """Run the complete IAM validation and template update process.
        
        Args:
            skip_validation: Skip IAM policy validation phase.
            skip_template_update: Skip CloudFormation template update phase.
            dry_run: Perform validation only, don't create output files.
            progress_callback: Optional callback function for progress reporting.
            
        Returns:
            IntegrationResult with complete process results.
        """
        logger.info("Starting Bedrock AgentCore integration process")
        logger.info(f"AWS Profile: {self.aws_profile or 'default'}")
        logger.info(f"AWS Region: {self.aws_region}")
        logger.info(f"Input Template: {self.input_template_path}")
        logger.info(f"Output Template: {self.output_template_path}")
        logger.info(f"Policy Directory: {self.policy_directory}")
        logger.info(f"Dry Run: {dry_run}")
        
        # Helper function for progress reporting
        def report_progress(step: str, status: str = "in_progress", details: str = ""):
            if progress_callback:
                progress_callback(step, status, details)
        
        validation_result = ValidationResult(
            success=True,
            temporary_role_arn=None,
            attached_policies=[],
            errors=[],
            cleanup_successful=True
        )
        
        update_result = UpdateResult(
            success=True,
            output_file="",
            new_resources_added=[],
            existing_resources_modified=[],
            errors=[]
        )
        
        try:
            # Phase 1: IAM Policy Validation
            if not skip_validation:
                logger.info("=== Phase 1: IAM Policy Validation ===")
                report_progress("Starting IAM policy validation", "in_progress")
                
                validation_result = self.validate_iam_policies()
                
                if not validation_result.success:
                    logger.error("IAM validation failed, stopping process")
                    report_progress("IAM validation failed", "error", 
                                  "\n".join(validation_result.errors))
                    return IntegrationResult.from_results(validation_result, update_result)
                
                logger.info("IAM validation completed successfully")
                report_progress("IAM validation completed", "success", 
                              f"Validated {len(validation_result.attached_policies)} policies")
            else:
                logger.info("Skipping IAM validation phase")
                report_progress("Skipping IAM validation", "success")
            
            # Phase 2: CloudFormation Template Update
            if not skip_template_update:
                logger.info("=== Phase 2: CloudFormation Template Update ===")
                report_progress("Starting template update", "in_progress")
                
                update_result = self.update_cloudformation_template(dry_run=dry_run)
                
                if not update_result.success:
                    logger.error("Template update failed")
                    report_progress("Template update failed", "error", 
                                  "\n".join(update_result.errors))
                    return IntegrationResult.from_results(validation_result, update_result)
                
                logger.info("Template update completed successfully")
                report_progress("Template update completed", "success", 
                              f"Output: {update_result.output_file}")
            else:
                logger.info("Skipping template update phase")
                report_progress("Skipping template update", "success")
            
            # Generate final result
            integration_result = IntegrationResult.from_results(validation_result, update_result)
            
            logger.info("=== Integration Process Complete ===")
            logger.info(integration_result.summary)
            
            return integration_result
            
        except Exception as e:
            logger.error(f"Integration process failed with unexpected error: {str(e)}")
            
            # Update results with error information
            if isinstance(e, ValidationException):
                validation_result.success = False
                validation_result.errors.append(str(e))
            elif isinstance(e, TemplateException):
                update_result.success = False
                update_result.errors.append(str(e))
            else:
                # Generic error - add to both results
                error_msg = f"Unexpected error: {str(e)}"
                validation_result.errors.append(error_msg)
                update_result.errors.append(error_msg)
                validation_result.success = False
                update_result.success = False
            
            return IntegrationResult.from_results(validation_result, update_result)
    
    def validate_iam_policies(self) -> ValidationResult:
        """Validate IAM policies by creating temporary role and testing attachment.
        
        Returns:
            ValidationResult with validation details.
        """
        try:
            logger.info("Starting IAM policy validation")
            
            # Validate AWS permissions first
            logger.info("Validating AWS credentials and permissions")
            self.validator.validate_aws_permissions()
            
            # Perform policy validation
            result = self.validator.validate_policies()
            
            if result.success:
                logger.info(f"IAM validation successful: {len(result.attached_policies)} policies validated")
                logger.info(f"Temporary role: {result.temporary_role_arn}")
                logger.info(f"Cleanup successful: {result.cleanup_successful}")
            else:
                logger.error(f"IAM validation failed: {len(result.errors)} errors")
                for error in result.errors:
                    logger.error(f"  - {error}")
            
            return result
            
        except Exception as e:
            logger.error(f"IAM validation process failed: {str(e)}")
            
            return ValidationResult(
                success=False,
                temporary_role_arn=None,
                attached_policies=[],
                errors=[str(e)],
                cleanup_successful=False
            )
    
    def update_cloudformation_template(self, dry_run: bool = False) -> UpdateResult:
        """Update CloudFormation template with Bedrock AgentCore resources.
        
        Args:
            dry_run: If True, validate template changes but don't write output file.
            
        Returns:
            UpdateResult with update details.
        """
        new_resources_added = []
        existing_resources_modified = []
        errors = []
        
        try:
            logger.info("Loading CloudFormation template")
            
            # Load existing template
            logger.debug(f"About to load template from: {self.template_manager.input_template_path}")
            template = self.template_manager.load_template()
            logger.info(f"Loaded template with {len(template.get('Resources', {}))} resources")
            
            # Validate template structure
            validation_issues = self.template_manager.validate_template_structure(template)
            if validation_issues:
                logger.warning(f"Template validation issues found: {len(validation_issues)}")
                for issue in validation_issues:
                    logger.warning(f"  - {issue}")
                    errors.append(f"Template validation: {issue}")
            
            # Add Bedrock AgentCore IAM role
            logger.info("Adding Bedrock AgentCore IAM role")
            template = self.template_manager.add_bedrock_agentcore_role(template)
            new_resources_added.append(CONFIG['bedrock_role_resource_name'])
            
            # Update ECS permissions
            logger.info("Updating ECS task role permissions")
            template = self.template_manager.update_ecs_permissions(template)
            
            # Find which ECS role was modified
            ecs_role_name = self.ecs_enhancer.find_ecs_task_role(template)
            if ecs_role_name:
                existing_resources_modified.append(ecs_role_name)
                logger.info(f"Enhanced ECS role: {ecs_role_name}")
            
            # Validate final template
            final_validation_issues = self.template_manager.validate_template_structure(template)
            if final_validation_issues:
                logger.error(f"Final template validation failed: {len(final_validation_issues)} issues")
                for issue in final_validation_issues:
                    logger.error(f"  - {issue}")
                    errors.append(f"Final validation: {issue}")
                
                return UpdateResult(
                    success=False,
                    output_file="",
                    new_resources_added=new_resources_added,
                    existing_resources_modified=existing_resources_modified,
                    errors=errors
                )
            
            # Save template (unless dry run)
            output_file = ""
            if not dry_run:
                logger.info(f"Saving updated template to: {self.output_template_path}")
                self.template_manager.save_template(template)
                output_file = str(self.output_template_path)
                logger.info("Template saved successfully")
            else:
                logger.info("Dry run mode: template changes validated but not saved")
                output_file = f"[DRY RUN] {self.output_template_path}"
            
            # Generate summary
            template_summary = self.template_manager.get_template_summary(template)
            logger.info(f"Final template summary:")
            logger.info(f"  - Total resources: {template_summary['total_resources']}")
            logger.info(f"  - IAM roles: {len(template_summary['iam_roles'])}")
            logger.info(f"  - New resources added: {len(new_resources_added)}")
            logger.info(f"  - Existing resources modified: {len(existing_resources_modified)}")
            
            return UpdateResult(
                success=True,
                output_file=output_file,
                new_resources_added=new_resources_added,
                existing_resources_modified=existing_resources_modified,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Template update process failed: {str(e)}")
            errors.append(str(e))
            
            return UpdateResult(
                success=False,
                output_file="",
                new_resources_added=new_resources_added,
                existing_resources_modified=existing_resources_modified,
                errors=errors
            )
    
    def validate_prerequisites(self) -> List[str]:
        """Validate that all prerequisites are met for the integration process.
        
        Returns:
            List of prerequisite issues (empty if all prerequisites are met).
        """
        issues = []
        
        # Check input template exists
        if not Path(self.input_template_path).exists():
            issues.append(f"Input template not found: {self.input_template_path}")
        
        # Check policy directory exists
        if not Path(self.policy_directory).exists():
            issues.append(f"Policy directory not found: {self.policy_directory}")
        
        # Check required policy files exist
        policy_dir = Path(self.policy_directory)
        for policy_file in CONFIG['policy_files']:
            policy_path = policy_dir / policy_file
            if not policy_path.exists():
                issues.append(f"Required policy file not found: {policy_file}")
        
        # Check output directory is writable
        output_dir = Path(self.output_template_path).parent
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create output directory: {output_dir} ({str(e)})")
        
        # Validate AWS credentials (basic check)
        try:
            import boto3
            session = boto3.Session(profile_name=self.aws_profile) if self.aws_profile else boto3.Session()
            credentials = session.get_credentials()
            if not credentials:
                issues.append("No AWS credentials found")
        except Exception as e:
            issues.append(f"AWS credential validation failed: {str(e)}")
        
        return issues
    
    def get_process_summary(self, result: IntegrationResult) -> str:
        """Generate a comprehensive summary of the integration process.
        
        Args:
            result: IntegrationResult to summarize.
            
        Returns:
            Formatted summary string.
        """
        summary_lines = []
        
        # Header
        summary_lines.append("=" * 60)
        summary_lines.append("BEDROCK AGENTCORE INTEGRATION SUMMARY")
        summary_lines.append("=" * 60)
        
        # Overall status
        status_icon = "✓" if result.overall_success else "✗"
        summary_lines.append(f"{status_icon} Overall Status: {'SUCCESS' if result.overall_success else 'FAILED'}")
        summary_lines.append("")
        
        # Validation results
        summary_lines.append("IAM Policy Validation:")
        if result.validation_result.success:
            summary_lines.append(f"  ✓ Status: PASSED")
            summary_lines.append(f"  ✓ Policies validated: {len(result.validation_result.attached_policies)}")
            if result.validation_result.temporary_role_arn:
                summary_lines.append(f"  ✓ Temporary role: {result.validation_result.temporary_role_arn}")
            summary_lines.append(f"  ✓ Cleanup: {'Successful' if result.validation_result.cleanup_successful else 'Failed'}")
        else:
            summary_lines.append(f"  ✗ Status: FAILED")
            summary_lines.append(f"  ✗ Errors: {len(result.validation_result.errors)}")
            for error in result.validation_result.errors:
                summary_lines.append(f"    - {error}")
        
        summary_lines.append("")
        
        # Template update results
        summary_lines.append("CloudFormation Template Update:")
        if result.update_result.success:
            summary_lines.append(f"  ✓ Status: PASSED")
            summary_lines.append(f"  ✓ Output file: {result.update_result.output_file}")
            summary_lines.append(f"  ✓ New resources: {len(result.update_result.new_resources_added)}")
            for resource in result.update_result.new_resources_added:
                summary_lines.append(f"    + {resource}")
            summary_lines.append(f"  ✓ Modified resources: {len(result.update_result.existing_resources_modified)}")
            for resource in result.update_result.existing_resources_modified:
                summary_lines.append(f"    ~ {resource}")
        else:
            summary_lines.append(f"  ✗ Status: FAILED")
            summary_lines.append(f"  ✗ Errors: {len(result.update_result.errors)}")
            for error in result.update_result.errors:
                summary_lines.append(f"    - {error}")
        
        summary_lines.append("")
        
        # Configuration used
        summary_lines.append("Configuration:")
        summary_lines.append(f"  - AWS Profile: {self.aws_profile or 'default'}")
        summary_lines.append(f"  - AWS Region: {self.aws_region}")
        summary_lines.append(f"  - Input Template: {self.input_template_path}")
        summary_lines.append(f"  - Output Template: {self.output_template_path}")
        summary_lines.append(f"  - Policy Directory: {self.policy_directory}")
        
        summary_lines.append("")
        summary_lines.append("=" * 60)
        
        return "\n".join(summary_lines)
    
    def cleanup_on_failure(self) -> bool:
        """Perform cleanup operations when the integration process fails.
        
        Returns:
            True if cleanup was successful.
        """
        logger.info("Performing cleanup after integration failure")
        
        cleanup_successful = True
        
        # Clean up any temporary IAM resources
        if hasattr(self.validator, 'failure_context') and self.validator.failure_context.temporary_role_name:
            try:
                role_cleanup = self.validator.cleanup_temporary_role(
                    self.validator.failure_context.temporary_role_name
                )
                if not role_cleanup:
                    cleanup_successful = False
                    logger.warning("Failed to clean up temporary IAM role")
            except Exception as e:
                logger.error(f"Error during IAM cleanup: {str(e)}")
                cleanup_successful = False
        
        # Remove partial output files if they exist
        try:
            output_path = Path(self.output_template_path)
            if output_path.exists():
                # Check if file was created recently (within last hour) as safety measure
                import time
                file_age = time.time() - output_path.stat().st_mtime
                if file_age < 3600:  # 1 hour
                    output_path.unlink()
                    logger.info(f"Removed partial output file: {output_path}")
        except Exception as e:
            logger.warning(f"Could not remove partial output file: {str(e)}")
            cleanup_successful = False
        
        return cleanup_successful