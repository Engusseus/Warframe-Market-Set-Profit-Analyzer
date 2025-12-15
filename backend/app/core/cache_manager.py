"""Cache management utilities.

Extracted from main.py lines 431-444 and 1153-1165.
"""
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional


def calculate_hash(data: Any) -> str:
    """Calculate SHA-256 hash of data.

    Args:
        data: Any JSON-serializable data

    Returns:
        SHA-256 hex digest string
    """
    return hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()
    ).hexdigest()


class CacheManager:
    """Manager for prime sets cache with SHA-256 validation."""

    def __init__(self, cache_dir: str = "cache"):
        """Initialize cache manager.

        Args:
            cache_dir: Directory for cache files
        """
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "prime_sets_cache.json")

        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)

    def load_cache(self) -> Dict[str, Any]:
        """Load cached data from file.

        Returns:
            Cached data dictionary, or empty dict if cache doesn't exist
        """
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load cache file: {e}")
        return {}

    def save_cache(self, data: Dict[str, Any]) -> None:
        """Save data to cache file.

        Args:
            data: Data to cache
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save cache file: {e}")

    def is_cache_valid(self, prime_sets: list) -> bool:
        """Check if cache is still valid based on hash comparison.

        Args:
            prime_sets: Current prime sets list from API

        Returns:
            True if cache is valid and can be used
        """
        cache = self.load_cache()
        current_hash = calculate_hash(prime_sets)
        cached_hash = cache.get('prime_sets_hash', '')

        return (
            current_hash == cached_hash and
            'detailed_sets' in cache
        )

    def get_detailed_sets(self) -> Optional[list]:
        """Get detailed sets from cache if available.

        Returns:
            List of detailed sets or None if not cached
        """
        cache = self.load_cache()
        return cache.get('detailed_sets')

    def update_cache(self, prime_sets: list, detailed_sets: list) -> None:
        """Update cache with new data.

        Args:
            prime_sets: Prime sets list for hash calculation
            detailed_sets: Detailed set information to cache
        """
        cache_data = {
            'prime_sets_hash': calculate_hash(prime_sets),
            'detailed_sets': detailed_sets,
            'last_updated': time.time()
        }
        self.save_cache(cache_data)

    def get_cache_age(self) -> Optional[float]:
        """Get age of cache in seconds.

        Returns:
            Age in seconds or None if cache doesn't exist
        """
        cache = self.load_cache()
        last_updated = cache.get('last_updated')
        if last_updated:
            return time.time() - last_updated
        return None
