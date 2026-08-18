"use client";

import Link from "next/link";
import { use, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { ApiError, checkInTicket, errorMessage } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import type { Ticket } from "@/lib/types";

type Outcome =
  | { kind: "idle" }
  | { kind: "admitted"; ticket: Ticket }
  | { kind: "already-used"; message: string }
  | { kind: "error"; message: string };

/**
 * What the QR code on a ticket opens.
 *
 * Scanning is intentionally not enough on its own: admitting someone is a
 * staff action, so the page asks a signed-in steward to confirm and the API
 * re-checks the permission. A stolen QR image is therefore useless without
 * staff credentials.
 */
export default function CheckInPage(props: PageProps<"/check-in/[code]">) {
  const { code } = use(props.params);
  const { user, loading } = useAuth();

  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });
  const [busy, setBusy] = useState(false);

  const admit = async () => {
    setBusy(true);
    try {
      setOutcome({ kind: "admitted", ticket: await checkInTicket(code) });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setOutcome({
          kind: "already-used",
          message: errorMessage(err, "This ticket has already been used."),
        });
      } else {
        setOutcome({
          kind: "error",
          message: errorMessage(err, "This ticket could not be verified."),
        });
      }
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <Shell>Loading…</Shell>;
  }

  if (!user) {
    return (
      <Shell title="Staff sign-in required">
        <p className="text-slate-600">
          Ticket verification is for door staff. Sign in to continue.
        </p>
        <Link
          href={`/login?next=/check-in/${code}`}
          className="mt-8 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Sign in
        </Link>
      </Shell>
    );
  }

  return (
    <Shell title="Ticket verification">
      <p className="font-mono text-sm tracking-wide text-slate-500">{code}</p>

      {outcome.kind === "idle" && (
        <button
          type="button"
          onClick={admit}
          disabled={busy}
          className="mt-8 w-full rounded-xl bg-blue-600 px-6 py-4 text-lg font-semibold text-white transition hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400"
        >
          {busy ? "Checking…" : "Verify and admit"}
        </button>
      )}

      {outcome.kind === "admitted" && (
        <Banner tone="ok" title="Admitted">
          <p className="text-lg font-semibold text-emerald-900">
            {outcome.ticket.holder_name}
          </p>
          <p className="mt-1 text-sm text-emerald-800">
            {outcome.ticket.ticket_type_name} · {outcome.ticket.event_title}
          </p>
          <p className="mt-1 text-sm text-emerald-800">
            {formatDate(outcome.ticket.starts_at)},{" "}
            {formatTime(outcome.ticket.starts_at)}
          </p>
        </Banner>
      )}

      {outcome.kind === "already-used" && (
        <Banner tone="warn" title="Already used">
          <p className="text-sm text-amber-800">{outcome.message}</p>
        </Banner>
      )}

      {outcome.kind === "error" && (
        <Banner tone="bad" title="Not valid">
          <p className="text-sm text-red-800">{outcome.message}</p>
        </Banner>
      )}
    </Shell>
  );
}

const TONES = {
  ok: "border-emerald-300 bg-emerald-50 text-emerald-900",
  warn: "border-amber-300 bg-amber-50 text-amber-900",
  bad: "border-red-300 bg-red-50 text-red-900",
} as const;

function Banner({
  tone,
  title,
  children,
}: {
  tone: keyof typeof TONES;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`mt-8 rounded-2xl border p-6 text-left ${TONES[tone]}`} role="status">
      <p className="text-xs font-semibold uppercase tracking-wide">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function Shell({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md px-6 py-16 text-center">
      {title && <h1 className="text-2xl font-bold tracking-tight">{title}</h1>}
      <div className="mt-4">{children}</div>
    </main>
  );
}
