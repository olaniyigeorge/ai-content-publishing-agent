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
    <iframe
      srcDoc={html}
      sandbox=""
      title="Rendered newsletter preview"
      className="mt-2 w-full rounded-lg border border-surface-border bg-white"
      style={{ height: "480px" }}
    />
  );
}
