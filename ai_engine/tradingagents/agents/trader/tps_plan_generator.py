"""
TPS Plan Generator
==================
An additional LLM processing step that takes the trader's narrative investment
plan and emits a structured TPS-YAML v0.1 trading plan.

The specification and JSON schema are loaded at import time from:
  backend/TPS/TPS-YAML-v0.1-1.yaml
  backend/TPS/TPS-YAML-v0.1.schema-1.json
"""

import functools
from pathlib import Path

from langchain_core.messages import AIMessage

# ---------------------------------------------------------------------------
# Load TPS spec files once at import time
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
# Walk up to the repo root (4 levels: trader -> agents -> tradingagents -> ai_engine -> repo)
_REPO_ROOT = _HERE.parents[4]
_TPS_DIR = _REPO_ROOT / "backend" / "TPS"

_TPS_SPEC = (_TPS_DIR / "TPS-YAML-v0.1-1.yaml").read_text(encoding="utf-8")
_TPS_SCHEMA = (_TPS_DIR / "TPS-YAML-v0.1.schema-1.json").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# System prompt – references the loaded spec/schema verbatim
# ---------------------------------------------------------------------------

TPS_PLAN_SYSTEM_PROMPT = f"""\
You are a trading plan formatter. Your ONLY job is to convert a trader's
narrative investment decision into a compact, machine-readable TPS-YAML v0.1
trading plan.

## TPS-YAML v0.1 Specification
{_TPS_SPEC}

## JSON Schema (for field validation reference)
```json
{_TPS_SCHEMA}
```

## Output rules
- Output ONLY a fenced YAML code block (```yaml ... ```) containing the plan.
- Do NOT add any prose, explanation, or commentary outside the code block.
- Use only the fields defined in the specification above; do not invent new fields.
- If a value cannot be reasonably inferred from the narrative, omit that field
  (never fabricate specific prices that are not mentioned or clearly implied).
- For `entry.near`, if only a single price is mentioned use that number; if a
  range or zone is mentioned use the "price ±percent%" band format.
- For `risk.stop`, use the stop-loss price mentioned in the narrative.
- For `risk.max_loss`, default to "1%" if not explicitly stated.
- For `timeframe`, default to "1D" if not explicitly stated.
- `side` must be "long" for BUY decisions and "short" for SELL/SHORT decisions;
  use "long" for HOLD decisions that maintain a long position.
"""


def create_tps_plan_generator(llm):
    """
    Returns a LangGraph node function that reads the trader's narrative plan
    from state and emits a TPS-YAML v0.1 structured plan into
    state["trader_tps_plan"].

    Args:
        llm: A LangChain chat model (quick_thinking_llm is sufficient).
    """

    def tps_plan_node(state, name):
        company_name = state["company_of_interest"]
        trader_plan = state.get("trader_investment_plan", "")
        recommendation = state.get("trader_recommendation", "")
        investment_plan = state.get("investment_plan", "")

        human_message = (
            f"Instrument: {company_name}\n"
            f"Trader recommendation: {recommendation}\n\n"
            f"Analyst investment plan summary:\n{investment_plan}\n\n"
            f"Trader narrative decision:\n{trader_plan}\n\n"
            "Please produce the TPS-YAML v0.1 trading plan for this instrument."
        )

        messages = [
            {"role": "system", "content": TPS_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": human_message},
        ]

        tps_plan = ""
        try:
            response = llm.invoke(messages)
            tps_plan = response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            tps_plan = f"# TPS plan generation failed: {exc}"

        return {
            "trader_tps_plan": tps_plan,
            "sender": name,
        }

    return functools.partial(tps_plan_node, name="TPS Plan Generator")

# Made with Bob
