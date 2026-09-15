// Mirrors backend/app/services/intake_guards.py — the backend is the source
// of truth (it re-validates everything on submit), this just gives instant
// feedback instead of a round-trip 422.

export const MIN_IDEA_WORDS = 3;
export const MAX_IDEA_LENGTH = 2000;
export const MIN_TARGET_AUDIENCE_LENGTH = 3;
export const MAX_TARGET_AUDIENCE_LENGTH = 300;
export const MAX_ATTACHMENTS = 10;

const BARE_URL_RE = /^\s*https?:\/\/\S+\s*$/i;

function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function looksLikeGibberish(text: string): string | null {
  const letters = text.replace(/[^a-zA-Z]/g, "");
  if (!letters) return "contains no actual words";

  const stripped = text.replace(/\s/g, "");
  if (stripped.length >= 6 && new Set(stripped.toLowerCase()).size <= 2) {
    return "looks like a repeated/mashed character, not a real idea";
  }
  if (letters.length >= 8 && !/[aeiouAEIOU]/.test(letters)) {
    return "doesn't look like real words (no vowels)";
  }
  return null;
}

export function validateRawIdea(raw: string): string | null {
  const idea = raw.trim();
  if (!idea) return null; // empty is allowed if there's a source URL — checked at the form level
  if (idea.length > MAX_IDEA_LENGTH) return `too long (${idea.length} chars, max ${MAX_IDEA_LENGTH})`;
  if (BARE_URL_RE.test(idea)) return "this looks like just a URL — add it in the source URL field instead";
  const gibberish = looksLikeGibberish(idea);
  if (gibberish) return gibberish;
  if (wordCount(idea) < MIN_IDEA_WORDS) return `too short — use at least ${MIN_IDEA_WORDS} words`;
  return null;
}

export function validateTargetAudience(raw: string): string | null {
  const audience = raw.trim();
  if (audience.length < MIN_TARGET_AUDIENCE_LENGTH) return "required";
  if (audience.length > MAX_TARGET_AUDIENCE_LENGTH) {
    return `too long (${audience.length} chars, max ${MAX_TARGET_AUDIENCE_LENGTH})`;
  }
  return null;
}

export function validateSourceUrl(raw: string): string | null {
  const url = raw.trim();
  if (!url) return null;
  if (!/^https?:\/\/\S+$/i.test(url)) return "doesn't look like a valid http(s) URL";
  return null;
}
