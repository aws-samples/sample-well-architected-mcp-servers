"""
Date and time utilities for both BedrockAgent and AgentCore versions.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import json


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> float:
    """Get current UTC timestamp."""
    return utc_now().timestamp()


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
    """
    Format datetime object as string.
    
    Args:
        dt: Datetime object to format
        format_str: Format string
        
    Returns:
        Formatted datetime string
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.strftime(format_str)


def parse_datetime(dt_str: str) -> datetime:
    """
    Parse datetime string in ISO format.
    
    Args:
        dt_str: Datetime string in ISO format
        
    Returns:
        Datetime object
    """
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except ValueError:
        # Try parsing without timezone info
        return datetime.fromisoformat(dt_str)


def time_ago(dt: datetime) -> str:
    """
    Get human-readable time ago string.
    
    Args:
        dt: Datetime to compare against current time
        
    Returns:
        Human-readable time difference string
    """
    now = utc_now()
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    
    hours = diff.seconds // 3600
    if hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    
    minutes = diff.seconds // 60
    if minutes > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    
    return "just now"


def duration_ms(start_time: datetime, end_time: Optional[datetime] = None) -> float:
    """
    Calculate duration in milliseconds between two datetime objects.
    
    Args:
        start_time: Start datetime
        end_time: End datetime (defaults to current time)
        
    Returns:
        Duration in milliseconds
    """
    if end_time is None:
        end_time = utc_now()
    
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    diff = end_time - start_time
    return diff.total_seconds() * 1000


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Add minutes to datetime.
    
    Args:
        dt: Base datetime
        minutes: Minutes to add
        
    Returns:
        New datetime with minutes added
    """
    return dt + timedelta(minutes=minutes)


def add_hours(dt: datetime, hours: int) -> datetime:
    """
    Add hours to datetime.
    
    Args:
        dt: Base datetime
        hours: Hours to add
        
    Returns:
        New datetime with hours added
    """
    return dt + timedelta(hours=hours)


def add_days(dt: datetime, days: int) -> datetime:
    """
    Add days to datetime.
    
    Args:
        dt: Base datetime
        days: Days to add
        
    Returns:
        New datetime with days added
    """
    return dt + timedelta(days=days)


def is_expired(dt: datetime, ttl_seconds: int) -> bool:
    """
    Check if datetime has expired based on TTL.
    
    Args:
        dt: Datetime to check
        ttl_seconds: Time-to-live in seconds
        
    Returns:
        True if expired, False otherwise
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    expiry_time = dt + timedelta(seconds=ttl_seconds)
    return utc_now() > expiry_time


def get_start_of_day(dt: Optional[datetime] = None) -> datetime:
    """
    Get start of day (00:00:00) for given datetime.
    
    Args:
        dt: Datetime (defaults to current time)
        
    Returns:
        Datetime at start of day
    """
    if dt is None:
        dt = utc_now()
    
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_end_of_day(dt: Optional[datetime] = None) -> datetime:
    """
    Get end of day (23:59:59.999999) for given datetime.
    
    Args:
        dt: Datetime (defaults to current time)
        
    Returns:
        Datetime at end of day
    """
    if dt is None:
        dt = utc_now()
    
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def format_duration(duration_ms: float) -> str:
    """
    Format duration in milliseconds as human-readable string.
    
    Args:
        duration_ms: Duration in milliseconds
        
    Returns:
        Human-readable duration string
    """
    if duration_ms < 1000:
        return f"{duration_ms:.1f}ms"
    
    seconds = duration_ms / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    
    hours = minutes / 60
    return f"{hours:.1f}h"


def get_age_in_seconds(dt: datetime) -> float:
    """
    Get age of datetime in seconds from current time.
    
    Args:
        dt: Datetime to calculate age for
        
    Returns:
        Age in seconds
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return (utc_now() - dt).total_seconds()


def is_recent(dt: datetime, threshold_seconds: int = 300) -> bool:
    """
    Check if datetime is recent (within threshold).
    
    Args:
        dt: Datetime to check
        threshold_seconds: Threshold in seconds (default: 5 minutes)
        
    Returns:
        True if recent, False otherwise
    """
    return get_age_in_seconds(dt) <= threshold_seconds


def create_timestamp_range(
    start_dt: datetime,
    end_dt: datetime,
    interval_minutes: int = 60
) -> list[datetime]:
    """
    Create list of timestamps between start and end with given interval.
    
    Args:
        start_dt: Start datetime
        end_dt: End datetime
        interval_minutes: Interval in minutes
        
    Returns:
        List of datetime objects
    """
    timestamps = []
    current = start_dt
    
    while current <= end_dt:
        timestamps.append(current)
        current = add_minutes(current, interval_minutes)
    
    return timestamps