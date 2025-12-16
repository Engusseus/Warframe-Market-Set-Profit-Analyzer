import os
import sys
import subprocess
import venv
import time
import hashlib
import json
import statistics
from collections import deque
from database import get_database_instance

try:
    from rich.console import Console
    from rich.prompt import Prompt, FloatPrompt, Confirm
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.layout import Layout
    from rich.align import Align
    from rich.rule import Rule
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

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

def show_ascii_banner(console):
    """Display ASCII art banner for the application."""
    if not RICH_AVAILABLE:
        print("\n" + "="*80)
        print("    WARFRAME MARKET SET PROFIT ANALYZER")
        print("="*80)
        return
    
    banner_art = """
    =============================================================================
    
       W   W   AAA   RRRR  FFFFF RRRR   AAA   M   M EEEEE
       W   W  A   A  R   R F     R   R A   A  MM MM E
       W W W  AAAAA  RRRR  FFF   RRRR  AAAAA  M M M EEE
       W W W  A   A  R  R  F     R  R  A   A  M   M E
        W W   A   A  R   R F     R   R A   A  M   M EEEEE
       
                    MARKET SET PROFIT ANALYZER
                     
            Find the most profitable Prime sets to trade!
            
    =============================================================================
    """
    
    console.print(Panel(
        Align.center(Text(banner_art, style="bold cyan")),
        style="bold blue",
        padding=(0, 1)
    ))
    
    console.print("")
    console.print(Align.center("Real-time analysis of Warframe Market data", style="bold green"))
    console.print(Align.center("Profit margins * Trading volume * Smart scoring", style="dim"))
    console.print("")

def get_cli_weights(console, previous_weights=None):
    """Get user-defined weights for profit and volume factors using Rich CLI."""
    if not RICH_AVAILABLE:
        return get_user_weights()  # Fallback to original function
    
    console.print(Rule("SCORING WEIGHT CONFIGURATION", style="bold yellow"))
    console.print("")
    
    # Create an informative panel
    info_panel = Panel(
        "[bold]Configure Analysis Weights[/bold]\n\n"
        "• [cyan]Profit Weight[/cyan]: Emphasizes profit margins in scoring\n"
        "• [green]Volume Weight[/green]: Emphasizes trading activity/liquidity\n\n"
        "[dim]Tip: Higher weights = more importance in final ranking\n"
        "Set to 0 to ignore a factor completely[/dim]",
        title="Scoring System",
        border_style="blue"
    )
    console.print(info_panel)
    console.print("")
    
    # Show previous weights if available
    if previous_weights:
        console.print(f"Previous weights: Profit={previous_weights[0]:.1f}, Volume={previous_weights[1]:.1f}", style="dim")
        use_previous = Confirm.ask("Use previous weights?", default=True)
        if use_previous:
            return previous_weights
        console.print("")
    
    # Get new weights with validation
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        try:
            console.print("[bold cyan]Profit Weight[/bold cyan] (default: 1.0)")
            profit_weight = FloatPrompt.ask(
                "Enter weight", 
                default=1.0,
                show_default=True
            )
            
            console.print("[bold green]Volume Weight[/bold green] (default: 1.2)")
            volume_weight = FloatPrompt.ask(
                "Enter weight", 
                default=1.2,
                show_default=True
            )
            
            # Validate weights
            if profit_weight < 0 or volume_weight < 0:
                console.print("[red]Error: Weights cannot be negative![/red]")
                attempts += 1
                continue
                
            if profit_weight == 0 and volume_weight == 0:
                console.print("[red]Error: At least one weight must be greater than 0![/red]")
                attempts += 1
                continue
            
            # Show confirmation
            console.print("")
            console.print(f"Selected weights: [cyan]Profit={profit_weight:.1f}[/cyan], [green]Volume={volume_weight:.1f}[/green]")
            
            confirm = Confirm.ask("Confirm these weights?", default=True)
            if confirm:
                return profit_weight, volume_weight
            
            attempts += 1
            
        except (ValueError, KeyboardInterrupt):
            attempts += 1
            if attempts < max_attempts:
                console.print("[red]Invalid input. Please try again.[/red]")
            else:
                console.print("[yellow]Too many invalid attempts. Using defaults.[/yellow]")
                return 1.0, 1.2
    
    # Fallback to defaults
    console.print("[yellow]Using default weights: Profit=1.0, Volume=1.2[/yellow]")
    return 1.0, 1.2

def display_paginated_results(console, scored_data, items_per_page=20):
    """Display analysis results with pagination support."""
    if not RICH_AVAILABLE:
        return display_top_profitable_sets(scored_data)  # Fallback
    
    if not scored_data:
        console.print("[red]No data to display[/red]")
        return
    
    total_items = len(scored_data)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    current_page = 0
    
    while True:
        # Calculate page bounds
        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        page_data = scored_data[start_idx:end_idx]
        
        # Clear and show header
        console.clear()
        show_ascii_banner(console)
        
        # Page info
        console.print(f"[bold cyan]Analysis Results[/bold cyan] - Page {current_page + 1} of {total_pages}")
        console.print(f"Showing items {start_idx + 1}-{end_idx} of {total_items}")
        console.print("")
        
        # Create results table
        table = Table(
            title="Prime Set Profitability Analysis",
            show_header=True,
            header_style="bold magenta",
            border_style="blue"
        )
        
        table.add_column("Rank", justify="center", style="bold")
        table.add_column("Set Name", style="cyan", min_width=25)
        table.add_column("Profit", justify="right", style="green")
        table.add_column("Volume", justify="right", style="yellow")
        table.add_column("Score", justify="right", style="bold magenta")
        table.add_column("ROI%", justify="right", style="bold green")
        
        # Add rows
        for i, item in enumerate(page_data, start_idx + 1):
            set_name = item['set_name']
            if len(set_name) > 28:
                set_name = set_name[:25] + "..."
            
            profit = f"{item['profit_margin']:.0f} plat"
            volume = f"{item.get('volume', 0):,.0f}"
            score = f"{item['total_score']:.3f}"
            roi = f"{item['profit_percentage']:.1f}%"
            
            # Color coding based on rank
            if i <= 5:
                rank_style = "bold gold1"
            elif i <= 10:
                rank_style = "bold orange1"
            else:
                rank_style = "white"
                
            table.add_row(
                f"{i}", set_name, profit, volume, score, roi,
                style=rank_style if i <= 10 else None
            )
        
        console.print(table)
        console.print("")
        
        # Navigation controls
        nav_options = []
        if current_page > 0:
            nav_options.append("[b]← Previous")
        if current_page < total_pages - 1:
            nav_options.append("[n]→ Next")
        nav_options.append("[q]◄ Back to Menu")
        
        console.print("Navigation: " + " | ".join(nav_options))
        
        # Get user input
        choice = Prompt.ask(
            "Choose action",
            choices=["b", "n", "q"] if current_page < total_pages - 1 else (["b", "q"] if current_page > 0 else ["q"]),
            default="q"
        ).lower()
        
        if choice == "b" and current_page > 0:
            current_page -= 1
        elif choice == "n" and current_page < total_pages - 1:
            current_page += 1
        elif choice == "q":
            break

def show_post_analysis_menu(console):
    """Show post-analysis menu options."""
    if not RICH_AVAILABLE:
        return show_fallback_menu()  # Simple fallback
    
    console.print("")
    console.print(Rule("WHAT'S NEXT?", style="bold yellow"))
    
    menu_panel = Panel(
        "[1] [bold cyan]Run Analysis Again[/bold cyan]\n"
        "    Start fresh analysis with new or same weights\n\n"
        "[2] [bold green]Try Different Weights[/bold green]\n"
        "    Re-score current data with different weights\n\n" 
        "[3] [bold red]Quit Application[/bold red]\n"
        "    Exit the program",
        title="Menu Options",
        border_style="blue"
    )
    console.print(menu_panel)
    
    choice = Prompt.ask(
        "Select option",
        choices=["1", "2", "3"],
        default="3"
    )
    
    return int(choice)

def show_fallback_menu():
    """Fallback menu when Rich is not available."""
    print("\n" + "="*50)
    print("WHAT'S NEXT?")
    print("="*50)
    print("1. Run Analysis Again")
    print("2. Try Different Weights")
    print("3. Quit Application")
    print("="*50)
    
    while True:
        try:
            choice = input("Select option (1-3): ").strip()
            if choice in ["1", "2", "3"]:
                return int(choice)
            print("Invalid choice. Please enter 1, 2, or 3.")
        except (ValueError, KeyboardInterrupt):
            return 3

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

def fetch_set_volume(cached_data, requests_module, rate_limiter):
    """Fetch individual 48-hour volume for all Prime sets using cached data.
    
    Returns:
        dict: Dictionary mapping set_slug to volume data, or int for backward compatibility
    """
    if not cached_data or 'detailed_sets' not in cached_data:
        print("No cached set data available for volume calculation.")
        return {}
    
    detailed_sets = cached_data['detailed_sets']
    volume_data = {}
    total_volume = 0
    successful_fetches = 0
    
    print(f"\nFetching 48-hour volume data for {len(detailed_sets)} Prime Sets...")
    print("Rate limited to 3 requests per second for API safety.")
    print("=" * 60)
    
    for i, set_data in enumerate(detailed_sets, 1):
        set_name = set_data.get('name', 'Unknown Set')
        set_slug = set_data.get('slug', '')
        
        if not set_slug:
            print(f"Skipping {set_name} - No slug available")
            continue
        
        print(f"Fetching volume for set {i}/{len(detailed_sets)}: {set_name}")
        
        # Use v1 statistics endpoint (v2 doesn't support statistics data)
        url = f"https://api.warframe.market/v1/items/{set_slug}/statistics"
        
        # Use retry logic
        response = fetch_with_retry(url, requests_module, rate_limiter)
        
        if response is None:
            print(f"  → No volume data available")
            continue
        
        try:
            data = response.json()
        except Exception as e:
            print(f"  → Error parsing JSON response: {e}")
            continue
        
        # Validate response structure
        if not isinstance(data, dict) or 'payload' not in data:
            print(f"  → Unexpected response structure")
            continue
        
        payload = data.get("payload", {})
        if not isinstance(payload, dict):
            print(f"  → Invalid payload structure")
            continue
        
        statistics_closed = payload.get("statistics_closed", {})
        if not isinstance(statistics_closed, dict):
            print(f"  → No statistics_closed data")
            continue
        
        hours_48_data = statistics_closed.get("48hours", [])
        if not isinstance(hours_48_data, list):
            print(f"  → No 48hours data")
            continue
        
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
            successful_fetches += 1
            print(f"  → Volume: {set_volume} units")
        else:
            volume_data[set_slug] = 0
            print(f"  → No volume data found")
    
    print(f"\nVolume data fetched for {successful_fetches}/{len(detailed_sets)} sets")
    print(f"Total 48-hour volume: {total_volume} units")
    
    # Return both individual volumes and total for backward compatibility
    return {'individual': volume_data, 'total': total_volume}

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

def calculate_profit_margins(set_prices, part_prices, detailed_sets):
    """Calculate profit margins for each set by comparing set price to sum of part prices.
    
    Args:
        set_prices: List of set pricing data
        part_prices: List of part pricing data
        detailed_sets: List of detailed set information from cache
    
    Returns:
        List of profit analysis data for each viable set
    """
    profit_data = []
    
    if not set_prices or not part_prices or not detailed_sets:
        print("Warning: Missing required data for profit calculation")
        return profit_data
    
    # Create lookup dictionaries for faster access
    set_price_lookup = {item['slug']: item for item in set_prices}
    part_price_lookup = {item['slug']: item for item in part_prices}
    
    print(f"\nCalculating profit margins for {len(detailed_sets)} Prime Sets...")
    print("=" * 60)
    
    for set_data in detailed_sets:
        set_slug = set_data.get('slug', '')
        set_name = set_data.get('name', 'Unknown Set')
        
        if not set_slug or set_slug not in set_price_lookup:
            print(f"Skipping {set_name} - No pricing data available")
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
            print(f"Skipping {set_name} - Missing part pricing: {', '.join(missing_parts)}")
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
            
            print(f"{set_name}: {profit_margin:+.0f} plat ({profit_percentage:+.1f}%)")
        else:
            print(f"Skipping {set_name} - Zero part cost calculated")
    
    print(f"\nProfit analysis completed for {len(profit_data)} sets")
    return profit_data

def normalize_data(values, min_val=None, max_val=None):
    """Normalize a list of values to 0-1 range.
    
    Args:
        values: List of numeric values to normalize
        min_val: Optional minimum value override
        max_val: Optional maximum value override
    
    Returns:
        List of normalized values in range [0, 1]
    """
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

def get_user_weights():
    """Get user-defined weights for profit and volume factors.
    
    Returns:
        tuple: (profit_weight, volume_weight) as floats
    """
    print("\n" + "=" * 60)
    print("SCORING WEIGHT CONFIGURATION")
    print("=" * 60)
    print("Configure how much weight to give each factor in the final score:")
    print("• Profit Weight: How much to emphasize profit margins")
    print("• Volume Weight: How much to emphasize trading volume")
    print("\nDefault weights: Profit=1.0, Volume=1.2")
    print("Higher weights mean more importance in final ranking")
    print("Note: Set weight to 0 to ignore that factor completely")
    
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        try:
            print("\nWeight Selection:")
            print("1. Use default weights (Profit=1.0, Volume=1.2)")
            print("2. Custom weights")
            
            choice = input("\nEnter choice (1-2): ").strip()
            
            if choice == "1":
                print("Using default weights: Profit=1.0, Volume=1.2")
                return 1.0, 1.2
            elif choice == "2":
                profit_weight = float(input("Enter profit weight (0.0-10.0): "))
                volume_weight = float(input("Enter volume weight (0.0-10.0): "))
                
                if profit_weight < 0 or volume_weight < 0:
                    print("Error: Weights must be non-negative numbers")
                    attempts += 1
                    continue
                
                if profit_weight > 10 or volume_weight > 10:
                    print("Warning: Very high weights (>10) may skew results")
                    confirm = input("Continue anyway? (y/N): ").strip().lower()
                    if confirm != 'y':
                        attempts += 1
                        continue
                
                print(f"Using custom weights: Profit={profit_weight}, Volume={volume_weight}")
                return profit_weight, volume_weight
            else:
                print("Invalid choice. Please enter 1 or 2.")
                attempts += 1
                continue
                
        except (ValueError, EOFError, KeyboardInterrupt):
            attempts += 1
            if attempts < max_attempts:
                print(f"Invalid input. Please try again. ({max_attempts - attempts} attempts remaining)")
            else:
                print("Too many invalid attempts. Using default weights.")
                return 1.0, 1.2
    
    print("Maximum attempts reached. Using default weights.")
    return 1.0, 1.2

def calculate_profitability_scores(profit_data, volume_data, profit_weight=1.0, volume_weight=1.2):
    """Calculate profitability scores combining profit and volume data.
    
    Args:
        profit_data: List of profit analysis results
        volume_data: Dict with 'individual' and 'total' keys, or legacy format
        profit_weight: Weight for profit factor (default: 1.0)
        volume_weight: Weight for volume factor (default: 1.2)
    
    Returns:
        List of scored data sorted by total score (descending)
    """
    if not profit_data:
        print("No profit data available for scoring")
        return []
    
    # Handle different volume data formats
    volume_lookup = {}
    
    if isinstance(volume_data, dict) and 'individual' in volume_data:
        # New format with individual volumes
        volume_lookup = volume_data['individual'].copy()
    elif isinstance(volume_data, (int, float)):
        # Legacy format - total volume only
        print("Warning: Using total volume only. Individual set volumes not available.")
        print("Volume scores will be equal for all sets.")
        # Set all volumes to 1 so they don't affect relative scoring
        for item in profit_data:
            volume_lookup[item['set_slug']] = 1
    else:
        # Handle other legacy formats
        if isinstance(volume_data, list):
            for item in volume_data:
                if isinstance(item, dict) and 'set_slug' in item:
                    volume_lookup[item['set_slug']] = item.get('volume', 0)
        else:
            print("Warning: Unrecognized volume data format. Using equal volumes.")
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
        
        scored_data.append({
            **profit_item,
            'volume': volume_values[i],
            'normalized_profit': normalized_profits[i],
            'normalized_volume': normalized_volumes[i],
            'profit_score': profit_score,
            'volume_score': volume_score,
            'total_score': total_score
        })
    
    # Sort by total score (descending)
    scored_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    return scored_data

def display_top_profitable_sets(scored_data, top_n=10, detailed_n=5):
    """Display the top N most profitable sets with detailed analysis.
    
    Args:
        scored_data: List of scored profit data
        top_n: Number of sets to show in summary table (default: 10)
        detailed_n: Number of sets to show detailed breakdown (default: 5)
    """
    if not scored_data:
        print("No scoring data available")
        return
    
    actual_top_n = min(top_n, len(scored_data))
    actual_detailed_n = min(detailed_n, len(scored_data))
    
    print("\n" + "=" * 100)
    print(f"TOP {actual_top_n} MOST PROFITABLE PRIME SETS")
    print("=" * 100)
    
    print(f"{'Rank':<4} {'Set Name':<30} {'Profit':<8} {'Volume':<8} {'Score':<8} {'ROI%':<8} {'Details'}")
    print("-" * 100)
    
    for i, item in enumerate(scored_data[:top_n], 1):
        set_name = item['set_name']
        profit = item['profit_margin']
        volume = item.get('volume', 0)  # Handle missing volume gracefully
        score = item['total_score']
        roi = item['profit_percentage']
        
        # Better name truncation that preserves readability
        if len(set_name) > 28:
            display_name = set_name[:25] + "..."
        else:
            display_name = set_name
        
        # Handle volume display for different scales
        if volume >= 1000:
            volume_str = f"{volume:>6,.0f}k".replace(",", ".")
        else:
            volume_str = f"{volume:>7,.0f}"
        
        print(f"{i:<4} {display_name:<30} {profit:>+7.0f} {volume_str:<8} {score:>7.2f} {roi:>+6.1f}% {'View below' if i <= detailed_n else ''}")
    
    # Display detailed breakdowns
    print("\n" + "=" * 100)
    print(f"DETAILED BREAKDOWN (TOP {actual_detailed_n})")
    print("=" * 100)
    
    for i, item in enumerate(scored_data[:actual_detailed_n], 1):
        print(f"\n{i}. {item['set_name']}")
        print("-" * 60)
        print(f"Set Price: {item['set_price']:.0f} platinum")
        print(f"Part Cost: {item['part_cost']:.0f} platinum")
        print(f"Profit Margin: {item['profit_margin']:+.0f} platinum ({item['profit_percentage']:+.1f}% ROI)")
        volume = item.get('volume', 0)
        if volume > 0:
            print(f"Trading Volume: {volume:,.0f} units (48h)")
        else:
            print("Trading Volume: No data available")
        print(f"Total Score: {item['total_score']:.2f} (Profit: {item['profit_score']:.2f}, Volume: {item['volume_score']:.2f})")
        
        print("\nPart Breakdown:")
        for part in item['part_details']:
            print(f"  • {part['name']}: {part['unit_price']:.0f} × {part['quantity']} = {part['total_cost']:.0f} plat")
    
    print("\n" + "=" * 100)
    print("ANALYSIS NOTES:")
    print("• Profit = Set Price - Total Part Cost")
    print("• ROI% = (Profit / Part Cost) × 100")
    print("• Score combines normalized profit and volume with user-defined weights")
    print("• Higher scores indicate better profit opportunities")
    print("• Volume data helps identify active vs. stagnant markets")
    print("=" * 100)

def display_pricing_summary(set_prices, part_prices, *, total_volume=0):
    """Display a comprehensive pricing summary with volume data."""
    print("\n" + "=" * 80)
    print("PRICING & VOLUME SUMMARY")
    print("=" * 80)
    
    # Display volume data first
    if total_volume > 0:
        print(f"\nTOTAL 48-HOUR TRADING VOLUME")
        print("-" * 60)
        print(f"Combined volume for all Prime Sets: {total_volume:,} units traded")
        print("Note: Volume data from past 48 hours, updated every few hours by Warframe Market")
    else:
        print(f"\nTOTAL 48-HOUR TRADING VOLUME")
        print("-" * 60)
        print("No volume data available")
    
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

def _initialize_analysis_dependencies():
    """Initialize dependencies for analysis."""
    try:
        import requests
        return requests, RateLimiter(max_requests=3, time_window=1.0)
    except ImportError:
        raise ImportError("requests module not found. Virtual environment setup may have failed.")

def _show_status_message(console, message):
    """Display status message to user."""
    if console and RICH_AVAILABLE:
        console.print(f"[bold cyan]{message}[/bold cyan]")
    else:
        print(message)

def _fetch_prime_sets_list(requests_module):
    """Fetch the list of prime sets from API."""
    url = "https://api.warframe.market/v2/items"
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

def _process_cached_data(cache, prime_sets, requests_module, rate_limiter, console, user_weights):
    """Process cached data if available and unchanged."""
    current_hash = calculate_hash(prime_sets)
    cached_hash = cache.get('prime_sets_hash', '')
    
    if current_hash != cached_hash or 'detailed_sets' not in cache:
        return None  # Need fresh data
    
    _show_status_message(console, "Data unchanged since last fetch. Using cached data...")
    _display_cached_sets(cache['detailed_sets'])
    
    # Fetch current pricing and analyze
    return _perform_analysis_with_data(cache, requests_module, rate_limiter, console, user_weights)

def _display_cached_sets(detailed_sets):
    """Display cached sets information."""
    print(f"\nUsing cached data for {len(detailed_sets)} Prime Sets.\n")
    print("=" * 80)
    
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

def _perform_analysis_with_data(cache, requests_module, rate_limiter, console, user_weights):
    """Perform analysis with cached or fresh data."""
    print("\n" + "=" * 80)
    print("FETCHING REAL-TIME PRICING DATA")
    print("=" * 80)
    
    # Fetch pricing data
    set_prices = fetch_set_lowest_prices(cache, requests_module, rate_limiter)
    part_prices = fetch_part_lowest_prices(cache, requests_module, rate_limiter)
    volume_result = fetch_set_volume(cache, requests_module, rate_limiter)
    
    total_volume = volume_result.get('total', 0) if isinstance(volume_result, dict) else volume_result
    display_pricing_summary(set_prices, part_prices, total_volume=total_volume)
    
    print("\n" + "=" * 80)
    print("PROFITABILITY ANALYSIS")
    print("=" * 80)
    
    detailed_sets = cache['detailed_sets']
    profit_data = calculate_profit_margins(set_prices, part_prices, detailed_sets)
    
    if not profit_data:
        if console and RICH_AVAILABLE:
            console.print("[red]No profitable sets found for analysis.[/red]")
        else:
            print("No profitable sets found for analysis.")
        return None, user_weights
    
    # Get weights if not provided
    if user_weights:
        profit_weight, volume_weight = user_weights
    else:
        if console and RICH_AVAILABLE:
            profit_weight, volume_weight = get_cli_weights(console)
        else:
            profit_weight, volume_weight = get_user_weights()
    
    # Calculate and return results
    scored_data = calculate_profitability_scores(profit_data, volume_result, profit_weight, volume_weight)
    
    # Save to database (transaction-safe - only saves if complete)
    try:
        if profit_data and set_prices:
            db = get_database_instance()
            run_id = db.save_market_run(profit_data, set_prices)
            
            if console and RICH_AVAILABLE:
                console.print(f"[dim]Market run saved to database (ID: {run_id})[/dim]")
            else:
                print(f"Market run saved to database (ID: {run_id})")
        else:
            if console and RICH_AVAILABLE:
                console.print("[yellow]Warning: No data available to save to database[/yellow]")
            else:
                print("Warning: No data available to save to database")
    except ValueError as e:
        # Input validation errors
        if console and RICH_AVAILABLE:
            console.print(f"[yellow]Warning: Invalid data format for database: {e}[/yellow]")
        else:
            print(f"Warning: Invalid data format for database: {e}")
    except Exception as e:
        # Database operation errors
        if console and RICH_AVAILABLE:
            console.print(f"[red]Error: Could not save to database: {e}[/red]")
        else:
            print(f"Error: Could not save to database: {e}")
    
    return scored_data, (profit_weight, volume_weight)

def run_analysis(console=None, user_weights=None):
    """Run the core analysis logic."""
    try:
        requests_module, rate_limiter = _initialize_analysis_dependencies()
        cache = load_cache()
        
        _show_status_message(console, "Fetching Prime sets from Warframe Market API...")
        prime_sets = _fetch_prime_sets_list(requests_module)
        
        # Try to use cached data first
        result = _process_cached_data(cache, prime_sets, requests_module, rate_limiter, console, user_weights)
        if result:
            return result
        
        # Need fresh data - continue with original logic for now
        return _fetch_fresh_data_and_analyze(prime_sets, cache, requests_module, rate_limiter, console, user_weights)
        
    except Exception as e:
        if console and RICH_AVAILABLE:
            console.print(f"[red]Error: {e}[/red]")
        else:
            print(f"Error: {e}")
        return None, user_weights

def _fetch_fresh_data_and_analyze(prime_sets, cache, requests_module, rate_limiter, console, user_weights):
    """Fetch fresh data when cache is outdated."""
    print(f"\nData changed or cache missing. Fetching detailed information for {len(prime_sets)} Prime Sets...\n")
    print("Rate limited to 3 requests per second for API safety.")
    print("=" * 80)
    
    # Sort alphabetically
    prime_sets.sort(key=lambda x: x.get('i18n', {}).get('en', {}).get('name', x.get('slug', '')))
    
    # Fetch detailed set information
    detailed_sets = []
    for i, item in enumerate(prime_sets, 1):
        slug = item.get('slug', '')
        print(f"Fetching details for set {i}/{len(prime_sets)}: {slug}")
        
        set_details = fetch_set_details(slug, requests_module, rate_limiter)
        
        if set_details:
            # Fetch part quantities and store complete information
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
            
            print(f"\n{i:2d}. {set_details['name']} [{set_details['id']}]")
            if parts_with_quantities:
                print("    Parts:")
                for part_info in parts_with_quantities:
                    print(f"      - {part_info['name']} [{part_info['code']}] (Quantity: {part_info['quantityInSet']})")
            else:
                print("    No individual parts found.")
            print()
        else:
            # Fallback for unavailable details
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
            print(f"\n{i:2d}. {name} [Details unavailable]")
            print()
    
    # Update cache
    current_hash = calculate_hash(prime_sets)
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
    
    # Perform analysis with fresh data
    return _perform_analysis_with_data(cache_data, requests_module, rate_limiter, console, user_weights)

def get_prime_sets():
    """Legacy wrapper function for backwards compatibility."""
    console = Console() if RICH_AVAILABLE else None
    main_cli_loop(console)

def main_cli_loop(console=None):
    """Main CLI loop with menu system."""
    if console and RICH_AVAILABLE:
        console.clear()
        show_ascii_banner(console)
    
    current_data = None
    current_weights = None
    
    while True:
        try:
            # Show startup menu first
            if current_data is None:
                if console and RICH_AVAILABLE:
                    startup_choice = show_startup_menu(console)
                else:
                    startup_choice = show_fallback_startup_menu()
                
                if startup_choice == 1:  # Start Analysis
                    if console and RICH_AVAILABLE:
                        console.clear()
                        show_ascii_banner(console)
                        console.print("[bold yellow]Starting Market Analysis...[/bold yellow]")
                        console.print("")
                        current_weights = get_cli_weights(console, current_weights)
                        
                        console.print("")
                        console.print("[bold green]Running analysis...[/bold green]")
                        console.print("")
                        
                        # Run analysis with selected weights
                        current_data, current_weights = run_analysis(console, current_weights)
                        
                        if current_data:
                            # Display results with pagination
                            display_paginated_results(console, current_data)
                            
                            # Show post-analysis menu
                            choice = show_post_analysis_menu(console)
                        else:
                            console.print("[red]Analysis failed or no data available.[/red]")
                            choice = 3  # Quit
                    else:
                        # Fallback for when Rich is not available
                        print("\nStarting Market Analysis...")
                        print("="*50)
                        current_weights = get_user_weights() if not current_weights else current_weights
                        current_data, current_weights = run_analysis(None, current_weights)
                        
                        if current_data:
                            display_top_profitable_sets(current_data)
                            choice = show_fallback_menu()
                        else:
                            print("Analysis failed or no data available.")
                            choice = 3
                elif startup_choice == 2:  # Export JSON
                    handle_json_export(console)
                    if console and RICH_AVAILABLE:
                        console.print("\n[dim]Press Enter to continue...[/dim]")
                        console.input()
                    else:
                        input("\nPress Enter to continue...")
                    continue  # Go back to startup menu
                elif startup_choice == 3:  # Exit
                    break
            else:
                # Show post-analysis menu for subsequent runs
                if console and RICH_AVAILABLE:
                    choice = show_post_analysis_menu(console)
                else:
                    choice = show_fallback_menu()
            
            # Handle menu choice
            if choice == 1:  # Run analysis again
                if console and RICH_AVAILABLE:
                    console.clear()
                    show_ascii_banner(console)
                    console.print("[bold cyan]Running fresh analysis...[/bold cyan]")
                    console.print("")
                    
                    # Get weights (with option to use previous)
                    current_weights = get_cli_weights(console, current_weights)
                    
                    # Run analysis
                    current_data, current_weights = run_analysis(console, current_weights)
                    
                    if current_data:
                        display_paginated_results(console, current_data)
                    else:
                        console.print("[red]Analysis failed.[/red]")
                else:
                    print("\nRunning fresh analysis...")
                    current_weights = get_user_weights()
                    current_data, current_weights = run_analysis(None, current_weights)
                    if current_data:
                        display_top_profitable_sets(current_data)
                    
            elif choice == 2:  # Try different weights
                if current_data:
                    if console and RICH_AVAILABLE:
                        console.clear()
                        show_ascii_banner(console)
                        console.print("[bold green]Trying different weights with current data...[/bold green]")
                        console.print("")
                        
                        # Get new weights
                        new_weights = get_cli_weights(console, current_weights)
                        
                        # Re-calculate scores with new weights (need to implement this)
                        rescored_data = recalculate_scores_with_new_weights(current_data, new_weights, current_weights)
                        current_weights = new_weights
                        current_data = rescored_data
                        
                        display_paginated_results(console, current_data)
                    else:
                        print("\nTrying different weights...")
                        new_weights = get_user_weights()
                        rescored_data = recalculate_scores_with_new_weights(current_data, new_weights, current_weights)
                        current_weights = new_weights
                        current_data = rescored_data
                        display_top_profitable_sets(current_data)
                else:
                    if console and RICH_AVAILABLE:
                        console.print("[yellow]No current data available. Please run analysis first.[/yellow]")
                    else:
                        print("No current data available. Please run analysis first.")
                        
            elif choice == 3:  # Quit
                if console and RICH_AVAILABLE:
                    console.print("")
                    console.print("[bold cyan]Thanks for using Warframe Market Set Profit Analyzer![/bold cyan]")
                    console.print("[dim]Happy trading, Tenno![/dim]")
                else:
                    print("\nThanks for using Warframe Market Set Profit Analyzer!")
                    print("Happy trading, Tenno!")
                break
                
        except KeyboardInterrupt:
            if console and RICH_AVAILABLE:
                console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            else:
                print("\nOperation cancelled by user.")
            break
        except Exception as e:
            if console and RICH_AVAILABLE:
                console.print(f"[red]Unexpected error: {e}[/red]")
            else:
                print(f"Unexpected error: {e}")
            break

def recalculate_scores_with_new_weights(scored_data, new_weights, old_weights):
    """Recalculate profitability scores with new weights."""
    if not scored_data:
        return scored_data
    
    new_profit_weight, new_volume_weight = new_weights
    old_profit_weight, old_volume_weight = old_weights
    
    # Create new scored data list
    rescored_data = []
    
    for item in scored_data:
        # Extract normalized values (reverse engineer from old score)
        old_total_score = item['total_score']
        
        # For simplicity, we'll extract the raw profit and volume values
        # and renormalize everything (this is more accurate than trying to reverse-engineer)
        rescored_data.append(item.copy())
    
    # Extract all profit margins and volumes for renormalization
    profit_margins = [item['profit_margin'] for item in rescored_data]
    volumes = [item.get('volume', 0) for item in rescored_data]
    
    # Normalize values
    normalized_profits = normalize_data(profit_margins)
    normalized_volumes = normalize_data(volumes)
    
    # Recalculate scores with new weights
    for i, item in enumerate(rescored_data):
        normalized_profit = normalized_profits[i] if normalized_profits else 0
        normalized_volume = normalized_volumes[i] if normalized_volumes else 0
        
        # Calculate new weighted score
        profit_score = normalized_profit * new_profit_weight
        volume_score = normalized_volume * new_volume_weight
        total_score = profit_score + volume_score

        item['normalized_profit'] = normalized_profit
        item['normalized_volume'] = normalized_volume
        item['profit_score'] = profit_score
        item['volume_score'] = volume_score
        item['total_score'] = total_score
    
    # Re-sort by new scores
    rescored_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    return rescored_data

def show_startup_menu(console):
    """Show startup menu with export option."""
    if not RICH_AVAILABLE:
        return show_fallback_startup_menu()
    
    console.print(Rule("WELCOME TO WARFRAME MARKET ANALYZER", style="bold yellow"))
    console.print("")
    
    # Show database stats if available
    try:
        db = get_database_instance()
        stats = db.get_database_stats()
        
        if stats['total_runs'] > 0:
            info_panel = Panel(
                f"[cyan]Database Stats:[/cyan]\n"
                f"• Total Runs: {stats['total_runs']}\n"
                f"• Total Records: {stats['total_profit_records']}\n"
                f"• Last Run: {stats.get('last_run', 'Unknown')}\n"
                f"• Database Size: {stats['database_size_bytes'] / 1024:.1f} KB",
                title="Historical Data Available",
                border_style="blue"
            )
            console.print(info_panel)
            console.print("")
    except Exception:
        pass
    
    menu_panel = Panel(
        "[1] [bold green]Start Market Analysis[/bold green]\n"
        "    Analyze current market data and save to database\n\n"
        "[2] [bold cyan]Export Database to JSON[/bold cyan]\n"
        "    Export all historical data for analysis\n\n"
        "[3] [bold red]Exit Application[/bold red]\n"
        "    Exit the program",
        title="Main Menu",
        border_style="blue"
    )
    console.print(menu_panel)
    
    choice = Prompt.ask(
        "Select option",
        choices=["1", "2", "3"],
        default="1"
    )
    
    return int(choice)

def show_fallback_startup_menu():
    """Fallback startup menu when Rich is not available."""
    print("\n" + "="*60)
    print("WARFRAME MARKET SET PROFIT ANALYZER")
    print("="*60)
    print("1. Start Market Analysis")
    print("2. Export Database to JSON")
    print("3. Exit Application")
    print("="*60)
    
    while True:
        try:
            choice = input("Select option (1-3): ").strip()
            if choice in ["1", "2", "3"]:
                return int(choice)
            print("Invalid choice. Please enter 1, 2, or 3.")
        except (ValueError, KeyboardInterrupt):
            return 3

def handle_json_export(console):
    """Handle JSON export functionality."""
    try:
        db = get_database_instance()
        stats = db.get_database_stats()
        
        if stats['total_runs'] == 0:
            if console and RICH_AVAILABLE:
                console.print("[yellow]No market data available to export. Run an analysis first.[/yellow]")
            else:
                print("No market data available to export. Run an analysis first.")
            return
        
        if console and RICH_AVAILABLE:
            console.print(f"[cyan]Exporting {stats['total_runs']} market runs with {stats['total_profit_records']} profit records...[/cyan]")
        else:
            print(f"Exporting {stats['total_runs']} market runs with {stats['total_profit_records']} profit records...")
        
        output_path = db.save_json_export()
        
        # Verify export was successful
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Export file was not created at {output_path}")
        
        file_size_kb = os.path.getsize(output_path) / 1024
        
        if console and RICH_AVAILABLE:
            console.print(f"[bold green]Export completed successfully![/bold green]")
            console.print(f"[dim]File saved to: {output_path}[/dim]")
            console.print(f"[dim]File size: {file_size_kb:.1f} KB[/dim]")
        else:
            print(f"Export completed successfully!")
            print(f"File saved to: {output_path}")
            print(f"File size: {file_size_kb:.1f} KB")
            
    except PermissionError as e:
        if console and RICH_AVAILABLE:
            console.print(f"[red]Export failed: Permission denied. Check file permissions.[/red]")
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            print(f"Export failed: Permission denied. Check file permissions.")
            print(f"Details: {e}")
    except OSError as e:
        if console and RICH_AVAILABLE:
            console.print(f"[red]Export failed: File system error.[/red]")
            console.print(f"[dim]Details: {e}[/dim]")
        else:
            print(f"Export failed: File system error.")
            print(f"Details: {e}")
    except Exception as e:
        if console and RICH_AVAILABLE:
            console.print(f"[red]Export failed: {e}[/red]")
        else:
            print(f"Export failed: {e}")

def main():
    """Main function to handle script execution."""
    if len(sys.argv) > 1 and sys.argv[1] == "--venv-active":
        console = Console() if RICH_AVAILABLE else None
        main_cli_loop(console)
    else:
        activate_venv_and_run()

if __name__ == "__main__":
    main()


