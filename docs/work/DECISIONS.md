# Open Decisions

Running log of calls that are genuinely product/business decisions rather than
obvious engineering fixes. Each entry: the question, the default I'm proceeding
with (so work isn't blocked), and why. Revisit anytime — nothing here is final
until you say so.

---

## Auth allowlist was empty — bootstrapped your own access

`access_rules` had zero rows, so `request_code()` was silently no-op'ing for
every email (by design, per §6 refinement 1 — it never reveals allowlist
rejection). Inserted one row: `{type: email, value: olaniyigeorge77@gmail.com,
enabled: true}` so login actually works for you. **Decision needed:** how do
other content managers get onto the allowlist — self-serve via a signup flow,
or purely manual via the `/auth/access-rules` admin endpoints? Currently
there's no UI for `access_rules` in the frontend (endpoints exist, page
doesn't) — flagging as a decision rather than building it blind.

## Frontend stack: plain fetch + useState, no data-fetching library

Went with a small typed `fetch` wrapper (`frontend/src/lib/api.ts`) and
`useState`/`useEffect` for data loading instead of pulling in TanStack Query
or SWR. **Why:** the app has ~5 pages and no complex cache invalidation
needs; a library would be pure overhead right now. **Revisit if:** the
review/publishing pages start needing optimistic updates or cross-page cache
sharing — TanStack Query would earn its place then.

## Request detail page polls every 5s while non-terminal

`/requests/[id]` re-fetches every 5s until status is `published`, `rejected`,
or `failed`, since the pipeline runs asynchronously via the worker and there's
no websocket/SSE channel. **Decision needed:** is polling acceptable for the
submission, or do you want a push-based update (SSE from the worker) for the
demo/Loom video? Polling is simpler and sufficient for a small reviewer team;
flagging in case the Loom video needs snappier updates.

## ✅ Fixed — filter-injection risk in `auth/service.py::_is_allowlisted`

**Resolved 2026-09-17.** `_is_allowlisted()` used to build
`.or_(f"and(type.eq.email,value.eq.{email}),...")` by interpolating the raw
email into a PostgREST filter string. PostgREST's filter grammar uses
`,`/`(`/`)`/`.` as syntax, so a crafted email containing those characters
could alter the filter logic and potentially bypass the allowlist check
entirely.

Fixed by replacing the single `.or_()` string with two separate `.eq()`
queries (one by email, one by domain) unioned in Python — `.eq()` values
are passed as parameters, not interpolated into filter syntax, so there's
no longer anywhere for a crafted value to break out of the intended field.
Added two regression tests in `tests/test_auth.py`:
`test_is_allowlisted_matches_email_and_domain_rules` (still matches real
email/domain rules) and `test_is_allowlisted_is_not_vulnerable_to_filter_injection`
(a crafted email containing `,`/`(`/`)` no longer widens the match). Full
backend suite: 92 passed.

## Backend audit fixes applied vs. logged as backlog

Ran a full production-readiness audit (3 blocker / 6 high / 6 medium / 3 low
findings). Fixed directly (safe, isolated, all 37 tests still pass):
- `resend_api_key` is now a required setting (was silently defaulting to
  `""`, which meant OTP emails could vanish with no signal at all).
- Anthropic client now has a 120s timeout (`claude/client.py`) — previously
  unbounded, so a hung call would stall the worker's single-threaded poll
  loop indefinitely, since retry/backoff logic never got a chance to run.
- Added `/health/ready`, which actually pings Supabase — `/health` alone
  always returns `ok` even if the DB is unreachable.
- Added `Dockerfile`s (backend + frontend), `docker-compose.yml`, and a
  GitHub Actions CI workflow (backend ruff+pytest, frontend eslint+build) —
  there was previously no deployment story or CI at all.
- Ran `ruff check --fix` across the backend (46 pre-existing lint errors,
  all mechanical: `datetime.timezone.utc` → `datetime.UTC`, import sorting)
  and added a ruff config exempting FastAPI's `Depends()`/`Cookie()`
  pattern from the mutable-default-arg check.
- Added tests for the new Resend email path and a few FastAPI-route-level
  smoke tests (health, 401 on missing/garbage session) — the audit found
  zero coverage through `TestClient` before this; everything else tests
  service functions directly, so a broken route wire-up wouldn't be caught.

**Logged as backlog / open decisions (not fixed — genuine product calls or
larger scope than a line fix):**
- The `_is_allowlisted` injection bug above (blocking on your in-progress edit).
- `access_rules` CRUD is open to any authenticated user, no admin role.
- No pagination on `GET /api/requests`, `/api/publishing-queue`,
  `/auth/access-rules` — fine at demo scale, not at real scale.
- No error tracking/APM (Sentry etc.) — needs a decision on whether to add
  a third-party dependency + DSN for this project's scope.
- No IP-level rate limiting on `/auth/verify-code` (only per-OTP-row attempt
  cap exists) — low practical risk given bcrypt + 6-digit + expiry, but a
  real gap if this ever needs to survive being IP-scanned.
- Single-process worker — one slow job blocks the whole queue system-wide.
- No reconciliation job for the rare case where a worker process dies
  mid-write between `jobs.status`, `publishing_queue.status`, and
  `stage_events`.
- Data retention policy for `jobs`/`stage_events`/failed queue rows —
  keep forever vs. purge after N days.
- Whether OTP-related debug logging is acceptable in prod at all, even at
  `debug` level, given upcoming compliance needs.

Full audit detail (file:line for everything above) is in this conversation's
history if you want the complete report re-surfaced.

## UI cleanup, asset uploads, and input/output guards (this round)

**UI**: fixed the stale `document.py`/`delivery.py`/`docs/edge-cases.md`
comment in `globals.css` (confirmed stale, from an old project). Redesigned
the pipeline activity view as a proper vertical timeline
(`components/pipeline-timeline.tsx` — status icons, connecting line,
staggered fade-in) instead of a plain list, and added a static "what
happens after you submit" stage preview (`components/pipeline-preview.tsx`)
to the new-request page. Applied the design-system tokens (`surface-card`,
`surface-border`, `primary`, `muted`, `glow-card`/`glow-primary`,
`animate-fade-in-up`) consistently across login, dashboard, request detail,
publishing queue, and the new-request form, replacing ad hoc Tailwind grays.
**Note**: I could not get a real browser screenshot to visually confirm
this in my sandbox — headless Chromium is missing a system library
(`libasound.so.2`) and I don't have sudo to install it. Build and lint both
pass, but please eyeball it yourself (`make frontend` or `npm run dev` in
`frontend/`) before treating the redesign as done.

**Asset uploads**: added `POST /api/uploads` (multipart) — validates size
(≤10MB) and content type (png/jpeg/webp/gif/pdf/txt/csv), sanitizes the
filename, uploads to Supabase Storage bucket `intake-media`, returns a
public URL. Frontend's new-request form now has a real upload UI (button →
file picker → thumbnail grid → remove). **You still need to create the
`intake-media` bucket** (public read) in the Supabase dashboard — I
couldn't create it myself (blocked as a security-sensitive sandbox action)
and you said you'd handle it.

**Input guards** (`app/services/intake_guards.py`, backend + mirrored
client-side in `lib/intake-validation.ts` for instant feedback): idea must
be ≥3 words and ≤2000 chars, rejects a bare URL as the idea (tell them to
use the source-URL field instead), rejects mechanically-obvious gibberish
(no letters, a hammered single character, no vowels at all — this is a
heuristic, not semantic understanding), target audience 3–300 chars,
supporting_material ≤5000 serialized chars, ≤10 attachments, URL format
checked. **Decision**: true "doesn't make sense" detection (a coherent-but-
irrelevant idea) would need an LLM call at intake time — I didn't add that
since it puts a synchronous Claude call + latency + cost on every
submission and would need test re-plumbing; flagging as an option if the
deterministic heuristics prove too weak in practice.

**Output guards** (`claude/quality_guards.py`) — the model's own
self-reported `formatting_check`/rubric "pass" is no longer trusted alone:
- Articles: real word count (300–3000), H1 presence, link count computed
  and checked; a rubric "pass" is downgraded to "revise" if these fail
  (new test: `test_model_claimed_pass_is_overridden_by_hard_length_guard`).
- Channel adaptations: real char/word counts recomputed per channel (X
  ≤280 chars, LinkedIn ≤3000, newsletter 250–600 words, X ≤2 hashtags,
  HTML stripped before counting). A violation marks that channel's
  adaptation `failed` instead of `approved` and it's never auto-queued for
  publish — visible to a human instead of silently going out over-limit.

Total backend test count: 31 → 63, all passing; ruff clean.

## ✅ Resolved — `access_rules` management UI built

**Resolved 2026-09-17.** Added `/admin/access` in the frontend
(`frontend/app/(app)/admin/access/page.tsx`) — any signed-in user can view,
grant, and revoke email/domain access rules against the existing
`GET/POST/DELETE /auth/access-rules` endpoints. No new backend endpoints
were needed; the router already allowed any authenticated user (no
separate admin role exists yet — same limitation as before, just no longer
also missing a UI). Deleting a rule prompts for confirmation since it can
lock someone out of logging in. Build and lint both pass (`npm run build`,
`npm run lint`), and the page's auth-gated shell behaves identically to the
existing publishing-queue page when hit without a session.

**Still open, not addressed by this:** no separate admin role — any
authenticated user can add/remove anyone's access, including their own.
Fine for a small trusted team; would need a real role check before this UI
is exposed to a wider group.

