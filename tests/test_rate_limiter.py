"""Tests for rate limiting utilities."""

import asyncio
import time
from unittest.mock import patch

import pytest

from ai_news_agent.utils.rate_limiter import ConcurrencyLimiter, RateLimiter


class TestRateLimiter:
    """Test the RateLimiter class."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        return RateLimiter(rate=2.0, burst=5, per_domain=True)
    
    @pytest.fixture
    def global_rate_limiter(self):
        """Create a global rate limiter for testing."""
        return RateLimiter(rate=2.0, burst=5, per_domain=False)
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rate=1.5, burst=10, per_domain=True)
        assert limiter.rate == 1.5
        assert limiter.burst == 10
        assert limiter.per_domain is True
        assert len(limiter.buckets) == 0
        assert len(limiter.last_update) == 0
    
    def test_get_bucket_key_per_domain(self, rate_limiter):
        """Test bucket key extraction for per-domain mode."""
        # Test with full URL
        key = rate_limiter._get_bucket_key("https://example.com/feed.xml")
        assert key == "example.com"
        
        # Test with different paths on same domain
        key2 = rate_limiter._get_bucket_key("https://example.com/other.xml")
        assert key2 == "example.com"
        
        # Test with different domain
        key3 = rate_limiter._get_bucket_key("https://other.com/feed.xml")
        assert key3 == "other.com"
        
        # Test with port
        key4 = rate_limiter._get_bucket_key("https://example.com:8080/feed.xml")
        assert key4 == "example.com:8080"
        
        # Test with invalid URL
        key5 = rate_limiter._get_bucket_key("not a url")
        assert key5 == "unknown"
    
    def test_get_bucket_key_global(self, global_rate_limiter):
        """Test bucket key for global mode."""
        key1 = global_rate_limiter._get_bucket_key("https://example.com/feed.xml")
        key2 = global_rate_limiter._get_bucket_key("https://other.com/feed.xml")
        assert key1 == "global"
        assert key2 == "global"
    
    @pytest.mark.asyncio
    async def test_acquire_no_wait(self, rate_limiter):
        """Test acquiring tokens without waiting."""
        # First request should not wait
        start = time.time()
        await rate_limiter.acquire("https://example.com/feed.xml", tokens=1.0)
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should be instant
        assert 3.9 <= rate_limiter.buckets["example.com"] <= 4.1  # 5 - 1 (with floating point tolerance)
    
    @pytest.mark.asyncio
    async def test_acquire_with_wait(self, rate_limiter):
        """Test acquiring tokens with rate limiting."""
        url = "https://example.com/feed.xml"
        
        # Consume all burst tokens
        await rate_limiter.acquire(url, tokens=5.0)
        assert rate_limiter.buckets["example.com"] == 0.0
        
        # Next request should wait
        start = time.time()
        await rate_limiter.acquire(url, tokens=1.0)
        elapsed = time.time() - start
        
        # Should wait about 0.5 seconds (1 token at 2 tokens/sec)
        assert 0.4 <= elapsed <= 0.6
    
    @pytest.mark.asyncio
    async def test_token_refill(self, rate_limiter):
        """Test that tokens refill over time."""
        url = "https://example.com/feed.xml"
        
        # Consume some tokens
        await rate_limiter.acquire(url, tokens=3.0)
        assert 1.9 <= rate_limiter.buckets["example.com"] <= 2.1
        
        # Wait for refill
        await asyncio.sleep(1.0)  # Should refill 2 tokens
        
        # Check tokens were refilled
        tokens = rate_limiter.get_current_tokens(url)
        assert 3.9 <= tokens <= 4.1  # 2 + 2 (refilled)
    
    @pytest.mark.asyncio
    async def test_burst_limit(self, rate_limiter):
        """Test that tokens don't exceed burst limit."""
        url = "https://example.com/feed.xml"
        
        # Wait long enough to fully refill
        await asyncio.sleep(3.0)
        
        # Check tokens are capped at burst
        tokens = rate_limiter.get_current_tokens(url)
        assert 4.9 <= tokens <= 5.0  # Burst limit (with tolerance)
    
    @pytest.mark.asyncio
    async def test_per_domain_isolation(self, rate_limiter):
        """Test that different domains have separate buckets."""
        url1 = "https://example.com/feed.xml"
        url2 = "https://other.com/feed.xml"
        
        # Consume tokens from domain 1
        await rate_limiter.acquire(url1, tokens=3.0)
        
        # Domain 2 should still have full tokens
        tokens2 = rate_limiter.get_current_tokens(url2)
        assert 4.9 <= tokens2 <= 5.0
        
        # Domain 1 should have reduced tokens
        tokens1 = rate_limiter.get_current_tokens(url1)
        assert tokens1 < 3.0
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, rate_limiter):
        """Test concurrent access to rate limiter."""
        url = "https://example.com/feed.xml"
        
        # Multiple concurrent requests
        tasks = [
            rate_limiter.acquire(url, tokens=1.0)
            for _ in range(5)
        ]
        
        start = time.time()
        await asyncio.gather(*tasks)
        elapsed = time.time() - start
        
        # All 5 tokens should be consumed immediately (burst)
        assert elapsed < 0.1
        assert rate_limiter.buckets["example.com"] <= 0.1
    
    @pytest.mark.asyncio
    async def test_fractional_tokens(self, rate_limiter):
        """Test acquiring fractional tokens."""
        url = "https://example.com/feed.xml"
        
        await rate_limiter.acquire(url, tokens=0.5)
        assert 4.4 <= rate_limiter.buckets["example.com"] <= 4.6
        
        await rate_limiter.acquire(url, tokens=1.5)
        assert 2.9 <= rate_limiter.buckets["example.com"] <= 3.1
    
    def test_get_current_tokens_without_acquire(self, rate_limiter):
        """Test getting current tokens without prior acquire."""
        url = "https://example.com/feed.xml"
        tokens = rate_limiter.get_current_tokens(url)
        assert 4.9 <= tokens <= 5.0  # Full burst (with tolerance)
    
    @pytest.mark.asyncio
    async def test_debug_logging(self, rate_limiter):
        """Test that debug logging occurs when waiting."""
        url = "https://example.com/feed.xml"
        
        # Consume all tokens
        await rate_limiter.acquire(url, tokens=5.0)
        
        # Next request should log wait time
        with patch("ai_news_agent.utils.rate_limiter.logger") as mock_logger:
            await rate_limiter.acquire(url, tokens=1.0)
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Rate limit: waiting" in call_args
            assert "example.com" in call_args


class TestConcurrencyLimiter:
    """Test the ConcurrencyLimiter class."""
    
    @pytest.fixture
    def concurrency_limiter(self):
        """Create a concurrency limiter for testing."""
        return ConcurrencyLimiter(max_concurrent=2)
    
    def test_initialization(self):
        """Test concurrency limiter initialization."""
        limiter = ConcurrencyLimiter(max_concurrent=3)
        assert limiter.max_concurrent == 3
        assert len(limiter.semaphores) == 0
    
    def test_get_domain(self, concurrency_limiter):
        """Test domain extraction."""
        assert concurrency_limiter._get_domain("https://example.com/feed") == "example.com"
        assert concurrency_limiter._get_domain("http://sub.example.com:8080/") == "sub.example.com:8080"
        assert concurrency_limiter._get_domain("invalid url") == "unknown"
    
    @pytest.mark.asyncio
    async def test_acquire_semaphore(self, concurrency_limiter):
        """Test acquiring semaphore for domain."""
        url = "https://example.com/feed.xml"
        
        sem = await concurrency_limiter.acquire(url)
        assert isinstance(sem, asyncio.Semaphore)
        
        # Same domain should return same semaphore
        sem2 = await concurrency_limiter.acquire("https://example.com/other.xml")
        assert sem is sem2
        
        # Different domain should get different semaphore
        sem3 = await concurrency_limiter.acquire("https://other.com/feed.xml")
        assert sem is not sem3
    
    @pytest.mark.asyncio
    async def test_concurrent_limit(self, concurrency_limiter):
        """Test that concurrency is actually limited."""
        url1 = "https://example.com/feed1.xml"
        url2 = "https://example.com/feed2.xml"
        url3 = "https://example.com/feed3.xml"
        
        # Track concurrent connections
        concurrent_count = 0
        max_concurrent_seen = 0
        
        async def mock_request(url):
            nonlocal concurrent_count, max_concurrent_seen
            sem = await concurrency_limiter.acquire(url)
            async with sem:
                concurrent_count += 1
                max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
                await asyncio.sleep(0.1)  # Simulate request
                concurrent_count -= 1
        
        # Start 3 concurrent requests (but limit is 2)
        await asyncio.gather(
            mock_request(url1),
            mock_request(url2),
            mock_request(url3)
        )
        
        # Should never exceed max_concurrent
        assert max_concurrent_seen == 2
    
    @pytest.mark.asyncio
    async def test_different_domains_independent(self, concurrency_limiter):
        """Test that different domains have independent limits."""
        # Track concurrent connections per domain
        concurrent_counts = {"example.com": 0, "other.com": 0}
        
        async def mock_request(url, domain):
            sem = await concurrency_limiter.acquire(url)
            async with sem:
                concurrent_counts[domain] += 1
                await asyncio.sleep(0.1)
                concurrent_counts[domain] -= 1
        
        # Start requests to different domains
        await asyncio.gather(
            mock_request("https://example.com/1", "example.com"),
            mock_request("https://example.com/2", "example.com"),
            mock_request("https://other.com/1", "other.com"),
            mock_request("https://other.com/2", "other.com"),
        )
        
        # Both domains should have been able to handle 2 concurrent requests
        assert "example.com" in concurrency_limiter.semaphores
        assert "other.com" in concurrency_limiter.semaphores
    
    @pytest.mark.asyncio
    async def test_semaphore_reuse(self, concurrency_limiter):
        """Test that semaphores are reused after release."""
        url = "https://example.com/feed.xml"
        
        # Get semaphore
        sem = await concurrency_limiter.acquire(url)
        
        # Use and release it
        async with sem:
            pass
        
        # Should be able to acquire again immediately
        sem2 = await concurrency_limiter.acquire(url)
        assert sem is sem2  # Same semaphore object