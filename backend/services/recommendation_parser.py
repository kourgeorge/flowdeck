"""Service to parse BUY/SELL/HOLD recommendations from reports into structured schema."""

import re
from typing import Optional
from pathlib import Path

from models.schemas import ParsedRecommendation


class RecommendationParser:
    """Parse recommendations from report files; returns Pydantic ParsedRecommendation."""

    @staticmethod
    def parse_recommendation(report_content: str) -> Optional[ParsedRecommendation]:
        """
        Parse recommendation from report content.

        Returns:
            ParsedRecommendation with recommendation (BUY/SELL/HOLD), confidence, source,
            or None if no recommendation found.
        """
        if not report_content:
            return None

        # Try final_trade_decision pattern first
        pattern1 = r'\*\*Recommendation:\s*(Buy|Sell|Hold)\*\*'
        match = re.search(pattern1, report_content, re.IGNORECASE)
        if match:
            return ParsedRecommendation(
                recommendation=match.group(1).upper(),
                confidence=1.0,
                source="final_trade_decision"
            )

        # Try trader_investment_plan pattern
        pattern2 = r'FINAL TRANSACTION PROPOSAL:\s*\*\*(Buy|Sell|Hold)\*\*'
        match = re.search(pattern2, report_content, re.IGNORECASE)
        if match:
            return ParsedRecommendation(
                recommendation=match.group(1).upper(),
                confidence=0.9,
                source="trader_investment_plan"
            )

        # Try alternative patterns
        patterns = [
            r'Recommendation:\s*(Buy|Sell|Hold)',
            r'recommendation:\s*["\']?(Buy|Sell|Hold)["\']?',  # YAML frontmatter
            r'decision to\s*\*\*(Buy|Sell|Hold)\*\*',  # "the decision to **Buy** is prescribed"
            r'recommendation is to\s*(buy|sell|hold)',
            r'recommend\s*(buying|selling|holding)',
        ]
        for pattern in patterns:
            match = re.search(pattern, report_content, re.IGNORECASE)
            if match:
                rec_text = match.group(1).upper()
                if 'BUY' in rec_text or rec_text == 'BUYING':
                    rec = 'BUY'
                elif 'SELL' in rec_text or rec_text == 'SELLING':
                    rec = 'SELL'
                elif 'HOLD' in rec_text or rec_text == 'HOLDING':
                    rec = 'HOLD'
                else:
                    continue
                return ParsedRecommendation(
                    recommendation=rec,
                    confidence=0.7,
                    source="general_parsing"
                )

        return None

    @staticmethod
    def get_recommendation_from_file(file_path: Path) -> Optional[ParsedRecommendation]:
        """Get recommendation from a report file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return RecommendationParser.parse_recommendation(content)
        except Exception:
            return None

