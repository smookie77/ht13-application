import Link from "next/link";

import { AvailabilityProvider } from "@/components/AvailabilityProvider";
import { EventLoadError } from "@/components/EventLoadError";
import { TicketCounter } from "@/components/TicketCounter";
import { formatDate, formatPrice, formatTime } from "@/lib/format";
import { loadFeaturedEvent } from "@/lib/event";

export default async function Home() {
  const result = await loadFeaturedEvent();
  if (!result.ok) return <EventLoadError hint={result.hint} />;

  const { event, availability } = result;
  const cheapest = event.ticket_types.reduce(
    (min, t) => Math.min(min, t.price_minor),
    Infinity,
  );

  return (
    <AvailabilityProvider initial={availability}>
      <main>
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-slate-200">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(37,99,235,0.10),transparent_60%)]" />
          <div className="relative mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-[1.4fr_1fr] lg:py-28">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-700">
                {formatDate(event.starts_at)} · {event.city}
              </p>
              <h1 className="mt-4 text-5xl font-bold tracking-tight lg:text-6xl">
                {event.title}
              </h1>
              <p className="mt-4 max-w-xl text-xl text-slate-600">{event.tagline}</p>
              <p className="mt-6 max-w-xl leading-relaxed text-slate-600">
                {event.description}
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-4">
                <Link
                  href="/tickets"
                  className="inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
                >
                  Get a ticket
                </Link>
                <Link
                  href="/event"
                  className="inline-flex rounded-xl border border-slate-300 px-6 py-3 font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                >
                  More about the event
                </Link>
              </div>
            </div>

            <div className="lg:pt-6">
              <TicketCounter />
            </div>
          </div>
        </section>

        {/* Practical details */}
        <section className="mx-auto max-w-6xl px-6 py-16">
          <dl className="grid gap-8 sm:grid-cols-3">
            <div>
              <dt className="text-sm uppercase tracking-wide text-slate-400">When</dt>
              <dd className="mt-2 font-medium">{formatDate(event.starts_at)}</dd>
              <dd className="text-slate-600">
                {event.doors_open_at
                  ? `Doors ${formatTime(event.doors_open_at)} · Starts ${formatTime(event.starts_at)}`
                  : `Starts ${formatTime(event.starts_at)}`}
              </dd>
            </div>
            <div>
              <dt className="text-sm uppercase tracking-wide text-slate-400">Where</dt>
              <dd className="mt-2 font-medium">{event.venue_name}</dd>
              <dd className="text-slate-600">
                {event.venue_address}, {event.city}
              </dd>
            </div>
            <div>
              <dt className="text-sm uppercase tracking-wide text-slate-400">
                Sales close
              </dt>
              <dd className="mt-2 font-medium">{formatDate(event.sales_close_at)}</dd>
              <dd className="text-slate-600">or when the last ticket goes</dd>
            </div>
          </dl>
        </section>

        {/* Tickets teaser - the full tier grid lives on /tickets */}
        <section className="border-t border-slate-200 bg-slate-50">
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-6 py-16 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">
                {event.ticket_types.length} ticket tiers, from{" "}
                {formatPrice(cheapest, event.ticket_types[0]?.currency ?? "BGN")}
              </h2>
              <p className="mt-2 text-slate-600">
                Limited quantities. Everyone is served in the order they ask.
              </p>
            </div>
            <Link
              href="/tickets"
              className="inline-flex whitespace-nowrap rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
            >
              See tickets
            </Link>
          </div>
        </section>
      </main>
    </AvailabilityProvider>
  );
}
