/**
 * Extract key takeaways from report markdown (heuristic). Port of backend/services/key_takeaways.py
 */

const BULLET_PATTERN = /^[\s]*[-*•]\s+(.+)$/gm;
const NUMBERED_PATTERN = /^[\s]*\d+[.)]\s+(.+)$/gm;

export function extractKeyTakeaways(content: string, maxItems: number = 5): string[] {
  if (!content?.trim()) return [];

  const takeaways: string[] = [];
  const seen = new Set<string>();

  for (const pattern of [BULLET_PATTERN, NUMBERED_PATTERN]) {
    pattern.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = pattern.exec(content)) !== null) {
      let line = m[1].trim();
      if (line.length < 15) continue;
      const key = line.slice(0, 80).toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      line = line.replace(/\s*\[.*?\]\s*$/, "").trim();
      if (line) takeaways.push(line);
      if (takeaways.length >= maxItems) return takeaways.slice(0, maxItems);
    }
  }

  if (takeaways.length < 2) {
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || trimmed.startsWith("---")) continue;
      if (trimmed.length < 20) continue;
      const key = trimmed.slice(0, 80).toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      takeaways.push(trimmed);
      if (takeaways.length >= maxItems) break;
    }
  }

  return takeaways.slice(0, maxItems);
}
