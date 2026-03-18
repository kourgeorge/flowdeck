"""
Shared constants for the data layer.
"""

# Curated tickers for market overview: (group_key, ticker, display_name)
MARKET_OVERVIEW_TICKERS = [
    ("indices", "^GSPC", "S&P 500"),
    ("indices", "^IXIC", "Nasdaq"),
    ("indices", "^DJI", "Dow Jones"),
    ("indices", "^NDX", "Nasdaq 100"),
    ("indices", "^RUT", "Russell 2000"),
    ("indices", "SPY", "S&P 500 ETF"),
    ("indices", "QQQ", "Nasdaq 100 ETF"),
    ("indices", "DIA", "Dow Jones ETF"),
    ("indices", "IWM", "Russell 2000 ETF"),
    ("indices", "MDY", "S&P MidCap 400"),
    ("indices", "VOO", "S&P 500 (Vanguard)"),
    ("indices", "VTI", "US Total Market"),
    ("sectors", "XLK", "Technology"),
    ("sectors", "XLF", "Financials"),
    ("sectors", "XLE", "Energy"),
    ("sectors", "XLV", "Healthcare"),
    ("sectors", "XLI", "Industrials"),
    ("sectors", "XLY", "Consumer Discretionary"),
    ("sectors", "XLP", "Consumer Staples"),
    ("sectors", "XLB", "Materials"),
    ("sectors", "XLU", "Utilities"),
    ("sectors", "XLC", "Communication"),
    ("sectors", "VGT", "Technology (Vanguard)"),
    ("sectors", "KRE", "Regional Banks"),
    ("international", "EFA", "Developed ex-US"),
    ("international", "EEM", "Emerging Markets"),
    ("international", "VEA", "Developed Markets"),
    ("international", "VWO", "Emerging Markets (Vanguard)"),
    ("international", "^TA125.TA", "Israel TA-125"),
    ("international", "^TASI.SR", "Saudi Arabia TASI"),
    ("international", "KSA", "Saudi Arabia (iShares)"),
    ("international", "UAE", "UAE (iShares)"),
    ("international", "QAT", "Qatar (iShares)"),
    ("international", "BAX", "Baxter International Inc."),
    ("international", "KWT", "Kuwait (iShares)"),
    ("international", "^FTSE", "UK FTSE 100"),
    ("international", "^GDAXI", "Germany DAX"),
    ("international", "^FCHI", "France CAC 40"),
    ("international", "^STOXX50E", "Euro Stoxx 50"),
    ("international", "EWG", "Germany (iShares)"),
    ("international", "EWU", "UK (iShares)"),
    ("international", "^IBEX", "Spain IBEX 35"),
    ("international", "^AEX", "Netherlands AEX"),
    ("international", "^SSMI", "Switzerland SMI"),
    ("international", "^OMXSPI", "Sweden OMX"),
    ("international", "^ATX", "Austria ATX"),
    ("international", "^BFX", "Belgium BEL 20"),
    ("international", "^OMXC20", "Denmark OMX Copenhagen"),
    ("international", "^OMXH25", "Finland OMX Helsinki"),
    ("international", "GD.AT", "Greece Athens General"),
    ("international", "EIRL", "Ireland (iShares)"),
    ("international", "^OSEAX", "Norway Oslo OBX"),
    ("international", "^N225", "Japan Nikkei 225"),
    ("international", "^HSI", "Hong Kong Hang Seng"),
    ("international", "^STI", "Singapore Straits"),
    ("international", "^AXJO", "Australia ASX 200"),
    ("international", "^KS11", "South Korea KOSPI"),
    ("international", "^TWII", "Taiwan TAIEX"),
    ("international", "^BSESN", "India Sensex"),
    ("international", "^NSEI", "India Nifty 50"),
    ("international", "^JKSE", "Indonesia IDX"),
    ("international", "^KLSE", "Malaysia KLCI"),
    ("international", "000001.SS", "China Shanghai"),
    ("international", "^SET.BK", "Thailand SET"),
    ("international", "PSEI.PS", "Philippines PSEi"),
    ("international", "VNM", "Vietnam (VanEck)"),
    ("international", "XBAK.DE", "Pakistan KSE 100"),
    ("international", "^NZ50", "New Zealand NZX 50"),
    ("international", "ENZL", "New Zealand (iShares)"),
    ("international", "EWJ", "Japan (iShares)"),
    ("international", "FXI", "China (iShares)"),
    ("international", "INDA", "India (iShares)"),
    ("international", "EWM", "Malaysia (iShares)"),
    ("international", "EIDO", "Indonesia (iShares)"),
    ("international", "XU100.IS", "Turkey BIST 100"),
    ("international", "TUR", "Turkey (iShares)"),
    ("international", "^GSPTSE", "Canada TSX"),
    ("international", "^BVSP", "Brazil Bovespa"),
    ("international", "^MXX", "Mexico IPC"),
    ("international", "^IPSA", "Chile IPSA"),
    ("international", "^MERV", "Argentina Merval"),
    ("international", "ICOLCAP.CL", "Colombia COLCAP"),
    ("international", "EPU", "Peru (iShares)"),
    ("international", "EWC", "Canada (iShares)"),
    ("international", "EWZ", "Brazil (iShares)"),
    ("international", "EWA", "Australia (iShares)"),
    ("international", "AFK", "Pan-Africa ETF"),
    ("international", "^JN0U.JO", "South Africa Top 40"),
    ("international", "EZA", "South Africa (iShares)"),
    ("commodities", "GC=F", "Gold"),
    ("commodities", "SI=F", "Silver"),
    ("commodities", "CL=F", "Oil (WTI)"),
    ("commodities", "NG=F", "Natural Gas"),
    ("commodities", "HG=F", "Copper"),
    ("commodities", "PA=F", "Palladium"),
    ("commodities", "PL=F", "Platinum"),
    ("commodities", "ZW=F", "Wheat"),
    ("commodities", "ZC=F", "Corn"),
    ("commodities", "DBA", "Agriculture"),
    ("commodities", "DBC", "Broad Commodities"),
]

_REQUIRED_OVERVIEW_INTERNATIONAL = {
    "^GDAXI",  # Germany DAX 30
    "^FTSE",   # UK FTSE 100
    "^FCHI",   # France CAC 40
    "^NSEI",   # India Nifty 50
    "^N225",   # Japan Nikkei 225
    "^HSI",    # Hong Kong Hang Seng
}

_all_international = [
    (g, t, n) for g, t, n in MARKET_OVERVIEW_TICKERS if g == "international"
]
_required_international = [
    entry for entry in _all_international if entry[1].upper() in _REQUIRED_OVERVIEW_INTERNATIONAL
]
_remaining_international = [
    entry for entry in _all_international if entry[1].upper() not in _REQUIRED_OVERVIEW_INTERNATIONAL
]

OVERVIEW_INTERNATIONAL_TICKERS = (_required_international + _remaining_international)[:18]
