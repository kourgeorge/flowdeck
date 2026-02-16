/**
 * Stock widgets and stock page. Same contract as Python backend.
 */

import { Router, Request, Response } from "express";
import { config } from "../config";
import { getQuote } from "../services/dataService";
import {
  getLatestReportDate,
  getReportsWithScores,
  getReportsForDate,
  getHistoricalAnalyses,
  getTickersWithReportsForDate,
} from "../services/reportService";
import { parseRecommendation } from "../services/recommendationParser";
import { getRunningAnalysisIdByTicker } from "../services/analysisOrchestrator";

export const stocksRouter = Router();

/** GET /api/stocks/widgets?tickers=&date= */
stocksRouter.get("/widgets", async (req: Request, res: Response) => {
  try {
    const tickersParam = (req.query.tickers as string) ?? "";
    const dateParam = (req.query.date as string) ?? "";
    let tickerList: string[];

    if (tickersParam.trim()) {
      tickerList = tickersParam.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);
    } else {
      const reportDate = dateParam || new Date().toISOString().slice(0, 10);
      const tickersForDate = getTickersWithReportsForDate(reportDate);
      const majorSet = new Set(config.MAJOR_STOCKS.map((t) => t.toUpperCase()));
      tickerList = [...config.MAJOR_STOCKS, ...tickersForDate.filter((t) => !majorSet.has(t.toUpperCase()))];
    }

    const widgets: Record<string, unknown>[] = [];

    for (const ticker of tickerList) {
      let quoteData: Record<string, unknown> | null = null;
      try {
        quoteData = await getQuote(ticker);
      } catch {
        // ignore
      }

      let latestDate: string | null = null;
      let recommendation: string | null = null;
      let confidence: number | null = null;
      let reportScores: Record<string, { score?: number; score_label?: string }> | null = null;

      try {
        latestDate = getLatestReportDate(ticker);
        if (latestDate) {
          const scoresRaw = getReportsWithScores(ticker, latestDate);
          if (Object.keys(scoresRaw).length > 0) {
            reportScores = {};
            for (const [k, v] of Object.entries(scoresRaw)) {
              if (v.score != null || v.score_label) {
                reportScores[k] = { score: v.score ?? undefined, score_label: v.score_label ?? undefined };
              }
            }
            if (Object.keys(reportScores).length === 0) reportScores = null;
            const ftd = scoresRaw.final_trade_decision;
            if (ftd?.recommendation) {
              recommendation = ftd.recommendation as string;
              confidence = (ftd.confidence as number) ?? null;
            }
            if (recommendation == null) {
              const tip = scoresRaw.trader_investment_plan;
              if (tip?.recommendation) {
                recommendation = tip.recommendation as string;
                confidence = (tip.confidence as number) ?? null;
              }
            }
            if (recommendation == null) {
              const reports = getReportsForDate(ticker, latestDate);
              const recData =
                (reports.final_trade_decision && parseRecommendation(reports.final_trade_decision))
                || (reports.trader_investment_plan && parseRecommendation(reports.trader_investment_plan))
                || null;
              if (recData) {
                recommendation = recData.recommendation;
                confidence = recData.confidence ?? null;
              }
            }
          }
        }
      } catch {
        // ignore
      }

      const q = quoteData;
      widgets.push({
        ticker,
        current_price: q?.current_price ?? 0,
        daily_change: q?.daily_change ?? 0,
        daily_change_percent: q?.daily_change_percent ?? 0,
        recommendation: latestDate ? recommendation : null,
        confidence: confidence ?? null,
        report_date: latestDate ?? null,
        has_report: latestDate != null,
        market_status: q?.market_status ?? "UNKNOWN",
        report_scores: reportScores ?? null,
      });
    }

    res.json({ widgets });
  } catch (e) {
    console.error("Error get widgets:", e);
    res.status(500).json({ detail: String(e) });
  }
});

/** GET /api/stocks/:ticker */
stocksRouter.get("/:ticker", async (req: Request, res: Response) => {
  const ticker = req.params.ticker.toUpperCase();
  try {
    const quoteData = await getQuote(ticker);
    if (quoteData == null) {
      return res.status(404).json({ detail: `Ticker '${ticker}' not found. Check the symbol and try again.` });
    }

    const latestDate = getLatestReportDate(ticker);
    let latestReports: Record<string, string | null> = {};
    let latestReportsWithScoresRaw: Record<string, ReturnType<typeof getReportsWithScores>[string]> = {};
    let latestRecommendation: { recommendation: string; confidence: number | null; source: string; date: string } | null = null;
    let reportDaysAgo: number | null = null;

    if (latestDate) {
      latestReports = getReportsForDate(ticker, latestDate);
      latestReportsWithScoresRaw = getReportsWithScores(ticker, latestDate);
      const firstReport = Object.values(latestReportsWithScoresRaw)[0];
      reportDaysAgo = firstReport?.days_ago ?? null;

      const ftd = latestReportsWithScoresRaw.final_trade_decision;
      if (ftd?.recommendation) {
        let conf = (ftd.confidence as number) ?? null;
        if (conf != null && (conf < 0 || conf > 1)) conf = 1;
        latestRecommendation = {
          recommendation: ftd.recommendation as string,
          confidence: conf ?? 1,
          source: "structured_output",
          date: latestDate,
        };
      }
      if (!latestRecommendation && latestReports.final_trade_decision) {
        const recData = parseRecommendation(latestReports.final_trade_decision);
        if (recData) {
          latestRecommendation = {
            recommendation: recData.recommendation,
            confidence: recData.confidence ?? null,
            source: recData.source,
            date: latestDate,
          };
        }
      }
      if (!latestRecommendation && latestReports.trader_investment_plan) {
        const recData = parseRecommendation(latestReports.trader_investment_plan);
        if (recData) {
          latestRecommendation = {
            recommendation: recData.recommendation,
            confidence: recData.confidence ?? null,
            source: recData.source,
            date: latestDate,
          };
        }
      }
    }

    const historical = getHistoricalAnalyses(ticker);
    const historicalAnalyses = historical.map((h) => {
      const reports = getReportsForDate(ticker, h.date);
      let rec: string | null = null;
      const recFtd = reports.final_trade_decision ? parseRecommendation(reports.final_trade_decision) : null;
      const recTip = reports.trader_investment_plan ? parseRecommendation(reports.trader_investment_plan) : null;
      if (recFtd) rec = recFtd.recommendation;
      else if (recTip) rec = recTip.recommendation;
      return { date: h.date, available_reports: h.available_reports, recommendation: rec };
    });

    const runningId = getRunningAnalysisIdByTicker(ticker);
    const isGenerating = runningId != null;
    const generationAnalysisId = runningId;

    const investmentPlanMeta = latestReportsWithScoresRaw.investment_plan ?? {};
    const expectedReturnPct = (investmentPlanMeta as { expected_return_pct?: number }).expected_return_pct;
    const bearCaseReturnPct = (investmentPlanMeta as { bear_case_return_pct?: number }).bear_case_return_pct;
    const bullCaseReturnPct = (investmentPlanMeta as { bull_case_return_pct?: number }).bull_case_return_pct;

    const reportsWithScores: Record<string, { content?: string | null; score?: number | null; score_label?: string | null; key_takeaways?: string[]; analysis_date?: string | null; generated_at?: string | null; days_ago?: number | null; models_used?: { provider?: string; deep_think?: string; quick_think?: string } | null; bull_viewpoint?: string[]; bear_viewpoint?: string[]; risky_viewpoint?: string[]; safe_viewpoint?: string[]; neutral_viewpoint?: string[] }> = {};
    for (const [k, v] of Object.entries(latestReportsWithScoresRaw)) {
      reportsWithScores[k] = {
        content: v.content,
        score: v.score,
        score_label: v.score_label,
        key_takeaways: v.key_takeaways ?? [],
        analysis_date: v.analysis_date,
        generated_at: v.generated_at,
        days_ago: v.days_ago,
        models_used: v.models_used ?? null,
        bull_viewpoint: v.bull_viewpoint,
        bear_viewpoint: v.bear_viewpoint,
        risky_viewpoint: v.risky_viewpoint,
        safe_viewpoint: v.safe_viewpoint,
        neutral_viewpoint: v.neutral_viewpoint,
      };
    }

    res.json({
      ticker,
      quote: quoteData,
      recommendation: latestRecommendation,
      report_date: latestDate ?? null,
      report_days_ago: reportDaysAgo,
      reports: latestReports,
      reports_with_scores: reportsWithScores,
      historical_analyses: historicalAnalyses,
      has_reports: latestDate != null,
      is_generating: isGenerating,
      generation_analysis_id: generationAnalysisId,
      expected_return_pct: expectedReturnPct ?? null,
      bear_case_return_pct: bearCaseReturnPct ?? null,
      bull_case_return_pct: bullCaseReturnPct ?? null,
    });
  } catch (e) {
    console.error("Error get stock page:", e);
    res.status(500).json({ detail: String(e) });
  }
});
