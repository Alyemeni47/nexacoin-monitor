"""
Utility functions for the NexaCoin Monitor Bot
"""
import logging
import os
import base58
from typing import Optional, Dict, Any, List

# Set up logger
logger = logging.getLogger(__name__)

def safe_get_nested(obj: Dict[str, Any], *keys: str, default=None) -> Any:
    """
    Safely get a nested value from a dictionary without raising KeyError
    
    Args:
        obj: The dictionary to extract values from
        *keys: A sequence of keys to navigate through the nested dictionaries
        default: The default value to return if any key is not found
        
    Returns:
        The value found at the specified path, or the default value if any key is missing
    """
    current = obj
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current

def split_amount_by_percentage(amount: int, percentages: List[float]) -> List[int]:
    """
    Split an amount based on a list of percentages
    
    Args:
        amount: The total amount to split
        percentages: A list of percentages (should sum to 100)
        
    Returns:
        A list of integer amounts corresponding to the percentages
    """
    # Validate the percentages
    total_percentage = sum(percentages)
    if abs(total_percentage - 100.0) > 0.01:  # Allow tiny floating point errors
        logger.warning(f"Percentages do not sum to 100% (got {total_percentage}%)")
    
    # Calculate amounts
    amounts = [int(amount * (p / 100.0)) for p in percentages]
    
    # Handle rounding errors by adjusting the last amount
    total_allocated = sum(amounts)
    if total_allocated != amount:
        amounts[-1] += (amount - total_allocated)
        
    return amounts

def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive data from strings before logging
    
    Args:
        text: The text that may contain sensitive information
        
    Returns:
        Text with sensitive information redacted
    """
    # List of patterns to look for and redact
    patterns = [
        # Private keys are base58 encoded and typically 88 characters
        (r'[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{87,88}', 'REDACTED_PRIVATE_KEY')
    ]
    
    result = text
    for pattern, replacement in patterns:
        import re
        result = re.sub(pattern, replacement, result)
        
    return result

def validate_solana_address(address: str) -> bool:
    """
    Validate if a string is a valid Solana address
    
    Args:
        address: The Solana address to validate
        
    Returns:
        True if the address is valid, False otherwise
    """
    try:
        # Solana addresses are base58 encoded and 32 bytes long
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except Exception:
        return False
