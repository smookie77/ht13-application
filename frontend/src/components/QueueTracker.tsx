"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { cancelReservation, confirmReservation, errorMessage, getReservation } from "@/lib/api";
import type { Reservation } from "@/lib/types";
import { reconnectDelay, startHeartbeat, websocketUrl } from "@/lib/ws";

/**
 * Live view of one reservation as it moves through the queue.
 *
 * Position is pushed from the server rather than polled, so the number moves
 * the moment the person ahead is served. The countdown on an allocated hold is
 * ticked locally from `seconds_left` - no request per second per waiting user.
 */
export function QueueTracker({ initial }: { initial: Reservation }) {
  const [reservation, setReservation] = useState(initial);
  const [connected, setConnected] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(initial.seconds_left);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attemptRef = useRef(0);
  const publicId = initial.public_id;

  const apply = useCallback((next: Reservation) => {
    setReservation(next);
    setSecondsLeft(next.seconds_left);
  }, []);

  // --- live updates ---------------------------------------------------------
  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let stopHeartbeat: (() => void) | null = null;
    let closed = false;

    const connect = () => {
      if (closed) return;
      socket = new WebSocket(websocketUrl(`/ws/reservations/${publicId}/`));

      socket.onopen = () => {
        setConnected(true);
        stopHeartbeat = startHeartbeat(socket!);
        if (attemptRef.current > 0) {
          getReservation(publicId).then(apply).catch(() => {});
        }
        attemptRef.current = 0;
      };

      socket.onmessage = (raw) => {
        try {
          const message = JSON.parse(raw.data);
          if (message.type === "reservation.update") {
            setReservation((current) => ({ ...current, ...message.payload }));
            if (typeof message.payload.seconds_left === "number") {
              setSecondsLeft(message.payload.seconds_left);
            }
          }
        } catch {
          // Ignore malformed frames.
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
  }, [publicId, apply]);

  // --- local countdown on the payment hold ----------------------------------
  useEffect(() => {
    if (reservation.status !== "allocated" || secondsLeft === null) return;
    if (secondsLeft <= 0) {
      getReservation(publicId).then(apply).catch(() => {});
      return;
    }
    const id = setTimeout(() => setSecondsLeft((s) => (s === null ? null : s - 1)), 1000);
    return () => clearTimeout(id);
  }, [reservation.status, secondsLeft, publicId, apply]);

  const act = async (action: typeof confirmReservation) => {
    setBusy(true);
    setError(null);
    try {
      apply(await action(publicId));
    } catch (err) {
      setError(errorMessage(err));
      getReservation(publicId).then(apply).catch(() => {});
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Header reservation={reservation} connected={connected} />

      <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        {reservation.status === "queued" && <Queued position={reservation.position} />}

        {reservation.status === "allocated" && (
          <Allocated
            secondsLeft={secondsLeft}
            busy={busy}
            onConfirm={() => act(confirmReservation)}
            onCancel={() => act(cancelReservation)}
          />
        )}

        {reservation.status === "confirmed" && <Confirmed />}

        {(reservation.status === "rejected" ||
          reservation.status === "expired" ||
          reservation.status === "cancelled") && (
          <Ended status={reservation.status} reason={reservation.failure_reason} />
        )}

        {error && (
          <p role="alert" className="mt-6 text-sm text-red-600">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

function Header({
  reservation,
  connected,
}: {
  reservation: Reservation;
  connected: boolean;
}) {
  return (
    <div className="text-center">
      <h1 className="text-3xl font-bold tracking-tight">{reservation.event_title}</h1>
      <p className="mt-2 text-slate-600">
        {reservation.quantity} × {reservation.ticket_type_name}
      </p>
      <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-slate-400">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            connected ? "bg-emerald-500" : "bg-slate-300"
          }`}
        />
        {connected ? "Live" : "Reconnecting…"}
      </p>
    </div>
  );
}

function Queued({ position }: { position: number | null }) {
  return (
    <div className="text-center">
      <p className="text-sm font-medium uppercase tracking-wide text-slate-400">
        Your place in line
      </p>
      <p className="mt-3 text-7xl font-bold tabular-nums text-blue-600" aria-live="polite">
        {position ?? "—"}
      </p>
      <p className="mt-4 text-slate-600">
        {position === 1
          ? "You are next. Hold on."
          : "Keep this page open — your place is saved and updates by itself."}
      </p>
      <div className="mt-6 h-1 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="h-full w-1/3 animate-pulse rounded-full bg-blue-600" />
      </div>
    </div>
  );
}

function Allocated({
  secondsLeft,
  busy,
  onConfirm,
  onCancel,
}: {
  secondsLeft: number | null;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const minutes = secondsLeft === null ? null : Math.floor(secondsLeft / 60);
  const seconds = secondsLeft === null ? null : secondsLeft % 60;

  return (
    <div className="text-center">
      <p className="text-sm font-medium uppercase tracking-wide text-emerald-600">
        Your tickets are held
      </p>
      <h2 className="mt-3 text-2xl font-bold">You made it through the queue</h2>

      {secondsLeft !== null && (
        <p className="mt-4 text-slate-600">
          Complete the purchase within{" "}
          <span className="font-semibold tabular-nums text-slate-900">
            {minutes}:{String(seconds).padStart(2, "0")}
          </span>{" "}
          or the tickets go back to the pool.
        </p>
      )}

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400"
        >
          {busy ? "Processing…" : "Complete purchase"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="rounded-xl border border-slate-300 px-6 py-3 font-semibold text-slate-700 transition hover:bg-slate-50 disabled:text-slate-400"
        >
          Release tickets
        </button>
      </div>
      <p className="mt-4 text-xs text-slate-400">
        Payment is simulated for this task — no card is charged.
      </p>
    </div>
  );
}

function Confirmed() {
  return (
    <div className="text-center">
      <p className="text-sm font-medium uppercase tracking-wide text-emerald-600">
        Confirmed
      </p>
      <h2 className="mt-3 text-2xl font-bold">Your tickets are yours</h2>
      <p className="mt-3 text-slate-600">
        The PDF ticket is on its way to your inbox. It is also available to
        download from your account at any time.
      </p>
      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-center">
        <Link
          href="/account"
          className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Go to my tickets
        </Link>
      </div>
    </div>
  );
}

const ENDED_COPY: Record<string, { title: string; body: string }> = {
  rejected: {
    title: "Sold out before your turn",
    body: "Everyone ahead of you was served first. Nothing was charged.",
  },
  expired: {
    title: "Your hold expired",
    body: "The tickets went back into the pool so someone else could buy them.",
  },
  cancelled: {
    title: "Reservation released",
    body: "You gave the tickets back. You can join the queue again.",
  },
};

function Ended({ status, reason }: { status: string; reason: string }) {
  const copy = ENDED_COPY[status] ?? { title: "Reservation closed", body: "" };
  return (
    <div className="text-center">
      <h2 className="text-2xl font-bold">{copy.title}</h2>
      <p className="mt-3 text-slate-600">{reason || copy.body}</p>
      <Link
        href="/tickets"
        className="mt-8 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
      >
        Back to tickets
      </Link>
    </div>
  );
}
