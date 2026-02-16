/**
 * Orchestrates Python analysis subprocess: spawn, track state, broadcast progress.
 */

import { spawn, ChildProcess } from "child_process";
import path from "path";
import { config } from "../config";

export interface RunningAnalysisInfo {
  ticker: string;
  date: string;
  status: "running" | "completed" | "error";
  agent_statuses?: Record<string, string>;
  current_agent?: string | null;
  reports?: Record<string, unknown>;
  error?: string;
}

const runningAnalyses = new Map<string, RunningAnalysisInfo>();

export type BroadcastFn = (analysisId: string, message: object) => void;
let broadcastFn: BroadcastFn | null = null;

export function setBroadcastFn(fn: BroadcastFn | null): void {
  broadcastFn = fn;
}

export function getRunningAnalysisId(ticker: string, analysisDate: string): string | null {
  const t = ticker.toUpperCase();
  for (const [id, info] of runningAnalyses) {
    if (info.status === "running" && info.ticker === t && info.date === analysisDate) return id;
  }
  return null;
}

/** Return any running analysis id for this ticker (for stock page is_generating). */
export function getRunningAnalysisIdByTicker(ticker: string): string | null {
  const t = ticker.toUpperCase();
  for (const [id, info] of runningAnalyses) {
    if (info.status === "running" && info.ticker === t) return id;
  }
  return null;
}

export function getAnalysisStatus(analysisId: string): RunningAnalysisInfo | null {
  return runningAnalyses.get(analysisId) ?? null;
}

function broadcast(analysisId: string, message: object): void {
  try {
    broadcastFn?.(analysisId, message);
  } catch (e) {
    console.error("Broadcast error:", e);
  }
}

/** Repo root: backend-node is at repo/backend-node, so parent of dirname is repo */
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const PYTHON_SCRIPT = path.join(REPO_ROOT, "backend", "run_analysis_standalone.py");

export function startAnalysis(
  analysisId: string,
  ticker: string,
  analysisDate: string,
  analysts: string[] = ["market", "news", "fundamentals"],
  researchDepth: number = 5,
  llmProvider: string = "azure",
  initiatorEmail?: string | null
): void {
  const tickerUpper = ticker.toUpperCase();
  const info: RunningAnalysisInfo = {
    ticker: tickerUpper,
    date: analysisDate,
    status: "running",
    agent_statuses: {},
    current_agent: null,
    reports: {},
  };
  runningAnalyses.set(analysisId, info);

  const args = [
    PYTHON_SCRIPT,
    "--ticker", tickerUpper,
    "--analysis-date", analysisDate,
    "--analysis-id", analysisId,
    "--analysts", analysts.join(","),
    "--research-depth", String(researchDepth),
    "--llm-provider", llmProvider,
    "--results-dir", config.RESULTS_DIR,
    "--info-service-url", config.BACKEND_URL,
  ];
  if (initiatorEmail && initiatorEmail.trim()) {
    args.push("--initiator-email", initiatorEmail.trim());
  }

  const env = { ...process.env, INFO_SERVICE_URL: config.BACKEND_URL };

  let proc: ChildProcess;
  try {
    proc = spawn("python3", args, {
      cwd: REPO_ROOT,
      env,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (e) {
    info.status = "error";
    info.error = String(e);
    broadcast(analysisId, { type: "status", data: { status: "error", ticker: tickerUpper, date: analysisDate, error: info.error } });
    return;
  }

  let buffer = "";
  const onData = (chunk: Buffer | string) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const msg = JSON.parse(trimmed) as { type?: string; data?: Record<string, unknown>; error?: string };
        if (msg.type === "progress" && msg.data) {
          if (msg.data.agent_statuses) info.agent_statuses = msg.data.agent_statuses as Record<string, string>;
          if (msg.data.current_agent != null) info.current_agent = msg.data.current_agent as string | null;
          if (msg.data.reports) info.reports = msg.data.reports as Record<string, unknown>;
          if (msg.data.status) info.status = msg.data.status as "running" | "completed" | "error";
          broadcast(analysisId, { type: "progress", data: msg.data });
        } else if (msg.type === "completed") {
          info.status = "completed";
          broadcast(analysisId, { type: "status", data: { status: "completed", ticker: tickerUpper, date: analysisDate } });
          cleanup();
        } else if (msg.type === "error") {
          info.status = "error";
          info.error = msg.error ?? "Unknown error";
          broadcast(analysisId, { type: "status", data: { status: "error", ticker: tickerUpper, date: analysisDate, error: info.error } });
          cleanup();
        }
      } catch {
        // ignore non-JSON lines
      }
    }
  };

  const cleanup = () => {
    proc.stdout?.removeListener("data", onData);
    proc.stderr?.removeListener("data", onStderr);
    proc.removeAllListeners("exit");
    try {
      proc.kill();
    } catch {
      // ignore
    }
  };

  const onStderr = (chunk: Buffer | string) => {
    process.stderr.write(`[analysis ${analysisId}] ${chunk}`);
  };

  proc.stdout?.on("data", onData);
  proc.stderr?.on("data", onStderr);
  proc.on("exit", (code, signal) => {
    if (info.status === "running") {
      info.status = code === 0 ? "completed" : "error";
      info.error = code !== 0 ? `Process exited with code ${code}${signal ? ` signal ${signal}` : ""}` : undefined;
      broadcast(analysisId, { type: "status", data: { status: info.status, ticker: tickerUpper, date: analysisDate, error: info.error } });
    }
    cleanup();
  });
}
