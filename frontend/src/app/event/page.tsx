import type { Metadata } from "next";
import Link from "next/link";

import { EventLoadError } from "@/components/EventLoadError";
import { formatDate, formatTime } from "@/lib/format";
import { loadFeaturedEvent } from "@/lib/event";

export const metadata: Metadata = {
  title: "The event",
  description:
    "Everything about Hack TUES 13 — schedule, venue, who it is for and what to bring.",
};

const SCHEDULE = [
  { day: "Day 1", items: ["Registration & opening", "Team forming", "Hacking starts"] },
  { day: "Day 2", items: ["Mentor sessions", "Checkpoint demos", "Night shift"] },
  { day: "Day 3", items: ["Final commits", "Demo night", "Awards"] },
];

const FAQ = [
  {
    q: "Who can take part?",
    a: "High-school students in teams of up to five. Beginners are welcome — mentors are on site the whole time.",
  },
  {
    q: "What should I bring?",
    a: "A laptop, a charger and an ID. Food, drinks and a place to crash are covered.",
  },
  {
    q: "Do I need a team in advance?",
    a: "No. There is a team-forming session right after the opening.",
  },
  {
    q: "Is the ticket transferable?",
    a: "Tickets are personal — the name on the PDF is checked with the QR code at the door.",
  },
];

export default async function EventPage() {
  const result = await loadFeaturedEvent();
  if (!result.ok) return <EventLoadError hint={result.hint} />;

  const { event } = result;

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-700">
        {formatDate(event.starts_at)} · {event.city}
      </p>
      <h1 className="mt-4 text-4xl font-bold tracking-tight">{event.title}</h1>
      <p className="mt-4 text-xl text-slate-600">{event.tagline}</p>
      <p className="mt-6 leading-relaxed text-slate-600">{event.description}</p>

      <section className="mt-12">
        <h2 className="text-2xl font-bold tracking-tight">Practical details</h2>
        <dl className="mt-6 divide-y divide-slate-200 border-y border-slate-200">
          <div className="grid gap-1 py-4 sm:grid-cols-[180px_1fr]">
            <dt className="font-medium text-slate-500">Starts</dt>
            <dd>
              {formatDate(event.starts_at)}, {formatTime(event.starts_at)}
            </dd>
          </div>
          {event.ends_at && (
            <div className="grid gap-1 py-4 sm:grid-cols-[180px_1fr]">
              <dt className="font-medium text-slate-500">Ends</dt>
              <dd>
                {formatDate(event.ends_at)}, {formatTime(event.ends_at)}
              </dd>
            </div>
          )}
          {event.doors_open_at && (
            <div className="grid gap-1 py-4 sm:grid-cols-[180px_1fr]">
              <dt className="font-medium text-slate-500">Doors open</dt>
              <dd>{formatTime(event.doors_open_at)}</dd>
            </div>
          )}
          <div className="grid gap-1 py-4 sm:grid-cols-[180px_1fr]">
            <dt className="font-medium text-slate-500">Venue</dt>
            <dd>
              {event.venue_name}
              <br />
              <span className="text-slate-600">
                {event.venue_address}, {event.city}
              </span>
            </dd>
          </div>
          <div className="grid gap-1 py-4 sm:grid-cols-[180px_1fr]">
            <dt className="font-medium text-slate-500">Seating</dt>
            <dd>{event.has_seating ? "Reserved seats" : "Open seating"}</dd>
          </div>
        </dl>
      </section>

      <section className="mt-12">
        <h2 className="text-2xl font-bold tracking-tight">Schedule</h2>
        <div className="mt-6 grid gap-6 sm:grid-cols-3">
          {SCHEDULE.map(({ day, items }) => (
            <div key={day} className="rounded-2xl border border-slate-200 p-5">
              <h3 className="font-semibold text-blue-700">{day}</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-600">
                {items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm text-slate-400">
          Indicative — the final programme is announced closer to the date.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-2xl font-bold tracking-tight">Frequently asked</h2>
        <div className="mt-6 space-y-4">
          {FAQ.map(({ q, a }) => (
            <details
              key={q}
              className="group rounded-2xl border border-slate-200 p-5 open:bg-slate-50"
            >
              <summary className="cursor-pointer font-medium marker:content-none">
                {q}
              </summary>
              <p className="mt-2 text-slate-600">{a}</p>
            </details>
          ))}
        </div>
      </section>

      <div className="mt-12 flex flex-wrap gap-4">
        <Link
          href="/tickets"
          className="inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Get a ticket
        </Link>
        <Link
          href="/contact"
          className="inline-flex rounded-xl border border-slate-300 px-6 py-3 font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
        >
          Still have a question?
        </Link>
      </div>
    </main>
  );
}
