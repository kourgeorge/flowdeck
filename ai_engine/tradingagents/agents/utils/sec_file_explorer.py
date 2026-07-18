"""
Agent-side SEC filing exploration - like a coding agent exploring files.
Provides grep, head, tail, section extraction on SEC filings.
"""

import json
import re
from typing import List, Dict, Any, Optional
from collections import Counter


class SECFilingExplorer:
    """
    File explorer for SEC filings - provides grep, section extraction, etc.
    Agent uses this to explore filing like exploring code files.
    """
    
    def __init__(self, filing_text: str, filing_metadata: Dict[str, Any]):
        self.text = filing_text
        self.metadata = filing_metadata
        self.lines = filing_text.split('\n')
    
    def grep(
        self,
        pattern: str,
        context_lines: int = 3,
        max_results: int = 10,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search filing for pattern (like grep -C).
        
        Args:
            pattern: Regex pattern to search
            context_lines: Lines of context before/after match
            max_results: Maximum matches to return
            case_sensitive: Case-sensitive search
        
        Returns:
            List of matches with context
        """
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags=flags)
        except re.error:
            return []
        
        matches = []
        for i, line in enumerate(self.lines):
            if regex.search(line):
                context_start = max(0, i - context_lines)
                context_end = min(len(self.lines), i + context_lines + 1)
                
                matches.append({
                    "line_number": i + 1,
                    "matched_line": line.strip(),
                    "context_before": [self.lines[j].strip() for j in range(context_start, i)],
                    "context_after": [self.lines[j].strip() for j in range(i + 1, context_end)],
                })
                
                if len(matches) >= max_results:
                    break
        
        return matches
    
    def head(self, lines: int = 100) -> str:
        """Get first N lines (like head -n)."""
        return '\n'.join(self.lines[:lines])
    
    def tail(self, lines: int = 100) -> str:
        """Get last N lines (like tail -n)."""
        return '\n'.join(self.lines[-lines:])
    
    def get_lines(self, start: int, end: int) -> str:
        """Get specific line range (1-indexed)."""
        start_idx = max(0, start - 1)
        end_idx = min(len(self.lines), end)
        return '\n'.join(self.lines[start_idx:end_idx])
    
    def find_section(self, section_name: str, max_chars: int = 20000) -> Optional[str]:
        """
        Find and extract section by name (like finding a function in code).
        
        Args:
            section_name: risk_factors, mda, business, competition, etc.
            max_chars: Maximum characters to return
        
        Returns:
            Section text or None if not found
        """
        patterns = {
            "risk_factors": [
                r"Item 1A\.?\s*Risk Factors",
                r"ITEM 1A\.?\s*RISK FACTORS",
            ],
            "mda": [
                r"Item 7\.?\s*Management'?s Discussion and Analysis",
                r"ITEM 7\.?\s*MANAGEMENT'?S DISCUSSION AND ANALYSIS",
            ],
            "business": [
                r"Item 1\.?\s*Business",
                r"ITEM 1\.?\s*BUSINESS",
            ],
            "competition": [
                r"Competition",
                r"COMPETITION",
                r"Competitive",
            ],
            "legal_proceedings": [
                r"Item 3\.?\s*Legal Proceedings",
                r"ITEM 3\.?\s*LEGAL PROCEEDINGS",
            ],
            "market_risk": [
                r"Item 7A\.?\s*Quantitative and Qualitative",
                r"ITEM 7A\.?\s*QUANTITATIVE AND QUALITATIVE",
            ],
        }
        
        section_patterns = patterns.get(section_name, [])
        if not section_patterns:
            return None
        
        for pattern in section_patterns:
            match = re.search(pattern, self.text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                
                # Find next section or take max_chars
                next_section = re.search(
                    r"\n\s*Item \d+[A-Z]?\.?\s+[A-Z]",
                    self.text[start_pos + 100:],
                    re.IGNORECASE
                )
                
                if next_section:
                    end_pos = start_pos + 100 + next_section.start()
                else:
                    end_pos = start_pos + max_chars
                
                section_text = self.text[start_pos:end_pos].strip()
                
                if len(section_text) > max_chars:
                    section_text = section_text[:max_chars] + "\n... (truncated)"
                
                return section_text
        
        return None
    
    def get_toc(self) -> List[Dict[str, Any]]:
        """
        Generate table of contents (like listing functions in a code file).
        
        Returns:
            List of sections with metadata
        """
        sections = []
        pattern = re.compile(r"^\s*(Item|ITEM)\s+(\d+[A-Z]?)\.?\s+(.+)$", re.IGNORECASE)
        
        for i, line in enumerate(self.lines):
            match = pattern.match(line)
            if match:
                item_num = match.group(2)
                name = match.group(3).strip()
                
                # Find next section to calculate size
                next_line = None
                for j in range(i + 1, len(self.lines)):
                    if pattern.match(self.lines[j]):
                        next_line = j
                        break
                
                if next_line:
                    section_lines = self.lines[i:next_line]
                else:
                    section_lines = self.lines[i:min(i + 1000, len(self.lines))]
                
                section_text = '\n'.join(section_lines)
                
                sections.append({
                    "item": item_num,
                    "name": name,
                    "line_start": i + 1,
                    "line_end": next_line if next_line else len(self.lines),
                    "char_count": len(section_text),
                    "preview": section_text[:200].strip() + "...",
                })
        
        return sections
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filing statistics."""
        words = re.findall(r'\b[a-z]{4,}\b', self.text.lower())
        common_words = {'the', 'and', 'or', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were'}
        word_counts = Counter(w for w in words if w not in common_words)

        return {
            "total_chars": len(self.text),
            "total_words": len(words),
            "total_lines": len(self.lines),
            "top_terms": word_counts.most_common(20),
        }

    # ------------------------------------------------------------------
    # Intelligence-extraction methods (deterministic regex, no LLM)
    # ------------------------------------------------------------------

    def _grep_patterns(
        self,
        patterns: List[str],
        context_lines: int = 3,
        max_results: int = 15,
        signal_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run multiple regex patterns over the filing and return de-duplicated
        matches with line context.  Each result dict carries:
          line_number, matched_line, context_before, context_after, signal_type
        Results are deduplicated by line number (first pattern wins).
        """
        seen_lines: set = set()
        matches: List[Dict[str, Any]] = []

        for pattern in patterns:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                continue
            for i, line in enumerate(self.lines):
                if i in seen_lines:
                    continue
                if regex.search(line):
                    seen_lines.add(i)
                    ctx_start = max(0, i - context_lines)
                    ctx_end = min(len(self.lines), i + context_lines + 1)
                    matches.append({
                        "line_number": i + 1,
                        "matched_line": line.strip(),
                        "context_before": [self.lines[j].strip() for j in range(ctx_start, i)],
                        "context_after": [self.lines[j].strip() for j in range(i + 1, ctx_end)],
                        "signal_type": signal_type or pattern,
                    })
                    if len(matches) >= max_results:
                        return sorted(matches, key=lambda m: m["line_number"])

        return sorted(matches, key=lambda m: m["line_number"])

    def extract_competitors(self, max_results: int = 15) -> str:
        """
        Mine the filing for sentences that name or describe competitors.

        Targets Item 1 Competition subsection language:
          "We compete with ...", "Our competitors include ...",
          "competitive landscape", market-leadership references, etc.

        Returns a JSON string with structure:
          {
            "total_matches": int,
            "signals": [
              {
                "line_number": int,
                "matched_line": str,
                "context_before": [str],
                "context_after": [str],
                "signal_type": str
              }
            ],
            "summary": str          # human-readable header for the agent
          }
        Returns JSON with total_matches=0 when nothing is found.
        """
        patterns = [
            r"[Ww]e compete with",
            r"[Oo]ur (primary |main |direct |key )?competitors? (include|are|consist)",
            r"competes? (directly |primarily )?with",
            r"competitive landscape",
            r"[Cc]ompetition (includes?|comes from|is (provided|offered))",
            r"[Cc]ompete (against|for)",
            r"[Mm]arket (leader|participant|incumbent)",
            r"[Rr]ivals?",
            r"[Cc]ompetitors? such as",
            r"[Cc]ompeting (product|solution|service|platform|provider)",
        ]
        signals = self._grep_patterns(patterns, context_lines=3, max_results=max_results, signal_type="competitor")
        result: Dict[str, Any] = {
            "total_matches": len(signals),
            "signals": signals,
            "summary": (
                f"Found {len(signals)} competitor signal(s) in filing."
                if signals
                else "No competitor signals found in filing."
            ),
        }
        return json.dumps(result, indent=2)

    def extract_tam_disclosures(self, max_results: int = 10) -> str:
        """
        Mine the filing for Total Addressable Market (TAM), Serviceable
        Addressable Market (SAM), and CAGR disclosures.

        Companies disclose third-party market size estimates (Gartner, IDC, etc.)
        inside Item 1 Business Overview to describe their growth opportunity.

        Returns a JSON string with structure:
          {
            "total_matches": int,
            "signals": [
              {
                "line_number": int,
                "matched_line": str,
                "context_before": [str],
                "context_after": [str],
                "signal_type": str   # e.g. "dollar_market_size", "cagr", "tam_label"
              }
            ],
            "summary": str
          }
        """
        # Run each category with its own signal_type label so the agent can
        # distinguish a "$5 billion market" claim from a "CAGR of 18%" claim.
        all_signals: List[Dict[str, Any]] = []

        categories: List[tuple] = [
            ("tam_label", [
                r"total addressable market",
                r"\bTAM\b",
                r"serviceable addressable market",
                r"\bSAM\b",
                r"serviceable obtainable market",
                r"\bSOM\b",
            ]),
            ("dollar_market_size", [
                r"\$[\d,\.]+\s*(billion|trillion)\s*(market|opportunity|industry|sector|TAM|SAM)",
                r"(market|industry|sector)\s*(size|opportunity)\s*(of|is|was|estimated|valued).*\$[\d,\.]",
                r"(estimated|valued|worth)\s*(at|around|approximately)?\s*\$[\d,\.]",
            ]),
            ("cagr", [
                r"\bCAGR\b",
                r"compound annual growth rate",
                r"growing at\s+[\d\.]+\s*%",
                r"expected to grow.*[\d\.]+\s*%",
                r"projected.*growth.*[\d\.]+\s*%",
            ]),
            ("market_opportunity", [
                r"market (size|opportunity|potential)",
                r"(industry|market) is (projected|expected|estimated|forecast)",
                r"(large|significant|growing|expanding|underpenetrated) (market|opportunity)",
            ]),
        ]

        seen_lines: set = set()
        for signal_type, patterns in categories:
            for match in self._grep_patterns(patterns, context_lines=3, max_results=max_results, signal_type=signal_type):
                if match["line_number"] not in seen_lines:
                    seen_lines.add(match["line_number"])
                    all_signals.append(match)
            if len(all_signals) >= max_results:
                break

        all_signals = sorted(all_signals[:max_results], key=lambda m: m["line_number"])
        result: Dict[str, Any] = {
            "total_matches": len(all_signals),
            "signals": all_signals,
            "summary": (
                f"Found {len(all_signals)} TAM/market-size signal(s) in filing."
                if all_signals
                else "No TAM or market-size disclosures found in filing."
            ),
        }
        return json.dumps(result, indent=2)

    def extract_customer_concentration(self, max_results: int = 10) -> str:
        """
        Mine the filing for customer and supplier concentration disclosures.

        Under ASC 280, public companies must disclose customers that exceed 10%
        of total revenue. Supplier concentration appears in risk factors.

        Returns a JSON string with structure:
          {
            "total_matches": int,
            "signals": [
              {
                "line_number": int,
                "matched_line": str,
                "context_before": [str],
                "context_after": [str],
                "signal_type": str   # "customer_revenue_pct", "sole_supplier", etc.
              }
            ],
            "summary": str
          }
        """
        categories: List[tuple] = [
            ("customer_revenue_pct", [
                r"accounted for\s+[\d\.]+\s*%",
                r"represented\s+[\d\.]+\s*%\s*(of|our)\s*(net\s+)?(revenue|sales)",
                r"[\d\.]+\s*%\s*(of|our)\s*(net\s+)?(revenue|sales|billings).*customer",
                r"percent of (our |total )?(net\s+)?revenues?",
            ]),
            ("major_customer", [
                r"(major|significant|key|large|important) customer",
                r"(single|one) customer",
                r"customer concentration",
                r"no (single |one )?customer (accounted|represented|exceeded)",
            ]),
            ("sole_supplier", [
                r"sole (source )?supplier",
                r"single(-| )source",
                r"sole(-| )source",
                r"only (source|supplier) of",
            ]),
            ("supplier_concentration", [
                r"supplier concentration",
                r"(limited|few) (number of )?suppliers?",
                r"supply (chain )?(risk|disruption|shortage)",
                r"(key|critical|primary) (component|material|ingredient).*supplier",
            ]),
        ]

        all_signals: List[Dict[str, Any]] = []
        seen_lines: set = set()

        for signal_type, patterns in categories:
            for match in self._grep_patterns(patterns, context_lines=3, max_results=max_results, signal_type=signal_type):
                if match["line_number"] not in seen_lines:
                    seen_lines.add(match["line_number"])
                    all_signals.append(match)
            if len(all_signals) >= max_results:
                break

        all_signals = sorted(all_signals[:max_results], key=lambda m: m["line_number"])
        result: Dict[str, Any] = {
            "total_matches": len(all_signals),
            "signals": all_signals,
            "summary": (
                f"Found {len(all_signals)} customer/supplier concentration signal(s) in filing."
                if all_signals
                else "No customer or supplier concentration disclosures found in filing."
            ),
        }
        return json.dumps(result, indent=2)

    def extract_porter_signals(self, max_results: int = 20) -> str:
        """
        Mine Item 1A Risk Factors for language that maps to Porter's Five Forces.

        Each matched line is tagged with the force it represents:
          - rivalry        : pricing pressure, market share competition
          - new_entrants   : barriers to entry, capital requirements
          - substitutes    : switching costs, alternative products
          - buyer_power    : customer bargaining, volume discounts
          - supplier_power : supplier concentration, sole-source risk

        Returns a JSON string with structure:
          {
            "total_matches": int,
            "by_force": {
              "rivalry":        [ {line_number, matched_line, context_before, context_after, signal_type} ],
              "new_entrants":   [...],
              "substitutes":    [...],
              "buyer_power":    [...],
              "supplier_power": [...]
            },
            "summary": str
          }
        """
        force_patterns: List[tuple] = [
            ("rivalry", [
                r"pricing pressure",
                r"price competition",
                r"competitive pressure",
                r"(compete|competition) on (price|cost)",
                r"aggressively pric",
                r"market share",
                r"(intense|increased|growing) competition",
                r"(discount|lower|reduce)\s+price",
            ]),
            ("new_entrants", [
                r"barriers? to entry",
                r"new entrant",
                r"ease of entry",
                r"low (barriers?|cost) (to|of) entry",
                r"capital requirement",
                r"(difficult|hard) (for|to) (enter|compete)",
                r"established (brand|reputation|position)",
            ]),
            ("substitutes", [
                r"substitute (product|service|solution|technology)",
                r"alternative (product|solution|service|technology|platform)",
                r"switching cost",
                r"customers? (may|could|might) switch",
                r"replace(d|ment)? (by|with) (alternative|new|different)",
                r"disruptive (technology|innovation)",
            ]),
            ("buyer_power", [
                r"bargaining (power|leverage)",
                r"customer (leverage|concentration|demand|negotiat)",
                r"volume (discount|pricing|rebate)",
                r"(large|significant|major) customer",
                r"customer (churn|attrition|retention)",
                r"price (sensitive|sensitivity)",
            ]),
            ("supplier_power", [
                r"sole (source )?supplier",
                r"single(-| )source",
                r"supplier (leverage|concentration|risk|power)",
                r"(raw material|component|ingredient) (supply|shortage|cost|price)",
                r"(limited|few) (number of )?suppliers?",
                r"(increase|raise) (the )?price.*supplier",
            ]),
        ]

        by_force: Dict[str, List[Dict[str, Any]]] = {}
        per_force_limit = max(4, max_results // len(force_patterns))
        seen_lines: set = set()
        total = 0

        for force, patterns in force_patterns:
            force_signals: List[Dict[str, Any]] = []
            for match in self._grep_patterns(patterns, context_lines=2, max_results=per_force_limit, signal_type=force):
                if match["line_number"] not in seen_lines:
                    seen_lines.add(match["line_number"])
                    force_signals.append(match)
            by_force[force] = sorted(force_signals, key=lambda m: m["line_number"])
            total += len(force_signals)

        # Build a plain-text summary listing which forces have signals
        active_forces = [f for f, sigs in by_force.items() if sigs]
        if active_forces:
            summary = (
                f"Found {total} Porter's Five Forces signal(s) across: "
                + ", ".join(active_forces) + "."
            )
        else:
            summary = "No Porter's Five Forces signals found in filing."

        result: Dict[str, Any] = {
            "total_matches": total,
            "by_force": by_force,
            "summary": summary,
        }
        return json.dumps(result, indent=2)

# Made with Bob
