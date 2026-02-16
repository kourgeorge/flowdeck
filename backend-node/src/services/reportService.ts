/**
 * Read reports from results directory. Port of backend/services/report_service.py
 */

import fs from "fs";
import path from "path";
import { config } from "../config";
import { extractKeyTakeaways } from "./keyTakeaways";

const EMPTY: ReportDataFromJson = {
  content: null,
  score: null,
  score_label: null,
  key_takeaways: [],
  analysis_date: null,
  generated_at: null,
  days_ago: null,
  recommendation: null,
  expected_return_pct: null,
  bear_case_return_pct: null,
  bull_case_return_pct: null,
  confidence: null,
  models_used: null,
};

export interface ModelsUsed {
  provider?: string;
  deep_think?: string;
  quick_think?: string;
}

export interface ReportDataFromJson {
  content: string | null;
  score: number | null;
  score_label: string | null;
  key_takeaways: string[];
  analysis_date: string | null;
  generated_at: string | null;
  days_ago: number | null;
  recommendation?: string | null;
  expected_return_pct?: number | null;
  bear_case_return_pct?: number | null;
  bull_case_return_pct?: number | null;
  confidence?: number | null;
  models_used?: ModelsUsed | null;
  bull_viewpoint?: string[];
  bear_viewpoint?: string[];
  risky_viewpoint?: string[];
  safe_viewpoint?: string[];
  neutral_viewpoint?: string[];
}

/** Extract YYYY-MM-DD from run id (YYYY-MM-DD_HH-MM-SS) or return as-is if date-only. */
function datePart(runIdOrDate: string | null): string | null {
  if (!runIdOrDate) return null;
  const i = runIdOrDate.indexOf("_");
  return i >= 0 ? runIdOrDate.slice(0, i) : runIdOrDate;
}

function daysAgo(reportDate: string | null, generatedAt: string | null): number | null {
  let ref: Date | null = null;
  if (generatedAt) {
    try {
      ref = new Date(generatedAt.replace("Z", "+00:00"));
    } catch {
      // ignore
    }
  }
  if (!ref && reportDate) {
    try {
      const d = datePart(reportDate);
      ref = d ? new Date(d + "T12:00:00Z") : null;
    } catch {
      // ignore
    }
  }
  if (!ref) return null;
  const now = new Date();
  const diff = Math.floor((now.getTime() - ref.getTime()) / (24 * 60 * 60 * 1000));
  return Math.max(0, diff);
}

function reportDataFromJson(data: { metadata?: Record<string, unknown>; content?: string; [k: string]: unknown }, date: string): ReportDataFromJson {
  const meta = data.metadata ?? {};
  const content = (data.content ?? "") as string;
  const analysisDate = (meta.analysis_date as string) || date;
  const keyTakeaways = (meta.key_takeaways as string[] | undefined) ?? (content ? extractKeyTakeaways(content) : []);
  const modelsUsed = meta.models_used as { provider?: string; deep_think?: string; quick_think?: string } | undefined;
  const out: ReportDataFromJson = {
    content: content || null,
    score: (meta.score as number) ?? null,
    score_label: (meta.score_label as string) ?? null,
    key_takeaways: keyTakeaways,
    analysis_date: analysisDate,
    generated_at: (meta.generated_at as string) ?? null,
    days_ago: daysAgo(analysisDate, (meta.generated_at as string) ?? null) ?? daysAgo(analysisDate, null),
    recommendation: (meta.recommendation as string) ?? null,
    expected_return_pct: (meta.expected_return_pct as number) ?? null,
    bear_case_return_pct: (meta.bear_case_return_pct as number) ?? null,
    bull_case_return_pct: (meta.bull_case_return_pct as number) ?? null,
    confidence: (meta.confidence as number) ?? null,
    models_used: modelsUsed ?? null,
  };
  if (Array.isArray(data.bull_viewpoint)) out.bull_viewpoint = data.bull_viewpoint as string[];
  if (Array.isArray(data.bear_viewpoint)) out.bear_viewpoint = data.bear_viewpoint as string[];
  if (Array.isArray(data.risky_viewpoint)) out.risky_viewpoint = data.risky_viewpoint as string[];
  if (Array.isArray(data.safe_viewpoint)) out.safe_viewpoint = data.safe_viewpoint as string[];
  if (Array.isArray(data.neutral_viewpoint)) out.neutral_viewpoint = data.neutral_viewpoint as string[];
  return out;
}

function reportsDir(ticker: string, runId: string): string {
  return path.join(config.RESULTS_DIR, ticker.toUpperCase(), runId, "reports");
}

export function getLatestReportDate(ticker: string): string | null {
  const tickerDir = path.join(config.RESULTS_DIR, ticker.toUpperCase());
  if (!fs.existsSync(tickerDir) || !fs.statSync(tickerDir).isDirectory()) return null;
  const dates = fs.readdirSync(tickerDir)
    .filter((name) => {
      const d = path.join(tickerDir, name);
      const reportsPath = path.join(d, "reports");
      return fs.statSync(d).isDirectory() && fs.existsSync(reportsPath) && fs.statSync(reportsPath).isDirectory();
    })
    .sort()
    .reverse();
  return dates[0] ?? null;
}

/** date can be YYYY-MM-DD (match any run that day) or full run id YYYY-MM-DD_HH-MM-SS (exact). */
export function hasReportForDate(ticker: string, date: string): boolean {
  const tickerDir = path.join(config.RESULTS_DIR, ticker.toUpperCase());
  if (!fs.existsSync(tickerDir) || !fs.statSync(tickerDir).isDirectory()) return false;
  if (date.includes("_")) {
    const rd = reportsDir(ticker, date);
    if (!fs.existsSync(rd) || !fs.statSync(rd).isDirectory()) return false;
    return fs.readdirSync(rd).some((f) => f.endsWith(".json"));
  }
  const names = fs.readdirSync(tickerDir);
  for (const name of names) {
    if (name.startsWith(date)) {
      const rd = path.join(tickerDir, name, "reports");
      if (fs.existsSync(rd) && fs.statSync(rd).isDirectory() && fs.readdirSync(rd).some((f) => f.endsWith(".json")))
        return true;
    }
  }
  return false;
}

export function getTickersWithReportsForDate(date: string): string[] {
  if (!fs.existsSync(config.RESULTS_DIR) || !fs.statSync(config.RESULTS_DIR).isDirectory()) return [];
  return fs.readdirSync(config.RESULTS_DIR).filter((name) => {
    const p = path.join(config.RESULTS_DIR, name);
    return fs.statSync(p).isDirectory() && hasReportForDate(name, date);
  });
}

export function getReportsWithScores(ticker: string, date: string): Record<string, ReportDataFromJson> {
  const rd = reportsDir(ticker, date);
  if (!fs.existsSync(rd) || !fs.statSync(rd).isDirectory()) return {};
  const result: Record<string, ReportDataFromJson> = {};
  for (const f of fs.readdirSync(rd)) {
    if (!f.endsWith(".json")) continue;
    const stem = path.basename(f, ".json");
    try {
      const raw = JSON.parse(fs.readFileSync(path.join(rd, f), "utf-8"));
      result[stem] = reportDataFromJson(raw, date);
    } catch {
      result[stem] = { ...EMPTY, analysis_date: date, days_ago: daysAgo(date, null) };
    }
  }
  return result;
}

export function getReportsForDate(ticker: string, date: string): Record<string, string | null> {
  const scores = getReportsWithScores(ticker, date);
  const out: Record<string, string | null> = {};
  for (const [k, v] of Object.entries(scores)) {
    out[k] = v.content ?? "";
  }
  return out;
}

export function getHistoricalAnalyses(ticker: string): { date: string; available_reports: string[] }[] {
  const tickerDir = path.join(config.RESULTS_DIR, ticker.toUpperCase());
  if (!fs.existsSync(tickerDir) || !fs.statSync(tickerDir).isDirectory()) return [];
  const analyses: { date: string; available_reports: string[] }[] = [];
  for (const name of fs.readdirSync(tickerDir)) {
    const d = path.join(tickerDir, name);
    const reportsPath = path.join(d, "reports");
    if (!fs.statSync(d).isDirectory() || !fs.existsSync(reportsPath)) continue;
    const files = fs.readdirSync(reportsPath).filter((f) => f.endsWith(".json")).map((f) => path.basename(f, ".json")).sort();
    analyses.push({ date: name, available_reports: files });
  }
  analyses.sort((a, b) => b.date.localeCompare(a.date));
  return analyses;
}
