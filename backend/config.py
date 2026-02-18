"""Configuration for stock dashboard backend."""

import os

# Default list of major stocks to show on homepage
MAJOR_STOCKS = [
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
DATA_CACHE_MAX_SIZE = 1000

# Per-type TTL in seconds
DATA_CACHE_TTL_QUOTE = 60              # Real-time
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
