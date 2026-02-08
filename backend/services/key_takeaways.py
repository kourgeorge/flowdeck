"""Extract 3-5 key takeaways from report markdown (heuristic)."""

import re
from typing import List


def extract_key_takeaways(content: str, max_items: int = 5) -> List[str]:
    """
    Extract up to max_items bullet points or numbered lines from report content.
    Used when key_takeaways are not stored in frontmatter (e.g. legacy reports).
    """
    if not content or not content.strip():
        return []

    takeaways: List[str] = []
    seen: set = set()

    # Prefer markdown bullets (-, *, •) and numbered lines (1. 2. etc.)
    bullet_pattern = re.compile(
        r'^[\s]*[-*•]\s+(.+)$',
        re.MULTILINE
    )
    numbered_pattern = re.compile(
        r'^[\s]*\d+[.)]\s+(.+)$',
        re.MULTILINE
    )

    for pattern in (bullet_pattern, numbered_pattern):
        for m in pattern.finditer(content):
            line = m.group(1).strip()
            # Skip very short or duplicate-looking lines
            if len(line) < 15:
                continue
            # Normalize for dedup
            key = line[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            # Strip trailing markdown
            line = re.sub(r'\s*\[.*?\]\s*$', '', line)
            if line:
                takeaways.append(line)
            if len(takeaways) >= max_items:
                return takeaways[:max_items]

    # Fallback: first N non-empty lines that look like sentences (end with . or :)
    if len(takeaways) < 2:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('---'):
                continue
            if len(line) < 20:
                continue
            key = line[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            takeaways.append(line)
            if len(takeaways) >= max_items:
                break

    return takeaways[:max_items]
