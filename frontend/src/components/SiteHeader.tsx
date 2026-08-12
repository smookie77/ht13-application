"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "./AuthProvider";
import { Logo } from "./Logo";

const NAV_LINKS = [
  { href: "/event", label: "The event" },
  { href: "/tickets", label: "Tickets" },
  { href: "/contact", label: "Contact" },
] as const;

export function SiteHeader() {
  const pathname = usePathname();
  const { user, loading } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/85 backdrop-blur">
      <nav
        aria-label="Main"
        className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4"
      >
        <Link
          href="/"
          className="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-600"
        >
          <Logo />
        </Link>

        <div className="flex items-center gap-1 sm:gap-2">
          {NAV_LINKS.map(({ href, label }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={isActive ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "text-blue-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                {label}
              </Link>
            );
          })}

          {/* Rendered only once auth state is known, to avoid a flash of the
              wrong control on first paint. */}
          {!loading &&
            (user ? (
              <Link
                href="/account"
                className="ml-1 rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                {user.full_name.split(" ")[0] || "Account"}
              </Link>
            ) : (
              <Link
                href="/login"
                className="ml-1 hidden rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 sm:inline-flex"
              >
                Sign in
              </Link>
            ))}
        </div>
      </nav>
    </header>
  );
}
