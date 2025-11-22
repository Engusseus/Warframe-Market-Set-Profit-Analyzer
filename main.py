import os
import sys
import subprocess
import venv
import time
import json
from database import get_database_instance
import market_analyzer as logic

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
    print("Note: Set weight to 0 to ignore a factor completely")
    
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

def _initialize_analysis_dependencies():
    """Initialize dependencies for analysis."""
    try:
        import requests
        return requests, logic.RateLimiter(max_requests=3, time_window=1.0)
    except ImportError:
        raise ImportError("requests module not found. Virtual environment setup may have failed.")

def _show_status_message(console, message):
    """Display status message to user."""
    if console and RICH_AVAILABLE:
        console.print(f"[bold cyan]{message}[/bold cyan]")
    else:
        print(message)

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
    
    def console_progress(i, total, msg):
        if i % 5 == 0 or i == total:
             print(f"{msg} ({i}/{total})")

    # Fetch pricing data
    set_prices = logic.fetch_set_lowest_prices(cache, requests_module, rate_limiter, console_progress)
    part_prices = logic.fetch_part_lowest_prices(cache, requests_module, rate_limiter, console_progress)
    volume_result = logic.fetch_set_volume(cache, requests_module, rate_limiter, console_progress)
    
    total_volume = volume_result.get('total', 0) if isinstance(volume_result, dict) else volume_result
    display_pricing_summary(set_prices, part_prices, total_volume=total_volume)
    
    print("\n" + "=" * 80)
    print("PROFITABILITY ANALYSIS")
    print("=" * 80)
    
    detailed_sets = cache['detailed_sets']
    profit_data = logic.calculate_profit_margins(set_prices, part_prices, detailed_sets)
    
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
    scored_data = logic.calculate_profitability_scores(profit_data, volume_result, profit_weight, volume_weight)
    
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
        cache = logic.load_cache()
        
        _show_status_message(console, "Fetching Prime sets from Warframe Market API...")
        prime_sets = logic.fetch_prime_sets_list(requests_module)
        
        # Try to use cached data first
        current_hash = logic.calculate_hash(prime_sets)
        cached_hash = cache.get('prime_sets_hash', '')

        if current_hash == cached_hash and 'detailed_sets' in cache:
             _show_status_message(console, "Data unchanged since last fetch. Using cached data...")
             _display_cached_sets(cache['detailed_sets'])
             return _perform_analysis_with_data(cache, requests_module, rate_limiter, console, user_weights)

        # Need fresh data
        print(f"\nData changed or cache missing. Fetching detailed information for {len(prime_sets)} Prime Sets...\n")

        def console_progress(i, total, msg):
            print(f"{msg} ({i}/{total})")

        cache = logic.refresh_cache_data(requests_module, rate_limiter, console_progress)

        print("=" * 80)
        print(f"Total Prime Sets processed: {len(cache['detailed_sets'])}")
        
        return _perform_analysis_with_data(cache, requests_module, rate_limiter, console, user_weights)
        
    except Exception as e:
        if console and RICH_AVAILABLE:
            console.print(f"[red]Error: {e}[/red]")
        else:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        return None, user_weights

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
                        
                        # Re-calculate scores with new weights
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
                import traceback
                traceback.print_exc()
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
        rescored_data.append(item.copy())
    
    # Extract all profit margins and volumes for renormalization
    profit_margins = [item['profit_margin'] for item in rescored_data]
    volumes = [item.get('volume', 0) for item in rescored_data]
    
    # Normalize values
    normalized_profits = logic.normalize_data(profit_margins)
    normalized_volumes = logic.normalize_data(volumes)
    
    # Recalculate scores with new weights
    for i, item in enumerate(rescored_data):
        normalized_profit = normalized_profits[i] if normalized_profits else 0
        normalized_volume = normalized_volumes[i] if normalized_volumes else 0
        
        # Calculate new weighted score
        total_score = (normalized_profit * new_profit_weight) + (normalized_volume * new_volume_weight)
        item['total_score'] = total_score
        item['profit_score'] = normalized_profit * new_profit_weight
        item['volume_score'] = normalized_volume * new_volume_weight
        item['normalized_profit'] = normalized_profit
        item['normalized_volume'] = normalized_volume
    
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
