"""
Data models for IAM validation and CloudFormation template updates.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of IAM policy validation process."""
    success: bool
    temporary_role_arn: Optional[str]
    attached_policies: List[str]
    errors: List[str]
    cleanup_successful: bool
    
    def __post_init__(self):
        """Ensure lists are initialized."""
        if self.attached_policies is None:
            self.attached_policies = []
        if self.errors is None:
            self.errors = []


@dataclass
class UpdateResult:
    """Result of CloudFormation template update process."""
    success: bool
    output_file: str
    new_resources_added: List[str]
    existing_resources_modified: List[str]
    errors: List[str]
    
    def __post_init__(self):
        """Ensure lists are initialized."""
        if self.new_resources_added is None:
            self.new_resources_added = []
        if self.existing_resources_modified is None:
            self.existing_resources_modified = []
        if self.errors is None:
            self.errors = []


@dataclass
class IntegrationResult:
    """Overall result of the integration process."""
    validation_result: ValidationResult
    update_result: UpdateResult
    overall_success: bool
    summary: str
    
    @classmethod
    def from_results(cls, validation_result: ValidationResult, 
                    update_result: UpdateResult) -> 'IntegrationResult':
        """Create IntegrationResult from validation and update results."""
        overall_success = validation_result.success and update_result.success
        
        summary_parts = []
        if validation_result.success:
            summary_parts.append(f"✓ IAM validation successful ({len(validation_result.attached_policies)} policies)")
        else:
            summary_parts.append(f"✗ IAM validation failed ({len(validation_result.errors)} errors)")
            
        if update_result.success:
            summary_parts.append(f"✓ Template update successful ({len(update_result.new_resources_added)} new resources)")
        else:
            summary_parts.append(f"✗ Template update failed ({len(update_result.errors)} errors)")
            
        summary = " | ".join(summary_parts)
        
        return cls(
            validation_result=validation_result,
            update_result=update_result,
            overall_success=overall_success,
            summary=summary
        )


@dataclass
class ErrorResponse:
    """Standardized error response."""
    error_type: str
    error_code: Optional[str]
    message: str
    details: Optional[str] = None
    
    def __str__(self) -> str:
        """String representation of error."""
        parts = [f"{self.error_type}: {self.message}"]
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        if self.details:
            parts.append(f"Details: {self.details}")
        return " | ".join(parts)


@dataclass
class FailureContext:
    """Context information for cleanup on failure."""
    temporary_role_name: Optional[str] = None
    attached_policies: List[str] = None
    created_resources: List[str] = None
    
    def __post_init__(self):
        """Ensure lists are initialized."""
        if self.attached_policies is None:
            self.attached_policies = []
        if self.created_resources is None:
            self.created_resources = []