"""Security utilities for the AI News Agent"""

import os
import re
from typing import Any


class SecretScanner:
    """Scan for potential secrets in configuration and environment"""

    # Patterns that might indicate secrets
    SECRET_PATTERNS = [
        (r'sk-[a-zA-Z0-9]{40,}', 'API Key'),
        (r'AKIA[0-9A-Z]{16}', 'AWS Access Key'),
        (r'[a-zA-Z0-9_-]{40,}', 'Generic Token'),
        (r'-----BEGIN.*PRIVATE KEY-----', 'Private Key'),
    ]

    # Keys that commonly contain secrets
    SENSITIVE_KEYS = [
        'api_key', 'apikey', 'api_secret', 'secret', 'password',
        'token', 'auth', 'credential', 'private_key'
    ]

    @classmethod
    def scan_dict(cls, data: dict[str, Any], path: str = "") -> list[str]:
        """Scan dictionary for potential secrets
        
        Args:
            data: Dictionary to scan
            path: Current path in nested structure
            
        Returns:
            List of warnings about potential secrets
        """
        warnings = []

        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            # Check if key name suggests sensitive data
            if any(sensitive in key.lower() for sensitive in cls.SENSITIVE_KEYS):
                if isinstance(value, str) and value and not value.startswith("${"):
                    # Check against patterns
                    for pattern, desc in cls.SECRET_PATTERNS:
                        if re.search(pattern, value):
                            warnings.append(
                                f"Potential {desc} found at {current_path}"
                            )

            # Recursively scan nested dictionaries
            elif isinstance(value, dict):
                warnings.extend(cls.scan_dict(value, current_path))

        return warnings

    @classmethod
    def scan_environment(cls) -> list[str]:
        """Scan environment variables for potential secrets
        
        Returns:
            List of warnings about potential secrets
        """
        warnings = []

        for key, value in os.environ.items():
            # Skip system variables
            if key.startswith(('PATH', 'HOME', 'USER', 'SHELL', 'TERM')):
                continue

            # Check sensitive keys
            if any(sensitive in key.lower() for sensitive in cls.SENSITIVE_KEYS):
                if value and not value.startswith("${"):
                    for pattern, desc in cls.SECRET_PATTERNS:
                        if re.search(pattern, value):
                            warnings.append(
                                f"Potential {desc} found in environment variable {key}"
                            )

        return warnings


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret value for safe logging
    
    Args:
        value: Secret value to mask
        show_chars: Number of characters to show at start
        
    Returns:
        Masked value
    """
    if not value or len(value) <= show_chars:
        return "***"

    return f"{value[:show_chars]}{'*' * (len(value) - show_chars)}"


def safe_config_dict(config: dict[str, Any]) -> dict[str, Any]:
    """Create a safe version of config dict for logging
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Safe dictionary with masked secrets
    """
    safe = {}

    for key, value in config.items():
        if any(sensitive in key.lower() for sensitive in SecretScanner.SENSITIVE_KEYS):
            if isinstance(value, str) and value:
                safe[key] = mask_secret(value)
            else:
                safe[key] = "***"
        elif isinstance(value, dict):
            safe[key] = safe_config_dict(value)
        else:
            safe[key] = value

    return safe
