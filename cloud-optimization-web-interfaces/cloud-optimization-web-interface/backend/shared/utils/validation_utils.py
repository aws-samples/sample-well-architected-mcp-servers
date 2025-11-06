"""
Common validation utilities for both BedrockAgent and AgentCore versions.
"""

import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime


def validate_aws_region(region: str) -> bool:
    """
    Validate AWS region format.
    
    Args:
        region: AWS region string
        
    Returns:
        True if valid region format, False otherwise
    """
    # AWS region pattern: us-east-1, eu-west-2, ap-southeast-1, etc.
    pattern = r'^[a-z]{2}-[a-z]+-\d+$'
    return bool(re.match(pattern, region))


def validate_aws_account_id(account_id: str) -> bool:
    """
    Validate AWS account ID format.
    
    Args:
        account_id: AWS account ID string
        
    Returns:
        True if valid account ID format, False otherwise
    """
    # AWS account ID is 12 digits
    pattern = r'^\d{12}$'
    return bool(re.match(pattern, account_id))


def validate_agent_id(agent_id: str) -> bool:
    """
    Validate Bedrock agent ID format.
    
    Args:
        agent_id: Agent ID string
        
    Returns:
        True if valid agent ID format, False otherwise
    """
    # Bedrock agent ID pattern: 10 alphanumeric characters
    pattern = r'^[A-Z0-9]{10}$'
    return bool(re.match(pattern, agent_id))


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.
    
    Args:
        session_id: Session ID string
        
    Returns:
        True if valid session ID format, False otherwise
    """
    # Session ID should be alphanumeric with hyphens (UUID-like)
    pattern = r'^[a-zA-Z0-9\-_]{8,64}$'
    return bool(re.match(pattern, session_id))


def validate_parameter_name(param_name: str) -> bool:
    """
    Validate SSM parameter name format.
    
    Args:
        param_name: Parameter name string
        
    Returns:
        True if valid parameter name format, False otherwise
    """
    # SSM parameter names can contain letters, numbers, periods, hyphens, underscores, and forward slashes
    pattern = r'^[a-zA-Z0-9\.\-_/]+$'
    return bool(re.match(pattern, param_name)) and len(param_name) <= 2048


def validate_json_string(json_str: str) -> bool:
    """
    Validate if string is valid JSON.
    
    Args:
        json_str: JSON string to validate
        
    Returns:
        True if valid JSON, False otherwise
    """
    try:
        import json
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid URL format, False otherwise
    """
    pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(pattern, url))


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> List[str]:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Returns:
        List of missing field names
    """
    missing_fields = []
    
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing_fields.append(field)
    
    return missing_fields


def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type]) -> List[str]:
    """
    Validate field types in data dictionary.
    
    Args:
        data: Dictionary to validate
        field_types: Dictionary mapping field names to expected types
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    for field, expected_type in field_types.items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], expected_type):
                errors.append(f"Field '{field}' must be of type {expected_type.__name__}")
    
    return errors


def validate_string_length(
    value: str, 
    min_length: Optional[int] = None, 
    max_length: Optional[int] = None
) -> bool:
    """
    Validate string length constraints.
    
    Args:
        value: String to validate
        min_length: Minimum length (optional)
        max_length: Maximum length (optional)
        
    Returns:
        True if length is valid, False otherwise
    """
    if not isinstance(value, str):
        return False
    
    length = len(value)
    
    if min_length is not None and length < min_length:
        return False
    
    if max_length is not None and length > max_length:
        return False
    
    return True


def validate_numeric_range(
    value: Union[int, float], 
    min_value: Optional[Union[int, float]] = None, 
    max_value: Optional[Union[int, float]] = None
) -> bool:
    """
    Validate numeric value is within range.
    
    Args:
        value: Numeric value to validate
        min_value: Minimum value (optional)
        max_value: Maximum value (optional)
        
    Returns:
        True if value is within range, False otherwise
    """
    if not isinstance(value, (int, float)):
        return False
    
    if min_value is not None and value < min_value:
        return False
    
    if max_value is not None and value > max_value:
        return False
    
    return True


def validate_list_items(
    items: List[Any], 
    item_validator: callable, 
    min_items: Optional[int] = None,
    max_items: Optional[int] = None
) -> List[str]:
    """
    Validate list items using a validator function.
    
    Args:
        items: List of items to validate
        item_validator: Function to validate each item
        min_items: Minimum number of items (optional)
        max_items: Maximum number of items (optional)
        
    Returns:
        List of validation error messages
    """
    errors = []
    
    if not isinstance(items, list):
        errors.append("Value must be a list")
        return errors
    
    # Check list length
    if min_items is not None and len(items) < min_items:
        errors.append(f"List must contain at least {min_items} items")
    
    if max_items is not None and len(items) > max_items:
        errors.append(f"List must contain at most {max_items} items")
    
    # Validate each item
    for i, item in enumerate(items):
        try:
            if not item_validator(item):
                errors.append(f"Item at index {i} is invalid")
        except Exception as e:
            errors.append(f"Item at index {i} validation failed: {str(e)}")
    
    return errors


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string by removing potentially harmful characters.
    
    Args:
        value: String to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return ""
    
    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()


def validate_datetime_string(dt_str: str) -> bool:
    """
    Validate datetime string in ISO format.
    
    Args:
        dt_str: Datetime string to validate
        
    Returns:
        True if valid datetime string, False otherwise
    """
    try:
        datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return True
    except (ValueError, TypeError):
        return False


class ValidationResult:
    """Container for validation results."""
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
    
    def add_error(self, message: str):
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add validation warning."""
        self.warnings.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings
        }


def create_validator(validation_rules: Dict[str, Any]) -> callable:
    """
    Create a validator function from validation rules.
    
    Args:
        validation_rules: Dictionary of validation rules
        
    Returns:
        Validator function
    """
    def validator(data: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        # Check required fields
        if 'required' in validation_rules:
            missing = validate_required_fields(data, validation_rules['required'])
            for field in missing:
                result.add_error(f"Required field '{field}' is missing")
        
        # Check field types
        if 'types' in validation_rules:
            type_errors = validate_field_types(data, validation_rules['types'])
            for error in type_errors:
                result.add_error(error)
        
        # Check custom validators
        if 'custom' in validation_rules:
            for field, custom_validator in validation_rules['custom'].items():
                if field in data:
                    try:
                        if not custom_validator(data[field]):
                            result.add_error(f"Field '{field}' failed custom validation")
                    except Exception as e:
                        result.add_error(f"Field '{field}' validation error: {str(e)}")
        
        return result
    
    return validator