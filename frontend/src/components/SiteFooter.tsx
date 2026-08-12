import Link from "next/link";

import { TicketIcon } from "./Logo";

export function SiteFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-6 py-10 sm:flex-row sm:justify-between">
        <span className="inline-flex items-center gap-2.5 text-sm text-slate-500">
          <TicketIcon className="h-6 w-6 text-blue-600" />
          Hack TUES 13 · application task
        </span>

        <div className="flex gap-5 text-sm text-slate-500">
          <Link href="/event" className="transition hover:text-slate-900">
            The event
          </Link>
          <Link href="/tickets" className="transition hover:text-slate-900">
            Tickets
          </Link>
          <Link href="/contact" className="transition hover:text-slate-900">
            Contact
          </Link>
        </div>
      </div>
    </footer>
  );
}
