import { Router, Request, Response } from "express";
import { randomUUID } from "crypto";
import {
  getRunningAnalysisId,
  getAnalysisStatus,
  startAnalysis as orchestratorStartAnalysis,
} from "../services/analysisOrchestrator";

export const analysesRouter = Router();

analysesRouter.post("/start", async (req: Request, res: Response) => {
  try {
    const body = req.body as {
      ticker?: string;
      analysis_date?: string;
      analysts?: string[];
      research_depth?: number;
      llm_provider?: string;
      initiator_email?: string | null;
    };
    const ticker = (body.ticker ?? "").toString().trim().toUpperCase();
    if (!ticker) {
      return res.status(400).json({ detail: "Ticker is required" });
    }
    const analysisDate = (body.analysis_date ?? new Date().toISOString().slice(0, 10)).toString().trim();
    const analysts = Array.isArray(body.analysts) ? body.analysts : ["market", "news", "fundamentals"];
    const researchDepth = typeof body.research_depth === "number" ? body.research_depth : 5;
    const llmProvider = (body.llm_provider ?? "azure").toString().toLowerCase();
    const initiatorEmail = typeof body.initiator_email === "string" ? body.initiator_email : undefined;

    const existingId = getRunningAnalysisId(ticker, analysisDate);
    if (existingId) {
      return res.json({ analysis_id: existingId, ticker, date: analysisDate, existing: true });
    }

    const analysisId = randomUUID();
    orchestratorStartAnalysis(analysisId, ticker, analysisDate, analysts, researchDepth, llmProvider, initiatorEmail);
    res.json({ analysis_id: analysisId, ticker, date: analysisDate, existing: false });
  } catch (e) {
    console.error("Error starting analysis:", e);
    res.status(500).json({ detail: String(e) });
  }
});

analysesRouter.get("/:analysis_id/status", (req: Request, res: Response) => {
  const status = getAnalysisStatus(req.params.analysis_id);
  if (!status) return res.status(404).json({ detail: "Analysis not found" });
  res.json(status);
});
