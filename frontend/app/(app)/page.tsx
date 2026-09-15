"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { LoadingLine } from "@/components/spinner";
import type { ContentRequestOut } from "@/lib/types";

export default function RequestsPage() {
  const [requests, setRequests] = useState<ContentRequestOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRequests()
      .then(setRequests)
      .catch((err) => setError(err instanceof ApiError ? err.message : "failed to load requests"));
  }, []);

  return (
    <div className="animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Content requests</h1>
          <p className="mt-1 text-sm text-muted">Track every request from idea to published.</p>
        </div>
        <Link
          href="/requests/new"
          className="glow-primary rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 active:translate-y-0"
        >
          New request
        </Link>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {!requests && !error && <LoadingLine label="Loading requests…" />}

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
                <th className="px-4 py-2.5 font-medium">Idea</th>
                <th className="px-4 py-2.5 font-medium">Audience</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r, i) => (
                <tr
                  key={r.id}
                  className="animate-fade-in-up border-b border-surface-border/70 transition-colors duration-150 last:border-0 hover:bg-surface-card-hover"
                  style={{ animationDelay: `${Math.min(i, 10) * 30}ms` }}
                >
                  <td className="px-4 py-3">
                    <Link href={`/requests/${r.id}`} className="font-medium text-foreground hover:text-primary hover:underline">
                      {r.raw_idea?.trim() || "(source URL only)"}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted">{r.target_audience}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-4 py-3 text-muted">{new Date(r.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
