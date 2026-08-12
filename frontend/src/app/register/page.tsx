"use client";

import Link from "next/link";
import { useState } from "react";

import { Field } from "@/components/Field";
import { errorMessage, register } from "@/lib/api";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ email, full_name: fullName, password });
      setSent(true);
    } catch (err) {
      setError(errorMessage(err, "Could not create the account."));
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <main className="mx-auto max-w-md px-6 py-16 text-center">
        <h1 className="text-3xl font-bold tracking-tight">Check your inbox</h1>
        <p className="mt-4 text-slate-600">
          We sent a confirmation link to <strong>{email}</strong>. Your email has to
          be confirmed before you can take a ticket.
        </p>
        <p className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
          In development the email is printed to the Django server log — copy the
          link from there.
        </p>
        <Link
          href="/login"
          className="mt-8 inline-flex rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition hover:bg-blue-700"
        >
          Go to sign in
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight">Create an account</h1>
      <p className="mt-2 text-slate-600">
        The name you enter goes on the ticket, so use the one you will show at the
        door.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-4">
        <Field
          label="Full name"
          type="text"
          value={fullName}
          onChange={setFullName}
          autoComplete="name"
        />
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
          autoComplete="new-password"
          hint="At least 8 characters, and not an obvious one."
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
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>

      <p className="mt-6 text-sm text-slate-600">
        Already registered?{" "}
        <Link href="/login" className="font-medium text-blue-700 hover:underline">
          Sign in
        </Link>
      </p>
    </main>
  );
}
