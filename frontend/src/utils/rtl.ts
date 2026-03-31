/**
 * Detect if text contains RTL (right-to-left) characters.
 * Returns true for Hebrew, Arabic, Persian, etc.
 */
export function detectRTL(text: string): boolean {
  if (!text) return false;
  
  // RTL Unicode ranges:
  // Hebrew: 0x0590-0x05FF
  // Arabic: 0x0600-0x06FF, 0x0750-0x077F, 0xFB50-0xFDFF, 0xFE70-0xFEFF
  let rtlChars = 0;
  let totalChars = 0;
  
  for (const char of text) {
    const code = char.charCodeAt(0);
    // Skip whitespace and punctuation
    if (/\s/.test(char) || !/\p{L}/u.test(char)) {
      continue;
    }
    totalChars++;
    // Check if character is in RTL range
    if (
      (code >= 0x0590 && code <= 0x05FF) ||  // Hebrew
      (code >= 0x0600 && code <= 0x06FF) ||  // Arabic
      (code >= 0x0750 && code <= 0x077F) ||  // Arabic Supplement
      (code >= 0xFB50 && code <= 0xFDFF) ||  // Arabic Presentation Forms-A
      (code >= 0xFE70 && code <= 0xFEFF)     // Arabic Presentation Forms-B
    ) {
      rtlChars++;
    }
  }
  
  // If more than 30% of characters are RTL, consider the text RTL
  return totalChars > 0 && (rtlChars / totalChars) > 0.3;
}

/**
 * Get the text direction ('rtl' or 'ltr') for a given text.
 */
export function getTextDirection(text: string): 'rtl' | 'ltr' {
  return detectRTL(text) ? 'rtl' : 'ltr';
}

// Made with Bob
