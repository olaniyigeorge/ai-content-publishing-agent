"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { ThinkingOrb, type OrbState } from "thinking-orbs";

import type { ArticleDraftOut, HumanReviewOut, StageEventOut } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  intake: "Intake",
  research: "Research",
  retrieval: "Source retrieval",
  planning: "Planning",
  generation: "Draft generation",
  evaluation: "Evaluation",
  revision: "Revision",
  human_review: "Human review",
  adaptation: "Channel adaptation",
  publishing_queue: "Publishing queue",
  publishing: "Publishing",
};

const STAGE_ORB_STATE: Record<string, OrbState> = {
  intake: "listening",
  research: "searching",
  retrieval: "searching",
  planning: "shaping",
  generation: "working",
  evaluation: "solving",
  revision: "composing",
  human_review: "breathing",
  adaptation: "weaving",
  publishing_queue: "connecting",
  publishing: "connecting",
};

// Grouped into one collapsible "Draft revisions" entry instead of each
// attempt's generation/grounding-check/evaluation events spilling out as
// separate top-level rows — a request that took a few automatic revisions
// to ground properly used to read as a wall of raw violation text by
// default, which is a lot to surface to someone who just wants a good
// draft (2026-09-17 report). The detail is still there on expand.
const CYCLE_STAGES = new Set(["generation", "grounding_validation", "evaluation"]);

const REVISION_CAP_PREFIX = "revision cap (";

function StatusIcon({ stage, status }: { stage: string; status: "started" | "succeeded" | "retrying" | "failed" }) {
  if (status === "succeeded") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white ring-4 ring-[var(--background)]">
        <svg viewBox="0 0 16 16" fill="none" className="h-3 w-3">
          <path d="M3 8.5L6.5 12L13 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (status === "failed") {
    // Deliberately amber, not red: nothing in this pipeline is ever a
    // silent dead end — a "failed" stage event always lands somewhere with
    // a next action (human review, a manual retry, a rewrite), so it reads
    // as "needs your attention" rather than "broken beyond repair."
    return (
      <span
        className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-white ring-4 ring-[var(--background)]"
        title="Stopped automatically and handed to you to review — not a dead end"
      >
        <svg viewBox="0 0 16 16" fill="none" className="h-3 w-3">
          <path d="M8 3v6M8 11.5v.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </span>
    );
  }
  if (status === "retrying") {
    return (
      <span
        className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-white ring-4 ring-[var(--background)]"
        title="Hit a transient error — retrying automatically"
      >
        <svg viewBox="0 0 16 16" fill="none" className="h-3 w-3">
          <path
            d="M13.5 8a5.5 5.5 0 1 1-1.6-3.87M13.5 2.5v3h-3"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    );
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center ring-4 ring-[var(--background)]">
      <ThinkingOrb state={STAGE_ORB_STATE[stage] ?? "working"} size={20} aria-label={`${stage} in progress`} />
    </span>
  );
}

function summarizeDetail(stage: string, detail: Record<string, unknown> | null): string | null {
  if (!detail) return null;
  if (stage === "generation" && typeof detail.version === "number") {
    const base = `option ${detail.option_label ?? "?"} · v${detail.version}`;
    return typeof detail.source_version === "number"
      ? `${base} (regenerated from v${detail.source_version})`
      : base;
  }
  if (stage === "evaluation" && "overall_status" in detail) {
    return `result: ${detail.overall_status}`;
  }
  if (stage === "adaptation" && Array.isArray(detail.channels_adapted)) {
    return `channels: ${(detail.channels_adapted as string[]).join(", ") || "none"}`;
  }
  if (stage === "intake" && "attachments" in detail) {
    return `${detail.attachments} attachment(s)`;
  }
  return null;
}

function findMatchingReview(
  ev: StageEventOut,
  humanReviews: HumanReviewOut[]
): HumanReviewOut | null {
  const draftId = ev.detail?.article_draft_id;
  const decision = ev.detail?.decision;
  if (typeof draftId !== "string" || typeof decision !== "string") return null;
  const candidates = humanReviews.filter((r) => r.article_draft_id === draftId && r.decision === decision);
  if (candidates.length === 0) return null;
  const evTime = new Date(ev.created_at).getTime();
  return candidates.reduce((closest, r) =>
    Math.abs(new Date(r.created_at).getTime() - evTime) < Math.abs(new Date(closest.created_at).getTime() - evTime)
      ? r
      : closest
  );
}

function draftLabel(draftId: string | undefined, drafts: ArticleDraftOut[]): string | null {
  if (!draftId) return null;
  const d = drafts.find((x) => x.id === draftId);
  return d ? `option ${d.option_label} · v${d.version}` : null;
}

type Row =
  | { type: "single"; event: StageEventOut }
  | { type: "repeat"; stage: string; events: StageEventOut[] }
  | { type: "cycle"; events: StageEventOut[] };

function groupEvents(events: StageEventOut[]): Row[] {
  const rows: Row[] = [];
  let i = 0;
  while (i < events.length) {
    const stage = events[i].stage;
    if (CYCLE_STAGES.has(stage)) {
      let j = i;
      while (j < events.length && CYCLE_STAGES.has(events[j].stage)) j++;
      const cycleEvents = events.slice(i, j);
      rows.push(cycleEvents.length > 1 ? { type: "cycle", events: cycleEvents } : { type: "single", event: cycleEvents[0] });
      i = j;
    } else {
      let j = i;
      while (j < events.length && events[j].stage === stage) j++;
      const repeated = events.slice(i, j);
      rows.push(repeated.length > 1 ? { type: "repeat", stage, events: repeated } : { type: "single", event: repeated[0] });
      i = j;
    }
  }
  return rows;
}

function cycleSummary(events: StageEventOut[]): { headline: string; latestStatus: StageEventOut["status"] } {
  const generations = events.filter((e) => e.stage === "generation");
  const evaluations = events.filter((e) => e.stage === "evaluation");
  const last = events[events.length - 1];
  const lastEvalResult =
    [...evaluations].reverse().find((e) => e.detail && "overall_status" in e.detail)?.detail?.overall_status;
  const atCap = evaluations.some((e) => e.error_message?.startsWith(REVISION_CAP_PREFIX));
  const headline = atCap
    ? `${generations.length} draft attempts completed. This didn't meet quality checks, so it's ready for your review.`
    : lastEvalResult === "pass"
      ? `${generations.length} draft attempt${generations.length === 1 ? "" : "s"} — passed evaluation`
      : lastEvalResult
        ? `${generations.length} draft attempt${generations.length === 1 ? "" : "s"} — last result: ${lastEvalResult}`
        : `${generations.length} draft attempt${generations.length === 1 ? "" : "s"} in progress`;
  return { headline, latestStatus: last.status };
}

function EventRow({
  ev,
  indent = false,
  humanReviews = [],
  drafts = [],
}: {
  ev: StageEventOut;
  indent?: boolean;
  humanReviews?: HumanReviewOut[];
  drafts?: ArticleDraftOut[];
}) {
  const detailSummary = summarizeDetail(ev.stage, ev.detail);
  const review = ev.stage === "human_review" ? findMatchingReview(ev, humanReviews) : null;
  const isRevisionCap = ev.stage === "evaluation" && ev.error_message?.startsWith(REVISION_CAP_PREFIX);

  return (
    <div className={`flex gap-3 ${indent ? "py-1.5" : ""}`}>
      <StatusIcon stage={ev.stage} status={ev.status} />
      <div className="min-w-0 flex-1 pt-px">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-sm font-medium text-foreground">
            {STAGE_LABELS[ev.stage] ?? ev.stage.replace(/_/g, " ")}
          </span>
          {detailSummary && <span className="text-xs text-muted">{detailSummary}</span>}
          {review && <span className="text-xs text-muted">{review.decision.replace(/_/g, " ")}</span>}
          <span className="ml-auto text-xs text-muted">
            {new Date(ev.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
        {review && (
          <p className="mt-1 text-xs text-muted">
            {draftLabel(review.article_draft_id, drafts) && (
              <span className="font-medium">{draftLabel(review.article_draft_id, drafts)}: </span>
            )}
            {review.notes || "no notes left"}
          </p>
        )}
        {isRevisionCap ? (
          <p className="mt-1 text-xs text-amber-600">
            This draft was revised the maximum number of times but still didn&apos;t clear the automatic quality
            checks (see the feedback on that draft above). Rather than loop forever, it was sent to you to review
            and decide manually.
          </p>
        ) : ev.status === "retrying" ? (
          ev.error_message && (
            <p className="mt-1 text-xs text-amber-600">
              {ev.error_message}
              {typeof ev.detail?.attempts === "number" && typeof ev.detail?.max_attempts === "number" && (
                <> — retrying (attempt {ev.detail.attempts}/{ev.detail.max_attempts})</>
              )}
            </p>
          )
        ) : (
          // Amber, not red — see StatusIcon: this stage stopped and handed
          // off to you, it isn't an unrecoverable dead end.
          ev.error_message && <p className="mt-1 text-xs text-amber-600">{ev.error_message}</p>
        )}
      </div>
    </div>
  );
}

export function PipelineTimeline({
  events,
  humanReviews = [],
  drafts = [],
}: {
  events: StageEventOut[];
  humanReviews?: HumanReviewOut[];
  drafts?: ArticleDraftOut[];
}) {
  const rows = groupEvents(events);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  if (events.length === 0) {
    return <p className="text-sm text-muted">No pipeline activity yet.</p>;
  }

  function toggle(i: number) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  return (
    <ol className="relative">
      <span aria-hidden className="absolute left-2.5 top-2 bottom-2 w-px bg-surface-border" />
      {rows.map((row, i) => {
        const isLastRow = i === rows.length - 1;
        if (row.type === "single") {
          return (
            <li
              key={row.event.id}
              className="relative animate-fade-in-up pb-5 last:pb-0"
              style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
            >
              <EventRow ev={row.event} humanReviews={humanReviews} drafts={drafts} />
            </li>
          );
        }

        // Default: collapse older groups, keep the most recent one open; a click flips it.
        const defaultOpen = isLastRow;
        const open = collapsed.has(i) ? !defaultOpen : defaultOpen;

        if (row.type === "repeat") {
          const last = row.events[row.events.length - 1];
          return (
            <li key={last.id} className="relative animate-fade-in-up pb-5 last:pb-0">
              <button type="button" onClick={() => toggle(i)} className="flex w-full gap-3 text-left">
                <StatusIcon stage={last.stage} status={last.status} />
                <div className="min-w-0 flex-1 pt-px">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-sm font-medium text-foreground">
                      {STAGE_LABELS[row.stage] ?? row.stage.replace(/_/g, " ")}
                      <span className="ml-1 font-normal text-muted">(attempt {row.events.length})</span>
                    </span>
                    <span className="ml-auto text-muted">
                      {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </span>
                  </div>
                </div>
              </button>
              {open && (
                <div className="ml-8 mt-1 divide-y divide-surface-border border-l border-surface-border pl-3">
                  {row.events.map((ev) => (
                    <EventRow key={ev.id} ev={ev} indent humanReviews={humanReviews} drafts={drafts} />
                  ))}
                </div>
              )}
            </li>
          );
        }

        // cycle
        const { headline, latestStatus } = cycleSummary(row.events);
        const last = row.events[row.events.length - 1];
        return (
          <li key={last.id} className="relative animate-fade-in-up pb-5 last:pb-0">
            <button type="button" onClick={() => toggle(i)} className="flex w-full gap-3 text-left">
              <StatusIcon stage={last.stage} status={latestStatus} />
              <div className="min-w-0 flex-1 pt-px">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-medium text-foreground">Draft revisions</span>
                  <span className="text-xs text-muted">{headline}</span>
                  <span className="ml-auto text-muted">
                    {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </span>
                </div>
              </div>
            </button>
            {open && (
              <div className="ml-8 mt-1 divide-y divide-surface-border border-l border-surface-border pl-3">
                {row.events.map((ev) => (
                  <EventRow key={ev.id} ev={ev} indent humanReviews={humanReviews} drafts={drafts} />
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
