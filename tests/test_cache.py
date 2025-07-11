"""Tests for the cache module."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from ai_news_agent.utils.cache import TTLCache, cached


@pytest.fixture
def cache():
    """Create a cache instance for testing."""
    return TTLCache(ttl=1, max_size=3)  # Short TTL for testing


class TestTTLCache:
    """Test TTL cache functionality."""
    
    @pytest.mark.asyncio
    async def test_basic_get_set(self, cache):
        """Test basic cache get/set operations."""
        # Set a value
        await cache.set("key1", "value1")
        
        # Get the value
        result = await cache.get("key1")
        assert result == "value1"
        
        # Get non-existent key
        result = await cache.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test that values expire after TTL."""
        # Set a value
        await cache.set("key1", "value1")
        
        # Value should exist immediately
        assert await cache.get("key1") == "value1"
        
        # Wait for TTL to expire
        await asyncio.sleep(1.1)
        
        # Value should be expired
        assert await cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_max_size_eviction(self, cache):
        """Test that cache evicts LRU items when full."""
        # Fill cache to max size
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # Access key1 and key3 to make them more recently used
        await cache.get("key1")
        await cache.get("key3")
        
        # Add new item - should evict key2 (least recently used)
        await cache.set("key4", "value4")
        
        # Check that key2 was evicted
        assert await cache.get("key2") is None
        assert await cache.get("key1") == "value1"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"
    
    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Test cache clearing."""
        # Add some items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # Clear cache
        await cache.clear()
        
        # Check all items are gone
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert len(cache._cache) == 0
        assert len(cache._access_count) == 0
    
    def test_make_key(self, cache):
        """Test cache key generation."""
        # Same arguments should produce same key
        key1 = cache._make_key("arg1", "arg2", param1="value1")
        key2 = cache._make_key("arg1", "arg2", param1="value1")
        assert key1 == key2
        
        # Different arguments should produce different keys
        key3 = cache._make_key("arg1", "arg3", param1="value1")
        assert key1 != key3
        
        # Order of keyword arguments shouldn't matter
        key4 = cache._make_key(param2="value2", param1="value1")
        key5 = cache._make_key(param1="value1", param2="value2")
        assert key4 == key5
    
    @pytest.mark.asyncio
    async def test_stats(self, cache):
        """Test cache statistics."""
        # Initial stats
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["total_accesses"] == 0
        
        # Add items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # Access items
        await cache.get("key1")
        await cache.get("key1")  # Access twice
        await cache.get("key2")
        await cache.get("nonexistent")  # Miss
        
        stats = cache.stats()
        assert stats["size"] == 2
        assert stats["total_accesses"] == 3  # Only hits count
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache):
        """Test concurrent access to cache."""
        # Define tasks that access cache concurrently
        async def set_value(key, value):
            await cache.set(key, value)
        
        async def get_value(key):
            return await cache.get(key)
        
        # Run multiple operations concurrently
        await asyncio.gather(
            set_value("key1", "value1"),
            set_value("key2", "value2"),
            set_value("key3", "value3"),
            get_value("key1"),
            get_value("key2"),
        )
        
        # Verify all values are set correctly
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
    
    @pytest.mark.asyncio
    async def test_different_value_types(self, cache):
        """Test caching different value types."""
        # String
        await cache.set("string", "test")
        assert await cache.get("string") == "test"
        
        # Number
        await cache.set("number", 42)
        assert await cache.get("number") == 42
        
        # List
        await cache.set("list", [1, 2, 3])
        assert await cache.get("list") == [1, 2, 3]
        
        # Dict
        await cache.set("dict", {"key": "value"})
        assert await cache.get("dict") == {"key": "value"}
        
        # None (special case)
        await cache.set("none", None)
        # This will return None, but it's indistinguishable from a miss


class TestCachedDecorator:
    """Test the cached decorator."""
    
    @pytest.mark.asyncio
    async def test_basic_caching(self):
        """Test that decorator caches function results."""
        call_count = 0
        
        @cached(ttl=1)
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - should execute function
        result1 = await test_func(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call with same args - should use cache
        result2 = await test_func(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again
        
        # Call with different args - should execute function
        result3 = await test_func(3)
        assert result3 == 6
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test that cached values expire."""
        call_count = 0
        
        @cached(ttl=0.5)  # 0.5 second TTL
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = await test_func(5)
        assert result1 == 10
        assert call_count == 1
        
        # Wait for cache to expire
        await asyncio.sleep(0.6)
        
        # Should call function again
        result2 = await test_func(5)
        assert result2 == 10
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_keyword_arguments(self):
        """Test caching with keyword arguments."""
        call_count = 0
        
        @cached(ttl=1)
        async def test_func(x, y=1):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # Different ways of calling should be cached separately
        result1 = await test_func(5)
        assert result1 == 6
        assert call_count == 1
        
        result2 = await test_func(5, y=1)  # Same as above
        assert result2 == 6
        assert call_count == 2  # Treated as different call
        
        result3 = await test_func(5, y=2)  # Different y value
        assert result3 == 7
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_cache_management(self):
        """Test accessing cache through decorator."""
        @cached(ttl=1)
        async def test_func(x):
            return x * 2
        
        # Call function
        await test_func(5)
        
        # Access cache stats
        stats = test_func.cache.stats()
        assert stats["size"] == 1
        
        # Clear cache
        await test_func.cache.clear()
        stats = test_func.cache.stats()
        assert stats["size"] == 0
    
    @pytest.mark.asyncio
    async def test_preserve_function_attributes(self):
        """Test that decorator preserves function attributes."""
        @cached(ttl=1)
        async def test_func(x):
            """Test function docstring."""
            return x * 2
        
        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test that exceptions are not cached."""
        call_count = 0
        
        @cached(ttl=1)
        async def test_func(x):
            nonlocal call_count
            call_count += 1
            if x < 0:
                raise ValueError("Negative value")
            return x * 2
        
        # First call with error
        with pytest.raises(ValueError):
            await test_func(-1)
        assert call_count == 1
        
        # Second call with same args - should call function again (error not cached)
        with pytest.raises(ValueError):
            await test_func(-1)
        assert call_count == 2
        
        # Successful call should be cached
        result = await test_func(5)
        assert result == 10
        assert call_count == 3
        
        # Second successful call should use cache
        result = await test_func(5)
        assert result == 10
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_decorated_calls(self):
        """Test concurrent calls to decorated function."""
        call_count = 0
        
        @cached(ttl=1)
        async def slow_func(x):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate slow operation
            return x * 2
        
        # Make concurrent calls with same arguments
        results = await asyncio.gather(
            slow_func(5),
            slow_func(5),
            slow_func(5),
        )
        
        # All should return same result
        assert all(r == 10 for r in results)
        # Due to concurrent execution, function might be called 1-3 times
        # depending on timing, but it should be cached after first completion
        assert 1 <= call_count <= 3
    
    @pytest.mark.asyncio
    async def test_with_logger(self):
        """Test that cache hits are logged."""
        @cached(ttl=1)
        async def test_func(x):
            return x * 2
        
        # First call
        await test_func(5)
        
        # Second call should log cache hit
        with patch("ai_news_agent.utils.cache.logger") as mock_logger:
            result = await test_func(5)
            assert result == 10
            mock_logger.debug.assert_called_once_with("Cache hit for test_func")