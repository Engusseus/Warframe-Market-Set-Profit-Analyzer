"""Cache management utilities.

Extracted from main.py lines 431-444 and 1153-1165.
"""
import hashlib
import json
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple


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

    def get_random_set_for_canary(self) -> Optional[str]:
        """Get a random set slug from cache for canary validation.

        Returns:
            Random set slug or None if cache is empty
        """
        detailed_sets = self.get_detailed_sets()
        if not detailed_sets:
            return None
        random_set = random.choice(detailed_sets)
        return random_set.get('slug')

    def get_cached_set_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a specific set from cache by slug.

        Args:
            slug: Set slug to find

        Returns:
            Cached set data or None if not found
        """
        detailed_sets = self.get_detailed_sets()
        if not detailed_sets:
            return None
        for set_data in detailed_sets:
            if set_data.get('slug') == slug:
                return set_data
        return None

    def compare_set_data(
        self,
        cached_set: Dict[str, Any],
        fresh_set: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Compare cached set data against fresh API data.

        Checks that parts and quantities match.

        Args:
            cached_set: Set data from cache
            fresh_set: Set data from fresh API call

        Returns:
            Tuple of (is_valid, reason)
        """
        cached_parts = cached_set.get('setParts', [])
        fresh_parts = fresh_set.get('setParts', [])

        # Check part count
        if len(cached_parts) != len(fresh_parts):
            return (
                False,
                f"Part count mismatch: cached={len(cached_parts)}, fresh={len(fresh_parts)}"
            )

        # Build lookup for fresh parts by code
        fresh_parts_lookup = {p.get('code'): p for p in fresh_parts}

        # Compare each cached part against fresh data
        for cached_part in cached_parts:
            part_code = cached_part.get('code')
            fresh_part = fresh_parts_lookup.get(part_code)

            if fresh_part is None:
                return (False, f"Part {part_code} not found in fresh data")

            cached_qty = cached_part.get('quantityInSet', 1)
            fresh_qty = fresh_part.get('quantityInSet', 1)

            if cached_qty != fresh_qty:
                return (
                    False,
                    f"Quantity mismatch for {part_code}: cached={cached_qty}, fresh={fresh_qty}"
                )

        return (True, "Canary check passed")
