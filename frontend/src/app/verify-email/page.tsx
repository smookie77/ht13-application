"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { errorMessage, resendVerification, verifyEmail } from "@/lib/api";

type State = "idle" | "verifying" | "done" | "failed";

function VerifyEmail() {
  const token = useSearchParams().get("token");
  const { user, refresh } = useAuth();

  const [state, setState] = useState<State>(token ? "verifying" : "idle");
  const [error, setError] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  // React runs effects twice in dev StrictMode; verify only once.
  const attempted = useRef(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    verifyEmail(token)
      .then(async () => {
        await refresh();
        setState("done");
      })
      .catch((err) => {
        setError(errorMessage(err, "This link is not valid."));
        setState("failed");
      });
  }, [token, refresh]);

  if (state === "verifying") {
    return <Shell>Confirming your email…</Shell>;
  }

  if (state === "done") {
    return (
      <Shell title="Email confirmed">
        <p className="text-slate-600">You can buy a ticket now.</p>
        <Link
          href="/tickets"
          className="mt-8 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Go to tickets
        </Link>
      </Shell>
    );
  }

  if (state === "failed") {
    return (
      <Shell title="That link did not work">
        <p className="text-slate-600">{error}</p>
        <ResendBlock
          email={user?.email}
          resent={resent}
          onResent={() => setResent(true)}
        />
      </Shell>
    );
  }

  return (
    <Shell title="Confirm your email">
      <p className="text-slate-600">
        {user
          ? user.is_email_verified
            ? "Your email is already confirmed."
            : "Open the link we emailed you. It is valid for 24 hours."
          : "Open the confirmation link we emailed you."}
      </p>
      {user && !user.is_email_verified && (
        <ResendBlock
          email={user.email}
          resent={resent}
          onResent={() => setResent(true)}
        />
      )}
    </Shell>
  );
}

function ResendBlock({
  email,
  resent,
  onResent,
}: {
  email?: string;
  resent: boolean;
  onResent: () => void;
}) {
  const [busy, setBusy] = useState(false);
  if (!email) return null;

  if (resent) {
    return (
      <p className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
        A fresh link is on its way to {email}.
      </p>
    );
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await resendVerification(email);
          onResent();
        } finally {
          setBusy(false);
        }
      }}
      className="mt-8 rounded-xl border border-slate-300 px-6 py-3 font-semibold text-slate-700 transition hover:bg-slate-50 disabled:text-slate-400"
    >
      {busy ? "Sending…" : "Send the link again"}
    </button>
  );
}

function Shell({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md px-6 py-20 text-center">
      {title && <h1 className="text-3xl font-bold tracking-tight">{title}</h1>}
      <div className="mt-4">{children}</div>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<Shell>Loading…</Shell>}>
      <VerifyEmail />
    </Suspense>
  );
}
