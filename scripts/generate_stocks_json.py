#!/usr/bin/env python3
"""
Generate a consolidated stocks.json for frontend search.

Sources (in order of preference):
  1. SEC EDGAR company tickers JSON         -- free, no key, ~13k US-listed companies
  2. Curated S&P 500 and NASDAQ-100 lists  -- static in-file
  3. Top crypto tickers                     -- static list

The script writes frontend/public/stocks.json with entries:
  - Non-major tickers: {"ticker": "...", "name": "..."}
  - Major tickers:     {"ticker": "...", "name": "...", "sector": "...", "industry": "..."}

Major ticker sector/industry data is loaded from:
  backend/data/major_stocks_sectors.json
and missing entries are fetched from yfinance (if installed), then cached back.

Usage:
  python scripts/generate_stocks_json.py
  python scripts/generate_stocks_json.py --source edgar
  python scripts/generate_stocks_json.py --source sp500
  python scripts/generate_stocks_json.py --skip-major-sector-enrichment
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "frontend" / "public" / "stocks.json"
MAJOR_SECTORS_CACHE_PATH = (
    Path(__file__).parent.parent / "backend" / "data" / "major_stocks_sectors.json"
)

# Curated list of major stocks (S&P 500 + NASDAQ 100 top stocks)
MAJOR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "V", "UNH",
    "JNJ", "WMT", "JPM", "MA", "PG", "XOM", "HD", "CVX", "MRK", "ABBV",
    "KO", "PEP", "COST", "AVGO", "TMO", "MCD", "CSCO", "ACN", "ABT", "LIN",
    "DHR", "NKE", "VZ", "ADBE", "TXN", "NEE", "CRM", "PM", "ORCL", "CMCSA",
    "DIS", "WFC", "BMY", "UPS", "RTX", "QCOM", "INTC", "HON", "UNP", "INTU",
    "AMD", "AMGN", "LOW", "BA", "SBUX", "CAT", "GE", "SPGI", "DE", "AXP",
    "BLK", "GILD", "MDT", "PLD", "ISRG", "TJX", "MMC", "C", "BKNG", "SYK",
    "ADI", "VRTX", "REGN", "ZTS", "CB", "MO", "CI", "PGR", "SO", "DUK",
    "SCHW", "LRCX", "EOG", "BSX", "MDLZ", "TMUS", "BDX", "SLB", "PYPL", "NOC",
    "MMM", "ITW", "USB", "PNC", "AON", "CL", "APD", "CME", "GD", "TGT",
    "NFLX", "SHOP", "SQ", "ROKU", "SNAP", "UBER", "LYFT", "ABNB", "COIN", "RBLX",
    "ADP", "AMAT", "ANET", "AEP", "AIG", "ALL", "ALGN", "AME", "AMP", "AMT",
    "AOS", "APA", "ARE", "ATO", "AWK", "AZO", "BALL", "BAX", "BBY", "BIIB",
    "BKR", "BRO", "BXP", "CDNS", "CDW", "CHD", "CHTR", "CINF", "CMS", "CNC",
    "COF", "CPB", "CRL", "CTSH", "CTAS", "CTVA", "DG", "DGX", "DOV", "DRI",
    "EBAY", "ED", "EFX", "EIX", "EL", "EMR", "ENPH", "EQIX", "EQT", "ES",
    "ESS", "ETSY", "EVRG", "EXC", "EXPD", "FAST", "FCX", "FDS", "FDX", "FTV",
    "GLW", "GRMN", "HCA", "HIG", "HLT", "HPE", "HPQ", "HSY", "HUBB", "HUM",
    "IEX", "ILMN", "IR", "K", "KDP", "KEY", "KMB", "KR", "LH", "LHX",
    "LKQ", "LLY", "LUV", "LYB", "MCHP", "MKC", "MSCI", "MTB", "NDAQ", "NTRS",
    "O", "ODFL", "OMC", "PAYX", "PFG", "PH", "PKG", "PNW", "PPG", "PSA",
    "A","AA","AAC","AADI","AAOI","AAWW","AB","ABB","ABCL","ABEO",
    "ABG","ABM","ABR","ABST","ABUS","ABVC","ABVX","AC","ACA","ACAD",
    "ACCO","ACEL","ACET","ACGL","ACHC","ACHR","ACHV","ACIC","ACIU","ACLS",
    "ACM","ACNB","ACON","ACRS","ACT","ACTG","ACVA","ACXP","ADAP","ADCT",
    "ADIL","ADMA","ADMP","ADPT","ADSE","ADTN","ADTX","ADUS","ADV","ADVM",
    "ADXN","AE","AEHR","AEIS","AEL","AEM","AENZ","AERI","AESI","AEVA",
    "AEY","AFBI","AFG","AFIB","AFIN","AFMD","AFYA","AG","AGAE","AGCO",
    "AGEN","AGFY","AGI","AGIO","AGL","AGLE","AGM","AGNC","AGO","AGR",
    "AGRO","AGRX","AGS","AGTI","AGX","AGYS","AHCO","AHH","AHT","AI",
    "AIHS","AIMC","AIN","AIP","AIR","AIRC","AIRI","AIT","AIV",
    "AIZ","AJRD","AJX","AKAM","AKBA","AKR","AKRO","AKTS","AKYA","AL",
    "ALB","ALC","ALDX","ALE","ALEC","ALEX","ALG","ALGM","ALGT","ALHC",
    "ALIT","ALK","ALKS","ALLK","ALLO","ALNY","ALRM","ALSN","ALT","ALTO",
    "ALTR","ALV","ALVR","ALXO","AM","AMAL","AMBA","AMBC","AMCX","AMED",
    "AMG","AMH","AMK","AMKR","AMN","AMOT","AMPS","AMPX","AMRC","AMRK",
    "AMRN","AMRX","AMSC","AMSF","AMSWA","AMTB","AMWD","AMWL","AMX","AMYT",
    "AN","ANAB","ANDE","ANF","ANGO","ANIK","ANIP","ANIX","ANNX","ANSS",
    "ANTE","ANY","AOMR","AORT","AOSL","AOUT","AP","APAM","APDN","APEI",
    "APG","APLD","APLS","APLT","APOG","APP","APPF","APPN","APPS","APRE",
    "APT","APTO","APTV","AQB","AQN","AQUA","AR","ARAV","ARAY","ARCB",
    "ARCC","ARCH","ARCO","ARCT","ARDX","AREC","ARES","ARGX","ARHS","ARI",
    "ARIS","ARKO","ARLO","ARLP","AROC","AROW","ARQT","ARR","ARRY","ARVN",
    "ASAN","ASB","ASGN","ASH","ASIX","ASLE","ASND","ASO","ASPN","ASTE",
    "ASTL","ASTS","ASUR","ASX","ATEN","ATI","ATKR","ATNI","ATRC","ATRO",
    "ATSG","ATUS","AU","AUB","AUPH","AVA","AVAV","AVDL","AVIR","AVNS",
    "AVNW","AVPT","AVRO","AVTR","AVXL","AVYA","AWI","AX","AXGN","AXL",
    "AXNX","AXON","AXS","AY","AYI","AYRO","AZEK","AZPN","AZTA","AZUL"
    ]

SP500 = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "AVGO", "TSLA", "BRK.B", "WMT", "LLY",
    "JPM", "XOM", "V", "JNJ", "MA", "MU", "COST", "ORCL", "ABBV", "NFLX", "CVX", "PG",
    "HD", "PLTR", "BAC", "GE", "CAT", "KO", "AMD", "CSCO", "MRK", "AMAT", "RTX", "PM",
    "LRCX", "UNH", "MS", "GS", "WFC", "TMUS", "MCD", "IBM", "LIN", "INTC", "GEV", "PEP",
    "VZ", "AXP", "AMGN", "T", "ABT", "C", "NEE", "KLAC", "TMO", "TXN", "GILD", "DIS",
    "CRM", "TJX", "BA", "ISRG", "ANET", "SCHW", "DE", "APH", "ADI", "BLK", "APP", "UBER",
    "UNP", "HON", "LMT", "PFE", "QCOM", "SYK", "LOW", "DHR", "WELL", "COP", "BKNG", "ETN",
    "SPGI", "CB", "PANW", "ACN", "NEM", "PLD", "BMY", "PGR", "PH", "MDT", "INTU", "COF",
    "VRTX", "HCA", "NOW", "GLW", "CEG", "MCK", "CME", "CMCSA", "MO", "ADBE", "SBUX", "SO",
    "NOC", "BSX", "HWM", "CVS", "DUK", "CRWD", "GD", "TT", "WM", "DELL", "EQIX", "ICE",
    "UPS", "FCX", "WMB", "FDX", "MRSH", "BX", "AMT", "WDC", "SNDK", "MAR", "ADP", "NKE",
    "PNC", "SHW", "JCI", "PWR", "MMM", "ECL", "STX", "USB", "MCO", "KKR", "CDNS", "REGN",
    "ITW", "SNPS", "ABNB", "EMR", "BK", "DASH", "CTAS", "MSI", "CSX", "CMI", "ORLY", "RCL",
    "CL", "MNST", "KMI", "MDLZ", "CRH", "HOOD", "TDG", "CI", "AON", "AEP", "COR", "SLB",
    "NSC", "GM", "RSG", "VLO", "WBD", "HLT", "EOG", "LHX", "ROST", "TRV", "PSX", "SPG",
    "MPC", "PCAR", "ELV", "DLR", "APO", "TEL", "TFC", "AZO", "SRE", "FTNT", "O", "APD",
    "BKR", "AJG", "AFL", "GWW", "FAST", "ALL", "COIN", "D", "VST", "PSA", "ADSK", "TGT",
    "NXPI", "OKE", "AME", "OXY", "CAH", "ZTS", "CTVA", "URI", "MPWR", "TRGP", "CARR", "KEYS",
    "IDXX", "F", "NDAQ", "EA", "FANG", "FIX", "EXC", "EW", "BDX", "XEL", "ETR", "GRMN",
    "CMG", "MET", "TER", "HSY", "AXON", "CIEN", "CVNA", "ODFL", "WAB", "FITB", "YUM", "DHI",
    "ROK", "AIG", "PYPL", "AMP", "KR", "PEG", "MSCI", "SYY", "CBRE", "PCG", "DDOG", "DAL",
    "EBAY", "VTR", "ED", "NUE", "MLM", "TTWO", "XYZ", "CCI", "KDP", "HIG", "EQT", "CCL",
    "RMD", "VMC", "WEC", "WDAY", "LVS", "MCHP", "LYV", "ROP", "TPL", "CPRT", "IR", "EL",
    "GEHC", "OTIS", "ACGL", "STT", "NRG", "KMB", "KVUE", "FICO", "PAYX", "PRU", "HBAN", "A",
    "FISV", "DG", "EME", "MTB", "ADM", "UAL", "VICI", "IRM", "TDY", "TPR", "ATO", "CBOE",
    "EXR", "XYL", "WAT", "CTSH", "DTE", "AEE", "RJF", "IBKR", "IQV", "VRSK", "DOV", "CHTR",
    "ULTA", "FE", "PPL", "WTW", "EXPE", "HAL", "KHC", "CNP", "HPE", "STLD", "EIX", "ROL",
    "BIIB", "DXCM", "ES", "DVN", "NTRS", "JBL", "TSCO", "WRB", "AWK", "OMC", "PPG", "STZ",
    "LEN", "CINF", "ARES", "HUBB", "FIS", "MTD", "EXE", "CFG", "PHM", "AVB", "Q", "EFX",
    "ON", "BRO", "CHD", "WSM", "SYF", "STE", "RF", "CMS", "DOW", "VLTO", "EQR", "SW",
    "DRI", "DLTR", "CTRA", "GIS", "LH", "DGX", "CPAY", "L", "LUV", "NI", "BR", "MRNA",
    "IP", "KEY", "LDOS", "BG", "JBHT", "CHRW", "TSN", "HUM", "CNC", "VRSN", "GPN", "RL",
    "FSLR", "AMCR", "PKG", "SBAC", "LYB", "LULU", "NVR", "PFG", "IFF", "TROW", "SNA", "ALB",
    "EXPD", "CSGP", "INCY", "DD", "NTAP", "EVRG", "LII", "PTC", "SMCI", "ZBH", "LNT", "FTV",
    "WY", "MKC", "HPQ", "WST", "BALL", "TXT", "PODD", "HII", "HOLX", "TKO", "VTRS", "TRMB",
    "ESS", "INVH", "CF", "COO", "NDSN", "CDW", "J", "GPC", "FFIV", "PNR", "KIM", "TYL",
    "MAA", "APTV", "IEX", "DECK", "TTD", "AKAM", "REG", "AVY", "ERIE", "CLX", "BBY", "HST",
    "BEN", "MAS", "DPZ", "HAS", "EG", "ALLE", "GEN", "HRL", "PSKY", "ALGN", "GNRC", "UHS",
    "PNW", "SJM", "SWK", "SOLV", "UDR", "JKHY", "DOC", "BF.B", "FOX", "GDDY", "IT", "FOXA",
    "AIZ", "GL", "ZBRA", "CPT", "APA", "IVZ", "RVTY", "WYNN", "BLDR", "DVA", "AOS", "AES",
    "BAX", "NCLH", "MGM", "FRT", "ARE", "HSIC", "TECH", "CAG", "TAP", "CRL", "BXP", "NWSA",
    "SWKS", "FDS", "MOS", "POOL", "MOH", "EPAM", "CPB", "MTCH", "PAYC", "LW", "NWS"
]

NASDAQ100 = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "AVGO", "TSLA", "WMT", "ASML", "MU",
    "COST", "NFLX", "PLTR", "AMD", "CSCO", "AMAT", "LRCX", "TMUS", "LIN", "INTC", "PEP", "AMGN",
    "KLAC", "TXN", "GILD", "ISRG", "SHOP", "ADI", "APP", "HON", "QCOM", "PDD", "BKNG", "ARM",
    "PANW", "INTU", "VRTX", "CEG", "CMCSA", "ADBE", "SBUX", "CRWD", "MELI", "WDC", "MAR", "ADP",
    "STX", "CDNS", "REGN", "SNPS", "ABNB", "DASH", "CTAS", "ORLY", "CSX", "MNST", "MDLZ", "AEP",
    "MRVL", "WBD", "ROST", "PCAR", "FTNT", "BKR", "FAST", "ADSK", "NXPI", "MPWR", "IDXX", "EA",
    "EXC", "FANG", "FER", "MSTR", "XEL", "CCEP", "TRI", "AXON", "ODFL", "ALNY", "PYPL", "DDOG",
    "TTWO", "KDP", "WDAY", "MCHP", "ROP", "CPRT", "GEHC", "PAYX", "INSM", "CTSH", "VRSK", "CHTR",
    "KHC", "DXCM", "ZS", "TEAM", "CSGP"
]
# Backward-compatible alias for older typo used in this file history.
NSDAQ100 = NASDAQ100

DowJones = [
    "GS", "CAT", "MSFT", "AMGN", "HD", "SHW", "MCD", "V", "TRV", "AXP", "JPM", "UNH",
    "AAPL", "IBM", "HON", "JNJ", "BA", "AMZN", "CRM", "CVX", "NVDA", "MMM", "PG", "WMT",
    "MRK", "DIS", "CSCO", "KO", "NKE", "VZ"
]

# ---------------------------------------------------------------------------
# Source 1: SEC EDGAR – all US-listed companies (~13 000 tickers, no API key)
# ---------------------------------------------------------------------------

def fetch_from_edgar() -> list[dict]:
    """
    Download the SEC EDGAR company tickers JSON.
    Returns list of {"ticker": ..., "name": ...} dicts.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    print(f"Fetching from SEC EDGAR: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "flowdeck/1.0 contact@example.com"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())

    stocks = []
    for entry in data.values():
        ticker = entry.get("ticker", "").strip().upper()
        name = entry.get("title", "").strip()
        if ticker and name and _is_valid_ticker(ticker):
            stocks.append({"ticker": ticker, "name": name})

    # Sort alphabetically by ticker
    stocks.sort(key=lambda x: x["ticker"])
    print(f"  → {len(stocks)} stocks from SEC EDGAR")
    return stocks


# ---------------------------------------------------------------------------
# Source 2: Curated index lists (local, no network)
# ---------------------------------------------------------------------------

def _stocks_from_tickers(tickers: list[str], source_name: str) -> list[dict]:
    stocks: list[dict] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        stocks.append({"ticker": ticker, "name": ticker})
    stocks.sort(key=lambda x: x["ticker"])
    print(f"  → {len(stocks)} tickers from {source_name}")
    return stocks


def fetch_nasdaq100() -> list[dict]:
    """Return NASDAQ-100 tickers from the local curated list."""
    return _stocks_from_tickers(NASDAQ100, "local NASDAQ100 list")


def fetch_sp500() -> list[dict]:
    """Return S&P 500 tickers from the local curated list."""
    return _stocks_from_tickers(SP500, "local SP500 list")


# ---------------------------------------------------------------------------
# Source 3: Cryptocurrencies via yfinance (top cryptos)
# ---------------------------------------------------------------------------

def fetch_crypto() -> list[dict]:
    """
    Fetch top cryptocurrencies that are tradeable via Yahoo Finance.
    Returns list of {"ticker": ..., "name": ...} dicts.
    """
    # Top cryptocurrencies available on Yahoo Finance (ticker format: SYMBOL-USD)
    crypto_list = [
        ("BTC-USD", "Bitcoin USD"),
        ("ETH-USD", "Ethereum USD"),
        ("USDT-USD", "Tether USD"),
        ("BNB-USD", "Binance Coin USD"),
        ("SOL-USD", "Solana USD"),
        ("XRP-USD", "XRP USD"),
        ("USDC-USD", "USD Coin"),
        ("ADA-USD", "Cardano USD"),
        ("AVAX-USD", "Avalanche USD"),
        ("DOGE-USD", "Dogecoin USD"),
        ("TRX-USD", "TRON USD"),
        ("DOT-USD", "Polkadot USD"),
        ("MATIC-USD", "Polygon USD"),
        ("LTC-USD", "Litecoin USD"),
        ("SHIB-USD", "Shiba Inu USD"),
        ("BCH-USD", "Bitcoin Cash USD"),
        ("LINK-USD", "Chainlink USD"),
        ("UNI-USD", "Uniswap USD"),
        ("ATOM-USD", "Cosmos USD"),
        ("XLM-USD", "Stellar USD"),
        ("ETC-USD", "Ethereum Classic USD"),
        ("XMR-USD", "Monero USD"),
        ("APT-USD", "Aptos USD"),
        ("FIL-USD", "Filecoin USD"),
        ("HBAR-USD", "Hedera USD"),
        ("ARB-USD", "Arbitrum USD"),
        ("OP-USD", "Optimism USD"),
        ("NEAR-USD", "NEAR Protocol USD"),
        ("VET-USD", "VeChain USD"),
        ("ALGO-USD", "Algorand USD"),
    ]
    
    stocks = [{"ticker": ticker, "name": name} for ticker, name in crypto_list]
    print(f"  → {len(stocks)} cryptocurrencies added")
    return stocks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TICKER_RE = re.compile(r'^[A-Z0-9]{1,6}(-[A-Z0-9]{1,2})?$')

def _is_valid_ticker(ticker: str) -> bool:
    """
    Accept standard US equity tickers.
    Only rejects clearly invalid entries: empty, containing spaces,
    or purely numeric strings.
    """
    if not ticker:
        return False
    if ' ' in ticker:
        return False
    if ticker.isdigit():
        return False
    return bool(_TICKER_RE.match(ticker))


def deduplicate(stocks: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for s in stocks:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            result.append(s)
    return result


def load_existing_stocks(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: could not read existing stocks file {path}: {e}")
        return []

    if not isinstance(data, list):
        return []

    stocks: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        name = str(item.get("name", "")).strip()
        if ticker and name:
            stock = {"ticker": ticker, "name": name}
            if item.get("sector"):
                stock["sector"] = item["sector"]
            if item.get("industry"):
                stock["industry"] = item["industry"]
            stocks.append(stock)
    return stocks


def _normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def _merge_major_ticker_lists(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for tickers in lists:
        for ticker in tickers:
            norm = _normalize_ticker(ticker)
            if norm in seen:
                continue
            seen.add(norm)
            merged.append(norm)
    return merged


MERGED_MAJOR_TICKERS = _merge_major_ticker_lists(
    MAJOR_TICKERS,
    SP500,
    NASDAQ100,
    DowJones,
)
_MAJOR_TICKER_SET = set(MERGED_MAJOR_TICKERS)


def load_major_sector_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: could not read major sectors cache {path}: {e}")
        return {}

    if not isinstance(data, dict):
        print(f"Warning: expected object in major sectors cache, got {type(data).__name__}")
        return {}

    cleaned: dict[str, dict] = {}
    for key, info in data.items():
        if not isinstance(info, dict):
            continue
        ticker = str(info.get("ticker") or key).upper()
        cleaned[ticker] = {
            "ticker": ticker,
            "name": info.get("name") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("market_cap"),
            "quote_type": info.get("quote_type"),
        }
    return cleaned


def save_major_sector_cache(cache: dict[str, dict], path: Path) -> None:
    payload = {}
    for ticker in sorted(cache):
        info = cache[ticker]
        payload[ticker] = {
            "ticker": ticker,
            "name": info.get("name") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("market_cap"),
            "quote_type": info.get("quote_type"),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_major_sector_data(tickers: list[str], delay: float) -> dict[str, dict]:
    if not tickers:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        print("Warning: yfinance not installed, skipping major sector enrichment fetch.")
        return {}

    total = len(tickers)
    print(f"Fetching sector/industry for {total} major tickers via yfinance...")
    fetched: dict[str, dict] = {}

    for i, ticker in enumerate(tickers, 1):
        print(f"  [{i}/{total}] {ticker}")
        try:
            info = yf.Ticker(ticker).info
            fetched[ticker] = {
                "ticker": ticker,
                "name": info.get("longName") or info.get("shortName") or ticker,
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "quote_type": info.get("quoteType"),
            }
        except Exception as e:
            print(f"    Warning: failed to fetch {ticker}: {e}")

        if i < total and delay > 0:
            time.sleep(max(0.0, delay + random.uniform(-0.1, 0.1)))

    return fetched


def _build_sector_index_by_normalized_ticker(sector_cache: dict[str, dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for ticker, info in sector_cache.items():
        index[_normalize_ticker(ticker)] = info
    return index


def collect_missing_major_tickers(stocks: list[dict], sector_cache: dict[str, dict]) -> list[str]:
    sector_index = _build_sector_index_by_normalized_ticker(sector_cache)
    seen_norm = set()
    missing = []

    for stock in stocks:
        ticker = stock["ticker"].upper()
        norm = _normalize_ticker(ticker)
        if norm not in _MAJOR_TICKER_SET or norm in seen_norm:
            continue
        seen_norm.add(norm)
        if norm not in sector_index:
            missing.append(ticker)
    return missing


def enrich_major_stocks(stocks: list[dict], sector_cache: dict[str, dict]) -> int:
    sector_index = _build_sector_index_by_normalized_ticker(sector_cache)
    enriched = 0

    for stock in stocks:
        norm = _normalize_ticker(stock["ticker"])
        if norm not in _MAJOR_TICKER_SET:
            continue

        info = sector_index.get(norm)
        if not info:
            continue

        sector = info.get("sector")
        industry = info.get("industry")
        if sector:
            stock["sector"] = sector
        if industry:
            stock["industry"] = industry
        if sector or industry:
            enriched += 1

    return enriched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate stocks.json for frontend search")
    parser.add_argument(
        "--source",
        choices=["edgar", "nasdaq", "crypto", "sp500", "all"],
        default="all",
        help="Data source to use (default: all, merges edgar + local index lists + crypto)",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=f"Output path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--major-sectors-cache",
        default=str(MAJOR_SECTORS_CACHE_PATH),
        help=f"Major sector cache path (default: {MAJOR_SECTORS_CACHE_PATH})",
    )
    parser.add_argument(
        "--major-sectors-delay",
        type=float,
        default=0.5,
        help="Delay between yfinance major-sector requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--refresh-major-sectors",
        action="store_true",
        help="Ignore local major-sector cache and refetch from yfinance.",
    )
    parser.add_argument(
        "--skip-major-sector-enrichment",
        action="store_true",
        help="Do not enrich major tickers with sector/industry data.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)

    equity_stocks: list[dict] = []
    crypto_stocks: list[dict] = []

    if args.source in ("edgar", "all"):
        try:
            equity_stocks += fetch_from_edgar()
        except Exception as e:
            print(f"SEC EDGAR fetch failed: {e}")

    if args.source in ("nasdaq", "all"):
        try:
            equity_stocks += fetch_nasdaq100()
        except Exception as e:
            print(f"NASDAQ100 list load failed: {e}")

    if args.source in ("sp500", "all"):
        try:
            equity_stocks += fetch_sp500()
        except Exception as e:
            print(f"S&P 500 list load failed: {e}")

    if args.source == "all" and not equity_stocks:
        existing_stocks = load_existing_stocks(output_path)
        if existing_stocks:
            print(f"Using existing {output_path} as equity fallback ({len(existing_stocks)} entries)")
            equity_stocks += existing_stocks

    if args.source in ("crypto", "all"):
        try:
            crypto_stocks += fetch_crypto()
        except Exception as e:
            print(f"Crypto fetch failed: {e}")

    stocks = equity_stocks + crypto_stocks

    if not stocks:
        print("ERROR: No stocks fetched from any source.", file=sys.stderr)
        sys.exit(1)

    stocks = deduplicate(stocks)
    stocks.sort(key=lambda x: x["ticker"])

    if not args.skip_major_sector_enrichment:
        cache_path = Path(args.major_sectors_cache)
        sector_cache: dict[str, dict] = {}

        if not args.refresh_major_sectors:
            sector_cache = load_major_sector_cache(cache_path)
            if sector_cache:
                print(f"Loaded {len(sector_cache)} cached major sector records from {cache_path}")

        missing_major_tickers = collect_missing_major_tickers(stocks, sector_cache)
        if missing_major_tickers:
            fetched = fetch_major_sector_data(
                missing_major_tickers,
                delay=args.major_sectors_delay,
            )
            if fetched:
                sector_cache.update(fetched)
                save_major_sector_cache(sector_cache, cache_path)
                print(f"Updated major sectors cache: {cache_path}")

        enriched_count = enrich_major_stocks(stocks, sector_cache)
        print(f"  -> Enriched {enriched_count} major stocks with sector/industry")
    else:
        print("Skipped major sector/industry enrichment.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stocks, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")

    print(f"\n✅ Written {len(stocks)} stocks to {output_path}")


if __name__ == "__main__":
    main()

# Made with Bob
