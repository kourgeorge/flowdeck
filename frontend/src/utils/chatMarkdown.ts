/**
 * Helpers to normalize chat markdown for display (e.g. convert ASCII tables to GFM).
 */

function isTableSeparatorLine(line: string): boolean {
  return /^[\s\u2500\-]+$/.test(line) && line.trim().length > 0;
}

function isPipeSeparatedRow(line: string): boolean {
  return /\s\|\s/.test(line.trim());
}

function toGfmTableRow(line: string): string {
  const trimmed = line.trim();
  const cells = trimmed.split(/\s\|\s/).map((c) => c.trim());
  return '| ' + cells.join(' | ') + ' |';
}

/**
 * Convert ASCII/box-drawing tables (e.g. "Indicator | INTC | NVDA" with ─── lines)
 * into proper GFM markdown so ReactMarkdown renders them as HTML tables.
 */
export function convertAsciiTableToMarkdown(content: string): string {
  if (!content) return content;
  const lines = content.split('\n');
  const out: string[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!isTableSeparatorLine(line) && !isPipeSeparatedRow(line)) {
      out.push(line);
      i++;
      continue;
    }
    const block: string[] = [];
    while (i < lines.length && (isTableSeparatorLine(lines[i]) || isPipeSeparatedRow(lines[i]))) {
      block.push(lines[i]);
      i++;
    }
    const hasSeparator = block.some((l) => isTableSeparatorLine(l));
    const pipeOnly = block.filter((l) => !isTableSeparatorLine(l));
    if (hasSeparator && pipeOnly.length >= 1) {
      const normalized = pipeOnly.map((l) => toGfmTableRow(l));
      const colCount = normalized[0].split('|').filter(Boolean).length;
      const sep = '|' + Array(colCount).fill('---').join('|') + '|';
      out.push(normalized[0], sep, ...normalized.slice(1));
    } else {
      block.forEach((l) => out.push(l));
    }
  }

  return out.join('\n');
}
