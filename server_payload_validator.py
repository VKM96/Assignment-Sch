"""
server_payload_validation.py - Data Validation Module

This module provides centralized validation functions for data processing.

Key features:
- Payload size validation
- UTF-8 encoding validation
- Extensible design for adding additional validators

Usage:
    from validation import validate_payload
    success, decoded_data, error_reason = validate_payload(data, max_size)

Dependencies:
    - logging (standard library)
"""


class PayloadValidationError(Exception):
    """Exception raised when payload validation fails."""
    pass


def validate_payload(data: bytes, max_size: int) -> tuple[bool, str | None, str | None]:
    """
    Validate incoming payload size and encoding.
    
    Args:
        data (bytes): Raw data to validate
        max_size (int): Maximum allowed payload size in bytes
    
    Returns:
        tuple: (success: bool, decoded_data: str | None, error_reason: str | None)
            - success: True if payload is valid, False otherwise
            - decoded_data: UTF-8 decoded string if valid, None if validation failed
            - error_reason: Reason for validation failure if success is False, None otherwise
    
    Validation checks:
        - Rejects payloads exceeding max_size
        - Rejects payloads with invalid UTF-8 encoding
    
    Examples:
        >>> success, data, error = validate_payload(b"hello", 1000)
        >>> success
        True
        >>> data
        'hello'
        
        >>> success, data, error = validate_payload(b"x" * 2000, 1000)
        >>> success
        False
        >>> error
        'Payload too large (2000 bytes)'
    """
    # Reject oversized payloads
    if len(data) > max_size:
        reason = (f"Payload too large ({len(data)} bytes)")
        return False, None, reason

    try:
        validated_data = data.decode("utf-8")
    except UnicodeDecodeError:
        reason = (f"Malformed/binary payload rejected")
        return False, None, reason

    return True, validated_data, None
