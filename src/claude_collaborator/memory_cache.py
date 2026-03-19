"""
File Content Cache for claude-collaborator
Caches file contents to avoid re-reading and enables semantic search
"""

import time
from typing import Any, Dict, Optional, Tuple

from .memory_vector import VectorStore


class FileCache:
    """
    Cache file contents to avoid re-reading

    Provides in-memory caching with automatic expiration and
    semantic storage for retrieval of file contents.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        max_entries: int = 100,
        default_ttl: int = 3600
    ):
        """
        Initialize file cache

        Args:
            vector_store: VectorStore for semantic storage
            max_entries: Maximum number of entries to keep in cache
            default_ttl: Default time-to-live for cache entries (seconds)
        """
        self.vector_store = vector_store
        self.max_entries = max_entries
        self.default_ttl = default_ttl

        # Cache structure: file_path -> (content, timestamp, embedding)
        self.cache: Dict[str, Tuple[str, float, Optional[bytes]]] = {}

    def get(self, file_path: str) -> Optional[str]:
        """
        Get cached file content

        Args:
            file_path: Path to the file

        Returns:
            Cached content if available and not expired, None otherwise
        """
        if file_path not in self.cache:
            return None

        content, timestamp, _ = self.cache[file_path]

        # Check if expired
        if time.time() - timestamp > self.default_ttl:
            del self.cache[file_path]
            return None

        return content

    def set(self, file_path: str, content: str):
        """
        Cache file content

        Args:
            file_path: Path to the file
            content: File content to cache
        """
        # Enforce max entries by evicting oldest
        if len(self.cache) >= self.max_entries:
            self._evict_oldest()

        # Store in cache
        self.cache[file_path] = (content, time.time(), None)

        # Auto-save to vector memory for semantic search
        # Store a summary (first 1000 chars) for quick retrieval
        if self.vector_store._check_embedding_available():
            summary = content[:1000] if len(content) > 1000 else content
            if len(content) > 1000:
                summary += f"\n\n... [Total: {len(content)} chars]"

            self.vector_store.add(
                topic=f"file:{file_path}",
                content=summary,
                category="files",
                metadata={
                    "file_path": file_path,
                    "size": len(content),
                    "cached_at": time.time()
                }
            )

    def _evict_oldest(self):
        """Evict the oldest cache entry"""
        if not self.cache:
            return

        oldest_path = min(self.cache.keys(), key=lambda k: self.cache[k][1])
        del self.cache[oldest_path]

    def clear_old(self, max_age_seconds: int = None):
        """
        Clear cache entries older than max_age

        Args:
            max_age_seconds: Maximum age in seconds (default: use default_ttl)
        """
        ttl = max_age_seconds or self.default_ttl
        current = time.time()

        expired_keys = [
            k for k, (_, timestamp, _) in self.cache.items()
            if current - timestamp > ttl
        ]

        for key in expired_keys:
            del self.cache[key]

    def get_stats(self) -> Dict[str, any]:
        """Get cache statistics"""
        return {
            "entries": len(self.cache),
            "max_entries": self.max_entries,
            "ttl": self.default_ttl,
            "paths": list(self.cache.keys())
        }

    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()

    def __contains__(self, file_path: str) -> bool:
        """Check if file is in cache and not expired"""
        return self.get(file_path) is not None
