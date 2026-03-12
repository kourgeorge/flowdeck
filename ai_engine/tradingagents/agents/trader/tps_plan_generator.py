"""
TPS Plan Generator
==================
An additional LLM processing step that takes the trader's narrative investment
plan and emits a structured TPS-YAML v0.1 trading plan.

The JSON schema is loaded at import time from:
  backend/TPS/TPS-YAML-v0.1.schema-1.json
"""

import functools
from pathlib import Path

# ---------------------------------------------------------------------------
# Load TPS JSON schema once at import time
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
# Walk up to the repo root (4 levels: trader -> agents -> tradingagents -> ai_engine -> repo)
_REPO_ROOT = _HERE.parents[4]
_TPS_DIR = _REPO_ROOT / "backend" / "TPS"

_TPS_SCHEMA = (_TPS_DIR / "TPS-YAML-v0.1.schema-1.json").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# System prompt – schema + inline example
# ---------------------------------------------------------------------------

TPS_PLAN_SYSTEM_PROMPT = f"""\
You are a trading plan formatter. Your ONLY job is to convert a trader's
narrative investment decision into a compact, machine-readable TPS-YAML v0.1
trading plan.

## JSON Schema
The following JSON Schema defines every allowed field, its type, and the exact
string patterns required for pattern-constrained fields.
```json
{_TPS_SCHEMA}
```

## Canonical example
```yaml
instrument: META
timeframe: 1D
side: long

entry:
  near: "607.99 ±1%"
  scale: "40/30/30"
  confirm:
    - rsi < 45
    - macd_hist rising_2

risk:
  max_loss: "1%"
  max_position: "5%"
  stop: 595.83
  invalidate: "close < 595.83 for 2d -> exit"

take_profit:
  tp1: "640.64 sell 50%"
  trail: "4%"

vol_guard: "atr20 > 1.5x avg -> reduce 30%"
add_if: "macd bull & close > ma50 -> max_position 7%"
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
  CRITICAL: The stop MUST be directionally consistent with `side`:
    • side=long  → stop MUST be BELOW entry.near (protects against downside)
    • side=short → stop MUST be ABOVE entry.near (protects against upside)
  If the narrative's stop price violates this rule, correct it by placing the
  stop a reasonable distance on the correct side (1–2% beyond entry).
- For `risk.max_loss`, default to "1%" if not explicitly stated.
- For `timeframe`, default to "1D" if not explicitly stated.
- `side` must be "long" for BUY decisions and "short" for SELL/SHORT decisions;
  use "long" for HOLD decisions that maintain a long position.
  CRITICAL: Do NOT emit side="short" when the narrative only recommends
  reducing exposure, being defensive, or managing an existing long position.
  "Reduce exposure" / "tight stop-loss" / "risk management" language on a long
  position means side="long", NOT side="short".
- For `entry.scale`, reflect the sizing intent from the narrative:
  "reduce exposure" or "partial" → use a partial scale (e.g., "50"), not "100".
  "full position" or "enter" → scale="100" is appropriate.

## Cross-field consistency (verify ALL before emitting YAML)
1. stop direction:
   - side=long  → risk.stop < entry.near price (stop is below entry)
   - side=short → risk.stop > entry.near price (stop is above entry)
   Fix and correct if violated.
2. side vs narrative action verb:
   - "reduce", "hold", "defensive", "protect", "mitigate" → side=long
   - "enter short", "sell short", "open short" → side=short
3. scale vs sizing intent:
   - "reduce exposure" → partial scale, not "100"
   - "full entry" / "enter position" → scale="100"

## Self-check before output
Silently verify each item before writing the YAML block:
  [ ] risk.stop is on the correct side of entry.near for the declared side
  [ ] side matches the dominant action verb in the narrative
  [ ] scale reflects the sizing intent (partial vs full)
Only emit the YAML after all checks pass.
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


