"use client";

/** Renders generated HTML (the newsletter channel — content_format "html")
 * as an actual rendered email instead of an escaped text dump. An iframe
 * with `srcDoc` is used rather than `dangerouslySetInnerHTML` in the page:
 * the generated markup is a full email document (its own <!doctype>, its
 * own background/table layout) that assumes it owns the whole page, so
 * injecting it directly would collide with this app's own styles. `sandbox`
 * with no `allow-scripts` means any script tag in the content simply won't
 * run — this is a read-only preview, not a place to execute the content. */
export function HtmlContentPreview({ html }: { html: string }) {
  return (
    <div className="mt-2">
      <iframe
        srcDoc={html}
        sandbox=""
        title="Rendered newsletter preview"
        className="h-[300px] w-full rounded-lg border border-surface-border bg-white sm:h-[480px]"
      />
      <p className="mt-1.5 text-[11px] text-muted">
        Use &ldquo;Copy for Gmail&rdquo; below to paste a formatted email — or click into the preview above, select
        all (Ctrl/Cmd+A) and copy from there. The plain copy icon copies raw HTML source instead.
      </p>
    </div>
  );
}
