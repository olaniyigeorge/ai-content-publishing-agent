"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { LoadingLine } from "@/components/spinner";
import type { ContentRequestOut, UsageSummaryOut } from "@/lib/types";

export default function RequestsPage() {
  const [requests, setRequests] = useState<ContentRequestOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<UsageSummaryOut | null>(null);

  useEffect(() => {
    api
      .listRequests()
      .then(setRequests)
      .catch((err) => setError(err instanceof ApiError ? err.message : "failed to load requests"));
    // Best-effort — a usage-summary hiccup shouldn't block the requests list.
    api.getUsageSummary().then(setUsage).catch(() => undefined);
  }, []);

  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Content requests</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>Track every request from idea to published.</span>
            {usage && usage.call_count > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full border border-surface-border bg-surface-card px-2.5 py-0.5 text-xs font-medium text-muted">
                {usage.call_count} call{usage.call_count === 1 ? "" : "s"}
                <span className="text-muted/50">·</span>
                <span className="text-foreground">${usage.total_cost_usd.toFixed(4)}</span>
                total
              </span>
            )}
          </p>
        </div>
        <Link
          href="/requests/new"
          className="glow-primary rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 active:translate-y-0"
        >
          New request
        </Link>
      </div>

      {error && <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {!requests && !error && <LoadingLine label="Loading requests…" centered />}

      {requests && requests.length === 0 && (
        <div className="glow-card mt-6 rounded-xl border border-dashed border-surface-border bg-surface-card p-10 text-center">
          <p className="text-sm text-muted">No content requests yet.</p>
          <Link href="/requests/new" className="mt-2 inline-block text-sm font-medium text-primary hover:underline">
            Submit your first one →
          </Link>
        </div>
      )}

      {requests && requests.length > 0 && (
        <div className="glow-card mt-6 overflow-hidden rounded-xl border border-surface-border bg-surface-card">
          <table className="w-full text-sm">
            <thead className="border-b border-surface-border bg-surface-base text-left text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">ID</th>
                <th className="px-4 py-2.5 font-medium">Idea</th>
                <th className="px-4 py-2.5 font-medium">Audience</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r, i) => {
                const idea = r.raw_idea?.trim();
                const displayIdea = idea
                  ? idea.charAt(0).toUpperCase() + idea.slice(1)
                  : "(source URL only)";

                return (
                  <tr
                    key={r.id}
                    className="animate-fade-in-up border-b border-surface-border/70 transition-colors duration-150 last:border-0 hover:bg-surface-card-hover"
                    style={{ animationDelay: `${Math.min(i, 10) * 30}ms` }}
                  >
                    <td className="px-4 py-3">
                      <span
                        className="font-mono text-xs text-muted/70"
                        title={r.id}
                      >
                        {r.id.slice(0, 8)}
                      </span>
                    </td>

                    <td className="px-4 py-3">
                      <Link
                        href={`/requests/${r.id}`}
                        className="font-medium text-foreground hover:text-primary hover:underline"
                      >
                        {displayIdea}
                      </Link>
                    </td>

                    <td className="px-4 py-3 text-muted">
                      {r.target_audience}
                    </td>

                    <td className="px-4 py-3">
                      <StatusBadge status={r.status} />
                    </td>

                    <td className="px-4 py-3 text-muted">
                      {new Date(r.updated_at).toLocaleString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
