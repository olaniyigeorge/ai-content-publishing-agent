"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, CheckCircle2, ChevronDown, ChevronUp, Copy, Info, Mail, Share2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { HtmlContentPreview } from "@/components/html-content-preview";
import { StatusBadge } from "@/components/status-badge";
import { LoadingLine } from "@/components/spinner";
import { QUEUE_STATUS_HELP, htmlToPlainText } from "@/lib/queue-status";
import type { PublishingQueueOut, QueueStatus } from "@/lib/types";

const MANUAL_STATUSES: QueueStatus[] = ["queued", "ready_to_publish", "published", "failed", "cancelled"];

const CHANNEL_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  x: "X",
  newsletter: "Newsletter",
};

const CHANNEL_TABS: { key: "all" | "linkedin" | "x" | "newsletter"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "x", label: "X" },
  { key: "newsletter", label: "Newsletter" },
];

const WAITING_STATUSES: QueueStatus[] = ["queued", "ready_to_publish"];
const FAILED_STATUSES: QueueStatus[] = ["failed", "dead_letter"];

function queueStats(items: PublishingQueueOut[]) {
  return {
    total: items.length,
    waiting: items.filter((q) => WAITING_STATUSES.includes(q.status)).length,
    scheduled: items.filter((q) => q.status === "queued" && q.scheduled_for).length,
    published: items.filter((q) => q.status === "published").length,
    failed: items.filter((q) => FAILED_STATUSES.includes(q.status)).length,
    cancelled: items.filter((q) => q.status === "cancelled").length,
  };
}

function StatTile({ label, value, tone }: { label: string; value: number; tone?: "emerald" | "amber" | "red" }) {
  const toneClass =
    tone === "emerald" ? "text-emerald-700" : tone === "amber" ? "text-amber-700" : tone === "red" ? "text-red-700" : "text-foreground";
  return (
    <div className="glow-card min-w-[92px] flex-1 rounded-xl border border-surface-border bg-surface-card px-3 py-2.5">
      <p className={`text-xl font-semibold ${toneClass}`}>{value}</p>
      <p className="mt-0.5 text-xs text-muted">{label}</p>
    </div>
  );
}

function previewOf(content: string | null, max = 160): string {
  if (!content) return "";
  const flat = content.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max)}…` : flat;
}

/** datetime-local's value has no timezone suffix — safe to string-compare
 * against "now" formatted the same way, no Date parsing ambiguity. */
function nowForDatetimeLocal(): string {
  const d = new Date();
  d.setSeconds(0, 0);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function shareUrl(q: PublishingQueueOut): { label: string; icon: typeof Share2; onClick: () => void } | null {
  if (!q.content) return null;
  const plainContent = q.content_format === "html" ? htmlToPlainText(q.content) : q.content;
  switch (q.channel) {
    case "x":
      return {
        label: "Share on X",
        icon: Share2,
        onClick: () =>
          window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(plainContent)}`, "_blank", "noopener,noreferrer"),
      };
    case "linkedin":
      return {
        label: "Share on LinkedIn",
        icon: Share2,
        onClick: () => {
          // LinkedIn's share intent only accepts a URL, not raw post text — so
          // we copy the content and open LinkedIn's own composer instead.
          navigator.clipboard?.writeText(plainContent).catch(() => {});
          window.open("https://www.linkedin.com/feed/?shareActive=true", "_blank", "noopener,noreferrer");
        },
      };
    case "newsletter":
      return {
        label: "Open in email",
        icon: Mail,
        onClick: () => {
          // mailto bodies are plain text only — email clients won't render
          // the HTML this channel's content is generated as.
          const subject = encodeURIComponent(q.article_title ?? "Newsletter");
          const body = encodeURIComponent(plainContent);
          window.location.href = `mailto:?subject=${subject}&body=${body}`;
        },
      };
    default:
      return null;
  }
}

function IconButton({
  icon: Icon,
  label,
  onClick,
  disabled,
  active,
  tone,
}: {
  icon: typeof Copy;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  tone?: "danger";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className={`flex h-8 w-8 items-center justify-center rounded-md border transition-colors duration-150 disabled:opacity-50 ${
        tone === "danger"
          ? "border-surface-border text-red-600 hover:bg-red-50"
          : active
            ? "border-primary bg-primary/10 text-primary"
            : "border-surface-border text-foreground hover:bg-surface-card-hover"
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function QueueRow({ q, onChanged }: { q: PublishingQueueOut; onChanged: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [scheduleDraft, setScheduleDraft] = useState("");
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [statusPending, setStatusPending] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setRowError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "action failed");
    }
  }

  async function copyContent() {
    if (!q.content) return;
    try {
      await navigator.clipboard.writeText(q.content_format === "html" ? htmlToPlainText(q.content) : q.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setRowError("couldn't copy to clipboard");
    }
  }

  function submitSchedule() {
    setScheduleError(null);
    if (scheduleDraft && new Date(scheduleDraft).getTime() < Date.now()) {
      setScheduleError("pick a time in the future");
      return;
    }
    run(() => api.scheduleQueueItem(q.id, scheduleDraft ? new Date(scheduleDraft).toISOString() : null));
  }

  const share = shareUrl(q);

  return (
    <li className="glow-card animate-fade-in-up rounded-xl border border-surface-border bg-surface-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex min-w-0 flex-1 items-start gap-3 text-left"
        >
          <span className="mt-0.5 shrink-0 rounded-full border border-surface-border bg-surface-card-hover px-2 py-0.5 text-xs font-medium text-foreground">
            {q.channel ? CHANNEL_LABELS[q.channel] ?? q.channel : "unknown channel"}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-foreground">
              {q.article_title ?? "Untitled"}
            </span>
            {!expanded && q.content && (
              <span className="mt-0.5 block truncate text-sm text-muted">{previewOf(q.content)}</span>
            )}
          </span>
          <span className="mt-0.5 shrink-0 text-muted">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </span>
        </button>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <StatusBadge status={q.status} />
          {q.content_request_id && (
            <Link
              href={`/requests/${q.content_request_id}`}
              className="text-xs text-primary underline-offset-2 hover:underline"
            >
              view request
            </Link>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
        <span>
          attempts {q.attempts}/{q.max_attempts}
        </span>
        {q.scheduled_for && <span>scheduled {new Date(q.scheduled_for).toLocaleString()}</span>}
        {q.published_at && <span className="text-emerald-700">published {new Date(q.published_at).toLocaleString()}</span>}
      </div>

      {expanded && q.content && (
        q.content_format === "html" ? (
          <HtmlContentPreview html={q.content} />
        ) : (
          <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-surface-border bg-surface-card-hover p-3 text-sm text-foreground">
            {q.content}
          </pre>
        )
      )}

      {(q.last_error || q.failure_reason) && (
        // Amber, not red: a queued item retries automatically, and even a
        // dead-lettered one can be retried below — never a silent dead end.
        <p className="mt-2 text-sm text-amber-600">{q.last_error ?? q.failure_reason}</p>
      )}
      {rowError && <p className="mt-2 text-sm text-red-600">{rowError}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <IconButton icon={copied ? Check : Copy} label={copied ? "Copied" : "Copy"} onClick={copyContent} disabled={!q.content} active={copied} />
        {share && <IconButton icon={share.icon} label={share.label} onClick={share.onClick} />}

        {q.status === "queued" && (
          <>
            <div className="flex flex-wrap items-center gap-1">
              <input
                type="datetime-local"
                min={nowForDatetimeLocal()}
                className="rounded-md border border-surface-border bg-surface-card px-2 py-1 text-sm focus:border-primary focus:outline-none"
                value={scheduleDraft}
                onChange={(e) => {
                  setScheduleDraft(e.target.value);
                  setScheduleError(null);
                }}
              />
              <button
                onClick={submitSchedule}
                className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-foreground transition-colors duration-150 hover:bg-surface-card-hover"
              >
                Schedule
              </button>
            </div>
            <button
              onClick={() => run(() => api.cancelQueueItem(q.id))}
              className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-red-600 transition-colors duration-150 hover:bg-red-50"
            >
              Cancel
            </button>
          </>
        )}
        {q.status === "dead_letter" && (
          <button
            onClick={() => run(() => api.retryQueueItem(q.id))}
            className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-foreground transition-colors duration-150 hover:bg-surface-card-hover"
          >
            Retry
          </button>
        )}
        {q.status === "ready_to_publish" && (
          <button
            onClick={() => run(() => api.setQueueItemStatus(q.id, "published"))}
            title="I posted this — mark Published"
            aria-label="I posted this — mark Published"
            className="flex items-center gap-1.5 rounded-md bg-primary px-2 py-1.5 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 sm:px-3"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">I posted this — mark Published</span>
          </button>
        )}

        <label className="flex items-center gap-2 text-sm text-muted sm:ml-auto">
          Mark as
          <select
            value={q.status}
            disabled={statusPending}
            onChange={async (e) => {
              const next = e.target.value as QueueStatus;
              if (next === q.status) return;
              setStatusPending(true);
              await run(() => api.setQueueItemStatus(q.id, next));
              setStatusPending(false);
            }}
            className="rounded-md border border-surface-border bg-surface-card px-2 py-1 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-50"
          >
            {MANUAL_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
            {!MANUAL_STATUSES.includes(q.status) && <option value={q.status}>{q.status}</option>}
          </select>
        </label>
      </div>
      {scheduleError && <p className="mt-2 text-sm text-red-600">{scheduleError}</p>}
    </li>
  );
}

export default function PublishingQueuePage() {
  const [items, setItems] = useState<PublishingQueueOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const [activeChannel, setActiveChannel] = useState<(typeof CHANNEL_TABS)[number]["key"]>("all");

  const load = useCallback(() => {
    api
      .listPublishingQueue()
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "failed to load publishing queue"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const stats = useMemo(() => queueStats(items ?? []), [items]);
  const filteredItems = useMemo(
    () => (items ?? []).filter((q) => activeChannel === "all" || q.channel === activeChannel),
    [items, activeChannel]
  );

  return (
    <div className="animate-fade-in-up">
      <h1 className="text-lg font-semibold text-foreground">Publishing queue</h1>
      <p className="mt-1 text-sm text-muted">Approved content waiting to go out, or that already has.</p>
      <button
        type="button"
        onClick={() => setShowHelp((v) => !v)}
        className="mt-2 flex items-center gap-1 text-xs text-muted hover:text-foreground"
      >
        <Info className="h-3.5 w-3.5" />
        what do these statuses mean?
      </button>
      {showHelp && (
        <ul className="mt-2 space-y-1 rounded-lg border border-surface-border bg-surface-card p-3 text-xs text-muted">
          {Object.entries(QUEUE_STATUS_HELP).map(([status, help]) => (
            <li key={status}>
              <span className="font-medium capitalize text-foreground">{status.replace(/_/g, " ")}</span>: {help}
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {!items && !error && <LoadingLine label="Loading publishing queue…" />}

      {items && items.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          <StatTile label="Waiting to publish" value={stats.waiting} />
          <StatTile label="Scheduled" value={stats.scheduled} />
          <StatTile label="Published" value={stats.published} tone="emerald" />
          <StatTile label="Failed" value={stats.failed} tone="red" />
          <StatTile label="Cancelled" value={stats.cancelled} />
          <StatTile label="Total" value={stats.total} />
        </div>
      )}

      {items && items.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5 border-b border-surface-border pb-2">
          {CHANNEL_TABS.map((tab) => {
            const count = tab.key === "all" ? items.length : items.filter((q) => q.channel === tab.key).length;
            const active = activeChannel === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveChannel(tab.key)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
                  active
                    ? "bg-primary text-white"
                    : "text-muted hover:bg-surface-card-hover hover:text-foreground"
                }`}
              >
                {tab.label}
                <span className={`ml-1.5 text-xs ${active ? "text-white/80" : "text-muted/70"}`}>{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {items && items.length === 0 && (
        <div className="glow-card mt-6 rounded-xl border border-dashed border-surface-border bg-surface-card p-10 text-center">
          <p className="text-sm text-muted">Nothing queued yet.</p>
        </div>
      )}

      {items && items.length > 0 && filteredItems.length === 0 && (
        <div className="glow-card mt-6 rounded-xl border border-dashed border-surface-border bg-surface-card p-10 text-center">
          <p className="text-sm text-muted">Nothing in this channel yet.</p>
        </div>
      )}

      {filteredItems.length > 0 && (
        <ul className="mt-6 space-y-3">
          {filteredItems.map((q) => (
            <QueueRow key={q.id} q={q} onChanged={load} />
          ))}
        </ul>
      )}
    </div>
  );
}
