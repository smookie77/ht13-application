"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { TicketList } from "@/components/TicketList";
import { errorMessage, listReservations } from "@/lib/api";
import { formatDate, formatTime } from "@/lib/format";
import type { Reservation, ReservationStatus } from "@/lib/types";

const STATUS_STYLES: Record<ReservationStatus, string> = {
  queued: "bg-blue-50 text-blue-700",
  allocated: "bg-amber-50 text-amber-700",
  confirmed: "bg-emerald-50 text-emerald-700",
  rejected: "bg-slate-100 text-slate-500",
  expired: "bg-slate-100 text-slate-500",
  cancelled: "bg-slate-100 text-slate-500",
};

export default function AccountPage() {
  const { user, loading, signOut } = useAuth();
  const [reservations, setReservations] = useState<Reservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    listReservations()
      .then((page) => setReservations(page.results))
      .catch((err) => setError(errorMessage(err, "Could not load your reservations.")));
  }, [user]);

  if (loading) {
    return <main className="px-6 py-20 text-center text-slate-500">Loading…</main>;
  }

  if (!user) {
    return (
      <main className="mx-auto max-w-md px-6 py-20 text-center">
        <h1 className="text-2xl font-bold">You are not signed in</h1>
        <Link
          href="/login?next=/account"
          className="mt-8 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Sign in
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{user.full_name}</h1>
          <p className="mt-1 text-slate-600">{user.email}</p>
        </div>
        <button
          type="button"
          onClick={signOut}
          className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Sign out
        </button>
      </div>

      {!user.is_email_verified && (
        <div className="mt-6 rounded-2xl border border-amber-300 bg-amber-50 p-5">
          <p className="font-medium text-amber-900">Your email is not confirmed yet</p>
          <p className="mt-1 text-sm text-amber-800">
            You cannot take a ticket until it is.
          </p>
          <Link
            href="/verify-email"
            className="mt-3 inline-flex text-sm font-semibold text-amber-900 underline"
          >
            Confirm now
          </Link>
        </div>
      )}

      <h2 className="mt-12 text-xl font-bold tracking-tight">My tickets</h2>
      <TicketList />

      <h2 className="mt-12 text-xl font-bold tracking-tight">My reservations</h2>

      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error}
        </p>
      )}

      {reservations === null && !error && (
        <p className="mt-4 text-slate-500">Loading…</p>
      )}

      {reservations?.length === 0 && (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-8 text-center">
          <p className="text-slate-600">You have not reserved anything yet.</p>
          <Link
            href="/tickets"
            className="mt-4 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
          >
            Browse tickets
          </Link>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {reservations?.map((reservation) => (
          <li key={reservation.public_id}>
            <Link
              href={`/reservations/${reservation.public_id}`}
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 p-5 transition hover:border-blue-400 hover:bg-slate-50"
            >
              <div>
                <p className="font-semibold">{reservation.event_title}</p>
                <p className="mt-1 text-sm text-slate-600">
                  {reservation.quantity} × {reservation.ticket_type_name} ·{" "}
                  {formatDate(reservation.created_at)} at{" "}
                  {formatTime(reservation.created_at)}
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                  STATUS_STYLES[reservation.status]
                }`}
              >
                {reservation.status}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
