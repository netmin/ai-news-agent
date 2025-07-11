"""Simple in-memory cache for RSS feeds"""

import asyncio
import hashlib
import time
from typing import Any, Optional

from loguru import logger


class TTLCache:
    """Time-based cache with TTL (time to live)"""
    
    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """Initialize cache
        
        Args:
            ttl: Time to live in seconds
            max_size: Maximum cache size
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()
        self._access_count: dict[str, int] = {}
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create cache key from arguments"""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self._lock:
            if key not in self._cache:
                return None
                
            timestamp, value = self._cache[key]
            if time.time() - timestamp > self.ttl:
                # Expired
                del self._cache[key]
                return None
                
            self._access_count[key] = self._access_count.get(key, 0) + 1
            return value
    
    async def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        async with self._lock:
            # Evict oldest if cache is full
            if len(self._cache) >= self.max_size:
                # Find least recently used
                lru_key = min(
                    self._cache.keys(),
                    key=lambda k: self._access_count.get(k, 0)
                )
                del self._cache[lru_key]
                if lru_key in self._access_count:
                    del self._access_count[lru_key]
                    
            self._cache[key] = (time.time(), value)
    
    async def clear(self) -> None:
        """Clear cache"""
        async with self._lock:
            self._cache.clear()
            self._access_count.clear()
    
    def stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        total_accesses = sum(self._access_count.values())
        return {
            "size": len(self._cache),
            "total_accesses": total_accesses,
            "hit_rate": total_accesses / max(1, total_accesses + len(self._cache))
        }


def cached(ttl: int = 300):
    """Decorator for caching async function results
    
    Args:
        ttl: Time to live in seconds
    """
    cache = TTLCache(ttl=ttl)
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create cache key
            key = cache._make_key(*args, **kwargs)
            
            # Try to get from cache
            result = await cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return result
                
            # Call function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result)
            return result
            
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.cache = cache  # Expose cache for management
        
        return wrapper
        
    return decorator