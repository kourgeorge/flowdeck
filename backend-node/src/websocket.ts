/**
 * WebSocket server for analysis progress. Path: /ws/analyses/:analysis_id
 */

import { Server as HttpServer } from "http";
import WebSocket, { WebSocketServer } from "ws";
import { getAnalysisStatus, setBroadcastFn } from "./services/analysisOrchestrator";

const wsClientsByAnalysisId = new Map<string, Set<WebSocket>>();

function send(ws: WebSocket, obj: object): void {
  if (ws.readyState === WebSocket.OPEN) {
    try {
      ws.send(JSON.stringify(obj));
    } catch (e) {
      console.error("WS send error:", e);
    }
  }
}

export function attachWebSocketServer(server: HttpServer): void {
  setBroadcastFn((analysisId, message) => {
    const clients = wsClientsByAnalysisId.get(analysisId);
    if (clients) {
      clients.forEach((ws) => send(ws, message));
    }
  });

  const wss = new WebSocketServer({ noServer: true });

  server.on("upgrade", (request, socket, head) => {
    const url = request.url ?? "";
    const match = /^\/ws\/analyses\/([^/?#]+)$/.exec(url);
    if (!match) {
      socket.destroy();
      return;
    }
    const analysisId = decodeURIComponent(match[1]);
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit("connection", ws, request, analysisId);
    });
  });

  wss.on("connection", (ws: WebSocket, _req: unknown, analysisId: string) => {
    let clients = wsClientsByAnalysisId.get(analysisId);
    if (!clients) {
      clients = new Set();
      wsClientsByAnalysisId.set(analysisId, clients);
    }
    clients.add(ws);

    const status = getAnalysisStatus(analysisId);
    send(ws, {
      type: "status",
      data: status
        ? {
            status: status.status,
            ticker: status.ticker,
            date: status.date,
            agent_statuses: status.agent_statuses ?? {},
            error: status.error,
          }
        : { status: "unknown", ticker: null, date: null, agent_statuses: {} },
    });

    ws.on("message", (data) => {
      try {
        const text = (data as Buffer).toString();
        if (text === "ping") send(ws, { type: "pong" });
      } catch {
        // ignore
      }
    });

    ws.on("close", () => {
      clients?.delete(ws);
      if (clients?.size === 0) wsClientsByAnalysisId.delete(analysisId);
    });

    ws.on("error", () => {
      clients?.delete(ws);
      if (clients?.size === 0) wsClientsByAnalysisId.delete(analysisId);
    });
  });
}
