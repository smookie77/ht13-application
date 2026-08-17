import { API_BASE_URL } from "./api";

/** Same host as the API, ws:// or wss:// to match its scheme. */
export function websocketUrl(path: string): string {
  const base = API_BASE_URL.replace(/^http/, "ws").replace(/\/$/, "");
  return `${base}${path}`;
}

/**
 * Reconnect delay with exponential backoff and jitter.
 *
 * The jitter matters more than usual here: if the server blips while a few
 * hundred people are queued, a fixed delay would reconnect them all in the
 * same instant and knock it over again.
 */
export function reconnectDelay(attempt: number): number {
  const base = Math.min(1000 * 2 ** attempt, 15000);
  return base * (0.7 + Math.random() * 0.6);
}

/** Well under the ~100s that Cloudflare and most proxies allow a socket to idle. */
export const HEARTBEAT_INTERVAL_MS = 30_000;

/**
 * Keep a socket from being culled for inactivity.
 *
 * A queue can sit quiet for minutes between allocations, and a proxy that drops
 * the connection would leave someone staring at a frozen position. Returns a
 * cleanup function.
 */
export function startHeartbeat(socket: WebSocket): () => void {
  const id = setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, HEARTBEAT_INTERVAL_MS);
  return () => clearInterval(id);
}
