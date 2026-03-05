"""Default configuration for the Warframe Market CLI analyzer."""

API_BASE_URL = "https://api.warframe.market"
API_V1_URL = f"{API_BASE_URL}/v1"
API_V2_URL = f"{API_BASE_URL}/v2"

HEADERS = {
    "Platform": "pc",
    "Language": "en",
    "Crossplay": "true",
    "Accept": "application/json",
}

REQUESTS_PER_SECOND = 3.0
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 3

DEFAULT_OUTPUT_DIR = "runs"
DEFAULT_OUTPUT_PREFIX = "set_profit_analysis"
LOG_FILE = "wf_market_analyzer.log"

DEBUG_MODE = False
PROFIT_WEIGHT = 1.0
VOLUME_WEIGHT = 1.2
PRICE_SAMPLE_SIZE = 2
