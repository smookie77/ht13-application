"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { Field } from "@/components/Field";
import { errorMessage } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { signIn } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only same-site paths are honoured, so `?next=` cannot bounce a signed-in
  // user off to an attacker's site.
  const rawNext = params.get("next");
  const next = rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//")
    ? rawNext
    : "/tickets";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      router.push(next);
    } catch (err) {
      setError(errorMessage(err, "Invalid email or password."));
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight">Sign in</h1>
      <p className="mt-2 text-slate-600">You need an account to buy a ticket.</p>

      <form onSubmit={submit} className="mt-8 space-y-4">
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
        />

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-6 text-sm text-slate-600">
        No account yet?{" "}
        <Link href="/register" className="font-medium text-blue-700 hover:underline">
          Create one
        </Link>
      </p>
    </main>
  );
}

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary during prerender.
  return (
    <Suspense fallback={<main className="px-6 py-20 text-center text-slate-500">Loading…</main>}>
      <LoginForm />
    </Suspense>
  );
}
