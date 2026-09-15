const DOT_COLORS: Record<string, string> = {
  intake: "bg-neutral-400",
  researching: "bg-blue-500",
  planning: "bg-blue-500",
  drafting: "bg-blue-500",
  evaluating: "bg-amber-500",
  revising: "bg-amber-500",
  in_review: "bg-violet-500",
  approved: "bg-emerald-500",
  rejected: "bg-red-500",
  adapting: "bg-blue-500",
  queued: "bg-neutral-400",
  processing: "bg-blue-500",
  published: "bg-emerald-500",
  failed: "bg-red-500",
  dead_letter: "bg-red-500",
  cancelled: "bg-neutral-300",
  started: "bg-blue-500",
  succeeded: "bg-emerald-500",
  draft: "bg-neutral-400",
  evaluated: "bg-amber-500",
  revised: "bg-amber-500",
  selected: "bg-emerald-500",
  discarded: "bg-neutral-300",
};

const TEXT_COLORS: Record<string, string> = {
  approved: "text-emerald-700",
  published: "text-emerald-700",
  selected: "text-emerald-700",
  succeeded: "text-emerald-700",
  rejected: "text-red-700",
  failed: "text-red-700",
  dead_letter: "text-red-700",
  evaluating: "text-amber-700",
  revising: "text-amber-700",
  evaluated: "text-amber-700",
  revised: "text-amber-700",
  in_review: "text-violet-700",
};

export function StatusBadge({ status }: { status: string }) {
  const dot = DOT_COLORS[status] ?? "bg-neutral-400";
  const text = TEXT_COLORS[status] ?? "text-muted";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border border-surface-border bg-surface-card px-2.5 py-1 text-xs font-medium ${text}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      {status.replace(/_/g, " ")}
    </span>
  );
}
