import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Contact",
  description: "Get in touch with the Hack TUES 13 organising team.",
};

// Placeholder details until the real organiser channels are wired up.
const CHANNELS = [
  {
    label: "General enquiries",
    value: "hello@hacktues.example",
    href: "mailto:hello@hacktues.example",
  },
  {
    label: "Ticket support",
    value: "tickets@hacktues.example",
    href: "mailto:tickets@hacktues.example",
  },
  {
    label: "Partnerships",
    value: "partners@hacktues.example",
    href: "mailto:partners@hacktues.example",
  },
];

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-bold tracking-tight">Contact</h1>
      <p className="mt-3 max-w-xl text-lg text-slate-600">
        Something unclear about the event or your ticket? Reach out — we answer
        within one working day.
      </p>

      <section className="mt-10 grid gap-4 sm:grid-cols-3">
        {CHANNELS.map(({ label, value, href }) => (
          <a
            key={label}
            href={href}
            className="rounded-2xl border border-slate-200 p-5 transition hover:border-blue-400 hover:bg-slate-50"
          >
            <h2 className="text-sm font-medium text-slate-500">{label}</h2>
            <p className="mt-2 font-medium text-blue-700">{value}</p>
          </a>
        ))}
      </section>

      <section className="mt-12 grid gap-8 sm:grid-cols-2">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Where to find us</h2>
          <address className="mt-4 not-italic leading-relaxed text-slate-600">
            TUES @ TU-Sofia
            <br />
            8 Kliment Ohridski Blvd
            <br />
            Sofia, Bulgaria
          </address>
        </div>

        <div>
          <h2 className="text-2xl font-bold tracking-tight">Before you write</h2>
          <p className="mt-4 text-slate-600">
            Most ticket questions are answered on the event page — including what to
            bring, whether tickets are transferable and how the door check works.
          </p>
          <Link
            href="/event"
            className="mt-4 inline-flex rounded-xl border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            Read the FAQ
          </Link>
        </div>
      </section>

      <p className="mt-12 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        Placeholder contact details — swap them for the real organiser channels
        before launch.
      </p>
    </main>
  );
}
