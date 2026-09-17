"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronUp,
  Check,
  Copy,
  History,
  Info,
  Paperclip,
  PencilLine,
  Sparkles,
  ChevronLeft,
} from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { api, ApiError } from "@/lib/api";
import { HtmlContentPreview } from "@/components/html-content-preview";
import { StatusBadge } from "@/components/status-badge";
import { PipelineTimeline } from "@/components/pipeline-timeline";
import { LoadingLine } from "@/components/spinner";
import { QUEUE_STATUS_HELP } from "@/lib/queue-status";
import type { ChannelAdaptationOut, ContentRequestDetail, ReviewDecision } from "@/lib/types";

const REWRITE_TIMEOUT_MS = 90_000;

// Mirrors pipeline-timeline.tsx's STAGE_ORB_STATE, keyed by request status
// instead of stage — used for the "nothing has landed yet" empty state.
const STARTED_ORB_STATE: Record<string, "listening" | "searching" | "shaping" | "working"> = {
  intake: "listening",
  researching: "searching",
  planning: "shaping",
  drafting: "working",
};
const STARTED_STATUS_LABEL: Record<string, string> = {
  intake: "Getting started…",
  researching: "Researching your sources…",
  planning: "Planning the article…",
  drafting: "Writing the first draft…",
};
type AwaitingRewrite =
  | { kind: "draft"; id: string; startedAt: number }
  | { kind: "adaptation"; beforeId: string; startedAt: number };

const MAX_RUBRIC_SCORE = 5;

const TERMINAL_STATUSES = new Set(["published", "rejected", "failed"]);
const REVIEWABLE_DRAFT_STATUSES = new Set(["evaluated", "revised"]);

function friendlyError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Your session has expired — please log in again.";
    return err.message;
  }
  return fallback;
}

export function RequestDetailClient({ id }: { id: string }) {
  const [detail, setDetail] = useState<ContentRequestDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewingDraftId, setReviewingDraftId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSubmittingId, setReviewSubmittingId] = useState<string | null>(null);
  const [expandedDraftId, setExpandedDraftId] = useState<string | null>(null);
  const [rewritingId, setRewritingId] = useState<string | null>(null);
  const [rewriteInstructions, setRewriteInstructions] = useState("");
  const [rewritePending, setRewritePending] = useState<string | null>(null);
  const [awaitingRewrite, setAwaitingRewrite] = useState<AwaitingRewrite | null>(null);
  const [expandedChannelHistory, setExpandedChannelHistory] = useState<string | null>(null);
  // Drafts render collapsed by default (title/version/score only) — a draft
  // only stays expanded once the user opens it here.
  const [expandedCardIds, setExpandedCardIds] = useState<Set<string>>(new Set());
  const [showIntakeContext, setShowIntakeContext] = useState(false);
  const [showQueueHelp, setShowQueueHelp] = useState(false);
  const [showUsage, setShowUsage] = useState(false);
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [sourceOverridePending, setSourceOverridePending] = useState<string | null>(null);

  function toggleDraftExpanded(draftId: string) {
    setExpandedCardIds((prev) => {
      const next = new Set(prev);
      if (next.has(draftId)) next.delete(draftId);
      else next.add(draftId);
      return next;
    });
  }

  const load = useCallback(() => {
    api
      .getRequestDetail(id)
      .then((d) => {
        setDetail(d);
        // A load-failure error must not outlive the failure — the next
        // successful poll (every 5s while the pipeline is active) has to
        // clear it, or a single transient blip leaves a permanent "failed to
        // load request" banner sitting on top of a page that's now fine.
        setError(null);
      })
      .catch((err) => setError(friendlyError(err, "failed to load request")));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  // Poll while the pipeline is still doing something — approval/rejection/
  // publish are terminal-ish for this view's purposes.
  useEffect(() => {
    if (!detail || TERMINAL_STATUSES.has(detail.request.status)) return;
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [detail, load]);

  async function handleReview(draftId: string, decision: ReviewDecision) {
    setError(null);
    setReviewSubmittingId(draftId);
    try {
      await api.submitReview(id, draftId, decision, reviewNotes.trim() || undefined);
      setReviewingDraftId(null);
      setReviewNotes("");
      load();
    } catch (err) {
      setError(friendlyError(err, "failed to submit review"));
    } finally {
      setReviewSubmittingId(null);
    }
  }

  async function handleRewriteDraft(draftId: string) {
    setError(null);
    setRewritePending(draftId);
    try {
      await api.rewriteDraft(draftId, rewriteInstructions);
      setRewritingId(null);
      setRewriteInstructions("");
      setAwaitingRewrite({ kind: "draft", id: draftId, startedAt: Date.now() });
      load();
    } catch (err) {
      setError(friendlyError(err, "failed to queue rewrite"));
    } finally {
      setRewritePending(null);
    }
  }

  async function handleRewriteAdaptation(adaptationId: string) {
    setError(null);
    setRewritePending(adaptationId);
    try {
      await api.rewriteAdaptation(adaptationId, rewriteInstructions);
      setRewritingId(null);
      setRewriteInstructions("");
      setAwaitingRewrite({ kind: "adaptation", beforeId: adaptationId, startedAt: Date.now() });
      load();
    } catch (err) {
      setError(friendlyError(err, "failed to queue rewrite"));
    } finally {
      setRewritePending(null);
    }
  }

  function startEditingDraft(draftId: string, title: string, bodyMarkdown: string) {
    setEditingDraftId(draftId);
    setEditTitle(title);
    setEditBody(bodyMarkdown);
    setEditError(null);
    setRewritingId(null);
  }

  async function handleSaveEdit(draftId: string) {
    setEditError(null);
    if (!editBody.trim()) {
      setEditError("the article body can't be empty");
      return;
    }
    setEditSaving(true);
    try {
      await api.editDraft(draftId, editBody, editTitle.trim() || undefined);
      setEditingDraftId(null);
      load();
    } catch (err) {
      setEditError(friendlyError(err, "failed to save edit"));
    } finally {
      setEditSaving(false);
    }
  }

  async function handleSourceOverride(sourceId: string, status: "selected" | "discarded") {
    setSourceOverridePending(sourceId);
    setError(null);
    try {
      await api.overrideSourceStatus(id, sourceId, status);
      load();
    } catch (err) {
      setError(friendlyError(err, "failed to update source"));
    } finally {
      setSourceOverridePending(null);
    }
  }

  if (error && !detail) {
    return (
      <div>
        <Link href="/" className="flex items-center gap-1 text-sm text-muted hover:text-foreground">
          <ChevronLeft className="mt-[2.5px] h-3.5 w-3.5" />
          <>back to requests</>
        </Link>
        <div className="mt-6 flex flex-col items-center gap-2 rounded-xl border border-red-200 bg-red-50 py-12 text-center">
          <p className="text-sm font-medium text-red-600">{error}</p>
          <p className="text-xs text-red-600/70">
            failed to load this request — it may not exist, or your session may need refreshing
          </p>
        </div>
      </div>
    );
  }

  if (!detail) return <LoadingLine label="Loading request…" centered />;

  const { request, sources, drafts, evaluations, human_reviews, adaptations, publishing_queue, stage_events, usage } =
    detail;
  const pipelineJustStarted =
    drafts.length === 0 &&
    sources.length === 0 &&
    adaptations.length === 0 &&
    publishing_queue.length === 0 &&
    !TERMINAL_STATUSES.has(request.status);

  const evaluationsByDraft = new Map(evaluations.map((e) => [e.article_draft_id, e]));
  const reviewsByDraft = new Map<string, typeof human_reviews>();
  for (const r of human_reviews) {
    reviewsByDraft.set(r.article_draft_id, [...(reviewsByDraft.get(r.article_draft_id) ?? []), r]);
  }

  return (
    <div className="animate-fade-in-up space-y-6">
      <div>
       <Link href="/" className="flex items-center gap-1 text-sm text-muted hover:text-foreground">
          <ChevronLeft className="mt-[2.5px] h-3.5 w-3.5" />
          <>back to requests</>
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="line-clamp-2 text-lg font-semibold text-foreground">
              {request.raw_idea?.trim() || "(source URL only)"}
            </h1>
            <p className="mt-1 text-sm text-muted">
              Audience: {request.target_audience}
              <span className="ml-2 font-mono text-xs text-muted/50" title={request.id}>
                #{request.id.slice(0, 8)}
              </span>
            </p>
          </div>
          <StatusBadge status={request.status} />
        </div>
        {error && (
          <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        {(request.supporting_material || detail.attachments.length > 0) && (
          <div className="mt-3">
            <button
              type="button"
              onClick={() => setShowIntakeContext((v) => !v)}
              className="flex items-center gap-1.5 text-sm text-muted hover:text-foreground"
            >
              <Paperclip className="h-3.5 w-3.5" />
              original submission ({detail.attachments.length} attachment{detail.attachments.length === 1 ? "" : "s"})
              {showIntakeContext ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </button>
            {showIntakeContext && (
              <div className="mt-2 space-y-3 rounded-lg border border-surface-border bg-surface-card p-3 text-sm">
                {typeof request.supporting_material?.notes === "string" && request.supporting_material.notes && (
                  <p className="text-muted">
                    <span className="font-medium text-foreground">Notes: </span>
                    {request.supporting_material.notes}
                  </p>
                )}
                {detail.attachments.length > 0 && (
                  <ul className="grid gap-2 sm:grid-cols-2">
                    {detail.attachments.map((a) => (
                      <li key={a.id} className="rounded-md border border-surface-border bg-surface-base p-2 text-xs">
                        <span className="mb-1 block font-medium uppercase tracking-wide text-muted">{a.type}</span>
                        {a.type === "image" && a.url ? (
                          // eslint-disable-next-line @next/next/no-img-element -- Supabase Storage public URL
                          <img src={a.url} alt={a.description ?? "attachment"} className="h-24 w-full rounded object-cover" />
                        ) : a.url ? (
                          <a href={a.url} target="_blank" rel="noreferrer" className="break-all text-primary hover:underline">
                            {a.description || a.url}
                          </a>
                        ) : (
                          <span className="text-muted">{a.description || "(no file)"}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {!pipelineJustStarted && <PipelinePhaseStepper status={request.status} onSelect={scrollToPipelineActivity} />}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        {pipelineJustStarted ? (
          <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-surface-border bg-surface-card py-24 text-center">
            <ThinkingOrb state={STARTED_ORB_STATE[request.status] ?? "working"} size={64} aria-label="Working" />
            <div>
              <p className="text-sm font-medium text-foreground">
                {STARTED_STATUS_LABEL[request.status] ?? "Working on it…"}
              </p>
              <p className="mt-1 text-xs text-muted">This updates automatically — no need to refresh.</p>
            </div>
          </div>
        ) : (
        <div className="space-y-6">
          <Section title={`Article options (${drafts.length})`}>
            {drafts.length === 0 ? (
              <EmptyNote text="no drafts generated yet" />
            ) : (
              <div className="space-y-4">
                {drafts.map((d) => {
                  const sourceVersion = d.parent_draft_id
                    ? drafts.find((sd) => sd.id === d.parent_draft_id)?.version
                    : undefined;
                  const evaluation = evaluationsByDraft.get(d.id);
                  const draftReviews = reviewsByDraft.get(d.id) ?? [];
                  const hasTerminalReview = draftReviews.some(
                    (r) => r.decision === "approved" || r.decision === "rejected"
                  );
                  const isReviewable = REVIEWABLE_DRAFT_STATUSES.has(d.status) && !hasTerminalReview;
                  const expanded = expandedDraftId === d.id;
                  const cardCollapsed = !expandedCardIds.has(d.id);
                  const isBeingRewritten =
                    awaitingRewrite?.kind === "draft" &&
                    awaitingRewrite.id === d.id &&
                    d.status !== "discarded" &&
                    Date.now() - awaitingRewrite.startedAt < REWRITE_TIMEOUT_MS;
                  const isEditing = editingDraftId === d.id;
                  // Let one action finish before starting the next: while an
                  // AI rewrite is actually in flight for this draft, or a
                  // review decision is being submitted, block the other
                  // actions instead of letting a click race the backend's
                  // own in-flight-revision guard (app/services/job_guard.py).
                  const draftBusy = isBeingRewritten || reviewSubmittingId === d.id;
                  const thinSourceCount = d.source_ids_used.filter(
                    (sid) => sources.find((s) => s.id === sid)?.confidence === "thin"
                  ).length;

                  return (
                    <div key={d.id} className="glow-card rounded-xl border border-surface-border bg-surface-card p-4 transition-shadow duration-200">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => toggleDraftExpanded(d.id)}
                          className="flex min-w-0 flex-1 items-start gap-2 text-left"
                        >
                          <span className="mt-0.5 shrink-0 text-muted">
                            {cardCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
                          </span>
                          <span className="min-w-0 font-medium text-foreground">
                            <span className="block truncate">{d.title}</span>
                            <span className="mt-1 flex flex-wrap items-center gap-1.5">
                              <VersionPill version={d.version} />
                              {sourceVersion != null && (
                                <span className="text-[11px] text-muted">regenerated from v{sourceVersion}</span>
                              )}
                            </span>
                          </span>
                        </button>
                        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                          {isBeingRewritten && <RewritingIndicator />}
                          {evaluation && <ScoreChip score={evaluation.overall_score} passed={evaluation.passed_threshold} />}
                          {thinSourceCount > 0 && (
                            <span
                              className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                              title="This option relies on weak evidence — see Sources below before approving"
                            >
                              {thinSourceCount} thin source{thinSourceCount === 1 ? "" : "s"}
                            </span>
                          )}
                          {evaluation && evaluation.unsupported_claims.length > 0 && (
                            <span
                              className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                              title="Claims flagged as unbacked or overstated by the evaluator"
                            >
                              {evaluation.unsupported_claims.length} flagged claim
                              {evaluation.unsupported_claims.length === 1 ? "" : "s"}
                            </span>
                          )}
                          <StatusBadge status={d.status} />
                        </div>
                      </div>

                      {!cardCollapsed && (
                        <>
                          {d.revision_instructions && <InstructionsGiven instructions={d.revision_instructions} />}
                          {evaluation && <EvaluationSummary evaluation={evaluation} />}

                          {isEditing ? (
                            <ManualEditControl
                              title={editTitle}
                              body={editBody}
                              onTitleChange={setEditTitle}
                              onBodyChange={setEditBody}
                              onSave={() => handleSaveEdit(d.id)}
                              onCancel={() => setEditingDraftId(null)}
                              saving={editSaving}
                              error={editError}
                            />
                          ) : (
                            <>
                              <div className="mt-3 flex flex-wrap items-center gap-2">
                                <IconButton
                                  icon={expanded ? ChevronUp : ChevronDown}
                                  label={expanded ? "Hide full draft" : "Show full draft"}
                                  onClick={() => setExpandedDraftId(expanded ? null : d.id)}
                                />
                                <CopyButton text={d.body_markdown} />
                                <IconButton
                                  icon={Sparkles}
                                  label={isBeingRewritten ? "Rewrite in progress…" : "Rewrite with AI"}
                                  onClick={() => {
                                    setRewritingId(rewritingId === d.id ? null : d.id);
                                    setRewriteInstructions("");
                                  }}
                                  active={rewritingId === d.id}
                                  disabled={draftBusy}
                                />
                                {isReviewable && (
                                  <IconButton
                                    icon={PencilLine}
                                    label="Edit manually"
                                    onClick={() => startEditingDraft(d.id, d.title, d.body_markdown)}
                                    disabled={draftBusy}
                                  />
                                )}
                              </div>
                              {expanded && (
                                <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-base p-3 text-sm text-muted">
                                  {d.body_markdown}
                                </pre>
                              )}
                            </>
                          )}
                        </>
                      )}
                      {!cardCollapsed && !isEditing && rewritingId === d.id && (
                        <RewriteControl
                          instructions={rewriteInstructions}
                          onChange={setRewriteInstructions}
                          onSubmit={() => handleRewriteDraft(d.id)}
                          onCancel={() => setRewritingId(null)}
                          pending={rewritePending === d.id}
                        />
                      )}

                      {!cardCollapsed && draftReviews.length > 0 && (
                        <ul className="mt-3 space-y-1 text-xs text-muted">
                          {draftReviews.map((r) => (
                            <li key={r.id}>
                              {r.decision.replace(/_/g, " ")} — {new Date(r.created_at).toLocaleString()}
                              {r.notes ? `: ${r.notes}` : ""}
                            </li>
                          ))}
                        </ul>
                      )}

                      {!cardCollapsed && isReviewable && (
                        <div className="mt-4 border-t border-surface-border pt-3">
                          {reviewingDraftId === d.id ? (
                            <div className="space-y-2">
                              <textarea
                                value={reviewNotes}
                                onChange={(e) => setReviewNotes(e.target.value)}
                                rows={2}
                                placeholder="notes (required for revise, optional for approve/reject)"
                                disabled={draftBusy}
                                className="w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 text-sm focus:border-primary focus:outline-none disabled:opacity-60"
                              />
                              <p className="text-[11px] text-muted">
                                &ldquo;Mark as selected option&rdquo; only records which draft you prefer — it
                                doesn&apos;t rewrite anything. To have the AI act on your notes, use &ldquo;Request
                                revision&rdquo; or the Rewrite with AI button above instead.
                              </p>
                              <div className="flex flex-wrap gap-2">
                                <ReviewButton
                                  label="Approve"
                                  onClick={() => handleReview(d.id, "approved")}
                                  variant="approve"
                                  disabled={draftBusy}
                                />
                                <ReviewButton
                                  label="Reject"
                                  onClick={() => handleReview(d.id, "rejected")}
                                  variant="reject"
                                  disabled={draftBusy}
                                />
                                <ReviewButton
                                  label="Request revision"
                                  onClick={() => handleReview(d.id, "revise_requested")}
                                  variant="neutral"
                                  disabled={draftBusy}
                                />
                                <ReviewButton
                                  label="Mark as selected option"
                                  onClick={() => handleReview(d.id, "option_selected")}
                                  variant="neutral"
                                  disabled={draftBusy}
                                />
                                <button
                                  onClick={() => {
                                    setReviewingDraftId(null);
                                    setReviewNotes("");
                                  }}
                                  disabled={draftBusy}
                                  className="rounded-md px-3 py-1.5 text-sm text-muted hover:bg-surface-card-hover disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setReviewingDraftId(d.id)}
                              disabled={draftBusy}
                              title={isBeingRewritten ? "Wait for the current rewrite to finish first" : undefined}
                              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
                            >
                              Review this option
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Section>

          <Section title={`Sources (${sources.length})`}>
            {sources.length === 0 ? (
              <EmptyNote text="no sources retrieved yet" />
            ) : (
              <ul className="space-y-3">
                {sources.map((s) => {
                  const pending = sourceOverridePending === s.id;
                  const canOverride = s.status !== "failed";
                  return (
                    <li key={s.id} className="rounded-lg border border-surface-border bg-surface-card p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <a href={s.url} target="_blank" rel="noreferrer" className="font-medium text-foreground hover:text-primary hover:underline">
                          {s.title || s.url}
                        </a>
                        <div className="flex shrink-0 items-center gap-2">
                          {s.retrieval_method === "web_search" && (
                            <span className="rounded-full border border-surface-border bg-surface-base px-2 py-0.5 text-[11px] text-muted" title="Found by an autonomous web search — no source URL was supplied">
                              found by agent
                            </span>
                          )}
                          {s.status === "selected" && s.confidence === "thin" && (
                            <span
                              className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                              title={s.confidence_reason ?? "Weak evidence — real, but not strongly supported"}
                            >
                              thin evidence
                            </span>
                          )}
                          <StatusBadge status={s.status} />
                        </div>
                      </div>
                      {s.excerpt_selected && <p className="mt-1 text-muted">&ldquo;{s.excerpt_selected}&rdquo;</p>}
                      {s.relevance_notes && <p className="mt-1 text-muted/70">{s.relevance_notes}</p>}
                      {s.status === "selected" && s.confidence === "thin" && s.confidence_reason && (
                        <p className="mt-1 text-amber-700">
                          Cited, but weak evidence: {s.confidence_reason} — claims from this source should read as
                          hedged, not stated as settled fact. Discard it below if you&apos;d rather the draft not use it.
                        </p>
                      )}
                      {(s.status === "discarded" || s.status === "failed") && s.discard_reason && (
                        <p className="mt-1 text-amber-700">
                          {s.status === "failed" ? "Couldn't retrieve this source: " : "Not used: "}
                          {s.discard_reason}
                        </p>
                      )}
                      {canOverride && (
                        <div className="mt-2 flex items-center gap-2">
                          {s.status !== "selected" && (
                            <button
                              type="button"
                              disabled={pending}
                              onClick={() => handleSourceOverride(s.id, "selected")}
                              className="rounded-md border border-surface-border px-2 py-1 text-xs text-foreground hover:bg-surface-card-hover disabled:opacity-60"
                            >
                              mark selected
                            </button>
                          )}
                          {s.status !== "discarded" && (
                            <button
                              type="button"
                              disabled={pending}
                              onClick={() => handleSourceOverride(s.id, "discarded")}
                              title="If the current draft cites this source, discarding it queues a regeneration without it"
                              className="rounded-md border border-surface-border px-2 py-1 text-xs text-muted hover:bg-surface-card-hover disabled:opacity-60"
                            >
                              discard
                            </button>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <Section title={`Channel adaptations (${adaptations.length})`}>
            {adaptations.length === 0 ? (
              <EmptyNote text="channel content is prepared after a draft is approved" />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {groupAdaptationsByChannel(adaptations).map(({ latest, previous }) => {
                  const isBeingRewritten =
                    awaitingRewrite?.kind === "adaptation" &&
                    awaitingRewrite.beforeId === latest.id &&
                    Date.now() - awaitingRewrite.startedAt < REWRITE_TIMEOUT_MS;
                  return (
                  <div key={latest.id} className="min-w-0 rounded-lg border border-surface-border bg-surface-card p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium capitalize text-foreground">{latest.channel}</span>
                      <div className="flex items-center gap-2">
                        {isBeingRewritten && <RewritingIndicator />}
                        <StatusBadge status={latest.status} />
                      </div>
                    </div>
                    {latest.formatting_check?.auto_trimmed ? (
                      <p className="mt-1 text-xs text-amber-600">auto-trimmed to fit channel limit</p>
                    ) : null}
                    {latest.content_format === "html" ? (
                      <HtmlContentPreview html={latest.content} />
                    ) : (
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-sm text-muted">
                        {latest.content}
                      </pre>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {latest.content_format === "html" ? (
                        <CopyHtmlButton html={latest.content} />
                      ) : (
                        <CopyButton text={latest.content} />
                      )}
                      <IconButton
                        icon={Sparkles}
                        label="Rewrite with AI"
                        onClick={() => {
                          setRewritingId(rewritingId === latest.id ? null : latest.id);
                          setRewriteInstructions("");
                        }}
                        active={rewritingId === latest.id}
                      />
                      {previous.length > 0 && (
                        <IconButton
                          icon={History}
                          label={
                            expandedChannelHistory === latest.channel
                              ? "Hide previous versions"
                              : `${previous.length} previous version${previous.length === 1 ? "" : "s"}`
                          }
                          onClick={() =>
                            setExpandedChannelHistory(expandedChannelHistory === latest.channel ? null : latest.channel)
                          }
                          active={expandedChannelHistory === latest.channel}
                        />
                      )}
                    </div>
                    {rewritingId === latest.id && (
                      <RewriteControl
                        instructions={rewriteInstructions}
                        onChange={setRewriteInstructions}
                        onSubmit={() => handleRewriteAdaptation(latest.id)}
                        onCancel={() => setRewritingId(null)}
                        pending={rewritePending === latest.id}
                      />
                    )}
                    {expandedChannelHistory === latest.channel && (
                      <div className="mt-2 space-y-2 border-t border-surface-border pt-2">
                        {previous.map((p) => (
                          <div key={p.id} className="text-xs text-muted">
                            <div className="flex items-center justify-between">
                              <span>{new Date(p.created_at).toLocaleString()}</span>
                              <StatusBadge status={p.status} />
                            </div>
                            <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap">{p.content}</pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            )}
          </Section>

          <Section title={`Publishing queue (${publishing_queue.length})`}>
            <button
              type="button"
              onClick={() => setShowQueueHelp((v) => !v)}
              className="mb-2 flex items-center gap-1 text-xs text-muted hover:text-foreground"
            >
              <Info className="h-3.5 w-3.5" />
              what do these statuses mean?
            </button>
            {showQueueHelp && (
              <ul className="mb-3 space-y-1 rounded-lg border border-surface-border bg-surface-base p-3 text-xs text-muted">
                {Object.entries(QUEUE_STATUS_HELP).map(([status, help]) => (
                  <li key={status}>
                    <span className="font-medium capitalize text-foreground">{status.replace(/_/g, " ")}</span>: {help}
                  </li>
                ))}
              </ul>
            )}
            {publishing_queue.length === 0 ? (
              <EmptyNote text="nothing queued yet" />
            ) : (
              <ul className="space-y-2">
                {publishing_queue.map((q) => (
                  <li key={q.id} className="rounded-lg border border-surface-border bg-surface-card p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      {q.channel && (
                        <span className="rounded-full border border-surface-border bg-surface-card-hover px-2 py-0.5 text-xs font-medium capitalize text-foreground">
                          {q.channel}
                        </span>
                      )}
                      <StatusBadge status={q.status} />
                      <span className="text-muted">
                        {q.scheduled_for
                          ? `scheduled for ${new Date(q.scheduled_for).toLocaleString()}`
                          : "not scheduled"}
                      </span>
                    </div>
                    {(q.last_error || q.failure_reason) && (
                      // Amber, not red — see publishing-queue/page.tsx: this
                      // either retries automatically or is retryable by hand.
                      <p className="mt-1 text-amber-600">{q.last_error ?? q.failure_reason}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted">
              Manage scheduling, cancelling, and retrying from the{" "}
              <Link href="/publishing-queue" className="text-primary hover:underline">
                publishing queue
              </Link>{" "}
              page.
            </p>
          </Section>
        </div>
        )}

        <aside className="xl:sticky xl:top-6 xl:self-start space-y-6">
          <Section title="API usage">
            <UsagePanel usage={usage} expanded={showUsage} onToggle={() => setShowUsage((v) => !v)} />
          </Section>
        </aside>
      </div>

      <section id="pipeline-activity" className="scroll-mt-6">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Pipeline activity</h2>
        <div className="glow-card mt-3 rounded-xl border border-surface-border bg-surface-card p-4">
          <PipelineTimeline events={stage_events} humanReviews={human_reviews} drafts={drafts} />
        </div>
      </section>
    </div>
  );
}

function scrollToPipelineActivity() {
  document.getElementById("pipeline-activity")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

const PHASES: { key: string; label: string }[] = [
  { key: "intake", label: "Intake" },
  { key: "research", label: "Research" },
  { key: "planning", label: "Planning" },
  { key: "drafting", label: "Drafting" },
  { key: "review", label: "Review" },
  { key: "publishing", label: "Publishing" },
];

// Coarse phase index for each request.status — the full detail (every
// retry, every grounding check) lives in the pipeline activity timeline
// below; this is meant to be readable at a glance.
const STATUS_PHASE_INDEX: Record<string, number> = {
  intake: 0,
  researching: 1,
  planning: 2,
  drafting: 3,
  evaluating: 3,
  revising: 3,
  in_review: 4,
  rejected: 4,
  approved: 5,
  adapting: 5,
  queued: 5,
  published: 5,
  // "failed" can happen at several points; drafting is the most common one
  // (an exhausted revision loop), so it's the best single-node approximation
  // — the timeline below has the actual stage it failed at.
  failed: 3,
};

type PhaseState = "done" | "active" | "pending" | "attention";

/** A glanceable "where is this request right now" strip — circular nodes
 * connected by a line, one per coarse pipeline phase. Every node is
 * clickable and smooth-scrolls to the full stage-by-stage detail at the
 * bottom of the page (id="pipeline-activity") rather than duplicating that
 * detail up here. */
function PipelinePhaseStepper({ status, onSelect }: { status: string; onSelect: () => void }) {
  const currentIndex = STATUS_PHASE_INDEX[status] ?? 0;
  const isTerminalIssue = status === "rejected" || status === "failed";

  return (
    <div className="overflow-x-auto rounded-xl border border-surface-border bg-surface-card p-4">
      <ol className="flex min-w-max items-center">
        {PHASES.map((phase, i) => {
          let state: PhaseState;
          if (isTerminalIssue && i === currentIndex) state = "attention";
          else if (i < currentIndex || status === "published") state = "done";
          else if (i === currentIndex) state = "active";
          else state = "pending";

          return (
            <li key={phase.key} className="flex flex-1 items-center last:flex-none">
              <button
                type="button"
                onClick={onSelect}
                className="flex flex-col items-center gap-1.5 px-1 text-center"
                title={`${phase.label} — jump to pipeline activity detail`}
              >
                <PhaseNode state={state} />
                <span
                  className={`whitespace-nowrap text-[11px] font-medium ${
                    state === "pending" ? "text-muted" : "text-foreground"
                  }`}
                >
                  {phase.label}
                </span>
              </button>
              {i < PHASES.length - 1 && (
                <div
                  className={`mx-1 h-0.5 flex-1 rounded transition-colors duration-300 ${
                    i < currentIndex || status === "published" ? "bg-emerald-500" : "bg-surface-border"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function PhaseNode({ state }: { state: PhaseState }) {
  if (state === "done") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white transition-transform duration-150 hover:scale-105">
        <Check className="h-4 w-4" />
      </span>
    );
  }
  if (state === "attention") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-500 text-white transition-transform duration-150 hover:scale-105">
        <Info className="h-4 w-4" />
      </span>
    );
  }
  if (state === "active") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-primary bg-primary/10 text-primary transition-transform duration-150 hover:scale-105">
        <ThinkingOrb state="working" size={20} aria-label="In progress" />
      </span>
    );
  }
  return (
    <span className="h-8 w-8 shrink-0 rounded-full border-2 border-surface-border transition-transform duration-150 hover:scale-105" />
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function EmptyNote({ text }: { text: string }) {
  return <p className="text-sm text-muted">{text}</p>;
}

function IconButton({
  icon: Icon,
  label,
  onClick,
  active,
  disabled,
}: {
  icon: typeof Copy;
  label: string;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className={`flex h-8 w-8 items-center justify-center rounded-md border transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 ${
        active
          ? "border-primary bg-primary/10 text-primary"
          : "border-surface-border text-muted hover:bg-surface-card-hover hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <IconButton
      icon={copied ? Check : Copy}
      label={copied ? "Copied" : "Copy"}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          // clipboard unavailable — silently ignore
        }
      }}
      active={copied}
    />
  );
}

/** Copies HTML content so pasting into a rich-text target (Gmail's composer,
 * Docs, Notion, etc.) renders the formatted email instead of dumping raw
 * markup. `ClipboardItem` with a "text/html" entry is what makes that work —
 * a plain `writeText` only ever puts a text/plain payload on the clipboard,
 * which is why the raw-HTML-in-Gmail complaint happens with the generic
 * copy button. Falls back to a plain-text copy (with a note) if the browser
 * doesn't support multi-type clipboard writes (e.g. older Safari). */
function CopyHtmlButton({ html }: { html: string }) {
  const [state, setState] = useState<"idle" | "copied" | "fallback">("idle");

  return (
    <button
      type="button"
      onClick={async () => {
        try {
          if (typeof ClipboardItem !== "undefined") {
            await navigator.clipboard.write([
              new ClipboardItem({
                "text/html": new Blob([html], { type: "text/html" }),
                "text/plain": new Blob([html], { type: "text/plain" }),
              }),
            ]);
            setState("copied");
          } else {
            await navigator.clipboard.writeText(html);
            setState("fallback");
          }
        } catch {
          try {
            await navigator.clipboard.writeText(html);
            setState("fallback");
          } catch {
            // clipboard unavailable — silently ignore
          }
        }
        setTimeout(() => setState("idle"), 2500);
      }}
      title="Copies the formatted email — paste directly into Gmail's compose window and it renders styled, not as raw HTML"
      className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors duration-150 ${
        state === "copied"
          ? "border-primary bg-primary/10 text-primary"
          : "border-surface-border text-muted hover:bg-surface-card-hover hover:text-foreground"
      }`}
    >
      {state === "copied" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {state === "copied" ? "Copied for pasting" : state === "fallback" ? "Copied as text (paste may not render)" : "Copy for Gmail"}
    </button>
  );
}

function VersionPill({ version }: { version: number }) {
  return (
    <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
      v{version}
    </span>
  );
}

function ScoreChip({ score, passed }: { score: number; passed: boolean }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
        passed ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-amber-300 bg-amber-50 text-amber-700"
      }`}
      title={`Evaluation score: ${score.toFixed(2)} / ${MAX_RUBRIC_SCORE}`}
    >
      {score.toFixed(1)}/{MAX_RUBRIC_SCORE}
    </span>
  );
}

function RewritingIndicator() {
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted">
      <ThinkingOrb state="composing" size={20} aria-label="Rewriting in progress" />
      Rewriting…
    </span>
  );
}

function ManualEditControl({
  title,
  body,
  onTitleChange,
  onBodyChange,
  onSave,
  onCancel,
  saving,
  error,
}: {
  title: string;
  body: string;
  onTitleChange: (v: string) => void;
  onBodyChange: (v: string) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
}) {
  return (
    <div className="mt-3 space-y-2 rounded-lg border border-surface-border bg-surface-base p-3">
      <p className="text-xs text-muted">
        Edit this option directly — paste in anything you liked from another draft's Copy button above.
      </p>
      <input
        value={title}
        onChange={(e) => onTitleChange(e.target.value)}
        placeholder="title"
        disabled={saving}
        className="w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 text-sm font-medium focus:border-primary focus:outline-none"
      />
      <textarea
        value={body}
        onChange={(e) => onBodyChange(e.target.value)}
        rows={12}
        disabled={saving}
        className="w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 font-mono text-xs focus:border-primary focus:outline-none"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:opacity-60"
        >
          {saving && <ThinkingOrb state="working" size={20} aria-label="Saving" />}
          {saving ? "Saving…" : "Save as new version"}
        </button>
        <button
          onClick={onCancel}
          disabled={saving}
          className="rounded-md px-3 py-1.5 text-sm text-muted hover:bg-surface-card-hover disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function UsagePanel({
  usage,
  expanded,
  onToggle,
}: {
  usage: ContentRequestDetail["usage"];
  expanded: boolean;
  onToggle: () => void;
}) {
  if (usage.length === 0) {
    return <EmptyNote text="no Claude calls logged yet" />;
  }
  const totalInput = usage.reduce((sum, u) => sum + u.input_tokens, 0);
  const totalOutput = usage.reduce((sum, u) => sum + u.output_tokens, 0);
  const totalCost = usage.reduce((sum, u) => sum + u.cost_usd, 0);

  return (
    <div className="glow-card rounded-xl border border-surface-border bg-surface-card p-4 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium text-foreground">${totalCost.toFixed(4)}</span>
        <span className="text-xs text-muted">
          {totalInput.toLocaleString()} in / {totalOutput.toLocaleString()} out · {usage.length} call
          {usage.length === 1 ? "" : "s"}
        </span>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
      >
        {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        {expanded ? "hide passes" : "show every pass"}
      </button>
      {expanded && (
        <ul className="mt-2 space-y-1.5">
          {usage.map((u) => (
            <li key={u.id} className="flex items-center justify-between gap-2 text-xs">
              <span className="min-w-0 truncate text-muted">
                {u.job_type ?? "—"} <span className="text-muted/60">({u.model})</span>
              </span>
              <span className="shrink-0 text-foreground">
                {u.input_tokens.toLocaleString()}/{u.output_tokens.toLocaleString()} · ${u.cost_usd.toFixed(4)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RewriteControl({
  instructions,
  onChange,
  onSubmit,
  onCancel,
  pending,
}: {
  instructions: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  pending: boolean;
}) {
  return (
    <div className="mt-3 space-y-2 rounded-lg border border-surface-border bg-surface-base p-3">
      <textarea
        value={instructions}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
        placeholder="optional instructions, e.g. 'make it punchier' — leave blank to just improve it"
        className="w-full rounded-md border border-surface-border bg-surface-card px-3 py-2 text-sm focus:border-primary focus:outline-none"
        disabled={pending}
      />
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onSubmit}
          disabled={pending}
          className="flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:opacity-60"
        >
          {pending && <ThinkingOrb state="composing" size={20} aria-label="Rewriting" />}
          {pending ? "Rewriting…" : "Submit"}
        </button>
        <button
          onClick={onCancel}
          disabled={pending}
          className="rounded-md px-3 py-1.5 text-sm text-muted hover:bg-surface-card-hover disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

/** Shows exactly what this version was told to do differently — a content
 * manager's review notes / rewrite instructions, folded together with the
 * prior evaluation's own feedback and unsupported-claims list (app/services/
 * evaluation_context.py). This is the actual text the generate job's payload
 * was seeded with; before article_drafts.revision_instructions existed, it
 * was only ever visible in a raw `jobs` row, not on the request detail page
 * a reviewer actually looks at. */
function InstructionsGiven({ instructions }: { instructions: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left font-medium text-foreground"
      >
        <span>Instructions given to the AI for this version</span>
        {expanded ? <ChevronUp className="h-3.5 w-3.5 shrink-0" /> : <ChevronDown className="h-3.5 w-3.5 shrink-0" />}
      </button>
      {expanded && <p className="mt-2 whitespace-pre-wrap text-muted">{instructions}</p>}
    </div>
  );
}

function EvaluationSummary({
  evaluation,
}: {
  evaluation: ContentRequestDetail["evaluations"][number];
}) {
  const [showDetail, setShowDetail] = useState(false);
  const pct = Math.max(0, Math.min(1, evaluation.overall_score / MAX_RUBRIC_SCORE));
  const barColor = evaluation.passed_threshold ? "bg-emerald-500" : "bg-amber-500";

  return (
    <div className="mt-3 rounded-lg bg-surface-base p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-foreground">
          Evaluation: {evaluation.passed_threshold ? "pass" : "revise/reject"}
        </span>
        <span className="text-muted">by {evaluation.evaluated_by}</span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-2 flex-1 max-w-[10rem] overflow-hidden rounded-full bg-surface-card-hover">
          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct * 100}%` }} />
        </div>
        <span className="text-xs font-medium text-foreground">
          {evaluation.overall_score.toFixed(2)} / {MAX_RUBRIC_SCORE}
        </span>
        {evaluation.score_delta_from_parent != null && (
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
              evaluation.score_delta_from_parent < 0
                ? "border-red-300 bg-red-50 text-red-700"
                : evaluation.score_delta_from_parent > 0
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                  : "border-surface-border bg-surface-card-hover text-muted"
            }`}
            title="Change in score versus the draft this version was regenerated from"
          >
            {evaluation.score_delta_from_parent > 0 ? "▲" : evaluation.score_delta_from_parent < 0 ? "▼" : "="}{" "}
            {Math.abs(evaluation.score_delta_from_parent).toFixed(2)} vs previous version
          </span>
        )}
      </div>
      {evaluation.score_delta_from_parent != null && evaluation.score_delta_from_parent < 0 && (
        <p className="mt-1 text-xs text-red-700">
          This version scored lower than the draft it was regenerated from — a regression like this is never sent
          to you as a &ldquo;pass&rdquo;: it&apos;s automatically retried, told to compare against the previous
          draft and restore whatever it dropped, for as long as revisions remain. If you&apos;re seeing this on a
          version awaiting review, the automatic retries ran out — check the previous version for anything worth
          keeping.
        </p>
      )}
      <p className="mt-1 text-muted">{evaluation.feedback}</p>
      {evaluation.unsupported_claims?.length > 0 && (
        <div className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-2">
          <p className="text-xs font-medium text-amber-800">
            Claims not backed by a provided source, or stated more confidently than the evidence supports:
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-amber-800">
            {evaluation.unsupported_claims.map((claim, i) => (
              <li key={i}>{claim}</li>
            ))}
          </ul>
        </div>
      )}
      {Object.keys(evaluation.rubric_scores ?? {}).length > 0 && (
        <>
          <button
            onClick={() => setShowDetail((v) => !v)}
            className="mt-2 flex items-center gap-1 text-xs text-primary hover:underline"
          >
            {showDetail ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {showDetail ? "hide criteria" : "why this score?"}
          </button>
          {showDetail && (
            <div className="mt-2 space-y-1.5">
              {Object.entries(evaluation.rubric_scores).map(([k, v]) => {
                const score = Number(v) || 0;
                const criterionPct = Math.max(0, Math.min(1, score / MAX_RUBRIC_SCORE));
                return (
                  <div key={k} className="flex items-center gap-2 text-xs">
                    <span className="w-32 shrink-0 truncate capitalize text-muted">{k.replace(/_/g, " ")}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-card-hover">
                      <div
                        className={`h-full rounded-full ${criterionPct >= 0.8 ? "bg-emerald-500" : criterionPct >= 0.6 ? "bg-amber-500" : "bg-red-500"}`}
                        style={{ width: `${criterionPct * 100}%` }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right font-medium text-foreground">{score}/{MAX_RUBRIC_SCORE}</span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function groupAdaptationsByChannel(
  adaptations: ChannelAdaptationOut[]
): { latest: ChannelAdaptationOut; previous: ChannelAdaptationOut[] }[] {
  const byChannel = new Map<string, ChannelAdaptationOut[]>();
  for (const a of adaptations) {
    byChannel.set(a.channel, [...(byChannel.get(a.channel) ?? []), a]);
  }
  return Array.from(byChannel.values()).map((group) => {
    const sorted = [...group].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return { latest: sorted[0], previous: sorted.slice(1) };
  });
}

function ReviewButton({
  label,
  onClick,
  variant,
  disabled,
}: {
  label: string;
  onClick: () => void;
  variant: "approve" | "reject" | "neutral";
  disabled?: boolean;
}) {
  const styles = {
    approve: "bg-emerald-600 text-white hover:bg-emerald-700",
    reject: "bg-red-600 text-white hover:bg-red-700",
    neutral: "border border-surface-border text-foreground hover:bg-surface-card-hover",
  }[variant];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${styles}`}
    >
      {label}
    </button>
  );
}
