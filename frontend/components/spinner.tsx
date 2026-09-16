const SIZE_CLASSES: Record<"small" | "medium", string> = {
  small: "h-3.5 w-3.5 border-[1.5px]",
  medium: "h-5 w-5 border-2",
};

export function Spinner({
  size = "small",
  className = "",
}: {
  size?: "small" | "medium";
  className?: string;
}) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block shrink-0 animate-spin rounded-full border-current border-t-transparent text-muted ${SIZE_CLASSES[size]} ${className}`}
    />
  );
}

export function LoadingLine({
  label = "Loading…",
  centered = false,
}: {
  label?: string;
  centered?: boolean;
}) {
  if (centered) {
    return (
      <div className="flex animate-fade-in items-center justify-center gap-2 py-16 text-sm text-muted">
        <Spinner />
        {label}
      </div>
    );
  }
  return (
    <p className="mt-6 flex animate-fade-in items-center gap-2 text-sm text-muted">
      <Spinner />
      {label}
    </p>
  );
}
