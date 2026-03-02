"""
Hardcoded skill implementations for the FlowDeck agent.

Skills are multi-step workflows that orchestrate multiple tools to accomplish
a higher-level goal. They are NOT exposed to the LLM as callable functions.
Instead, the SkillAgent detects intent and dispatches to the right skill.

Import ALL_SKILLS to get the full list ready for SkillRegistry.register_many().
"""

from ai_engine.agent.skills.stock_deep_dive import StockDeepDiveSkill
from ai_engine.agent.skills.portfolio_health import PortfolioHealthSkill
from ai_engine.agent.skills.compare_stocks import CompareStocksSkill
from ai_engine.agent.skills.portfolio_performance import PortfolioPerformanceSkill

ALL_SKILLS = [
    StockDeepDiveSkill(),
    PortfolioHealthSkill(),
    PortfolioPerformanceSkill(),
    CompareStocksSkill(),
]

__all__ = [
    "StockDeepDiveSkill",
    "PortfolioHealthSkill",
    "PortfolioPerformanceSkill",
    "CompareStocksSkill",
    "ALL_SKILLS",
]

# Made with Bob
