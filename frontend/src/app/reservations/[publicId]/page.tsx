"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { QueueTracker } from "@/components/QueueTracker";
import { errorMessage, getReservation } from "@/lib/api";
import type { Reservation } from "@/lib/types";

/**
 * Client-rendered on purpose: a reservation is private, and the session lives
 * in a browser cookie. Fetching it here keeps the credential in the browser
 * rather than forwarding it through the Next server.
 */
export default function ReservationPage(props: PageProps<"/reservations/[publicId]">) {
  const { publicId } = use(props.params);
  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getReservation(publicId)
      .then(setReservation)
      .catch((err) =>
        setError(
          errorMessage(err, "This reservation could not be found, or is not yours."),
        ),
      );
  }, [publicId]);

  if (error) {
    return (
      <main className="mx-auto max-w-md px-6 py-20 text-center">
        <h1 className="text-2xl font-bold">Reservation unavailable</h1>
        <p className="mt-3 text-slate-600">{error}</p>
        <Link
          href="/tickets"
          className="mt-8 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Back to tickets
        </Link>
      </main>
    );
  }

  if (!reservation) {
    return (
      <main className="px-6 py-20 text-center text-slate-500">
        Loading your place in line…
      </main>
    );
  }

  return (
    <main className="px-6 py-16">
      <QueueTracker initial={reservation} />
    </main>
  );
}
