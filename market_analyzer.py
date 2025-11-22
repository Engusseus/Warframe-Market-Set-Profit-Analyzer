import time
import json
import hashlib
import statistics
import os
from collections import deque
from database import get_database_instance

# Constants
API_BASE_URL_V2 = "https://api.warframe.market/v2"
API_BASE_URL_V1 = "https://api.warframe.market/v1"

class RateLimiter:
    """Rate limiter to ensure max 3 requests per second."""
    def __init__(self, max_requests=3, time_window=1.0):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if time_window <= 0:
            raise ValueError("time_window must be positive")

        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()  # Use deque for efficient operations

    def _cleanup_old_requests(self, current_time):
        """Remove requests older than time_window."""
        while self.requests and current_time - self.requests[0] >= self.time_window:
            self.requests.popleft()

    def wait_if_needed(self):
        """Wait if necessary to maintain rate limit."""
        current_time = time.time()

        # Remove requests older than time_window
        self._cleanup_old_requests(current_time)

        # If we're at the limit, wait until the oldest request expires
        if len(self.requests) >= self.max_requests:
            # Calculate when the oldest request will expire
            oldest_request_time = self.requests[0]
            sleep_time = self.time_window - (current_time - oldest_request_time)

            if sleep_time > 0:
                # print(f"Rate limiting: waiting {sleep_time:.2f}s...")
                time.sleep(sleep_time)

                # Clean up after waiting
                current_time = time.time()
                self._cleanup_old_requests(current_time)

        # Record this request
        self.requests.append(current_time)

    def get_current_rate(self):
        """Get the current number of requests in the time window."""
        current_time = time.time()
        self._cleanup_old_requests(current_time)
        return len(self.requests)

def calculate_hash(data):
    """Calculate SHA-256 hash of data."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def load_cache():
    """Load cached data from file."""
    cache_file = os.path.join("cache", "prime_sets_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cache file: {e}")
    return {}

def save_cache(data):
    """Save data to cache file."""
    cache_dir = "cache"
    cache_file = os.path.join(cache_dir, "prime_sets_cache.json")

    # Ensure cache directory exists
    os.makedirs(cache_dir, exist_ok=True)

    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save cache file: {e}")

def fetch_with_retry(url, requests_module, rate_limiter, max_retries=3):
    """Fetch URL with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            rate_limiter.wait_if_needed()
            response = requests_module.get(url, timeout=10)

            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limited
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            elif response.status_code == 404:
                # Item not found, don't retry
                return None
            else:
                print(f"HTTP {response.status_code} for {url}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                continue

        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Request failed (attempt {attempt + 1}): {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Request failed after {max_retries} attempts: {e}")
                return None

    return None

def fetch_part_quantity(part_code, requests_module, rate_limiter):
    """Fetch quantityInSet for a specific part with rate limiting."""
    url = f"{API_BASE_URL_V2}/item/{part_code}"

    try:
        response = fetch_with_retry(url, requests_module, rate_limiter)
        if response and response.status_code == 200:
            data = response.json()
            item_data = data.get("data", {})
            quantity_in_set = item_data.get("quantityInSet", 1)  # Default to 1 if not found
            part_name = item_data.get("i18n", {}).get("en", {}).get("name", part_code.replace('_', ' ').title())
            return {
                "code": part_code,
                "name": part_name,
                "quantityInSet": quantity_in_set
            }
        else:
            # print(f"Warning: Could not fetch quantity for part {part_code}")
            return {"code": part_code, "name": part_code.replace('_', ' ').title(), "quantityInSet": 1}

    except Exception as e:
        print(f"Error fetching quantity for part {part_code}: {e}")
        return {"code": part_code, "name": part_code.replace('_', ' ').title(), "quantityInSet": 1}

def fetch_set_details(slug, requests_module, rate_limiter):
    """Fetch detailed information for a specific set with rate limiting."""
    url = f"{API_BASE_URL_V2}/item/{slug}"

    try:
        response = fetch_with_retry(url, requests_module, rate_limiter)
        if response and response.status_code == 200:
            data = response.json()
            item_data = data.get("data", {})

            # Extract setParts and id
            set_parts = item_data.get("setParts", [])
            item_id = item_data.get("id", "")

            # Remove the original prime_set ID from setParts if it exists
            filtered_set_parts = [part for part in set_parts if part != item_id]

            return {
                "id": item_id,
                "setParts": filtered_set_parts,
                "name": item_data.get("i18n", {}).get("en", {}).get("name", slug.replace('_', ' ').title())
            }
        else:
            print(f"Warning: Could not fetch details for {slug}")
            return None

    except Exception as e:
        print(f"Error fetching details for {slug}: {e}")
        return None

def calculate_pricing_statistics(prices):
    """Calculate comprehensive pricing statistics."""
    if not prices:
        return {
            'lowest': 0,
            'mean': 0,
            'std_dev': 0,
            'min': 0,
            'max': 0,
            'count': 0
        }

    stats = {
        'lowest': min(prices),
        'mean': statistics.mean(prices),
        'min': min(prices),
        'max': max(prices),
        'count': len(prices)
    }

    if len(prices) > 1:
        stats['std_dev'] = statistics.stdev(prices)
    else:
        stats['std_dev'] = 0

    return stats

def fetch_item_prices(item_identifier, requests_module, rate_limiter, identifier_type="slug"):
    """Fetch top sell orders for a specific item and return platinum values."""
    url = f"{API_BASE_URL_V2}/orders/item/{item_identifier}/top"

    # Use retry logic
    response = fetch_with_retry(url, requests_module, rate_limiter)

    if response is None:
        return []

    try:
        data = response.json()
    except Exception as e:
        print(f"Error: Invalid JSON response for {item_identifier}: {e}")
        return []

    # Validate response structure
    if not isinstance(data, dict) or 'data' not in data:
        # print(f"Error: Unexpected response structure for {item_identifier}")
        return []

    orders_data = data.get("data", {})
    if not isinstance(orders_data, dict):
        return []

    sell_orders = orders_data.get("sell", [])
    if not isinstance(sell_orders, list):
        return []

    # Extract and validate prices
    sell_prices = []
    for order in sell_orders:
        if isinstance(order, dict):
            platinum = order.get("platinum")
            if isinstance(platinum, (int, float)) and platinum > 0:
                sell_prices.append(platinum)

    return sell_prices

def fetch_set_lowest_prices(cached_data, requests_module, rate_limiter, progress_callback=None):
    """Fetch lowest prices for all Prime sets using cached data."""
    if not cached_data or 'detailed_sets' not in cached_data:
        return []

    lowest_prices = []
    detailed_sets = cached_data['detailed_sets']

    total_sets = len(detailed_sets)

    for i, set_data in enumerate(detailed_sets, 1):
        set_name = set_data.get('name', 'Unknown Set')
        set_id = set_data.get('id', '')

        if progress_callback:
            progress_callback(i, total_sets, f"Fetching prices for {set_name}")

        if not set_id:
            continue

        # Use original slug from cache instead of generating it
        set_slug = set_data.get('slug', '')
        if not set_slug:
            continue

        prices = fetch_item_prices(set_slug, requests_module, rate_limiter)

        if prices:
            stats = calculate_pricing_statistics(prices)
            lowest_prices.append({
                'slug': set_slug,
                'name': set_name,
                'id': set_id,
                'lowest_price': stats['lowest'],
                'price_count': stats['count'],
                'min_price': stats['min'],
                'max_price': stats['max']
            })

    return lowest_prices

def fetch_set_volume(cached_data, requests_module, rate_limiter, progress_callback=None):
    """Fetch individual 48-hour volume for all Prime sets using cached data."""
    if not cached_data or 'detailed_sets' not in cached_data:
        return {}

    detailed_sets = cached_data['detailed_sets']
    volume_data = {}
    total_volume = 0

    total_sets = len(detailed_sets)

    for i, set_data in enumerate(detailed_sets, 1):
        set_name = set_data.get('name', 'Unknown Set')
        set_slug = set_data.get('slug', '')

        if progress_callback:
            progress_callback(i, total_sets, f"Fetching volume for {set_name}")

        if not set_slug:
            continue

        # Use v1 statistics endpoint (v2 doesn't support statistics data)
        url = f"{API_BASE_URL_V1}/items/{set_slug}/statistics"

        # Use retry logic
        response = fetch_with_retry(url, requests_module, rate_limiter)

        if response is None:
            continue

        try:
            data = response.json()
            payload = data.get("payload", {})
            statistics_closed = payload.get("statistics_closed", {})
            hours_48_data = statistics_closed.get("48hours", [])

            # Sum up all volume values from 48hours data
            set_volume = 0
            for entry in hours_48_data:
                if isinstance(entry, dict):
                    volume = entry.get("volume", 0)
                    if isinstance(volume, (int, float)) and volume >= 0:
                        set_volume += volume

            if set_volume > 0:
                volume_data[set_slug] = set_volume
                total_volume += set_volume
            else:
                volume_data[set_slug] = 0

        except Exception as e:
            print(f"Error parsing volume data for {set_name}: {e}")
            continue

    # Return both individual volumes and total
    return {'individual': volume_data, 'total': total_volume}

def fetch_part_lowest_prices(cached_data, requests_module, rate_limiter, progress_callback=None):
    """Fetch lowest prices for all Prime parts using cached data."""
    if not cached_data or 'detailed_sets' not in cached_data:
        return []

    part_lowest_prices = []
    detailed_sets = cached_data['detailed_sets']

    # Use dict to deduplicate parts by code
    unique_parts = {}
    for set_data in detailed_sets:
        parts = set_data.get('setParts', [])
        for part in parts:
            part_code = part.get('code')
            if part_code and part_code not in unique_parts:
                unique_parts[part_code] = part

    # Convert to list for processing
    all_parts = list(unique_parts.values())
    total_parts = len(all_parts)

    for i, part in enumerate(all_parts, 1):
        part_code = part.get('code', '')
        part_name = part.get('name', 'Unknown Part')

        if progress_callback:
            progress_callback(i, total_parts, f"Fetching prices for {part_name}")

        if not part_code:
            continue

        prices = fetch_item_prices(part_code, requests_module, rate_limiter, "id")

        if prices:
            stats = calculate_pricing_statistics(prices)
            part_lowest_prices.append({
                'slug': part_code,
                'name': part_name,
                'lowest_price': stats['lowest'],
                'price_count': stats['count'],
                'min_price': stats['min'],
                'max_price': stats['max'],
                'quantity_in_set': part.get('quantityInSet', 1)
            })

    return part_lowest_prices

def calculate_profit_margins(set_prices, part_prices, detailed_sets):
    """Calculate profit margins for each set by comparing set price to sum of part prices."""
    profit_data = []

    if not set_prices or not part_prices or not detailed_sets:
        return profit_data

    # Create lookup dictionaries for faster access
    set_price_lookup = {item['slug']: item for item in set_prices}
    part_price_lookup = {item['slug']: item for item in part_prices}

    for set_data in detailed_sets:
        set_slug = set_data.get('slug', '')
        set_name = set_data.get('name', 'Unknown Set')

        if not set_slug or set_slug not in set_price_lookup:
            continue

        set_price_data = set_price_lookup[set_slug]
        set_lowest_price = set_price_data['lowest_price']

        # Calculate total cost of individual parts
        total_part_cost = 0
        missing_parts = []
        part_details = []

        for part in set_data.get('setParts', []):
            part_code = part.get('code', '')
            part_name = part.get('name', 'Unknown Part')
            quantity_needed = part.get('quantityInSet', 1)

            if part_code in part_price_lookup:
                part_price_data = part_price_lookup[part_code]
                part_lowest_price = part_price_data['lowest_price']
                part_total_cost = part_lowest_price * quantity_needed
                total_part_cost += part_total_cost

                part_details.append({
                    'name': part_name,
                    'code': part_code,
                    'unit_price': part_lowest_price,
                    'quantity': quantity_needed,
                    'total_cost': part_total_cost
                })
            else:
                missing_parts.append(part_name)

        # Skip sets with missing part data
        if missing_parts:
            continue

        # Calculate profit margin
        if total_part_cost > 0:
            profit_margin = set_lowest_price - total_part_cost
            profit_percentage = (profit_margin / total_part_cost) * 100

            profit_data.append({
                'set_slug': set_slug,
                'set_name': set_name,
                'set_price': set_lowest_price,
                'part_cost': total_part_cost,
                'profit_margin': profit_margin,
                'profit_percentage': profit_percentage,
                'part_details': part_details
            })

    return profit_data

def normalize_data(values, min_val=None, max_val=None):
    """Normalize a list of values to 0-1 range."""
    if not values:
        return []

    if min_val is None:
        min_val = min(values)
    if max_val is None:
        max_val = max(values)

    # Handle case where all values are the same
    if max_val == min_val:
        # Return zeros instead of 0.5 to avoid artificial boosting
        return [0.0] * len(values)

    range_val = max_val - min_val
    return [(value - min_val) / range_val for value in values]

def calculate_profitability_scores(profit_data, volume_data, profit_weight=1.0, volume_weight=1.2):
    """Calculate profitability scores combining profit, volume and derived metrics.

    Added Metrics:
    - Sales Velocity: Volume / 48h (items per hour)
    - Investment Rating: A score representing ROI adjusted by liquidity
    """
    if not profit_data:
        return []

    # Handle different volume data formats
    volume_lookup = {}

    if isinstance(volume_data, dict) and 'individual' in volume_data:
        # New format with individual volumes
        volume_lookup = volume_data['individual'].copy()
    elif isinstance(volume_data, (int, float)):
        # Legacy format - total volume only
        for item in profit_data:
            volume_lookup[item['set_slug']] = 1
    else:
        # Handle other legacy formats
        if isinstance(volume_data, list):
            for item in volume_data:
                if isinstance(item, dict) and 'set_slug' in item:
                    volume_lookup[item['set_slug']] = item.get('volume', 0)
        else:
            for item in profit_data:
                volume_lookup[item['set_slug']] = 1

    # Extract values for normalization
    profit_values = [item['profit_margin'] for item in profit_data]
    volume_values = []

    for item in profit_data:
        set_slug = item['set_slug']
        volume = volume_lookup.get(set_slug, 0)
        volume_values.append(volume)

    # Normalize both datasets to 0-1 range
    normalized_profits = normalize_data(profit_values)
    normalized_volumes = normalize_data(volume_values)

    # Calculate weighted scores
    scored_data = []
    for i, profit_item in enumerate(profit_data):
        profit_score = normalized_profits[i] * profit_weight
        volume_score = normalized_volumes[i] * volume_weight
        total_score = profit_score + volume_score

        volume = volume_values[i]

        # Derived Metrics
        sales_velocity = volume / 48.0  # Sales per hour

        # Investment Rating: (ROI * log(Volume + 1)) - Simple heuristic
        # We use volume to ensure we don't rate high ROI but 0 volume items too highly
        import math
        roi = profit_item['profit_percentage']
        investment_rating = roi * math.log1p(volume) if volume > 0 else 0

        scored_data.append({
            **profit_item,
            'volume': volume,
            'sales_velocity': sales_velocity,
            'investment_rating': investment_rating,
            'normalized_profit': normalized_profits[i],
            'normalized_volume': normalized_volumes[i],
            'profit_score': profit_score,
            'volume_score': volume_score,
            'total_score': total_score
        })

    # Sort by total score (descending)
    scored_data.sort(key=lambda x: x['total_score'], reverse=True)

    return scored_data

def fetch_prime_sets_list(requests_module):
    """Fetch the list of prime sets from API."""
    url = f"{API_BASE_URL_V2}/items"
    response = requests_module.get(url, timeout=30)

    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")

    data = response.json()
    items = data.get("data", [])

    # Filter for items ending with 'prime_set'
    prime_sets = [item for item in items if item.get('slug', '').endswith('_prime_set')]

    if not prime_sets:
        raise Exception("No Prime sets found.")

    return prime_sets

def refresh_cache_data(requests_module, rate_limiter, progress_callback=None):
    """Refreshes the detailed set cache."""

    prime_sets = fetch_prime_sets_list(requests_module)
    prime_sets.sort(key=lambda x: x.get('i18n', {}).get('en', {}).get('name', x.get('slug', '')))

    detailed_sets = []
    total_sets = len(prime_sets)

    for i, item in enumerate(prime_sets, 1):
        slug = item.get('slug', '')

        if progress_callback:
            progress_callback(i, total_sets, f"Fetching details for {slug}")

        set_details = fetch_set_details(slug, requests_module, rate_limiter)

        if set_details:
            # Fetch part quantities
            parts_with_quantities = []
            for part_code in set_details['setParts']:
                part_info = fetch_part_quantity(part_code, requests_module, rate_limiter)
                parts_with_quantities.append(part_info)

            complete_set_data = {
                'id': set_details['id'],
                'name': set_details['name'],
                'slug': slug,
                'setParts': parts_with_quantities
            }
            detailed_sets.append(complete_set_data)
        else:
            # Fallback
            i18n = item.get('i18n', {})
            en_info = i18n.get('en', {})
            name = en_info.get('name', slug.replace('_', ' ').title())
            fallback_data = {
                'id': '',
                'name': name,
                'slug': slug,
                'setParts': []
            }
            detailed_sets.append(fallback_data)

    # Update cache
    current_hash = calculate_hash(prime_sets)
    cache_data = {
        'prime_sets_hash': current_hash,
        'detailed_sets': detailed_sets,
        'last_updated': time.time()
    }
    save_cache(cache_data)
    return cache_data
