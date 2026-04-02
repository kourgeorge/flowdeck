import os

# data_dir: backend data layer uses DATA_SOURCES_DATA_DIR; here we default to project/data
_DATA_DIR = os.getenv("DATA_SOURCES_DATA_DIR", "").strip() or os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data"
)
_DATA_DIR = os.path.abspath(_DATA_DIR)

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_dir": _DATA_DIR,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "o4-mini",
    "quick_think_llm": "gpt-4o-mini",
    "backend_url": "https://api.openai.com/v1",
    # Run selected analysts concurrently (LangGraph Send + join) when more than one is selected
    "parallel_analysts": True,
    # Debate and discussion settings
    "max_debate_rounds": 2,
    "max_risk_discuss_rounds": 2,
    "max_recur_limit": 100,
    # Data vendor configuration (aligned with data_layer/vendors/config)
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_ticker_data": "alpha_vantage",  # Override category default
        # Example: "get_news": "openai",               # Override category default
    },
    # Information Fetcher Service: when set, agent tools (get_news, get_ticker_data, get_fundamentals, etc.)
    # fetch data from this URL instead of local vendors. Use the same service as the dashboard UI.
    # Example: "info_service_url": "http://localhost:8002",
    "info_service_url": os.getenv("INFO_SERVICE_URL", "").strip() or None,
}
