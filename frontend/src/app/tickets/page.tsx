import type { Metadata } from "next";

import { AvailabilityProvider } from "@/components/AvailabilityProvider";
import { EventLoadError } from "@/components/EventLoadError";
import { TicketCounter } from "@/components/TicketCounter";
import { TicketTypeCard } from "@/components/TicketTypeCard";
import { loadFeaturedEvent } from "@/lib/event";

export const metadata: Metadata = {
  title: "Tickets",
  description: "Choose a ticket tier for Hack TUES 13. Limited quantities.",
};

const QUEUE_STEPS = [
  {
    title: "You ask",
    body: "Your request is recorded the instant it arrives and you get a place in line.",
  },
  {
    title: "You wait in order",
    body: "Requests are served strictly first-come, first-served. You see your position live.",
  },
  {
    title: "You get your ticket",
    body: "A PDF ticket lands in your inbox and stays downloadable from your account.",
  },
];

export default async function TicketsPage() {
  const result = await loadFeaturedEvent();
  if (!result.ok) return <EventLoadError hint={result.hint} />;

  const { event, availability } = result;

  return (
    <AvailabilityProvider initial={availability}>
      <main className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr] lg:items-start">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">Tickets</h1>
            <p className="mt-3 max-w-xl text-lg text-slate-600">
              {event.title} · {event.venue_name}, {event.city}. Pick a tier below —
              quantities are limited and update live.
            </p>
          </div>
          <TicketCounter />
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {event.ticket_types.map((ticketType) => (
            <TicketTypeCard key={ticketType.id} ticketType={ticketType} />
          ))}
        </div>

        <section className="mt-16 rounded-2xl border border-slate-200 bg-slate-50 p-8">
          <h2 className="text-xl font-bold tracking-tight">How the queue works</h2>
          <p className="mt-2 max-w-2xl text-slate-600">
            Hundreds of people press buy in the same second. Nobody gets skipped and
            we never sell a ticket twice.
          </p>
          <ol className="mt-6 grid gap-6 sm:grid-cols-3">
            {QUEUE_STEPS.map((step, index) => (
              <li key={step.title}>
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                  {index + 1}
                </span>
                <h3 className="mt-3 font-semibold text-slate-900">{step.title}</h3>
                <p className="mt-1 text-sm text-slate-600">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </AvailabilityProvider>
  );
}
