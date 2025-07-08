"""
Configuration settings for Warframe Market Analyzer
"""

# API Settings
API_BASE_URL = 'https://api.warframe.market'
REQUESTS_PER_SECOND = 2  # Rate limit to avoid API throttling
HEADERS = {
    'Platform': 'pc',
    'Language': 'en',
    'Accept': 'application/json',
    'Crossplay': 'true'  # Enable crossplay to get all relevant orders
}

# Output Settings
OUTPUT_FILE = 'set_profit_analysis.csv'
DEBUG_MODE = True  # Enable detailed logging

# Scoring Settings
PROFIT_WEIGHT = 1.0
VOLUME_WEIGHT = 1.2

# Get average/median prices from this many orders
PRICE_SAMPLE_SIZE = 2

# Use median pricing instead of averaging when calculating prices
USE_MEDIAN_PRICING = False
