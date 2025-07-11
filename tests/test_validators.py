"""Tests for input validation utilities."""

import pytest

from ai_news_agent.validators import ContentValidator, URLValidator


class TestURLValidator:
    """Test URL validation functionality."""
    
    def test_valid_urls(self):
        """Test that valid URLs are accepted."""
        valid_urls = [
            "https://example.com",
            "http://example.com/path",
            "https://example.com/path?query=value",
            "https://subdomain.example.com",
            "https://example.com:8080/path",
            "https://example.com/path/to/resource.html",
        ]
        
        for url in valid_urls:
            assert URLValidator.is_valid_url(url), f"URL should be valid: {url}"
    
    def test_invalid_schemes(self):
        """Test that URLs with invalid schemes are rejected."""
        invalid_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "vbscript:msgbox('xss')",
            "file:///etc/passwd",
            "about:blank",
            "ftp://example.com",
        ]
        
        for url in invalid_urls:
            assert not URLValidator.is_valid_url(url), f"URL should be invalid: {url}"
    
    def test_suspicious_patterns(self):
        """Test that URLs with suspicious patterns are rejected."""
        suspicious_urls = [
            "https://example.com/../../../etc/passwd",
            "https://example.com/path%00.jpg",
            "https://example.com/path%0d%0aSet-Cookie:test",
            "https://example.com/javascript:test",
        ]
        
        for url in suspicious_urls:
            assert not URLValidator.is_valid_url(url), f"URL should be suspicious: {url}"
    
    def test_missing_hostname(self):
        """Test that URLs without hostname are rejected."""
        assert not URLValidator.is_valid_url("https://")
        assert not URLValidator.is_valid_url("http:///path")
    
    def test_url_too_long(self):
        """Test that URLs exceeding max length are rejected."""
        long_url = "https://example.com/" + "a" * 2050
        assert not URLValidator.is_valid_url(long_url)
    
    def test_empty_or_none_url(self):
        """Test that empty or None URLs are rejected."""
        assert not URLValidator.is_valid_url("")
        assert not URLValidator.is_valid_url(None)
    
    def test_malformed_urls(self):
        """Test that malformed URLs are rejected."""
        malformed_urls = [
            "not a url",
            "http://",
            "https:/",
            "://example.com",
            "http//example.com",
        ]
        
        for url in malformed_urls:
            assert not URLValidator.is_valid_url(url), f"URL should be malformed: {url}"
    
    def test_sanitize_url(self):
        """Test URL sanitization."""
        # Test whitespace removal
        assert URLValidator.sanitize_url("  https://example.com  ") == "https://example.com"
        
        # Test null byte removal
        assert URLValidator.sanitize_url("https://example.com\x00/path") == "https://example.com/path"
        
        # Test slash normalization
        assert URLValidator.sanitize_url("https://example.com/path//to///resource") == "https://example.com/path/to/resource"
        
        # Test empty input
        assert URLValidator.sanitize_url("") == ""
        assert URLValidator.sanitize_url(None) == ""


class TestContentValidator:
    """Test content validation functionality."""
    
    def test_validate_text_normal(self):
        """Test validation of normal text."""
        text = "This is a normal title"
        result = ContentValidator.validate_text(text, 100, "Title")
        assert result == text
    
    def test_validate_text_empty(self):
        """Test validation of empty text."""
        assert ContentValidator.validate_text("", 100, "Field") == ""
        assert ContentValidator.validate_text(None, 100, "Field") == ""
    
    def test_validate_text_control_characters(self):
        """Test removal of control characters."""
        text = "Hello\x00World\x01Test\x7FEnd"
        result = ContentValidator.validate_text(text, 100, "Field")
        assert result == "HelloWorldTestEnd"
    
    def test_validate_text_whitespace_normalization(self):
        """Test whitespace normalization."""
        text = "Hello   \n\t  World    Test"
        result = ContentValidator.validate_text(text, 100, "Field")
        assert result == "Hello World Test"
    
    def test_validate_text_truncation(self):
        """Test text truncation when exceeding max length."""
        text = "A" * 150
        result = ContentValidator.validate_text(text, 100, "Field")
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")
    
    def test_validate_news_item_data_valid(self):
        """Test validation of valid news item data."""
        data = {
            "url": "https://example.com/article",
            "title": "Test Article",
            "content": "This is the article content.",
            "summary": "Article summary"
        }
        
        result = ContentValidator.validate_news_item_data(data.copy())
        assert result["url"] == data["url"]
        assert result["title"] == data["title"]
        assert result["content"] == data["content"]
        assert result["summary"] == data["summary"]
    
    def test_validate_news_item_data_invalid_url(self):
        """Test validation fails with invalid URL."""
        data = {
            "url": "javascript:alert('xss')",
            "title": "Test Article"
        }
        
        with pytest.raises(ValueError, match="Invalid URL"):
            ContentValidator.validate_news_item_data(data)
    
    def test_validate_news_item_data_text_sanitization(self):
        """Test text field sanitization in news item data."""
        data = {
            "url": "  https://example.com  ",
            "title": "Title\x00with\x01control\x7Fchars",
            "content": "Content   with    extra     spaces",
            "summary": "S" * 1500  # Exceeds max length
        }
        
        result = ContentValidator.validate_news_item_data(data)
        assert result["url"] == "https://example.com"
        assert result["title"] == "Titlewithcontrolchars"
        assert result["content"] == "Content with extra spaces"
        assert len(result["summary"]) == 1003  # MAX_SUMMARY_LENGTH + "..."
        assert result["summary"].endswith("...")
    
    def test_validate_news_item_data_partial(self):
        """Test validation with partial data."""
        # Only URL is required
        data = {"url": "https://example.com"}
        result = ContentValidator.validate_news_item_data(data)
        assert result["url"] == "https://example.com"
        
        # Missing optional fields should not cause issues
        data = {
            "url": "https://example.com",
            "title": "Test"
            # No content or summary
        }
        result = ContentValidator.validate_news_item_data(data)
        assert "content" not in result or result["content"] == ""
        assert "summary" not in result or result["summary"] == ""
    
    def test_max_lengths(self):
        """Test that max length constants are reasonable."""
        assert ContentValidator.MAX_TITLE_LENGTH == 500
        assert ContentValidator.MAX_CONTENT_LENGTH == 50000
        assert ContentValidator.MAX_SUMMARY_LENGTH == 1000