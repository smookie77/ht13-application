"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { createReservation, errorMessage } from "@/lib/api";
import { formatPrice } from "@/lib/format";
import type { TicketType } from "@/lib/types";

import { useAuth } from "./AuthProvider";
import { useAvailability } from "./AvailabilityProvider";

export function TicketTypeCard({ ticketType }: { ticketType: TicketType }) {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { availability } = useAvailability();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Static copy comes from the server render; the count comes from the live
  // feed so a tier greys out the moment it sells out.
  const live = availability.ticket_types.find((t) => t.id === ticketType.id);
  const available = live?.quantity_available ?? ticketType.quantity_available;
  const soldOut = live?.is_sold_out ?? ticketType.is_sold_out;
  const salesOpen = availability.sales_state === "open";

  const join = async () => {
    setBusy(true);
    setError(null);
    try {
      const reservation = await createReservation({ ticket_type_id: ticketType.id });
      router.push(`/reservations/${reservation.public_id}`);
    } catch (err) {
      setError(errorMessage(err, "Could not join the queue. Please try again."));
      setBusy(false);
    }
  };

  return (
    <div
      className={`flex flex-col rounded-2xl border p-6 transition ${
        soldOut
          ? "border-slate-200 bg-slate-50 opacity-60"
          : "border-slate-200 bg-white shadow-sm hover:border-blue-400 hover:shadow-md"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-lg font-semibold text-slate-900">{ticketType.name}</h3>
        <p className="whitespace-nowrap text-lg font-bold text-blue-700">
          {formatPrice(ticketType.price_minor, ticketType.currency)}
        </p>
      </div>

      <p className="mt-2 flex-1 text-sm text-slate-600">{ticketType.description}</p>

      <p className="mt-4 text-sm tabular-nums text-slate-500" aria-live="polite">
        {soldOut ? "Sold out" : `${available.toLocaleString("en-GB")} left`}
      </p>

      <div className="mt-4">
        <BuyControl
          soldOut={soldOut}
          salesOpen={salesOpen}
          loading={loading}
          user={user}
          busy={busy}
          onJoin={join}
        />
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

const buttonClass =
  "w-full rounded-xl bg-blue-600 px-4 py-2.5 text-center text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400";

function BuyControl({
  soldOut,
  salesOpen,
  loading,
  user,
  busy,
  onJoin,
}: {
  soldOut: boolean;
  salesOpen: boolean;
  loading: boolean;
  user: { is_email_verified: boolean } | null;
  busy: boolean;
  onJoin: () => void;
}) {
  if (soldOut) {
    return (
      <button type="button" disabled className={buttonClass}>
        Sold out
      </button>
    );
  }
  if (!salesOpen) {
    return (
      <button type="button" disabled className={buttonClass}>
        Not on sale
      </button>
    );
  }
  if (loading) {
    return (
      <button type="button" disabled className={buttonClass}>
        Loading…
      </button>
    );
  }
  // Signed-out and unverified buyers are told what to do next rather than
  // being handed a button that would fail server-side.
  if (!user) {
    return (
      <Link href="/login?next=/tickets" className={`block ${buttonClass}`}>
        Sign in to buy
      </Link>
    );
  }
  if (!user.is_email_verified) {
    return (
      <Link href="/verify-email" className={`block ${buttonClass}`}>
        Confirm your email first
      </Link>
    );
  }
  return (
    <button type="button" onClick={onJoin} disabled={busy} className={buttonClass}>
      {busy ? "Joining the queue…" : "Get in line"}
    </button>
  );
}
