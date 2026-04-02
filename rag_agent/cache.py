"""
Disk-based caching layer using diskcache.
"""

import hashlib
import json
from typing import Any, Optional
from pathlib import Path

from diskcache import Cache


class QueryCache:
    """
    File-based cache for query results using diskcache.
    
    Provides persistent caching with TTL support to reduce
    repeated LLM calls and database queries.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, max_size: int = 1024**3):
        """
        Initialize the cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to ./cache.
            max_size: Maximum cache size in bytes (default 1GB).
        """
        if cache_dir is None:
            cache_dir = str(Path(__file__).parent.parent / "cache")
        
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self._cache = Cache(cache_dir, size_limit=max_size)
    
    def _compute_key(self, question: str, schema: Any, sql: str) -> str:
        """
        Compute a cache key from question, schema hash, and SQL.
        
        Args:
            question: The natural language question.
            schema: Database schema (will be hashed).
            sql: The SQL query.
            
        Returns:
            A unique cache key string.
        """
        schema_str = json.dumps(schema, sort_keys=True) if schema else ""
        key_data = f"{question}|{schema_str}|{sql}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, question: str, schema: Any, sql: str) -> Optional[Any]:
        """
        Get cached query result.
        
        Args:
            question: The natural language question.
            schema: Database schema.
            sql: The SQL query.
            
        Returns:
            Cached data if found, None otherwise.
        """
        key = self._compute_key(question, schema, sql)
        return self._cache.get(key)
    
    def set(self, question: str, schema: Any, sql: str, data: Any, expire: int = 3600) -> None:
        """
        Store query result in cache.
        
        Args:
            question: The natural language question.
            schema: Database schema.
            sql: The SQL query.
            data: Query results to cache.
            expire: TTL in seconds (default 1 hour).
        """
        key = self._compute_key(question, schema, sql)
        self._cache.set(key, data, expire=expire)
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
    
    def delete(self, question: str, schema: Any, sql: str) -> bool:
        """
        Delete a specific cache entry.
        
        Args:
            question: The natural language question.
            schema: Database schema.
            sql: The SQL query.
            
        Returns:
            True if entry was deleted, False if not found.
        """
        key = self._compute_key(question, schema, sql)
        return self._cache.delete(key) is not None
    
    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)
    
    def close(self) -> None:
        """Close the cache and release resources."""
        self._cache.close()


# Global cache instance
_cache_instance: Optional[QueryCache] = None


def get_cache(cache_dir: Optional[str] = None) -> QueryCache:
    """
    Get or create the global cache instance.
    
    Args:
        cache_dir: Optional custom cache directory.
        
    Returns:
        QueryCache instance.
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = QueryCache(cache_dir)
    return _cache_instance
