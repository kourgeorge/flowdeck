/**
 * Data API: same paths and shapes as Python backend /api/data/*
 */

import { Router, Request, Response } from "express";
import {
  getQuote,
  getHistorical,
  getCompanyInfo,
  getExtendedInfo,
  getFundamentals,
  getFinancialStatements,
  getFinancialCharts,
  getStockData,
  getAnalystRecommendations,
  getNews,
} from "../services/dataService";

export const dataRouter = Router();

dataRouter.get("/quote/:ticker", async (req: Request, res: Response) => {
  try {
    const result = await getQuote(req.params.ticker);
    if (result == null) return res.status(404).json({ detail: "Quote not found" });
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/news", async (req: Request, res: Response) => {
  try {
    const ticker = (req.query.ticker as string) ?? "";
    const vendor = req.query.vendor as string | undefined;
    const lookbackDays = Math.min(90, Math.max(1, parseInt((req.query.lookback_days as string) ?? "7", 10) || 7));
    const result = await getNews(ticker, vendor, lookbackDays);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/company/:ticker", async (req: Request, res: Response) => {
  try {
    const result = await getCompanyInfo(req.params.ticker);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/extended-info/:ticker", async (req: Request, res: Response) => {
  try {
    const result = await getExtendedInfo(req.params.ticker);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/fundamentals/:ticker", async (req: Request, res: Response) => {
  try {
    const result = await getFundamentals(req.params.ticker);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/financial-statements/:ticker", async (req: Request, res: Response) => {
  try {
    const statementType = (req.query.statement_type as string) ?? "all";
    const freq = (req.query.freq as string) ?? "quarterly";
    const result = await getFinancialStatements(req.params.ticker, statementType, freq);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/financial-charts/:ticker", async (req: Request, res: Response) => {
  try {
    const freq = (req.query.freq as string) ?? "annual";
    const result = await getFinancialCharts(req.params.ticker, freq);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/historical/:ticker", async (req: Request, res: Response) => {
  try {
    const period = (req.query.period as string) ?? "6mo";
    const interval = (req.query.interval as string) ?? "1d";
    const result = await getHistorical(req.params.ticker, period, interval);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/stock-data/:ticker", async (req: Request, res: Response) => {
  try {
    const startDate = (req.query.start_date as string) ?? "";
    const endDate = (req.query.end_date as string) ?? "";
    if (!startDate || !endDate) return res.status(400).json({ detail: "start_date and end_date required" });
    const data = await getStockData(req.params.ticker, startDate, endDate);
    res.json({
      ticker: req.params.ticker.toUpperCase(),
      start_date: startDate,
      end_date: endDate,
      data,
    });
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});

dataRouter.get("/analyst-recommendations/:ticker", async (req: Request, res: Response) => {
  try {
    const result = await getAnalystRecommendations(req.params.ticker);
    res.json(result);
  } catch (e) {
    res.status(500).json({ detail: String(e) });
  }
});
