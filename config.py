"""Default configuration for the Warframe Market CLI analyzer."""

APP_NAME = "Warframe Market Set Profit Analyzer"
APP_VERSION = "0.5.0"
ENV_PREFIX = "WF_MARKET_ANALYZER"
PROJECT_URL = "https://github.com/Engusseus/Warframe-Market-Set-Profit-Analyzer"
USER_AGENT = f"wf-market-analyzer/{APP_VERSION} (+{PROJECT_URL})"

API_BASE_URL = "https://api.warframe.market"
API_V1_URL = f"{API_BASE_URL}/v1"
API_V2_URL = f"{API_BASE_URL}/v2"

DEFAULT_PLATFORM = "pc"
DEFAULT_LANGUAGE = "en"
DEFAULT_CROSSPLAY = True

REQUESTS_PER_SECOND = 3.0
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 3

DEFAULT_OUTPUT_DIR = "runs"
DEFAULT_OUTPUT_PREFIX = "set_profit_analysis"

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FILE = None
LOG_MAX_BYTES = 1_048_576
LOG_BACKUP_COUNT = 3

DEBUG_MODE = False
JSON_SUMMARY = False
ALLOW_THIN_ORDERBOOKS = False
PROFIT_WEIGHT = 1.0
VOLUME_WEIGHT = 1.2
PRICE_SAMPLE_SIZE = 2
