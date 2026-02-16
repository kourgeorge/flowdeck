import { Router, Request, Response } from "express";
import { config } from "../config";
import { hasReportForDate } from "../services/reportService";
import { startAnalysis } from "../services/analysisOrchestrator";
import { randomUUID } from "crypto";

export const syncRouter = Router();

/** POST /api/sync/major-stocks. Trigger analyses for major stocks missing a report for the date. */
syncRouter.post("/major-stocks", async (req: Request, res: Response) => {
  try {
    const body = (req.body ?? {}) as { analysis_date?: string };
    const analysisDate = (body.analysis_date ?? new Date().toISOString().slice(0, 10)).toString().trim();

    const triggered: string[] = [];
    const skipped: string[] = [];

    for (const ticker of config.MAJOR_STOCKS) {
      const t = ticker.toUpperCase();
      if (hasReportForDate(ticker, analysisDate)) {
        skipped.push(t);
      } else {
        triggered.push(t);
      }
    }

    for (const ticker of triggered) {
      const analysisId = randomUUID();
      startAnalysis(analysisId, ticker, analysisDate, ["market", "news", "fundamentals"], 5, "azure");
    }

    res.json({ date: analysisDate, triggered, skipped });
  } catch (e) {
    console.error("Error sync major stocks:", e);
    res.status(500).json({ detail: String(e) });
  }
});
