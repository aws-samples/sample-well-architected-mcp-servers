"""
Logging configuration utilities for both BedrockAgent and AgentCore versions.
"""

import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging with JSON-like output."""
    
    def __init__(self, include_extra: bool = True):
        """
        Initialize structured formatter.
        
        Args:
            include_extra: Whether to include extra fields in log records
        """
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured text."""
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if enabled
        if self.include_extra:
            extra_fields = {
                key: value for key, value in record.__dict__.items()
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'getMessage', 'exc_info',
                    'exc_text', 'stack_info'
                }
            }
            if extra_fields:
                log_data["extra"] = extra_fields
        
        # Format as key=value pairs for readability
        formatted_parts = []
        for key, value in log_data.items():
            if isinstance(value, str):
                formatted_parts.append(f'{key}="{value}"')
            else:
                formatted_parts.append(f'{key}={value}')
        
        return " ".join(formatted_parts)


def setup_logging(
    level: str = "INFO",
    format_type: str = "structured",
    include_extra: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ("structured", "simple", "detailed")
        include_extra: Whether to include extra fields in structured logs
        log_file: Optional log file path
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter based on type
    if format_type == "structured":
        formatter = StructuredFormatter(include_extra=include_extra)
    elif format_type == "simple":
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    elif format_type == "detailed":
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'
        )
    else:
        raise ValueError(f"Unknown format_type: {format_type}")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels for noisy libraries
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def get_logger_with_context(name: str, context: Dict[str, Any] = None) -> logging.Logger:
    """
    Get logger with additional context that will be included in all log messages.
    
    Args:
        name: Logger name
        context: Additional context to include in logs
        
    Returns:
        Logger with context adapter
    """
    logger = logging.getLogger(name)
    
    if context:
        return logging.LoggerAdapter(logger, context)
    else:
        return logger


def log_function_call(func_name: str, args: Dict[str, Any] = None, **kwargs):
    """
    Log function call with arguments.
    
    Args:
        func_name: Name of the function being called
        args: Function arguments
        **kwargs: Additional context
    """
    logger = logging.getLogger(__name__)
    
    log_data = {
        "function": func_name,
        "event": "function_call"
    }
    
    if args:
        log_data["arguments"] = args
    
    log_data.update(kwargs)
    
    logger.info("Function called", extra=log_data)


def log_performance_metric(
    operation: str,
    duration_ms: float,
    success: bool = True,
    **kwargs
):
    """
    Log performance metric.
    
    Args:
        operation: Name of the operation
        duration_ms: Duration in milliseconds
        success: Whether the operation was successful
        **kwargs: Additional context
    """
    logger = logging.getLogger(__name__)
    
    log_data = {
        "operation": operation,
        "duration_ms": duration_ms,
        "success": success,
        "event": "performance_metric"
    }
    
    log_data.update(kwargs)
    
    logger.info("Performance metric", extra=log_data)


def log_error_with_context(
    error: Exception,
    context: Dict[str, Any] = None,
    logger_name: str = None
):
    """
    Log error with additional context.
    
    Args:
        error: Exception that occurred
        context: Additional context about the error
        logger_name: Name of logger to use (defaults to calling module)
    """
    if logger_name:
        logger = logging.getLogger(logger_name)
    else:
        logger = logging.getLogger(__name__)
    
    log_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "event": "error"
    }
    
    if context:
        log_data.update(context)
    
    logger.error("Error occurred", extra=log_data, exc_info=True)


class LoggingContext:
    """Context manager for adding context to all log messages within a block."""
    
    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        """
        Initialize logging context.
        
        Args:
            logger: Logger to add context to
            context: Context to add to all log messages
        """
        self.logger = logger
        self.context = context
        self.original_logger = None
    
    def __enter__(self):
        """Enter context and wrap logger with adapter."""
        if isinstance(self.logger, logging.LoggerAdapter):
            # Already an adapter, merge contexts
            merged_context = {**self.logger.extra, **self.context}
            self.original_logger = self.logger.logger
            return logging.LoggerAdapter(self.original_logger, merged_context)
        else:
            self.original_logger = self.logger
            return logging.LoggerAdapter(self.logger, self.context)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass  # Nothing to clean up


def configure_version_specific_logging(version: str):
    """
    Configure logging specific to backend version.
    
    Args:
        version: Backend version ("bedrockagent" or "agentcore")
    """
    # Add version to all log messages
    root_logger = logging.getLogger()
    
    # Create a filter that adds version to all log records
    class VersionFilter(logging.Filter):
        def filter(self, record):
            record.backend_version = version
            return True
    
    version_filter = VersionFilter()
    
    # Add filter to all handlers
    for handler in root_logger.handlers:
        handler.addFilter(version_filter)
    
    logging.info(f"Logging configured for backend version: {version}")


def get_logging_config() -> Dict[str, Any]:
    """
    Get current logging configuration.
    
    Returns:
        Dictionary with logging configuration details
    """
    root_logger = logging.getLogger()
    
    return {
        "level": logging.getLevelName(root_logger.level),
        "handlers": [
            {
                "type": type(handler).__name__,
                "level": logging.getLevelName(handler.level),
                "formatter": type(handler.formatter).__name__ if handler.formatter else None
            }
            for handler in root_logger.handlers
        ],
        "filters": [
            type(filter_obj).__name__ for filter_obj in root_logger.filters
        ]
    }