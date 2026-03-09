"""
Agent Skills for the FlowDeck agent.

Skills are multi-step workflows that orchestrate multiple tools to accomplish
a higher-level goal. Each skill is defined by:

  1. A SKILL.md file (agentskills.io standard) — contains the name, description,
     and instructions that are loaded into the LLM's context for discovery and
     activation. The LLM reads skill descriptions at startup and decides which
     skill to invoke based on the user's message.

  2. A Python class (BaseSkill subclass) — implements the deterministic
     multi-step workflow that runs once the LLM has selected the skill and
     extracted the arguments.

Progressive disclosure (per agentskills.io spec):
  - Discovery: only name + description are injected into the system prompt
  - Activation: the LLM selects the skill and extracts arguments
  - Execution: the Python skill class runs the workflow

Import ALL_SKILLS to get the full list ready for SkillRegistry.register_many().
Import SKILL_DESCRIPTIONS to get the {name: description} dict for the system prompt.
Import load_skill_md(name) to get the full SKILL.md body for a skill.
"""

from __future__ import annotations

import pathlib
import re
from typing import Optional

from ai_engine.agent.skills.stock_deep_dive import StockDeepDiveSkill
from ai_engine.agent.skills.portfolio_health import PortfolioHealthSkill
from ai_engine.agent.skills.compare_stocks import CompareStocksSkill
from ai_engine.agent.skills.portfolio_performance import PortfolioPerformanceSkill
from ai_engine.agent.skills.chart_creation import CreateChartSkill

ALL_SKILLS = [
    StockDeepDiveSkill(),
    PortfolioHealthSkill(),
    PortfolioPerformanceSkill(),
    CompareStocksSkill(),
    CreateChartSkill(),
]

# ---------------------------------------------------------------------------
# SKILL.md directory map: skill name → directory containing SKILL.md
# ---------------------------------------------------------------------------

_SKILLS_DIR = pathlib.Path(__file__).parent

SKILL_MD_DIRS: dict[str, pathlib.Path] = {
    "compare_stocks":        _SKILLS_DIR / "compare-stocks",
    "stock_deep_dive":       _SKILLS_DIR / "stock-deep-dive",
    "portfolio_health":      _SKILLS_DIR / "portfolio-health",
    "portfolio_performance": _SKILLS_DIR / "portfolio-performance",
    "chart_creation":        _SKILLS_DIR / "chart-creation",
}


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """
    Parse YAML frontmatter from a SKILL.md file.

    Returns (frontmatter_dict, body_text).
    Only handles simple key: value pairs (no nested YAML).
    """
    fm: dict[str, str] = {}
    body = text

    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            fm_block = text[3:end].strip()
            body = text[end + 3:].strip()
            for line in fm_block.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    fm[key.strip()] = val.strip()

    return fm, body


def load_skill_md(skill_name: str) -> Optional[str]:
    """
    Load and return the full content of a skill's SKILL.md file.

    Returns None if the file does not exist.
    """
    skill_dir = SKILL_MD_DIRS.get(skill_name)
    if skill_dir is None:
        return None
    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.exists():
        return None
    return skill_md_path.read_text(encoding="utf-8")


def get_skill_description(skill_name: str) -> Optional[str]:
    """
    Return only the description field from a skill's SKILL.md frontmatter.

    Used for the discovery phase: injected into the system prompt so the LLM
    knows what each skill does and when to use it.
    """
    content = load_skill_md(skill_name)
    if content is None:
        # Fall back to the Python spec description
        for skill in ALL_SKILLS:
            if skill.spec.name == skill_name:
                return skill.spec.description
        return None
    fm, _ = _parse_frontmatter(content)
    return fm.get("description")


# ---------------------------------------------------------------------------
# SKILL_DESCRIPTIONS: {skill_name: description} — for system prompt injection
# ---------------------------------------------------------------------------

SKILL_DESCRIPTIONS: dict[str, str] = {}
for _skill_name in SKILL_MD_DIRS:
    _desc = get_skill_description(_skill_name)
    if _desc:
        SKILL_DESCRIPTIONS[_skill_name] = _desc


__all__ = [
    "StockDeepDiveSkill",
    "PortfolioHealthSkill",
    "PortfolioPerformanceSkill",
    "CompareStocksSkill",
    "CreateChartSkill",
    "ALL_SKILLS",
    "SKILL_MD_DIRS",
    "SKILL_DESCRIPTIONS",
    "load_skill_md",
    "get_skill_description",
]

# Made with Bob
