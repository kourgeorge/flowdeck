/**
 * Stock Dashboard API — Node.js backend.
 * Same REST + WebSocket API as Python backend; Python agents run as subprocess.
 */

import express from "express";
import cron from "node-cron";
import { config } from "./config";
import { dataRouter } from "./routes/data";
import { stocksRouter } from "./routes/stocks";
import { analysesRouter } from "./routes/analyses";
import { syncRouter } from "./routes/sync";
import { attachWebSocketServer } from "./websocket";
import { hasReportForDate } from "./services/reportService";
import { startAnalysis } from "./services/analysisOrchestrator";
import { randomUUID } from "crypto";

const app = express();

app.use(express.json());

app.use((_req, res, next) => {
  const origin = _req.headers.origin;
  if (origin && config.CORS_ORIGINS.includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }
  res.setHeader("Access-Control-Allow-Credentials", "true");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "*");
  res.setHeader("Access-Control-Expose-Headers", "*");
  if (_req.method === "OPTIONS") {
    return res.sendStatus(204);
  }
  next();
});

app.get("/", (_req, res) => {
  res.json({ message: "Stock Dashboard API", status: "running" });
});

app.get("/health", (_req, res) => {
  res.json({ status: "healthy", service: "tradingagents-api" });
});

app.use("/api/data", dataRouter);
app.use("/api/stocks", stocksRouter);
app.use("/api/analyses", analysesRouter);
app.use("/api/sync", syncRouter);

const server = app.listen(config.PORT, "0.0.0.0", () => {
  console.log(`Stock Dashboard API (Node) listening on port ${config.PORT}`);
});

attachWebSocketServer(server);

if (config.ENABLE_DAILY_SYNC && config.SYNC_SCHEDULE_TIME) {
  const [hourStr, minuteStr] = config.SYNC_SCHEDULE_TIME.split(":");
  const hour = parseInt(hourStr ?? "6", 10);
  const minute = parseInt(minuteStr ?? "0", 10);
  const cronExpr = `${minute} ${hour} * * *`;
  cron.schedule(cronExpr, () => {
    const analysisDate = new Date().toISOString().slice(0, 10);
    for (const ticker of config.MAJOR_STOCKS) {
      const t = ticker.toUpperCase();
      if (!hasReportForDate(ticker, analysisDate)) {
        startAnalysis(randomUUID(), t, analysisDate, ["market", "news", "fundamentals"], 5, "azure");
      }
    }
  });
  console.log(`Daily sync scheduled at ${config.SYNC_SCHEDULE_TIME}`);
}
