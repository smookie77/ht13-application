"use client";

import { useAvailability } from "./AvailabilityProvider";

const STATE_LABELS: Record<string, string> = {
  upcoming: "Sales not open yet",
  open: "On sale now",
  sold_out: "Sold out",
  closed: "Sales closed",
};

/** Headline "X of Y tickets left" bar, pushed live over the WebSocket. */
export function TicketCounter() {
  const { availability, connected } = useAvailability();
  const { tickets_available, tickets_total, sales_state, queue_length } = availability;

  const soldPercent =
    tickets_total > 0
      ? ((tickets_total - tickets_available) / tickets_total) * 100
      : 0;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <p
            className="text-4xl font-bold tabular-nums text-slate-900"
            aria-live="polite"
          >
            {tickets_available.toLocaleString("en-GB")}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            of {tickets_total.toLocaleString("en-GB")} tickets left
          </p>
        </div>
        <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
          {STATE_LABELS[sales_state] ?? sales_state}
        </span>
      </div>

      <div
        className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuenow={Math.round(soldPercent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Tickets sold"
      >
        <div
          className="h-full rounded-full bg-blue-600 transition-[width] duration-700 ease-out"
          style={{ width: `${soldPercent}%` }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
        <span className="inline-flex items-center gap-1.5 text-slate-400">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              connected ? "bg-emerald-500" : "bg-slate-300"
            }`}
          />
          {connected ? "Live" : "Reconnecting…"}
        </span>
        {typeof queue_length === "number" && queue_length > 0 && (
          <span className="tabular-nums text-slate-400">
            {queue_length.toLocaleString("en-GB")} waiting in line
          </span>
        )}
      </div>
    </div>
  );
}
