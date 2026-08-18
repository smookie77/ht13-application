"use client";

import { useEffect, useState } from "react";

import { errorMessage, listTickets, ticketDownloadUrl } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import type { Ticket } from "@/lib/types";

import { TicketIcon } from "./Logo";

export function TicketList() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const page = await listTickets();
        if (!cancelled) setTickets(page.results);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err, "Could not load your tickets."));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <p role="alert" className="mt-4 text-sm text-red-600">
        {error}
      </p>
    );
  }

  if (tickets === null) return <p className="mt-4 text-slate-500">Loading…</p>;

  if (tickets.length === 0) {
    return (
      <p className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-6 text-slate-600">
        No tickets yet. They appear here as soon as a purchase is completed.
      </p>
    );
  }

  return (
    <ul className="mt-4 space-y-3">
      {tickets.map((ticket) => (
        <li
          key={ticket.code}
          className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 p-5"
        >
          <div className="flex items-center gap-4">
            <TicketIcon className="h-8 w-8 shrink-0 text-blue-600" />
            <div>
              <p className="font-semibold">{ticket.event_title}</p>
              <p className="mt-1 text-sm text-slate-600">
                {ticket.ticket_type_name} · {ticket.holder_name}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {formatDate(ticket.starts_at)}, {formatTime(ticket.starts_at)} ·{" "}
                {ticket.venue_name}
              </p>
              <p className="mt-1 font-mono text-xs tracking-wide text-slate-400">
                {ticket.code}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {ticket.is_checked_in && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Used
              </span>
            )}
            {/* A plain link, not fetch(): the browser follows the API's
                redirect to a signed storage URL and downloads the file. */}
            <a
              href={ticketDownloadUrl(ticket.code)}
              className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700"
            >
              Download PDF
            </a>
          </div>
        </li>
      ))}
    </ul>
  );
}
