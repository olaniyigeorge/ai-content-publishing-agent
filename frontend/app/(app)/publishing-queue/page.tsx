"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Check, ChevronDown, ChevronUp, Copy, Info, Mail, Share2 } from "lucide-react";

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
        <p className="mt-2 text-sm text-red-600">{q.last_error ?? q.failure_reason}</p>
      )}
      {rowError && <p className="mt-2 text-sm text-red-600">{rowError}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <IconButton icon={copied ? Check : Copy} label={copied ? "Copied" : "Copy"} onClick={copyContent} disabled={!q.content} active={copied} />
        {share && <IconButton icon={share.icon} label={share.label} onClick={share.onClick} />}

        {q.status === "queued" && (
          <>
            <div className="flex items-center gap-1">
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
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110"
          >
            I posted this — mark Published
          </button>
        )}

        <label className="ml-auto flex items-center gap-2 text-sm text-muted">
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

  const load = useCallback(() => {
    api
      .listPublishingQueue()
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "failed to load publishing queue"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
      {items && items.length === 0 && (
        <div className="glow-card mt-6 rounded-xl border border-dashed border-surface-border bg-surface-card p-10 text-center">
          <p className="text-sm text-muted">Nothing queued yet.</p>
        </div>
      )}

      {items && items.length > 0 && (
        <ul className="mt-6 space-y-3">
          {items.map((q) => (
            <QueueRow key={q.id} q={q} onChanged={load} />
          ))}
        </ul>
      )}
    </div>
  );
}
