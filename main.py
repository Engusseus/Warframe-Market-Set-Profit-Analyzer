import os
import sys
import subprocess
import venv
import time
import hashlib
import json
import statistics
from collections import deque

def setup_venv():
    """Set up virtual environment and install dependencies."""
    venv_dir = "venv"
    
    try:
        if not os.path.exists(venv_dir):
            print("Creating virtual environment...")
            venv.create(venv_dir, with_pip=True)
    except Exception as e:
        print(f"Error creating virtual environment: {e}")
        sys.exit(1)
    
    if sys.platform == "win32":
        pip_path = os.path.join(venv_dir, "Scripts", "pip.exe")
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        pip_path = os.path.join(venv_dir, "bin", "pip")
        python_path = os.path.join(venv_dir, "bin", "python")
    
    if not os.path.exists(pip_path):
        print(f"Error: pip not found at {pip_path}")
        sys.exit(1)
    
    if os.path.exists("requirements.txt"):
        try:
            print("Installing requirements...")
            subprocess.check_call([pip_path, "install", "-r", "requirements.txt"])
        except subprocess.CalledProcessError as e:
            print(f"Error installing requirements: {e}")
            sys.exit(1)
    
    print("Virtual environment setup complete!")
    return python_path

def activate_venv_and_run():
    """Activate virtual environment and run the main script."""
    python_path = setup_venv()
    
    if sys.executable != python_path:
        print("Activating virtual environment and restarting...")
        subprocess.check_call([python_path, __file__, "--venv-active"])
        sys.exit(0)

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
                print(f"Rate limiting: waiting {sleep_time:.2f}s...")
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

def fetch_part_quantity(part_code, requests_module, rate_limiter):
    """Fetch quantityInSet for a specific part with rate limiting."""
    rate_limiter.wait_if_needed()
    
    url = f"https://api.warframe.market/v2/item/{part_code}"
    
    try:
        response = requests_module.get(url, timeout=10)
        if response.status_code == 200:
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
            print(f"Warning: Could not fetch quantity for part {part_code} (Status: {response.status_code})")
            return {"code": part_code, "name": part_code.replace('_', ' ').title(), "quantityInSet": 1}
            
    except Exception as e:
        print(f"Error fetching quantity for part {part_code}: {e}")
        return {"code": part_code, "name": part_code.replace('_', ' ').title(), "quantityInSet": 1}

def fetch_set_details(slug, requests_module, rate_limiter):
    """Fetch detailed information for a specific set with rate limiting."""
    rate_limiter.wait_if_needed()
    
    url = f"https://api.warframe.market/v2/item/{slug}"
    
    try:
        response = requests_module.get(url, timeout=10)
        if response.status_code == 200:
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
            print(f"Warning: Could not fetch details for {slug} (Status: {response.status_code})")
            return None
            
    except Exception as e:
        print(f"Error fetching details for {slug}: {e}")
        return None

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

def calculate_lowest_price(prices):
    """Calculate lowest price from a list of prices."""
    if not prices:
        return 0
    return min(prices)

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

def fetch_item_prices(item_identifier, requests_module, rate_limiter, identifier_type="slug"):
    """Fetch top sell orders for a specific item and return platinum values."""
    url = f"https://api.warframe.market/v2/orders/item/{item_identifier}/top"
    
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
        print(f"Error: Unexpected response structure for {item_identifier}")
        return []
    
    orders_data = data.get("data", {})
    if not isinstance(orders_data, dict):
        print(f"Error: Expected orders data to be dict for {item_identifier}")
        return []
    
    sell_orders = orders_data.get("sell", [])
    if not isinstance(sell_orders, list):
        print(f"Error: Expected list of sell orders for {item_identifier}")
        return []
    
    # Extract and validate prices
    sell_prices = []
    for order in sell_orders:
        if isinstance(order, dict):
            platinum = order.get("platinum")
            if isinstance(platinum, (int, float)) and platinum > 0:
                sell_prices.append(platinum)
    
    return sell_prices

def fetch_set_lowest_prices(cached_data, requests_module, rate_limiter):
    """Fetch lowest prices for all Prime sets using cached data."""
    if not cached_data or 'detailed_sets' not in cached_data:
        print("No cached set data available for pricing.")
        return []
    
    lowest_prices = []
    detailed_sets = cached_data['detailed_sets']
    
    print(f"\nFetching pricing data for {len(detailed_sets)} Prime Sets...")
    print("Rate limited to 3 requests per second for API safety.")
    print("=" * 60)
    
    for i, set_data in enumerate(detailed_sets, 1):
        set_name = set_data.get('name', 'Unknown Set')
        set_id = set_data.get('id', '')
        
        if not set_id:
            print(f"Skipping {set_name} - No ID available")
            continue
        
        print(f"Fetching prices for set {i}/{len(detailed_sets)}: {set_name}")
        
        # Use original slug from cache instead of generating it
        set_slug = set_data.get('slug', '')
        if not set_slug:
            print(f"  → No slug available for {set_name}")
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
            print(f"  → Lowest price: {stats['lowest']} platinum (from {stats['count']} sellers)")
        else:
            print(f"  → No valid prices found")
    
    return lowest_prices

def fetch_part_lowest_prices(cached_data, requests_module, rate_limiter):
    """Fetch lowest prices for all Prime parts using cached data."""
    if not cached_data or 'detailed_sets' not in cached_data:
        print("No cached set data available for part pricing.")
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
    
    if not all_parts:
        print("No parts found in cached data.")
        return []
    
    print(f"\nFetching pricing data for {len(all_parts)} Prime Parts...")
    print("Rate limited to 3 requests per second for API safety.")
    print("=" * 60)
    
    for i, part in enumerate(all_parts, 1):
        part_code = part.get('code', '')
        part_name = part.get('name', 'Unknown Part')
        
        if not part_code:
            print(f"Skipping {part_name} - No code available")
            continue
        
        print(f"Fetching prices for part {i}/{len(all_parts)}: {part_name}")
        
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
            print(f"  → Lowest price: {stats['lowest']} platinum (from {stats['count']} sellers)")
        else:
            print(f"  → No valid prices found")
    
    return part_lowest_prices

def display_pricing_summary(set_prices, part_prices):
    """Display a comprehensive pricing summary."""
    print("\n" + "=" * 80)
    print("PRICING SUMMARY")
    print("=" * 80)
    
    # Display set prices
    if set_prices:
        print(f"\nPRIME SET LOWEST PRICES ({len(set_prices)} sets)")
        print("-" * 60)
        set_prices_sorted = sorted(set_prices, key=lambda x: x['lowest_price'], reverse=True)
        
        for i, set_data in enumerate(set_prices_sorted, 1):
            name = set_data['name']
            price = set_data['lowest_price']
            count = set_data['price_count']
            min_price = set_data['min_price']
            max_price = set_data['max_price']
            print(f"{i:3d}. {name:<35} {price:>6.0f} plat ({min_price}-{max_price}) ({count} sellers)")
        
        total_set_value = sum(s['lowest_price'] for s in set_prices)
        avg_set_price = total_set_value / len(set_prices)
        
        print(f"\nTotal market value of all sets: {total_set_value:.0f} platinum")
        print(f"Average set price: {avg_set_price:.0f} platinum")
    else:
        print("\nNo set pricing data available")
    
    # Display part prices
    if part_prices:
        print(f"\nPRIME PART LOWEST PRICES ({len(part_prices)} parts)")
        print("-" * 60)
        part_prices_sorted = sorted(part_prices, key=lambda x: x['lowest_price'], reverse=True)
        
        # Show top 20 most expensive parts
        top_parts = part_prices_sorted[:20]
        print("Top 20 Most Expensive Parts:")
        for i, part_data in enumerate(top_parts, 1):
            name = part_data['name']
            price = part_data['lowest_price']
            count = part_data['price_count']
            min_price = part_data['min_price']
            max_price = part_data['max_price']
            qty = part_data['quantity_in_set']
            total_part_cost = price * qty
            print(f"{i:3d}. {name:<40} {price:>6.0f} plat ({min_price}-{max_price}) x{qty} = {total_part_cost:>6.0f} plat ({count} sellers)")
        
        if len(part_prices) > 20:
            print(f"\n... and {len(part_prices) - 20} more parts")
        
        total_part_value = sum(p['lowest_price'] * p['quantity_in_set'] for p in part_prices)
        avg_part_price = sum(p['lowest_price'] for p in part_prices) / len(part_prices)
        
        print(f"\nTotal market value of all parts: {total_part_value:.0f} platinum")
        print(f"Average part price: {avg_part_price:.0f} platinum")
    else:
        print("\nNo part pricing data available")
    
    print("\n" + "=" * 80)
    print("Note: Prices are live market data and change frequently.")
    print("Lowest prices taken from top 5 online sellers per item.")
    print("Price ranges show (min-max) from all available sellers.")
    print("Duplicate parts are automatically deduplicated for efficiency.")
    print("=" * 80)

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

def get_prime_sets():
    """Fetch and display Prime sets with their parts from Warframe Market API."""
    try:
        import requests
    except ImportError:
        print("Error: requests module not found. Virtual environment setup may have failed.")
        return
    
    # Initialize rate limiter (3 requests per second)
    rate_limiter = RateLimiter(max_requests=3, time_window=1.0)
    
    # Load existing cache
    cache = load_cache()
    
    print("Fetching Prime sets from Warframe Market API...")
    url = "https://api.warframe.market/v2/items"
    
    try:
        # First API call to get all items (not rate limited as it's just one call)
        response = requests.get(url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", [])
            
            # Filter for items ending with 'prime_set'
            prime_sets = []
            for item in items:
                slug = item.get('slug', '')
                if slug.endswith('_prime_set'):
                    prime_sets.append(item)
            
            if not prime_sets:
                print("No Prime sets found.")
                return
            
            # Calculate hash of prime_sets array
            current_hash = calculate_hash(prime_sets)
            cached_hash = cache.get('prime_sets_hash', '')
            
            # Check if data has changed
            if current_hash == cached_hash and 'detailed_sets' in cache:
                print("Data unchanged since last fetch. Using cached data...")
                print(f"\nUsing cached data for {len(prime_sets)} Prime Sets.\n")
                print("=" * 80)
                
                # Display cached data
                detailed_sets = cache['detailed_sets']
                for i, set_data in enumerate(detailed_sets, 1):
                    print(f"\n{i:2d}. {set_data['name']} [{set_data['id']}]")
                    
                    if set_data.get('setParts'):
                        print("    Parts:")
                        for part in set_data['setParts']:
                            print(f"      - {part['name']} [{part['code']}] (Quantity: {part['quantityInSet']})")
                    else:
                        print("    No individual parts found.")
                    
                    print()
                
                print("=" * 80)
                print(f"Total Prime Sets processed: {len(detailed_sets)}")
                print("Data loaded from cache (1 API call instead of many!)")
                
                # Fetch pricing data using cached information
                print("\n" + "=" * 80)
                print("FETCHING REAL-TIME PRICING DATA")
                print("=" * 80)
                
                # Fetch set lowest prices
                set_prices = fetch_set_lowest_prices(cache, requests, rate_limiter)
                
                # Fetch part lowest prices
                part_prices = fetch_part_lowest_prices(cache, requests, rate_limiter)
                
                # Display pricing summary
                display_pricing_summary(set_prices, part_prices)
                return
            
            # Data has changed or no cache exists, fetch fresh data
            print(f"\nData changed or cache missing. Fetching detailed information for {len(prime_sets)} Prime Sets...\n")
            print("Rate limited to 3 requests per second for API safety.")
            print("=" * 80)
            
            # Sort alphabetically
            prime_sets.sort(key=lambda x: x.get('i18n', {}).get('en', {}).get('name', x.get('slug', '')))
            
            # Store detailed information for caching
            detailed_sets = []
            
            # Fetch details for each set with rate limiting
            for i, item in enumerate(prime_sets, 1):
                slug = item.get('slug', '')
                
                print(f"Fetching details for set {i}/{len(prime_sets)}: {slug}")
                
                set_details = fetch_set_details(slug, requests, rate_limiter)
                
                if set_details:
                    # Fetch part quantities and store complete information
                    parts_with_quantities = []
                    for part_code in set_details['setParts']:
                        # Fetch quantity information for each part
                        part_info = fetch_part_quantity(part_code, requests, rate_limiter)
                        parts_with_quantities.append(part_info)
                    
                    # Create complete set data for caching
                    complete_set_data = {
                        'id': set_details['id'],
                        'name': set_details['name'],
                        'slug': slug,  # Store original slug for pricing API
                        'setParts': parts_with_quantities
                    }
                    detailed_sets.append(complete_set_data)
                    
                    # Display set information
                    print(f"\n{i:2d}. {set_details['name']} [{set_details['id']}]")
                    
                    if parts_with_quantities:
                        print("    Parts:")
                        for part_info in parts_with_quantities:
                            print(f"      - {part_info['name']} [{part_info['code']}] (Quantity: {part_info['quantityInSet']})")
                    else:
                        print("    No individual parts found.")
                    
                    print()
                else:
                    # Fallback display if details couldn't be fetched
                    i18n = item.get('i18n', {})
                    en_info = i18n.get('en', {})
                    name = en_info.get('name', slug.replace('_', ' ').title())
                    fallback_data = {
                        'id': '',
                        'name': name,
                        'slug': slug,  # Store original slug even for fallback
                        'setParts': []
                    }
                    detailed_sets.append(fallback_data)
                    print(f"\n{i:2d}. {name} [Details unavailable]")
                    print()
            
            # Update cache with new data
            cache_data = {
                'prime_sets_hash': current_hash,
                'detailed_sets': detailed_sets,
                'last_updated': time.time()
            }
            save_cache(cache_data)
            
            print("=" * 80)
            print(f"Total Prime Sets processed: {len(detailed_sets)}")
            print("Note: Processing time will vary based on number of parts per set.")
            print("Each set requires 1 API call + 1 additional call per part (rate limited to 3 req/sec)")
            print("Data cached for future use - next run will be much faster if data unchanged!")
            
            # After caching, fetch pricing data using the fresh cache
            print("\n" + "=" * 80)
            print("FETCHING REAL-TIME PRICING DATA")
            print("=" * 80)
            
            # Fetch set lowest prices
            set_prices = fetch_set_lowest_prices(cache_data, requests, rate_limiter)
            
            # Fetch part lowest prices
            part_prices = fetch_part_lowest_prices(cache_data, requests, rate_limiter)
            
            # Display pricing summary
            display_pricing_summary(set_prices, part_prices)
            
        else:
            print(f"Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

def main():
    """Main function to handle script execution."""
    if len(sys.argv) > 1 and sys.argv[1] == "--venv-active":
        get_prime_sets()
    else:
        activate_venv_and_run()

if __name__ == "__main__":
    main()


