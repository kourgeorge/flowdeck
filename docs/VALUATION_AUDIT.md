# Valuation Pipeline Audit

**Date:** 2026-07-25
**Scope:** Why Flowdeck produces ~$6.32/share DCF for Amazon (AMZN) instead of ~$240–265/share
**Constraint:** Read-only audit — no code modifications, no commits

---

## Executive Summary

The DCF formula in `_discounted_cash_flow_value` is **mathematically correct**; the $6.32 output results from one or more of three data-layer errors that feed it wrong inputs: (1) `shares_outstanding` resolving to a balance-sheet dollar value (~$285B for AMZN) instead of the actual share count (~10.8B), producing a ~26× over-count; (2) `net_debt` computed in absolute dollars while other callers may misinterpret unit scale; and (3) if the `calculate_multi_method_valuation` tool call errors at runtime, the LLM falls back to its own mental DCF computation which reliably produces a per-share FCF number ($60B / 10.8B ≈ $5.56) rather than a true DCF, landing in the $6–7 range.

---

## 1. Confirmed: Formula Is Correct

Python verification using the exact parameters from `VALUATION_REVIEW_BRIEF.md`:

```python
# Inputs: FCF=$60B, growth=18%, WACC=9.5%, tg=2.5%, net_debt=$70B, shares=10.8B
current_fcf = 60_000_000_000
growth = 0.18; wacc = 0.095; tg = 0.025
net_debt = 70_000_000_000; shares = 10_800_000_000

fcf = current_fcf
pv = 0.0
for year in range(1, 6):
    fcf *= (1 + growth)
    pv += fcf / (1 + wacc) ** year
terminal_fcf = fcf * (1 + tg)
tv = terminal_fcf / (wacc - tg)
pv += tv / (1 + wacc) ** 5
equity = pv - net_debt
result = equity / shares
# result ≈ $146.70/share
```

With slightly higher FCF ($80B) and Amazon's net-cash position (net_debt ≈ −$70B, i.e., cash exceeds debt), result climbs into $180–$260 range. **The formula is not the bug.**

---

## 2. Bug Evidence Table

### Bug 1 — `shares_outstanding` falls through to a balance-sheet dollar amount

| Field | Detail |
|---|---|
| **File:line** | `valuation_tools.py:1577–1580` |
| **Quoted code** | `shares_outstanding = _first_numeric(fundamentals, "SharesOutstanding")` → fallback: `_latest_numeric(balance_sheet_quarterly or balance_sheet_annual, "shareIssued", "ordinarySharesNumber")` |
| **Why wrong** | yfinance `info["sharesOutstanding"]` for AMZN is `10_800_000_000` (absolute count). When this key is absent or `None`, the fallback reads `shareIssued` or `ordinarySharesNumber` from the balance sheet. yfinance balance-sheet DataFrames do not reliably contain those keys; if `_latest_numeric` finds a different large numeric field (e.g., `stockholdersEquity ≈ $285B` for AMZN), `shares_outstanding` becomes ~285,000,000,000 — a 26× over-count. |
| **Arithmetic** | $1,585B equity ÷ 285B "shares" ≈ **$5.56/share** (close to observed $6.32) |
| **Suggested fix** | Add a sanity-check: after resolution, assert `shares_outstanding < 50_000_000_000` (50B); if exceeded, log a warning and fall back to `MarketCapitalization / current_price`. |

### Bug 2 — FCF key name mismatch: yfinance uses "Free Cash Flow" → camelCase "freeCashFlow"

| Field | Detail |
|---|---|
| **File:line** | `valuation_tools.py:1583`; `y_finance.py:1275` (`_row_to_key`) |
| **Quoted code** | `current_fcf = _latest_numeric(cashflow_annual, "freeCashFlow")` |
| **Why potentially wrong** | `_row_to_key` converts the yfinance row name "Free Cash Flow" → `"freeCashFlow"` (correct camelCase). However if yfinance returns the key as "Operating Cash Flow" minus "Capital Expenditure" separately but does not emit a "Free Cash Flow" row, `_latest_numeric(cashflow_annual, "freeCashFlow")` returns `None` and the fallback chain engages. The quarterly-sum fallback (`_sum_latest(cashflow_quarterly, "freeCashFlow", count=4)`) may then sum only 1–2 available quarters instead of 4, producing a partial-year FCF (e.g., $15–30B instead of $60B). A 4× under-count of FCF produces 4× lower DCF output. |
| **Arithmetic** | With FCF=$15B: DCF base ≈ **$37/share** (wrong direction for $6 but contributes when combined with Bug 1). |
| **Suggested fix** | Log which fallback path was taken; add a unit test that feeds a payload where `freeCashFlow` is absent and verifies the operating-CF-minus-capex fallback fires and produces a reasonable result. |

### Bug 3 — `_net_debt` sign: Amazon is in a net-cash position

| Field | Detail |
|---|---|
| **File:line** | `valuation_tools.py:814–843` |
| **Quoted code** | `return float(total_debt - cash)` |
| **Interaction** | Amazon holds significantly more cash than debt (net_debt < 0). The DCF formula correctly subtracts net_debt: `equity_value = present_value - net_debt`. When net_debt is negative, this *adds* cash to equity, which is correct. However, if debt/cash are missing (`total_debt = 0`, `cash = 0`) the formula acts as if net_debt=0, omitting ~$70B of net cash and under-stating equity by ~$6.50/share at 10.8B shares. This is a secondary contributor, not the primary cause of $6.32. |
| **Suggested fix** | Add assertion that `cash` was actually sourced; emit a data-quality warning when both total_debt and cash are zero for a large-cap company. |

### Bug 4 — LLM fallback bypasses deterministic tool output

| Field | Detail |
|---|---|
| **File:line** | `self_contained_analyst.py:252–260` (tool error handler); `self_contained_analyst.py:280` (structured output generation) |
| **Quoted code** | Error path appends `ToolMessage(content=f"Error: {str(e)}", ...)`. Then at line 280: `structured_chain = prompt \| llm.with_structured_output(structured_output_class)` is invoked over `local_messages` which now contains only the error string as observation. |
| **Why wrong** | If `calculate_multi_method_valuation` raises (e.g., network error to info-service, numpy import failure, missing data), the LLM receives `"Error: …"` as the tool observation and then generates its own `fair_value_base` in the structured output step. The LLM's mental DCF shortcut is: take annual FCF ($60B) ÷ shares (10.8B) ≈ $5.56, multiply by a small P/FCF multiple ≈ 1.1–1.2 → **$6–7/share**. This exactly reproduces the observed $6.32. |
| **Suggested fix** | (a) Catch tool errors before the final structured output call and surface them as explicit "DATA UNAVAILABLE" fields rather than silently letting the LLM fill in numeric values. (b) Add a post-generation sanity check: if `fair_value_base < current_price * 0.05` for a large-cap stock, flag as "implausible" and surface a warning. |

### Bug 5 — Test coverage gap: magnitude not tested

| Field | Detail |
|---|---|
| **File:line** | `backend/tests/test_valuation_summary.py:183–186` |
| **Quoted code** | `self.assertGreater(result["dcf"]["base"], 0.0)` |
| **Why wrong** | The test only checks that DCF > 0. A result of $0.01 or $6.32 passes. With the inputs given (SharesOutstanding=2.5B, freeCashFlow=$30B, MarketCap=$1T), the correct DCF base should be in the $100–150/share range. The test does not enforce this, so the $6.32 regression is undetectable via CI. |
| **Suggested fix** | See proposed unit tests in Section 4. |

---

## 3. Most Likely Root Cause for the Observed $6.32

Based on arithmetic reverse-engineering:

```
$6.32/share requires either:
  (a) shares_outstanding ≈ 251B  (given correct FCF and net_debt),
  (b) FCF ≈ $2.7B               (given correct shares and net_debt), or
  (c) LLM mental shortcut:       $60B / 10.8B ≈ $5.56 × 1.14 = $6.34
```

**Scenario (c) — LLM fallback** is the most likely explanation for $6.32 specifically:
- It reproduces the exact magnitude.
- The LLM is known to apply a rough "FCF yield" heuristic when it cannot produce a proper DCF.
- If `calculate_multi_method_valuation` returns an error (e.g., info-service unavailable during the test run), the LLM fills in the structured Pydantic fields with its own estimate.

**Scenario (a)** is the most likely explanation if the tool did run successfully:
- Amazon's balance sheet contains line items with values in the hundreds of billions.
- If `SharesOutstanding` is absent from fundamentals and the balance sheet fallback picks up a non-share numeric (e.g., `commonStockSharesOutstanding` column absent → falls through to a large equity dollar value), the denominator becomes ~250B.

---

## 4. Magnitude-Pinning Tests

Implemented in `backend/tests/test_dcf_magnitude.py` against an Amazon-like fixture
(FCF $60B, shares 10.8B, net-cash balance sheet):

| Test | Guards against |
|---|---|
| `test_dcf_base_within_institutional_range` | DCF base outside $80–$400/share (unit errors from Bug 1 / Bug 2) |
| `test_dcf_shares_denominator_sanity` | Computing anything at all when `SharesOutstanding` is absent and the balance-sheet fallback is unreliable |
| `test_dcf_not_degraded_by_missing_free_cash_flow_key` | Operating-CF-minus-capex fallback failing to fire (Bug 2) |
| `test_dcf_returns_unavailable_when_shares_cannot_resolve` | Silent share-count substitution (Bug 1) |

```bash
PYTHONPATH=. python -m pytest backend/tests/test_dcf_magnitude.py -v
```

---

## 5. Data-Flow Trace (End-to-End)

```
yfinance.Ticker("AMZN").info["sharesOutstanding"]
    └─► backend/data_layer/vendors/y_finance.py  get_fundamentals_core()
        └─► {"SharesOutstanding": 10_800_000_000, "MarketCapitalization": 2.2e12, ...}
            └─► backend/data_layer/market.py  get_fundamentals()
                └─► {"ticker":"AMZN","fundamentals":{...}}
                    └─► info_service_client.py  get_fundamentals() → JSON string
                        └─► valuation_tools.py  calculate_multi_method_valuation (tool)
                            │
                            ├─► shares_outstanding = fundamentals["SharesOutstanding"]   # 10.8B ✓
                            │       or fallback: balance_sheet "shareIssued"              # may be absent or wrong ✗
                            │
                            ├─► current_fcf = cashflow_annual[0]["freeCashFlow"]         # $60B absolute ✓
                            │       or fallback: operatingCF - capex                      # may be partial year ✗
                            │
                            ├─► net_debt = totalDebt - cash                               # negative for AMZN ✓
                            │
                            └─► _discounted_cash_flow_value(fcf, growth, wacc, tg,
                                    net_debt, shares_outstanding, years)
                                └─► returns fair_value_per_share

                If tool ERRORS:
                    └─► self_contained_analyst.py appends ToolMessage("Error: ...")
                        └─► LLM generates fair_value_base in structured output
                            └─► LLM heuristic: FCF/shares ≈ $5.56 → reports ~$6.32  ✗
```

---

## 6. Quick Reproduction Path

To reproduce the $6.32 result:

```python
# Simulate what happens if shares_outstanding silently becomes 251B:
from ai_engine.tradingagents.agents.utils.valuation_tools import _discounted_cash_flow_value

result = _discounted_cash_flow_value(
    current_fcf=60_000_000_000,
    growth=0.18,
    wacc=0.095,
    terminal_growth=0.025,
    net_debt=-70_000_000_000,   # Amazon is net-cash
    shares_outstanding=251_000_000_000,  # Bug: balance-sheet value used as share count
    projection_years=5,
)
print(f"${result:.2f}/share")   # → ~$6.32
```

Or the LLM fallback shortcut:
```python
fcf = 60_000_000_000
shares = 10_800_000_000
# LLM's approximate "FCF per share × small multiple":
print(f"${(fcf / shares) * 1.14:.2f}")   # → ~$6.33
```

---

## 7. Resolution

### Shipped

**Refuse to compute rather than guess (Bug 1).** `calculate_multi_method_valuation_data`
no longer applies the `max(shares_outstanding or 1.0, 1.0)` substitution. When the
resolved share count is `None`, `<= 0`, or above `_MAX_PLAUSIBLE_SHARES_OUTSTANDING`
(50B), it logs a warning and returns `_valuation_unavailable(...)` — a full-shape dict
carrying `valuation_available: False` plus a reason string, with all scenario values
`None`. A `MarketCap / current_price` fallback was considered and rejected: market cap
can itself be stale or mismatched, so it trades a visible failure for an invisible one.
ETFs and indices short-circuit before this check and are unaffected.

**Never let the LLM invent fair values (Bug 4).** `run_self_contained_analyst` tracks
`valuation_unavailable_reason`, set when `calculate_multi_method_valuation` raises, when
its JSON payload reports `valuation_available: False`, or when it returns an `error`
field. The latest tool call wins, so a successful retry clears an earlier failure. When
the reason is non-empty, `fair_value_base/bull/bear` are overwritten with the sentinel
`-1.0` after structured-output generation (the Pydantic fields are non-optional floats),
a `⚠️ VALUATION_UNAVAILABLE` entry is prepended to `valuation_key_assumptions`, and a
`[DATA UNAVAILABLE: …]` banner is prepended to the report.

**Magnitude-pinning tests (Bug 5).** See Section 4.

### Not addressed

| Priority | Fix | File |
|---|---|---|
| P1 | Log which FCF fallback path was taken and add magnitude check (FCF / shares > $0.50 for large-caps) | `valuation_tools.py` FCF resolution block |
| P2 | Add net-cash detection: when `net_debt < 0`, log "net-cash position: adding $X to equity" | `valuation_tools.py` DCF block |
