/**
 * Configuration for Node backend. Matches Python backend env where possible.
 */

import path from "path";

const PORT = parseInt(process.env.PORT ?? "8002", 10);

// Results directory: repo root "results" when running from backend-node
const RESULTS_DIR_ENV = (process.env.RESULTS_DIR ?? "results").trim();
const RESULTS_DIR = path.isAbsolute(RESULTS_DIR_ENV)
  ? RESULTS_DIR_ENV
  : path.resolve(__dirname, "..", "..", RESULTS_DIR_ENV);

const CORS_ORIGINS_ENV = (process.env.CORS_ORIGINS ?? "").trim();
const CORS_ORIGINS =
  CORS_ORIGINS_ENV.length > 0
    ? CORS_ORIGINS_ENV.split(",").map((o) => o.trim()).filter(Boolean)
    : [
        "http://localhost:3003",
        "http://127.0.0.1:3003",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
      ];

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8002").trim().replace(/\/$/, "");

// 10 major stocks for homepage
const MAJOR_STOCKS = [
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
];

const ENABLE_DAILY_SYNC = /^(true|1|yes)$/i.test(process.env.ENABLE_DAILY_SYNC ?? "true");
const SYNC_SCHEDULE_TIME = (process.env.SYNC_SCHEDULE_TIME ?? "06:00").trim();

export const config = {
  PORT,
  RESULTS_DIR,
  CORS_ORIGINS,
  BACKEND_URL,
  MAJOR_STOCKS,
  ENABLE_DAILY_SYNC,
  SYNC_SCHEDULE_TIME,
};
