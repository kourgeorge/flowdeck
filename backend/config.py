"""Configuration for stock dashboard backend."""

import os

# Default list of major stocks to show on homepage
MAJOR_TICKERS = [
    "AAPL",  # Apple
    "MSFT",  # Microsoft
    "GOOGL", # Alphabet (Google)
    "AMZN",  # Amazon
    "NVDA",  # NVIDIA
    "META",  # Meta
    "TSLA",  # Tesla
]

# Results directory path (in repo root; relative to backend or absolute)
RESULTS_DIR = "results"

# Market data cache TTL in seconds (legacy, used as fallback)
MARKET_DATA_CACHE_TTL = 60  # 1 minute

# Data cache layer (avoids repeated third-party fetches)
DATA_CACHE_ENABLED = True
DATA_CACHE_MAX_SIZE = 10000
# Default: same directory as system DB (backend/flowdeck.db)
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_CACHE_PATH = os.environ.get("DATA_CACHE_PATH", "").strip() or os.path.join(_BACKEND_DIR, "data_cache.sqlite")

# Per-type TTL in seconds
DATA_CACHE_TTL_QUOTE = 300             # 5min
DATA_CACHE_TTL_COMPANY = 86400         # 24h
DATA_CACHE_TTL_EXTENDED = 3600         # 1h
DATA_CACHE_TTL_FUNDAMENTALS = 86400    # 24h
DATA_CACHE_TTL_FUND_INFO = 86400       # 24h (ETF/fund data)
DATA_CACHE_TTL_FINANCIAL_STATEMENTS = 86400  # 24h
DATA_CACHE_TTL_FINANCIAL_CHARTS = 86400      # 24h
DATA_CACHE_TTL_HISTORICAL = 900        # 15min
DATA_CACHE_TTL_STOCK_DATA = 900        # 15min
DATA_CACHE_TTL_ANALYST = 3600          # 1h
DATA_CACHE_TTL_NEWS = 900              # 15min
DATA_CACHE_TTL_SIMILAR_TICKERS = 86400  # 24h (sector/industry rarely changes)
DATA_CACHE_TTL_INSIDER_TRANSACTIONS = 900  # 15min
DATA_CACHE_TTL_MARKET_MOVERS = 600     # 10min (daily gainers/losers; reduces load on refresh)
DATA_CACHE_TTL_MARKET_OVERVIEW = 600   # 10min (indices, sectors, regions; Overview & Regional Map)
DATA_CACHE_TTL_INDICATORS = 900        # 15min (technical indicators)
DATA_CACHE_TTL_VENDOR_OHLCV = 86400    # 24h (raw Yahoo OHLCV for indicators)
DATA_CACHE_TTL_GLOBAL_NEWS = 900       # 15min (global/macro news)
DATA_CACHE_TTL_INSIDER_SENTIMENT = 900  # 15min (insider sentiment)
PROCESSING_CACHE_TTL_TICKER_EVENTS = 900  # 15min (derived ticker event snapshots)

# CORS: comma-separated origins (e.g. "https://app.example.com,https://example.com")
# If empty, defaults to common local dev origins for backwards compatibility
CORS_ORIGINS_ENV = os.environ.get("CORS_ORIGINS", "").strip()
CORS_ORIGINS = (
    [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()]
    if CORS_ORIGINS_ENV
    else [
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
)

# Backend base URL (used by analysis service when INFO_SERVICE_URL/BACKEND_URL not set)
BACKEND_URL = os.environ.get("BACKEND_URL", "").strip() or "http://127.0.0.1:8002"

# Whether to write AI agent reports as markdown files inside the results folder.
# Disabled by default; set WRITE_AI_REPORTS_TO_RESULTS=true to enable.
WRITE_AI_REPORTS_TO_RESULTS = os.environ.get("WRITE_AI_REPORTS_TO_RESULTS", "false").strip().lower() in ("1", "true", "yes")

# Whether each analysis run should build upon the previous completed run for the
# same ticker: each aspect-agent receives its own prior report and produces an
# updated, standalone report with a "What changed since {date}" section.
# Enabled by default; set BUILD_ON_PRIOR_ANALYSIS=false to force from-scratch runs.
BUILD_ON_PRIOR_ANALYSIS = os.environ.get("BUILD_ON_PRIOR_ANALYSIS", "true").strip().lower() in ("1", "true", "yes")

# Chat token conversion: N LLM tokens = 1 platform token. User balance is in platform tokens.
# Set LLM_TOKENS_PER_PLATFORM_TOKEN (e.g. 10000) to configure. Default: 10000.
def _parse_llm_tokens_per_platform() -> int:
    raw = os.environ.get("LLM_TOKENS_PER_PLATFORM_TOKEN", "10000").strip()
    val = int(raw)
    if val < 1:
        raise ValueError("LLM_TOKENS_PER_PLATFORM_TOKEN must be >= 1")
    return val


LLM_TOKENS_PER_PLATFORM_TOKEN = _parse_llm_tokens_per_platform()
