"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";

import { getAvailability } from "@/lib/api";
import type { Availability } from "@/lib/types";
import { reconnectDelay, startHeartbeat, websocketUrl } from "@/lib/ws";

interface AvailabilityState {
  availability: Availability;
  connected: boolean;
}

const AvailabilityContext = createContext<AvailabilityState | null>(null);

export function useAvailability(): AvailabilityState {
  const value = useContext(AvailabilityContext);
  if (!value) {
    throw new Error("useAvailability must be used inside <AvailabilityProvider>");
  }
  return value;
}

/**
 * Keeps ticket counters live over a WebSocket.
 *
 * The server-rendered snapshot is the initial value, so the first paint already
 * shows real numbers and the socket only has to deliver changes. On reconnect
 * we re-fetch over HTTP rather than trusting the last known state - anything
 * missed while disconnected would otherwise linger as a wrong count.
 */
export function AvailabilityProvider({
  initial,
  children,
}: {
  initial: Availability;
  children: React.ReactNode;
}) {
  const [availability, setAvailability] = useState(initial);
  const [connected, setConnected] = useState(false);
  const slug = initial.slug;
  const attemptRef = useRef(0);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let stopHeartbeat: (() => void) | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      socket = new WebSocket(websocketUrl(`/ws/events/${slug}/`));

      socket.onopen = () => {
        setConnected(true);
        stopHeartbeat = startHeartbeat(socket!);
        // Catch up on anything missed while we were away.
        if (attemptRef.current > 0) {
          getAvailability(slug).then(setAvailability).catch(() => {});
        }
        attemptRef.current = 0;
      };

      socket.onmessage = (raw) => {
        try {
          const message = JSON.parse(raw.data);
          if (message.type === "availability.update") {
            setAvailability(message.payload);
          }
        } catch {
          // Ignore malformed frames rather than tearing down the stream.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        stopHeartbeat?.();
        if (closed) return;
        retryTimer = setTimeout(connect, reconnectDelay(attemptRef.current++));
      };

      socket.onerror = () => socket?.close();
    };

    connect();

    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      stopHeartbeat?.();
      socket?.close();
    };
  }, [slug]);

  return (
    <AvailabilityContext.Provider value={{ availability, connected }}>
      {children}
    </AvailabilityContext.Provider>
  );
}
