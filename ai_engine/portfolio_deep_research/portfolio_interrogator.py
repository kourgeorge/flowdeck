"""Portfolio Interrogator: Generate critical questions about portfolio composition and risk."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PortfolioQuestion:
    """A critical question about the portfolio with context and urgency."""
    
    def __init__(
        self,
        question: str,
        category: str,
        urgency: str,
        context: str,
        suggested_action: str = "",
    ):
        self.question = question
        self.category = category  # risk, opportunity, rebalancing, macro, behavioral
        self.urgency = urgency  # high, medium, low
        self.context = context
        self.suggested_action = suggested_action
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for state storage."""
        return {
            "question": self.question,
            "category": self.category,
            "urgency": self.urgency,
            "context": self.context,
            "suggested_action": self.suggested_action,
        }


def generate_sector_concentration_questions(
    sector_exposure: Dict[str, float],
    tickers: List[str],
) -> List[PortfolioQuestion]:
    """Generate questions about sector concentration risks."""
    questions = []
    
    if not sector_exposure:
        return questions
    
    max_sector, max_pct = max(sector_exposure.items(), key=lambda x: x[1])
    
    if max_pct > 40:
        urgency = "high" if max_pct > 50 else "medium"
        questions.append(PortfolioQuestion(
            question=f"Why are you {max_pct:.0f}% exposed to {max_sector}?",
            category="risk",
            urgency=urgency,
            context=f"Your portfolio is heavily concentrated in {max_sector} ({max_pct:.1f}%). "
                    f"If this sector underperforms, your entire portfolio could suffer significant losses. "
                    f"Sector-specific risks (regulation, technology disruption, economic cycles) are amplified.",
            suggested_action=f"Consider reducing {max_sector} exposure to 25-30% and diversifying into "
                           f"defensive sectors (Healthcare, Consumer Staples) or uncorrelated sectors.",
        ))
    
    # Check for missing defensive sectors
    defensive_sectors = {"Healthcare", "Consumer Staples", "Utilities"}
    present_defensive = set(sector_exposure.keys()) & defensive_sectors
    
    if not present_defensive and len(tickers) >= 5:
        questions.append(PortfolioQuestion(
            question="Where is your downside protection?",
            category="risk",
            urgency="medium",
            context="Your portfolio has no exposure to defensive sectors (Healthcare, Consumer Staples, Utilities). "
                    "These sectors typically hold up better during market downturns and provide stability.",
            suggested_action="Add 15-25% allocation to defensive sectors to reduce portfolio volatility and "
                           "provide downside protection during corrections.",
        ))
    
    return questions


def generate_concentration_questions(
    concentration_risk: Dict[str, Any],
    tickers: List[str],
) -> List[PortfolioQuestion]:
    """Generate questions about position concentration."""
    questions = []
    
    top_3_pct = concentration_risk.get("top_3_concentration", 0)
    total_positions = concentration_risk.get("total_positions", 0)
    
    if top_3_pct > 50:
        questions.append(PortfolioQuestion(
            question=f"What happens if one of your top 3 holdings drops 30%?",
            category="risk",
            urgency="high",
            context=f"Your top 3 positions represent {top_3_pct:.0f}% of your portfolio. "
                    f"A 30% drop in just one position would cause a {(top_3_pct/3 * 0.3):.1f}% portfolio loss. "
                    f"This concentration creates significant single-stock risk.",
            suggested_action="Reduce top 3 concentration to under 40% by trimming winners and "
                           "adding new positions. No single stock should exceed 15% of portfolio.",
        ))
    
    if total_positions < 5:
        questions.append(PortfolioQuestion(
            question=f"Is {total_positions} stocks enough diversification?",
            category="risk",
            urgency="high",
            context=f"With only {total_positions} positions, you're exposed to high idiosyncratic risk. "
                    f"Company-specific events (earnings misses, management changes, product failures) "
                    f"can dramatically impact your portfolio.",
            suggested_action="Increase to at least 10-15 positions across different sectors to reduce "
                           "company-specific risk while maintaining focus.",
        ))
    
    if total_positions > 30:
        questions.append(PortfolioQuestion(
            question=f"Can you really track {total_positions} stocks effectively?",
            category="behavioral",
            urgency="medium",
            context=f"With {total_positions} positions, you may be over-diversified. "
                    f"This makes it difficult to stay informed about each company and "
                    f"your portfolio will likely track the market index closely.",
            suggested_action="Consider consolidating to 15-25 high-conviction positions. "
                           "Focus on quality over quantity.",
        ))
    
    return questions


def generate_beta_questions(
    beta_analysis: Dict[str, Any],
    tickers: List[str],
) -> List[PortfolioQuestion]:
    """Generate questions about portfolio beta and volatility."""
    questions = []
    
    portfolio_beta = beta_analysis.get("portfolio_beta")
    if portfolio_beta is None:
        return questions
    
    if portfolio_beta > 1.3:
        volatility_increase = (portfolio_beta - 1) * 100
        questions.append(PortfolioQuestion(
            question=f"Are you prepared for {volatility_increase:.0f}% more volatility than the market?",
            category="risk",
            urgency="high",
            context=f"Your portfolio beta is {portfolio_beta:.2f}, meaning it's {volatility_increase:.0f}% "
                    f"more volatile than the market. When the market drops 10%, you could drop {portfolio_beta * 10:.1f}%. "
                    f"But you also get amplified gains in bull markets.",
            suggested_action="If this volatility is uncomfortable, add lower-beta stocks (Consumer Staples, Utilities) "
                           "or reduce position sizes in high-beta names. Target beta of 1.0-1.2 for balanced risk.",
        ))
    
    if portfolio_beta < 0.7:
        questions.append(PortfolioQuestion(
            question="Are you willing to underperform in bull markets?",
            category="opportunity",
            urgency="medium",
            context=f"Your portfolio beta is {portfolio_beta:.2f}, meaning you'll likely underperform "
                    f"when the market rallies. While this provides downside protection, you're sacrificing "
                    f"upside potential in strong markets.",
            suggested_action="If you want more market participation, add growth stocks or increase exposure "
                           "to cyclical sectors. Consider if your low-beta stance matches your investment goals.",
        ))
    
    high_beta_count = beta_analysis.get("high_beta_count", 0)
    if high_beta_count >= 3:
        questions.append(PortfolioQuestion(
            question=f"Why do you have {high_beta_count} high-beta stocks?",
            category="risk",
            urgency="medium",
            context=f"You have {high_beta_count} stocks with beta > 1.2. These amplify both gains and losses. "
                    f"In a correction, these will likely fall harder than the market.",
            suggested_action="Review if all high-beta positions are justified by strong conviction. "
                           "Consider reducing sizes or adding hedges.",
        ))
    
    return questions


def generate_correlation_questions(
    correlation_clusters: List[List[str]],
    sector_exposure: Dict[str, float],
) -> List[PortfolioQuestion]:
    """Generate questions about correlation and diversification."""
    questions = []
    
    if not correlation_clusters:
        return questions
    
    largest_cluster = max(correlation_clusters, key=len)
    
    if len(largest_cluster) >= 4:
        questions.append(PortfolioQuestion(
            question=f"Are {len(largest_cluster)} correlated stocks really diversified?",
            category="risk",
            urgency="medium",
            context=f"You have {len(largest_cluster)} stocks that likely move together: "
                    f"{', '.join(largest_cluster[:5])}{'...' if len(largest_cluster) > 5 else ''}. "
                    f"When one drops, they all tend to drop. Your diversification benefit is limited.",
            suggested_action="Add stocks from uncorrelated sectors or with different business models. "
                           "True diversification requires low correlation, not just different ticker symbols.",
        ))
    
    return questions


def generate_macro_questions(
    tickers: List[str],
    sector_exposure: Dict[str, float],
    beta_analysis: Dict[str, Any],
) -> List[PortfolioQuestion]:
    """Generate questions about macro environment and portfolio positioning."""
    questions = []
    
    # Interest rate sensitivity
    rate_sensitive_sectors = {"Real Estate", "Utilities", "Financials"}
    rate_exposure = sum(
        pct for sector, pct in sector_exposure.items()
        if sector in rate_sensitive_sectors
    )
    
    if rate_exposure > 30:
        questions.append(PortfolioQuestion(
            question="How will your portfolio perform if rates rise?",
            category="macro",
            urgency="high",
            context=f"You have {rate_exposure:.0f}% in rate-sensitive sectors (Real Estate, Utilities, Financials). "
                    f"Rising interest rates typically hurt these sectors as borrowing costs increase and "
                    f"dividend yields become less attractive relative to bonds.",
            suggested_action="Monitor Fed policy closely. Consider reducing rate-sensitive exposure or "
                           "adding rate-beneficiary sectors (Financials can benefit from higher rates).",
        ))
    
    # Growth vs Value
    growth_sectors = {"Technology", "Communication Services", "Consumer Discretionary"}
    growth_exposure = sum(
        pct for sector, pct in sector_exposure.items()
        if sector in growth_sectors
    )
    
    if growth_exposure > 60:
        questions.append(PortfolioQuestion(
            question="Are you implicitly betting on continued low rates and growth?",
            category="macro",
            urgency="medium",
            context=f"Your portfolio is {growth_exposure:.0f}% in growth sectors. "
                    f"This positioning works well in low-rate environments but can underperform "
                    f"when rates rise or during value rotations.",
            suggested_action="Consider adding value exposure (Financials, Energy, Industrials) "
                           "to balance your growth tilt and reduce macro sensitivity.",
        ))
    
    return questions


def generate_behavioral_questions(
    tickers: List[str],
    risk_score: float,
) -> List[PortfolioQuestion]:
    """Generate questions about investor behavior and psychology."""
    questions = []
    
    if risk_score > 60:
        questions.append(PortfolioQuestion(
            question="Have you stress-tested your emotional response to a 30% drawdown?",
            category="behavioral",
            urgency="high",
            context=f"Your portfolio risk score is {risk_score:.0f}/100 (high risk). "
                    f"In a market correction, you could experience significant losses. "
                    f"Many investors panic-sell at the bottom, locking in losses.",
            suggested_action="Write down your plan for a 20-30% drawdown NOW, before it happens. "
                           "Decide in advance: will you hold, buy more, or rebalance? "
                           "Having a plan prevents emotional decisions.",
        ))
    
    return questions


def generate_portfolio_questions(
    tickers: List[str],
    risk_profile_dict: Dict[str, Any],
) -> List[PortfolioQuestion]:
    """
    Main function: Generate critical questions about the portfolio.
    Returns list of PortfolioQuestion objects prioritized by urgency.
    """
    logger.info("Generating portfolio questions for %d tickers", len(tickers))
    
    questions: List[PortfolioQuestion] = []
    
    # Extract risk profile components
    sector_exposure = risk_profile_dict.get("sector_exposure", {})
    concentration_risk = risk_profile_dict.get("concentration_risk", {})
    beta_analysis = risk_profile_dict.get("beta_analysis", {})
    correlation_clusters = risk_profile_dict.get("correlation_clusters", [])
    risk_score = risk_profile_dict.get("risk_score", 0.0)
    
    # Generate questions from each category
    questions.extend(generate_sector_concentration_questions(sector_exposure, tickers))
    questions.extend(generate_concentration_questions(concentration_risk, tickers))
    questions.extend(generate_beta_questions(beta_analysis, tickers))
    questions.extend(generate_correlation_questions(correlation_clusters, sector_exposure))
    questions.extend(generate_macro_questions(tickers, sector_exposure, beta_analysis))
    questions.extend(generate_behavioral_questions(tickers, risk_score))
    
    # Sort by urgency (high -> medium -> low)
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    questions.sort(key=lambda q: urgency_order.get(q.urgency, 3))
    
    # Limit to top 8 most critical questions
    questions = questions[:8]
    
    logger.info(
        "Generated %d portfolio questions | high=%d medium=%d low=%d",
        len(questions),
        sum(1 for q in questions if q.urgency == "high"),
        sum(1 for q in questions if q.urgency == "medium"),
        sum(1 for q in questions if q.urgency == "low"),
    )
    
    return questions

# Made with Bob
