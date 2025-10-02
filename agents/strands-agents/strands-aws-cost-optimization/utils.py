"""
Utility functions for AWS Billing Management Agent.

This module provides common utility functions for cost analysis,
data formatting, and optimization calculations.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
import json


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format currency amount with proper formatting."""
    if amount == 0:
        return f"${0:.2f}"
    
    if amount < 0.01:
        return f"<${0.01}"
    
    if amount >= 1000000:
        return f"${amount/1000000:.2f}M"
    elif amount >= 1000:
        return f"${amount/1000:.2f}K"
    else:
        return f"${amount:.2f}"


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change between two values."""
    if old_value == 0:
        return 100.0 if new_value > 0 else 0.0
    
    return ((new_value - old_value) / old_value) * 100


def format_percentage(percentage: float, decimal_places: int = 1) -> str:
    """Format percentage with appropriate sign and formatting."""
    if percentage > 0:
        return f"+{percentage:.{decimal_places}f}%"
    else:
        return f"{percentage:.{decimal_places}f}%"


def parse_time_period(period_str: str) -> Tuple[datetime, datetime]:
    """Parse time period string into start and end dates."""
    now = datetime.now()
    
    # Common period patterns
    patterns = {
        r'last\s+(\d+)\s+days?': lambda m: (now - timedelta(days=int(m.group(1))), now),
        r'last\s+(\d+)\s+weeks?': lambda m: (now - timedelta(weeks=int(m.group(1))), now),
        r'last\s+(\d+)\s+months?': lambda m: (now - timedelta(days=int(m.group(1)) * 30), now),
        r'this\s+month': lambda m: (now.replace(day=1), now),
        r'last\s+month': lambda m: get_last_month_range(now),
        r'this\s+year': lambda m: (now.replace(month=1, day=1), now),
        r'last\s+year': lambda m: get_last_year_range(now),
    }
    
    period_lower = period_str.lower().strip()
    
    for pattern, func in patterns.items():
        match = re.search(pattern, period_lower)
        if match:
            return func(match)
    
    # Default to last 30 days
    return now - timedelta(days=30), now


def get_last_month_range(current_date: datetime) -> Tuple[datetime, datetime]:
    """Get the date range for the previous month."""
    first_day_current = current_date.replace(day=1)
    last_day_previous = first_day_current - timedelta(days=1)
    first_day_previous = last_day_previous.replace(day=1)
    return first_day_previous, last_day_previous


def get_last_year_range(current_date: datetime) -> Tuple[datetime, datetime]:
    """Get the date range for the previous year."""
    last_year = current_date.year - 1
    start_date = datetime(last_year, 1, 1)
    end_date = datetime(last_year, 12, 31)
    return start_date, end_date


def calculate_savings_potential(current_cost: float, optimized_cost: float) -> Dict[str, Any]:
    """Calculate savings potential and related metrics."""
    savings = current_cost - optimized_cost
    savings_percentage = (savings / current_cost * 100) if current_cost > 0 else 0
    
    return {
        "current_cost": current_cost,
        "optimized_cost": optimized_cost,
        "potential_savings": savings,
        "savings_percentage": savings_percentage,
        "formatted_current": format_currency(current_cost),
        "formatted_optimized": format_currency(optimized_cost),
        "formatted_savings": format_currency(savings),
        "formatted_percentage": format_percentage(savings_percentage)
    }


def prioritize_recommendations(recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prioritize recommendations based on savings potential and implementation effort."""
    
    def calculate_priority_score(rec: Dict[str, Any]) -> float:
        """Calculate priority score for a recommendation."""
        savings = rec.get('potential_savings', 0)
        effort = rec.get('implementation_effort', 'medium')
        
        # Effort multipliers
        effort_multipliers = {
            'low': 1.0,
            'medium': 0.7,
            'high': 0.4
        }
        
        multiplier = effort_multipliers.get(effort.lower(), 0.7)
        return savings * multiplier
    
    # Sort by priority score (descending)
    return sorted(recommendations, key=calculate_priority_score, reverse=True)


def categorize_costs(cost_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize costs by service, region, or other dimensions."""
    categories = {}
    
    for item in cost_data:
        category = item.get('service', 'Unknown')
        if category not in categories:
            categories[category] = []
        categories[category].append(item)
    
    return categories


def calculate_trend(data_points: List[float], periods: int = 3) -> str:
    """Calculate trend direction from data points."""
    if len(data_points) < 2:
        return "insufficient_data"
    
    # Use last N periods for trend calculation
    recent_data = data_points[-periods:] if len(data_points) >= periods else data_points
    
    if len(recent_data) < 2:
        return "insufficient_data"
    
    # Simple linear trend
    increases = 0
    decreases = 0
    
    for i in range(1, len(recent_data)):
        if recent_data[i] > recent_data[i-1]:
            increases += 1
        elif recent_data[i] < recent_data[i-1]:
            decreases += 1
    
    if increases > decreases:
        return "increasing"
    elif decreases > increases:
        return "decreasing"
    else:
        return "stable"


def format_recommendation_summary(recommendations: List[Dict[str, Any]]) -> str:
    """Format a summary of recommendations."""
    if not recommendations:
        return "No recommendations available."
    
    total_savings = sum(rec.get('potential_savings', 0) for rec in recommendations)
    high_impact = [rec for rec in recommendations if rec.get('potential_savings', 0) > 100]
    
    summary = f"""
## Cost Optimization Summary

**Total Potential Savings**: {format_currency(total_savings)}
**Number of Recommendations**: {len(recommendations)}
**High-Impact Opportunities**: {len(high_impact)}

### Top 3 Recommendations:
"""
    
    for i, rec in enumerate(recommendations[:3], 1):
        savings = rec.get('potential_savings', 0)
        title = rec.get('title', f'Recommendation {i}')
        summary += f"{i}. **{title}** - {format_currency(savings)} potential savings\n"
    
    return summary


def validate_cost_data(data: Dict[str, Any]) -> bool:
    """Validate cost data structure and values."""
    required_fields = ['amount', 'currency']
    
    for field in required_fields:
        if field not in data:
            return False
    
    # Validate amount is numeric and non-negative
    try:
        amount = float(data['amount'])
        if amount < 0:
            return False
    except (ValueError, TypeError):
        return False
    
    return True


def extract_service_from_arn(arn: str) -> str:
    """Extract AWS service name from ARN."""
    if not arn or not arn.startswith('arn:aws:'):
        return 'unknown'
    
    parts = arn.split(':')
    if len(parts) >= 3:
        return parts[2]
    
    return 'unknown'


def calculate_roi(investment: float, savings: float, time_period_months: int = 12) -> Dict[str, Any]:
    """Calculate Return on Investment for cost optimization initiatives."""
    if investment <= 0:
        return {
            'roi_percentage': float('inf') if savings > 0 else 0,
            'payback_period_months': 0,
            'net_benefit': savings * time_period_months,
            'formatted_roi': "∞%" if savings > 0 else "0%"
        }
    
    annual_savings = savings * 12
    roi_percentage = ((annual_savings - investment) / investment) * 100
    payback_period_months = investment / savings if savings > 0 else float('inf')
    net_benefit = (savings * time_period_months) - investment
    
    return {
        'roi_percentage': roi_percentage,
        'payback_period_months': payback_period_months,
        'net_benefit': net_benefit,
        'formatted_roi': format_percentage(roi_percentage),
        'formatted_payback': f"{payback_period_months:.1f} months" if payback_period_months != float('inf') else "Never",
        'formatted_net_benefit': format_currency(net_benefit)
    }


def generate_cost_alert_message(current_cost: float, threshold: float, period: str) -> str:
    """Generate cost alert message based on threshold breach."""
    percentage_over = ((current_cost - threshold) / threshold) * 100
    
    if current_cost > threshold:
        return f"""
🚨 **Cost Alert**: Your AWS spending for {period} is {format_currency(current_cost)}, 
which is {format_percentage(percentage_over)} over your threshold of {format_currency(threshold)}.

**Immediate Actions Recommended**:
1. Review top spending services
2. Check for any unusual resource usage
3. Implement immediate cost controls if necessary
"""
    else:
        remaining_budget = threshold - current_cost
        return f"""
✅ **Budget Status**: Your AWS spending for {period} is {format_currency(current_cost)}, 
which is within your threshold of {format_currency(threshold)}. 
Remaining budget: {format_currency(remaining_budget)}.
"""


class CostAnalyzer:
    """Utility class for advanced cost analysis operations."""
    
    @staticmethod
    def analyze_cost_distribution(costs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze cost distribution across services/resources."""
        if not costs:
            return {"error": "No cost data provided"}
        
        total_cost = sum(item.get('amount', 0) for item in costs)
        
        # Calculate percentages
        distribution = []
        for item in costs:
            amount = item.get('amount', 0)
            percentage = (amount / total_cost * 100) if total_cost > 0 else 0
            distribution.append({
                **item,
                'percentage': percentage,
                'formatted_amount': format_currency(amount),
                'formatted_percentage': format_percentage(percentage)
            })
        
        # Sort by amount (descending)
        distribution.sort(key=lambda x: x.get('amount', 0), reverse=True)
        
        return {
            'total_cost': total_cost,
            'formatted_total': format_currency(total_cost),
            'distribution': distribution,
            'top_3_services': distribution[:3]
        }
    
    @staticmethod
    def detect_anomalies(historical_costs: List[float], current_cost: float, threshold_std: float = 2.0) -> Dict[str, Any]:
        """Detect cost anomalies using statistical analysis."""
        if len(historical_costs) < 3:
            return {"anomaly_detected": False, "reason": "Insufficient historical data"}
        
        # Calculate mean and standard deviation
        mean_cost = sum(historical_costs) / len(historical_costs)
        variance = sum((x - mean_cost) ** 2 for x in historical_costs) / len(historical_costs)
        std_dev = variance ** 0.5
        
        # Check if current cost is an anomaly
        z_score = (current_cost - mean_cost) / std_dev if std_dev > 0 else 0
        is_anomaly = abs(z_score) > threshold_std
        
        return {
            'anomaly_detected': is_anomaly,
            'z_score': z_score,
            'mean_cost': mean_cost,
            'std_deviation': std_dev,
            'current_cost': current_cost,
            'threshold': threshold_std,
            'severity': 'high' if abs(z_score) > 3 else 'medium' if abs(z_score) > 2 else 'low',
            'formatted_mean': format_currency(mean_cost),
            'formatted_current': format_currency(current_cost)
        }


if __name__ == "__main__":
    # Test utility functions
    print("AWS Billing Management Agent Utilities")
    print("=" * 50)
    
    # Test currency formatting
    test_amounts = [0, 0.005, 1.50, 150.75, 1500.00, 150000.00, 1500000.00]
    print("Currency Formatting:")
    for amount in test_amounts:
        print(f"  {amount} -> {format_currency(amount)}")
    
    # Test percentage calculations
    print("\nPercentage Calculations:")
    old_cost, new_cost = 1000, 1200
    change = calculate_percentage_change(old_cost, new_cost)
    print(f"  {old_cost} -> {new_cost}: {format_percentage(change)}")
    
    # Test savings calculation
    print("\nSavings Calculation:")
    savings = calculate_savings_potential(1000, 750)
    print(f"  Current: {savings['formatted_current']}")
    print(f"  Optimized: {savings['formatted_optimized']}")
    print(f"  Savings: {savings['formatted_savings']} ({savings['formatted_percentage']})")
    
    # Test ROI calculation
    print("\nROI Calculation:")
    roi = calculate_roi(500, 100)  # $500 investment, $100/month savings
    print(f"  ROI: {roi['formatted_roi']}")
    print(f"  Payback: {roi['formatted_payback']}")
    print(f"  Net Benefit: {roi['formatted_net_benefit']}")