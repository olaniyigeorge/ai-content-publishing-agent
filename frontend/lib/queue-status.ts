export const QUEUE_STATUS_HELP: Record<string, string> = {
  queued: "waiting for its scheduled time (or to be sent immediately if none is set)",
  processing: "currently being posted",
  published: "successfully posted to the channel",
  failed: "posting failed and won't be retried automatically",
  dead_letter: "retried the maximum number of times and gave up — use Retry to try again",
  cancelled: "manually cancelled before it was posted",
};

/** Strip HTML down to readable plain text — used for channels (mailto:, X,
 * LinkedIn) that can't render markup, since newsletter content is generated
 * as HTML (content_format: "html") but mailto bodies are plain text only. */
export function htmlToPlainText(html: string): string {
  return html
    .replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<(br|\/p|\/div|\/h[1-6]|\/li)\s*\/?>/gi, "\n")
    .replace(/<li[^>]*>/gi, "- ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
