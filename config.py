"""Configuration settings for Warframe Market Analyzer"""

# API Settings
API_BASE_URL = 'https://api.warframe.market/v1'  # Base URL must include /v1
REQUESTS_PER_SECOND = 3  # Slower default to comply with API ToS; exponential backoff still handles 429/5xx
USER_AGENT = (
    "Warframe-Market-Set-Profit-Analyzer/1.0 "
    "(github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer; "
    "testing; high-rate requests will be stopped ASAP)"
)
HEADERS = {
    'Platform': 'pc',
    'Language': 'en',
    'Accept': 'application/json',
    'User-Agent': USER_AGENT,
}

# Output Settings
OUTPUT_FILE = 'set_profit_analysis.csv'
# Choose 'csv' or 'xlsx'
OUTPUT_FORMAT = 'csv'  # 'csv' or 'xlsx'
DEBUG_MODE = True  # Enable detailed logging

# Scoring Settings
PROFIT_WEIGHT = 1.0
VOLUME_WEIGHT = 1.2
PROFIT_MARGIN_WEIGHT = 0.0  # Set >0 to factor profit margin into scores

# Get average/median prices from this many orders
PRICE_SAMPLE_SIZE = 2
# Use median pricing instead of averaging when calculating prices
USE_MEDIAN_PRICING = False  # Deprecated in UI

# Always use aggregated statistics endpoint for pricing instead of raw orders (faster, smaller payloads)
USE_STATISTICS_FOR_PRICING = True


# Directory where cached API responses are stored
CACHE_DIR = 'data'
# Number of days to keep cached API responses
CACHE_TTL_DAYS = 7


# Persistent storage (single-file SQLite database)
DB_PATH = 'data/market_history.sqlite'
