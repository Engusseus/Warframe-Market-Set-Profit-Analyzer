import os
import sys
import subprocess
import venv
import time
import hashlib
import json
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




