/**
 * Placeholder brand mark: a ticket stub with a perforated stub line.
 *
 * Deliberately an inline SVG rather than an image file - it inherits
 * `currentColor`, scales without a second asset, and the same shape is reused
 * as the favicon (`app/icon.svg`). Swap it for the real logo when there is one.
 */
export function TicketIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <path
        d="M4 9a3 3 0 0 1 3-3h18a3 3 0 0 1 3 3v2.5a4.5 4.5 0 0 0 0 9V23a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-2.5a4.5 4.5 0 0 0 0-9V9Z"
        fill="currentColor"
      />
      <path
        d="M20 8v16"
        stroke="white"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeDasharray="2 3"
      />
    </svg>
  );
}

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <TicketIcon className="h-7 w-7 text-blue-600" />
      <span className="text-lg font-bold tracking-tight text-slate-900">
        Hack TUES 13
      </span>
    </span>
  );
}
