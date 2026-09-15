const STAGES = [
  { label: "Research", detail: "retrieves and reads your source material" },
  { label: "Plan", detail: "outlines the article around your idea" },
  { label: "Draft", detail: "writes SEO-grounded article options" },
  { label: "Evaluate", detail: "scores each draft, revises weak ones" },
  { label: "Review", detail: "you approve, reject, or request changes" },
  { label: "Adapt & publish", detail: "prepares LinkedIn, X, and newsletter" },
];

export function PipelinePreview() {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-card p-5">
      <h2 className="text-sm font-semibold text-foreground">What happens after you submit</h2>
      <ol className="mt-4 grid gap-3 sm:grid-cols-2">
        {STAGES.map((stage, i) => (
          <li key={stage.label} className="flex items-start gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
              {i + 1}
            </span>
            <div>
              <p className="text-sm font-medium text-foreground">{stage.label}</p>
              <p className="text-xs text-muted">{stage.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
