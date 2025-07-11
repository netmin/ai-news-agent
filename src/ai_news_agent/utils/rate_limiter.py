"""Rate limiting utilities for RSS feed fetching"""

import asyncio
import time
from collections import defaultdict

from loguru import logger


class RateLimiter:
    """Token bucket rate limiter for RSS feeds
    
    Prevents overwhelming feed servers with too many requests
    """

    def __init__(
        self,
        rate: float = 1.0,  # requests per second
        burst: int = 5,     # burst capacity
        per_domain: bool = True
    ):
        """Initialize rate limiter
        
        Args:
            rate: Sustained request rate (requests/second)
            burst: Maximum burst size
            per_domain: Whether to rate limit per domain
        """
        self.rate = rate
        self.burst = burst
        self.per_domain = per_domain
        self.buckets: dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: dict[str, float] = defaultdict(time.time)
        self._lock = asyncio.Lock()

    def _get_bucket_key(self, url: str) -> str:
        """Get bucket key for URL"""
        if not self.per_domain:
            return "global"

        # Extract domain from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def acquire(self, url: str, tokens: float = 1.0) -> None:
        """Acquire tokens from bucket, waiting if necessary
        
        Args:
            url: URL being requested
            tokens: Number of tokens to acquire
        """
        bucket_key = self._get_bucket_key(url)

        async with self._lock:
            now = time.time()

            # Refill bucket based on time elapsed
            elapsed = now - self.last_update[bucket_key]
            self.buckets[bucket_key] = min(
                self.burst,
                self.buckets[bucket_key] + elapsed * self.rate
            )
            self.last_update[bucket_key] = now

            # Wait if not enough tokens
            if self.buckets[bucket_key] < tokens:
                wait_time = (tokens - self.buckets[bucket_key]) / self.rate
                logger.debug(
                    f"Rate limit: waiting {wait_time:.2f}s for {bucket_key}"
                )
                await asyncio.sleep(wait_time)

                # Update bucket after wait
                now = time.time()
                elapsed = now - self.last_update[bucket_key]
                self.buckets[bucket_key] = min(
                    self.burst,
                    self.buckets[bucket_key] + elapsed * self.rate
                )
                self.last_update[bucket_key] = now

            # Consume tokens
            self.buckets[bucket_key] -= tokens

    def get_current_tokens(self, url: str) -> float:
        """Get current token count for URL's bucket"""
        bucket_key = self._get_bucket_key(url)
        now = time.time()
        elapsed = now - self.last_update[bucket_key]

        return min(
            self.burst,
            self.buckets[bucket_key] + elapsed * self.rate
        )


class ConcurrencyLimiter:
    """Limit concurrent connections per domain"""

    def __init__(self, max_concurrent: int = 2):
        """Initialize concurrency limiter
        
        Args:
            max_concurrent: Maximum concurrent connections per domain
        """
        self.max_concurrent = max_concurrent
        self.semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"

    async def acquire(self, url: str):
        """Get semaphore for URL's domain"""
        domain = self._get_domain(url)

        async with self._lock:
            if domain not in self.semaphores:
                self.semaphores[domain] = asyncio.Semaphore(self.max_concurrent)

        return self.semaphores[domain]
