"""Portfolio Risk Profiling: Analyze portfolio composition, exposures, and risk metrics."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


def _fetch_company_info_from_service(ticker: str) -> Dict[str, Any]:
    """Fetch company info (sector, industry) directly from yfinance via info_fetcher."""
    try:
        # Import here to avoid circular dependencies
        from backend.services.info_fetcher import InfoFetcher
        fetcher = InfoFetcher()
        return fetcher.get_company_info(ticker)
    except Exception as e:
        logger.warning(f"Failed to fetch company info for {ticker}: {e}")
        return {}


def _fetch_extended_info_from_service(ticker: str) -> Dict[str, Any]:
    """Fetch extended info (beta, market cap) directly from yfinance via info_fetcher."""
    try:
        from backend.services.info_fetcher import InfoFetcher
        fetcher = InfoFetcher()
        return fetcher.get_extended_info(ticker)
    except Exception as e:
        logger.warning(f"Failed to fetch extended info for {ticker}: {e}")
        return {}


class PortfolioRiskProfile:
    """Container for portfolio risk analysis results."""
    
    def __init__(self):
        self.sector_exposure: Dict[str, float] = {}
        self.market_cap_distribution: Dict[str, float] = {}
        self.concentration_risk: Dict[str, Any] = {}
        self.correlation_clusters: List[List[str]] = []
        self.volatility_metrics: Dict[str, float] = {}
        self.beta_analysis: Dict[str, float] = {}
        self.risk_warnings: List[str] = []
        self.risk_score: float = 0.0  # 0-100 scale
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for state storage."""
        return {
            "sector_exposure": self.sector_exposure,
            "market_cap_distribution": self.market_cap_distribution,
            "concentration_risk": self.concentration_risk,
            "correlation_clusters": self.correlation_clusters,
            "volatility_metrics": self.volatility_metrics,
            "beta_analysis": self.beta_analysis,
            "risk_warnings": self.risk_warnings,
            "risk_score": self.risk_score,
        }


def calculate_sector_exposure(
    tickers: List[str],
    existing_reports: Dict[str, Dict[str, Any]],
) -> Dict[str, float]:
    """
    Calculate sector exposure percentages from portfolio.
    Returns dict of sector -> percentage.
    """
    sector_counts = defaultdict(int)
    total = len(tickers)
    
    if total == 0:
        return {}
    
    for ticker in tickers:
        report_data = existing_reports.get(ticker.upper(), {})
        reports = report_data.get("reports", {})
        sector = "Unknown"
        
        # Try multiple locations for sector data in reports
        # 1. fundamentals_analyst report
        if "fundamentals_analyst" in reports:
            fundamentals = reports["fundamentals_analyst"]
            sector = fundamentals.get("sector") or fundamentals.get("Sector") or sector
        
        # 2. market_analyst report
        if sector == "Unknown" and "market_analyst" in reports:
            market = reports["market_analyst"]
            sector = market.get("sector") or market.get("Sector") or sector
        
        # 3. Check in analysis field (some reports store it there)
        if sector == "Unknown":
            for report_type, report_content in reports.items():
                if isinstance(report_content, dict):
                    if "sector" in report_content:
                        sector = report_content["sector"]
                        break
                    if "Sector" in report_content:
                        sector = report_content["Sector"]
                        break
                    # Check in analysis text
                    analysis = report_content.get("analysis", "")
                    if isinstance(analysis, str) and "sector:" in analysis.lower():
                        # Try to extract sector from analysis text
                        for line in analysis.split("\n"):
                            if "sector:" in line.lower():
                                parts = line.split(":", 1)
                                if len(parts) == 2:
                                    sector = parts[1].strip().split()[0]
                                    break
        
        # 4. Fallback: fetch directly from yfinance via info_fetcher
        if sector == "Unknown":
            logger.info(f"Sector not found in reports for {ticker}, fetching from yfinance...")
            company_info = _fetch_company_info_from_service(ticker)
            sector = company_info.get("sector", "Unknown")
            if sector and sector != "N/A":
                logger.info(f"Found sector for {ticker}: {sector}")
        
        sector_counts[sector] += 1
    
    # Convert to percentages
    sector_exposure = {
        sector: (count / total) * 100
        for sector, count in sector_counts.items()
    }
    
    return dict(sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True))


def calculate_concentration_risk(
    tickers: List[str],
    existing_reports: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze concentration risk: top holdings, single-stock risk.
    Assumes equal weighting if no position sizes provided.
    """
    total = len(tickers)
    if total == 0:
        return {"top_3_concentration": 0.0, "top_5_concentration": 0.0, "herfindahl_index": 0.0}
    
    # Equal weight assumption
    weight_per_stock = 100.0 / total
    
    # Top N concentration
    top_3_pct = min(3, total) * weight_per_stock
    top_5_pct = min(5, total) * weight_per_stock
    
    # Herfindahl-Hirschman Index (HHI) for concentration
    # HHI = sum of squared market shares (0-10000 scale)
    hhi = sum((weight_per_stock) ** 2 for _ in range(total))
    
    return {
        "top_3_concentration": round(top_3_pct, 2),
        "top_5_concentration": round(top_5_pct, 2),
        "herfindahl_index": round(hhi, 2),
        "total_positions": total,
        "avg_position_size": round(weight_per_stock, 2),
    }


def calculate_beta_analysis(
    tickers: List[str],
    existing_reports: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extract and analyze portfolio beta from existing reports.
    Returns portfolio-level beta metrics.
    """
    betas = []
    
    for ticker in tickers:
        report_data = existing_reports.get(ticker.upper(), {})
        reports = report_data.get("reports", {})
        beta = None
        
        # Try multiple locations for beta data
        # 1. technical_analyst report
        if "technical_analyst" in reports:
            technical = reports["technical_analyst"]
            beta = technical.get("beta") or technical.get("Beta")
        
        # 2. fundamentals_analyst report
        if beta is None and "fundamentals_analyst" in reports:
            fundamentals = reports["fundamentals_analyst"]
            beta = fundamentals.get("beta") or fundamentals.get("Beta")
        
        # 3. market_analyst report
        if beta is None and "market_analyst" in reports:
            market = reports["market_analyst"]
            beta = market.get("beta") or market.get("Beta")
        
        # 4. Check any report for beta field
        if beta is None:
            for report_content in reports.values():
                if isinstance(report_content, dict):
                    beta = report_content.get("beta") or report_content.get("Beta")
                    if beta is not None:
                        break
        
        # 5. Fallback: fetch directly from yfinance via info_fetcher
        if beta is None:
            logger.info(f"Beta not found in reports for {ticker}, fetching from yfinance...")
            extended_info = _fetch_extended_info_from_service(ticker)
            beta = extended_info.get("beta")
            if beta is not None:
                logger.info(f"Found beta for {ticker}: {beta}")
        
        if beta is not None and isinstance(beta, (int, float)):
            betas.append(float(beta))
    
    if not betas:
        return {
            "portfolio_beta": None,
            "high_beta_count": 0,
            "low_beta_count": 0,
        }
    
    avg_beta = statistics.mean(betas)
    high_beta_count = sum(1 for b in betas if b > 1.2)
    low_beta_count = sum(1 for b in betas if b < 0.8)
    
    return {
        "portfolio_beta": round(avg_beta, 2),
        "beta_std": round(statistics.stdev(betas), 2) if len(betas) > 1 else 0.0,
        "high_beta_count": high_beta_count,
        "low_beta_count": low_beta_count,
        "beta_range": f"{min(betas):.2f} - {max(betas):.2f}",
    }


def identify_correlation_clusters(
    tickers: List[str],
    existing_reports: Dict[str, Dict[str, Any]],
) -> List[List[str]]:
    """
    Identify groups of stocks that likely move together (same sector, similar business).
    Returns list of clusters.
    """
    sector_groups = defaultdict(list)
    
    for ticker in tickers:
        report_data = existing_reports.get(ticker.upper(), {})
        reports = report_data.get("reports", {})
        
        fundamentals = reports.get("fundamentals_analyst", {})
        sector = fundamentals.get("sector", "Unknown")
        
        if sector == "Unknown":
            market = reports.get("market_analyst", {})
            sector = market.get("sector", "Unknown")
        
        sector_groups[sector].append(ticker.upper())
    
    # Return clusters with 2+ stocks (correlated groups)
    clusters = [group for group in sector_groups.values() if len(group) >= 2]
    
    return clusters


def generate_risk_warnings(
    profile: PortfolioRiskProfile,
    tickers: List[str],
) -> List[str]:
    """
    Generate specific risk warnings based on portfolio analysis.
    Returns list of warning strings.
    """
    warnings = []
    
    # Sector concentration warning
    if profile.sector_exposure:
        max_sector, max_pct = max(profile.sector_exposure.items(), key=lambda x: x[1])
        if max_pct > 40:
            warnings.append(
                f"High sector concentration: {max_pct:.1f}% in {max_sector}. "
                f"Sector-specific risks could significantly impact portfolio."
            )
    
    # Position concentration warning
    conc = profile.concentration_risk
    if conc.get("top_3_concentration", 0) > 50:
        warnings.append(
            f"Top 3 positions represent {conc['top_3_concentration']:.1f}% of portfolio. "
            f"Consider diversification to reduce single-stock risk."
        )
    
    # Beta warning
    beta_data = profile.beta_analysis
    if beta_data.get("portfolio_beta"):
        beta = beta_data["portfolio_beta"]
        if beta > 1.3:
            warnings.append(
                f"High portfolio beta ({beta:.2f}). Portfolio is {((beta - 1) * 100):.0f}% "
                f"more volatile than market. Expect larger swings in both directions."
            )
        elif beta < 0.7:
            warnings.append(
                f"Low portfolio beta ({beta:.2f}). Portfolio may underperform in bull markets "
                f"but provide downside protection in corrections."
            )
    
    # Correlation cluster warning
    if profile.correlation_clusters:
        largest_cluster = max(profile.correlation_clusters, key=len)
        if len(largest_cluster) >= 4:
            warnings.append(
                f"Large correlation cluster detected: {len(largest_cluster)} stocks likely move together "
                f"({', '.join(largest_cluster[:5])}{'...' if len(largest_cluster) > 5 else ''}). "
                f"Diversification benefit may be limited."
            )
    
    # Small portfolio warning
    if len(tickers) < 5:
        warnings.append(
            f"Portfolio has only {len(tickers)} positions. Consider adding more stocks "
            f"to reduce idiosyncratic risk."
        )
    
    # Over-diversification warning
    if len(tickers) > 30:
        warnings.append(
            f"Portfolio has {len(tickers)} positions. May be over-diversified, "
            f"making it difficult to outperform market indices."
        )
    
    return warnings


def calculate_risk_score(profile: PortfolioRiskProfile) -> float:
    """
    Calculate overall risk score (0-100, higher = riskier).
    Combines multiple risk factors.
    """
    score = 0.0
    
    # Sector concentration (0-30 points)
    if profile.sector_exposure:
        max_sector_pct = max(profile.sector_exposure.values())
        if max_sector_pct > 50:
            score += 30
        elif max_sector_pct > 40:
            score += 20
        elif max_sector_pct > 30:
            score += 10
    
    # Position concentration (0-25 points)
    conc = profile.concentration_risk
    top_3 = conc.get("top_3_concentration", 0)
    if top_3 > 60:
        score += 25
    elif top_3 > 50:
        score += 15
    elif top_3 > 40:
        score += 8
    
    # Beta risk (0-25 points)
    beta = profile.beta_analysis.get("portfolio_beta")
    if beta:
        if beta > 1.5:
            score += 25
        elif beta > 1.3:
            score += 15
        elif beta > 1.1:
            score += 8
        elif beta < 0.6:
            score += 10  # Low beta also a risk (opportunity cost)
    
    # Diversification (0-20 points)
    total_positions = conc.get("total_positions", 0)
    if total_positions < 5:
        score += 20
    elif total_positions < 10:
        score += 10
    elif total_positions > 40:
        score += 5  # Over-diversification
    
    return min(100.0, round(score, 1))


def analyze_portfolio_risk(
    tickers: List[str],
    existing_reports: Dict[str, Dict[str, Any]],
) -> PortfolioRiskProfile:
    """
    Main function: Perform comprehensive portfolio risk analysis.
    Returns PortfolioRiskProfile with all metrics.
    """
    logger.info("Analyzing portfolio risk for %d tickers", len(tickers))
    
    profile = PortfolioRiskProfile()
    
    # Calculate all risk metrics
    profile.sector_exposure = calculate_sector_exposure(tickers, existing_reports)
    profile.concentration_risk = calculate_concentration_risk(tickers, existing_reports)
    profile.beta_analysis = calculate_beta_analysis(tickers, existing_reports)
    profile.correlation_clusters = identify_correlation_clusters(tickers, existing_reports)
    
    # Generate warnings and risk score
    profile.risk_warnings = generate_risk_warnings(profile, tickers)
    profile.risk_score = calculate_risk_score(profile)
    
    logger.info(
        "Portfolio risk analysis complete | risk_score=%.1f | warnings=%d",
        profile.risk_score,
        len(profile.risk_warnings),
    )
    
    return profile


