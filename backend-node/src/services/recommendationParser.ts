/**
 * Parse BUY/SELL/HOLD from report content. Port of backend/services/recommendation_parser.py
 */

export interface ParsedRecommendation {
  recommendation: "BUY" | "SELL" | "HOLD";
  confidence: number | null;
  source: string;
}

export function parseRecommendation(reportContent: string | null | undefined): ParsedRecommendation | null {
  if (!reportContent?.trim()) return null;

  const content = reportContent;

  let m = content.match(/\*\*Recommendation:\s*(Buy|Sell|Hold)\*\*/i);
  if (m) {
    return {
      recommendation: m[1].toUpperCase() as "BUY" | "SELL" | "HOLD",
      confidence: 1.0,
      source: "final_trade_decision",
    };
  }

  m = content.match(/FINAL TRANSACTION PROPOSAL:\s*\*\*(Buy|Sell|Hold)\*\*/i);
  if (m) {
    return {
      recommendation: m[1].toUpperCase() as "BUY" | "SELL" | "HOLD",
      confidence: 0.9,
      source: "trader_investment_plan",
    };
  }

  const patterns: RegExp[] = [
    /Recommendation:\s*(Buy|Sell|Hold)/i,
    /recommendation:\s*["']?(Buy|Sell|Hold)["']?/i,
    /decision to\s*\*\*(Buy|Sell|Hold)\*\*/i,
    /recommendation is to\s*(buy|sell|hold)/i,
    /recommend\s*(buying|selling|holding)/i,
  ];

  for (const pattern of patterns) {
    m = content.match(pattern);
    if (m) {
      const recText = m[1].toUpperCase();
      let rec: "BUY" | "SELL" | "HOLD";
      if (recText.includes("BUY") || recText === "BUYING") rec = "BUY";
      else if (recText.includes("SELL") || recText === "SELLING") rec = "SELL";
      else if (recText.includes("HOLD") || recText === "HOLDING") rec = "HOLD";
      else continue;
      return { recommendation: rec, confidence: 0.7, source: "general_parsing" };
    }
  }

  return null;
}
