"""
jira_cache.py

TTL-based cache for JIRA responses to reduce API calls and improve performance.
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


class JIRACache:
    """TTL-based cache for JIRA responses."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        """
        Initialize JIRA cache.

        Args:
            ttl_seconds: Time to live for cache entries in seconds
            max_size: Maximum number of entries to keep in cache
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _generate_key(self, key_data: Any) -> str:
        """
        Generate a cache key from input data.

        Args:
            key_data: Data to generate key from (string, dict, etc.)

        Returns:
            Cache key string
        """
        if isinstance(key_data, str):
            return key_data

        # For complex data, create a hash
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    async def get(self, key: Any) -> Optional[Any]:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key (can be string or complex object)

        Returns:
            Cached value or None if not found/expired
        """
        cache_key = self._generate_key(key)

        async with self._lock:
            if cache_key in self._cache:
                value, timestamp = self._cache[cache_key]

                # Check if expired
                if time.time() - timestamp < self.ttl_seconds:
                    self._hits += 1
                    logger.info(f"Cache hit for key: {cache_key[:20]}...")
                    # Move to end (LRU behavior)
                    del self._cache[cache_key]
                    self._cache[cache_key] = (value, timestamp)
                    return value
                else:
                    # Expired, remove it
                    del self._cache[cache_key]
                    logger.info(f"Cache entry expired for key: {cache_key[:20]}...")

            self._misses += 1
            return None

    async def set(self, key: Any, value: Any) -> None:
        """
        Set value in cache with current timestamp.

        Args:
            key: Cache key (can be string or complex object)
            value: Value to cache
        """
        cache_key = self._generate_key(key)

        async with self._lock:
            # Check cache size and evict if necessary
            if len(self._cache) >= self.max_size and cache_key not in self._cache:
                # Evict oldest entries (first 10% of cache)
                num_to_evict = max(1, self.max_size // 10)
                keys_to_evict = list(self._cache.keys())[:num_to_evict]

                for old_key in keys_to_evict:
                    del self._cache[old_key]
                    self._evictions += 1

                logger.info(f"Evicted {len(keys_to_evict)} cache entries")

            # Add/update cache entry
            self._cache[cache_key] = (value, time.time())
            logger.info(f"Cached value for key: {cache_key[:20]}...")

    async def invalidate(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate cache entries matching pattern.

        Args:
            pattern: Optional pattern to match keys. If None, clears all.

        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            if pattern is None:
                # Clear all
                count = len(self._cache)
                self._cache.clear()
                logger.info(f"Invalidated all {count} cache entries")
                return count
            else:
                # Remove entries matching pattern
                keys_to_delete = [k for k in self._cache.keys() if pattern in k]

                for key in keys_to_delete:
                    del self._cache[key]

                logger.info(f"Invalidated {len(keys_to_delete)} cache entries matching '{pattern}'")
                return len(keys_to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary of cache statistics
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        # Calculate average age of entries
        current_time = time.time()
        ages = []
        for _, (_, timestamp) in self._cache.items():
            ages.append(current_time - timestamp)

        avg_age = sum(ages) / len(ages) if ages else 0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
            "size": len(self._cache),
            "max_size": self.max_size,
            "evictions": self._evictions,
            "ttl_seconds": self.ttl_seconds,
            "avg_age_seconds": round(avg_age, 1),
        }

    async def warm_cache(self, entries: Dict[str, Any]) -> None:
        """
        Pre-populate cache with entries.

        Args:
            entries: Dictionary of key-value pairs to cache
        """
        count = 0
        for key, value in entries.items():
            await self.set(key, value)
            count += 1

        logger.info(f"Warmed cache with {count} entries")

    def clear_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logger.info("Cache statistics cleared")

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of expired entries removed
        """
        current_time = time.time()
        expired_count = 0

        async with self._lock:
            keys_to_remove = []

            for key, (_, timestamp) in self._cache.items():
                if current_time - timestamp >= self.ttl_seconds:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._cache[key]
                expired_count += 1

            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired cache entries")

        return expired_count
