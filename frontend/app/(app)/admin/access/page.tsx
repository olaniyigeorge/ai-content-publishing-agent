"use client";

import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { LoadingLine } from "@/components/spinner";
import { useAuth } from "@/lib/auth-context";
import type { AccessRuleOut, AccessRuleType } from "@/lib/types";

/** datetime-local's value has no timezone suffix — matches the pattern
 * already used for scheduling in the publishing queue page. */
function nowForDatetimeLocal(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function RuleRow({ rule, onDeleted }: { rule: AccessRuleOut; onDeleted: () => void }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (!window.confirm(`Remove access for ${rule.type} "${rule.value}"? They will no longer be able to log in.`)) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api.deleteAccessRule(rule.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "failed to remove");
      setPending(false);
    }
  }

  return (
    <li className="animate-fade-in-up flex flex-wrap items-center justify-between gap-3 rounded-xl border border-surface-border bg-surface-card p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-surface-border bg-surface-card-hover px-2 py-0.5 text-xs font-medium text-foreground">
            {rule.type}
          </span>
          <span className="truncate text-sm font-medium text-foreground">{rule.value}</span>
          {!rule.enabled && <span className="text-xs text-muted">(disabled)</span>}
        </div>
        <p className="mt-1 text-xs text-muted">
          added {new Date(rule.created_at).toLocaleString()}
          {rule.expires_at && <> · expires {new Date(rule.expires_at).toLocaleString()}</>}
        </p>
        {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      </div>
      <button
        type="button"
        onClick={handleDelete}
        disabled={pending}
        title="Remove access"
        aria-label="Remove access"
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-surface-border text-red-600 transition-colors duration-150 hover:bg-red-50 disabled:opacity-50"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </li>
  );
}

export default function AccessRulesPage() {
  const { user } = useAuth();
  const [rules, setRules] = useState<AccessRuleOut[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [type, setType] = useState<AccessRuleType>("email");
  const [value, setValue] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(() => {
    api
      .listAccessRules()
      .then((data) => {
        setRules(data);
        setLoadError(null);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "failed to load access rules"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function validate(): string | null {
    const trimmed = value.trim();
    if (!trimmed) return "enter an email or domain";
    if (type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) return "that doesn't look like a valid email";
    if (type === "domain" && !/^[^\s@]+\.[^\s@]+$/.test(trimmed)) return "that doesn't look like a valid domain (e.g. koyatalent.com)";
    if (expiresAt && new Date(expiresAt).getTime() < Date.now()) return "expiry must be in the future";
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) {
      setFormError(err);
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      await api.createAccessRule({
        type,
        value: value.trim(),
        enabled: true,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      });
      setValue("");
      setExpiresAt("");
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "failed to add rule");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="animate-fade-in-up">
      <h1 className="text-lg font-semibold text-foreground">Access</h1>
      <p className="mt-1 text-sm text-muted">
        Who can log in. An email or a whole domain (e.g. <span className="font-mono">koyatalent.com</span>) grants access —
        nobody else can request a login code. There is no separate admin role yet: any signed-in user, including you
        ({user?.email}), can add or remove access here.
      </p>

      <form
        onSubmit={handleSubmit}
        className="glow-card mt-6 flex flex-col gap-3 rounded-xl border border-surface-border bg-surface-card p-4 sm:flex-row sm:flex-wrap sm:items-end"
      >
        <label className="flex flex-col gap-1 text-sm text-muted sm:w-auto">
          Type
          <select
            value={type}
            onChange={(e) => setType(e.target.value as AccessRuleType)}
            className="w-full rounded-md border border-surface-border bg-surface-card px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none sm:w-auto"
          >
            <option value="email">Email</option>
            <option value="domain">Domain</option>
          </select>
        </label>
        <label className="flex min-w-0 flex-col gap-1 text-sm text-muted sm:flex-1">
          {type === "email" ? "Email address" : "Domain"}
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={type === "email" ? "person@koyatalent.com" : "koyatalent.com"}
            className="w-full rounded-md border border-surface-border bg-surface-card px-3 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-muted sm:w-auto">
          Expires (optional)
          <input
            type="datetime-local"
            min={nowForDatetimeLocal()}
            value={expiresAt}
            onChange={(e) => setExpiresAt(e.target.value)}
            className="w-full rounded-md border border-surface-border bg-surface-card px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none sm:w-auto"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:opacity-50 sm:w-auto"
        >
          {submitting ? "Adding…" : "Grant access"}
        </button>
      </form>
      {formError && <p className="mt-2 text-sm text-red-600">{formError}</p>}

      {loadError && <p className="mt-4 text-sm text-red-600">{loadError}</p>}
      {!rules && !loadError && <LoadingLine label="Loading access rules…" />}
      {rules && rules.length === 0 && (
        <div className="glow-card mt-6 rounded-xl border border-dashed border-surface-border bg-surface-card p-10 text-center">
          <p className="text-sm text-muted">
            No access rules yet — nobody can log in until at least one is added (including you, next time your session expires).
          </p>
        </div>
      )}
      {rules && rules.length > 0 && (
        <ul className="mt-6 space-y-3">
          {rules.map((rule) => (
            <RuleRow key={rule.id} rule={rule} onDeleted={load} />
          ))}
        </ul>
      )}
    </div>
  );
}
