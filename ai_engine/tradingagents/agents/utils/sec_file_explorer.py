"""
Agent-side SEC filing exploration - like a coding agent exploring files.
Provides grep, head, tail, section extraction on SEC filings.
"""

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

# Made with Bob
