"""Input validation utilities"""

import re
from urllib.parse import urlparse

from loguru import logger


class URLValidator:
    """Validate and sanitize URLs"""
    
    # Allowed URL schemes
    ALLOWED_SCHEMES = {'http', 'https'}
    
    # Suspicious patterns in URLs
    SUSPICIOUS_PATTERNS = [
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'file:',
        r'about:',
        r'\.\./',  # Path traversal
        r'%00',     # Null byte
        r'%0d%0a',  # CRLF injection
    ]
    
    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Check if URL is valid and safe
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and safe
        """
        if not url:
            return False
            
        try:
            parsed = urlparse(url)
            
            # Check scheme
            if parsed.scheme not in cls.ALLOWED_SCHEMES:
                logger.warning(f"Invalid URL scheme: {parsed.scheme}")
                return False
                
            # Check for suspicious patterns
            url_lower = url.lower()
            for pattern in cls.SUSPICIOUS_PATTERNS:
                if re.search(pattern, url_lower):
                    logger.warning(f"Suspicious pattern in URL: {pattern}")
                    return False
                    
            # Check hostname
            if not parsed.hostname:
                logger.warning("URL missing hostname")
                return False
                
            # Additional checks
            if len(url) > 2048:  # Max URL length
                logger.warning("URL too long")
                return False
                
            return True
            
        except Exception as e:
            logger.warning(f"Error validating URL: {e}")
            return False
    
    @classmethod
    def sanitize_url(cls, url: str) -> str:
        """Sanitize URL by removing dangerous parts
        
        Args:
            url: URL to sanitize
            
        Returns:
            Sanitized URL
        """
        if not url:
            return ""
            
        # Remove whitespace
        url = url.strip()
        
        # Remove null bytes
        url = url.replace('\x00', '')
        
        # Normalize slashes
        url = re.sub(r'/+', '/', url)
        
        return url


class ContentValidator:
    """Validate content from RSS feeds"""
    
    # Maximum content sizes
    MAX_TITLE_LENGTH = 500
    MAX_CONTENT_LENGTH = 50000  # 50KB
    MAX_SUMMARY_LENGTH = 1000
    
    @classmethod
    def validate_text(cls, text: str, max_length: int, field_name: str) -> str:
        """Validate and truncate text field
        
        Args:
            text: Text to validate
            max_length: Maximum allowed length
            field_name: Name of field for logging
            
        Returns:
            Validated text
        """
        if not text:
            return ""
            
        # Remove null bytes and control characters
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Truncate if too long
        if len(text) > max_length:
            logger.warning(
                f"{field_name} truncated from {len(text)} to {max_length} chars"
            )
            text = text[:max_length] + "..."
            
        return text
    
    @classmethod
    def validate_news_item_data(cls, data: dict) -> dict:
        """Validate news item data before creating model
        
        Args:
            data: Raw data dictionary
            
        Returns:
            Validated data dictionary
        """
        # Validate URL
        if 'url' in data:
            url = URLValidator.sanitize_url(data['url'])
            if not URLValidator.is_valid_url(url):
                raise ValueError(f"Invalid URL: {data['url']}")
            data['url'] = url
            
        # Validate text fields
        if 'title' in data:
            data['title'] = cls.validate_text(
                data['title'], 
                cls.MAX_TITLE_LENGTH, 
                'Title'
            )
            
        if 'content' in data:
            data['content'] = cls.validate_text(
                data['content'], 
                cls.MAX_CONTENT_LENGTH, 
                'Content'
            )
            
        if 'summary' in data:
            data['summary'] = cls.validate_text(
                data['summary'], 
                cls.MAX_SUMMARY_LENGTH, 
                'Summary'
            )
            
        return data