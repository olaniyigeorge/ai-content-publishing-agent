"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();

  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleRequestCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.requestCode(email.trim());
      setStep("code");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "something went wrong — try again");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifyCode(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.verifyCode(email.trim(), code.trim());
      await refresh();
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? "invalid or expired code" : "something went wrong — try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center bg-surface-base px-4">
      <div className="glow-card w-full max-w-sm animate-fade-in-up rounded-xl border border-surface-border bg-surface-card p-8">
        <h1 className="text-xl font-semibold text-foreground">Koya Content Agent</h1>
        <p className="mt-1 text-sm text-muted">Sign in with an emailed one-time code.</p>

        {step === "email" ? (
          <form onSubmit={handleRequestCode} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-foreground">
                Work email
              </label>
              <input
                id="email"
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 text-sm transition-colors duration-150 focus:border-primary focus:outline-none"
                placeholder="you@koyatalent.com"
              />
            </div>
            {error && <p className="animate-fade-in text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="glow-primary w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-50"
            >
              {submitting ? "Sending..." : "Send code"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyCode} className="mt-6 animate-fade-in-up space-y-4">
            <p className="text-sm text-muted">
              If <span className="font-medium text-foreground">{email}</span> is eligible, a 6-digit code was sent. Enter it below.
            </p>
            <div>
              <label htmlFor="code" className="block text-sm font-medium text-foreground">
                Code
              </label>
              <input
                id="code"
                type="text"
                inputMode="numeric"
                autoFocus
                required
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="mt-1 w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 text-center text-lg tracking-[0.5em] transition-colors duration-150 focus:border-primary focus:outline-none"
                placeholder="000000"
              />
            </div>
            {error && <p className="animate-fade-in text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="glow-primary w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-50"
            >
              {submitting ? "Verifying..." : "Verify and sign in"}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setCode("");
                setError(null);
              }}
              className="w-full text-center text-sm text-muted hover:text-foreground hover:underline"
            >
              Use a different email
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
