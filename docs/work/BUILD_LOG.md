# Koya Content Agent — Build Log

> Resumable reference for the build. Updated every session. If this session breaks, come back here — it tells you what exists, what's built, what's tested, what broke, and the open decisions that still need resolving.

---

## 2026-09-17 — production-readiness review + submission prep session

### What happened this session

Full review of the project for production readiness, framed as a business owner about to trust this with their agency's LinkedIn/X/newsletter content, plus a pass at the submission deliverables.

- **Security fix (real, not cosmetic):** `_is_allowlisted()` in `backend/auth/service.py` had an unresolved filter-injection risk (flagged in `DECISIONS.md`, never fixed) — it built a PostgREST `.or_()` filter by string-interpolating the raw email. Fixed by replacing it with two separate parameterized `.eq()` queries unioned in Python. Added two regression tests (`tests/test_auth.py`): one confirming real email/domain rules still match, one proving a crafted email containing filter syntax no longer widens the match. Full backend suite: **92/92 passing.**
- **Confirmed live and healthy:** frontend (`ai-content-publishing-agent.vercel.app`) returns 200; backend `/health/ready` returns 200 (pings Supabase for real); `/auth/request-code` gives an identical response for allowlisted vs. non-allowlisted emails (no enumeration).
- **Confirmed clean:** no secrets, keys, or `.env` files anywhere in git history.
- **New docs created:**
  - `BUSINESS_OWNER_QA.md` — added an "Expected Business Results" section (§0) framing this in ROI terms a founder would actually use: time-to-first-draft, where the bottleneck actually moves, cost-per-piece visibility, and what the system explicitly does *not* do.
  - `LIVE_TEST_SESSION.md` — the 8 required scenarios turned into a concrete live walkthrough plan against the deployed URLs, so the testing evidence table gets filled with verified results, not carried-over assumptions from earlier local sessions.
  - `VIDEO_SCRIPT.md` — a timed script hitting the required flow within the actual 5–8 minute limit (Week 3's video ran 9 minutes and lost marks for it).
  - `ONE_PAGER.md` — the one-page documentation deliverable, which did not exist before this session. Covers purpose/success criteria, how it works, how to use it, and an honest appendix of limitations.
- **Testing evidence table and reflection sheet in `SUBMISSION_WORKBOOK.md` filled in**, sourced from real findings in `TESTING_FINDINGS.md`/`TEST_INTAKE_REQUESTS.md` where they exist, and honestly marked "pending live reconfirm" where they haven't been re-walked on the actual deployed build yet — Human Approval and Channel Formatting are flagged as **not yet verified live at all** and should be the first things checked in the next session.

### What's still genuinely missing before Friday's submission

- [ ] Live walkthrough of all 8 scenarios on the deployed app (`LIVE_TEST_SESSION.md`), especially Human Approval and Channel Formatting which have never been explicitly re-walked.
- [ ] Content sample pack (input + article + LinkedIn + X + newsletter + source list) — does not exist yet, needs a real approved request to generate it from.
- [ ] Demo video recorded and uploaded (script is ready in `VIDEO_SCRIPT.md`).
- [ ] One-pager published somewhere linkable (currently a repo file, `ONE_PAGER.md` — needs to go somewhere shareable per the submission form's "paste the link" requirement).
- [ ] Final settle-and-check pass against `SUBMISSION_WORKBOOK.md`'s "Things to verify before submitting" checklist.

---

## 2026-09-14 — first build session

### What exists so far

- `docs/provided/` — PRD + 3 asset files, untouched from the project (PRD.md, seo-best-practices.md, channel-formatting-rules.md, content-evaluation-rubric.md)
- `docs/work/architecture.md` — full architecture doc, 9 sections: design principles, enum types, 10 tables (content_requests, intake_attachments, sources, content_plans, article_drafts, evaluations, human_reviews, channel_adaptations, publishing_queue, jobs, stage_events), indexes, retry/dead-letter logic, minimal auth (§6: access_rules, users, login_attempts, sessions + 3 refinements + RLS decision), what's deferred, full example data trace (§8), project structure for backend + frontend (§9 — FastAPI + polling worker + Claude service + Next.js, no n8n)
- `docs/work/PROJECT_SUMMARY.md` — verbatim dump of everything in the project (PRD, workflow, SEO rules, channel rules, rubric, 8 test scenarios, 6 deliverables, resource links, decision checklist)
- `docs/work/SUBMISSION_WORKBOOK.md` — combined submission template (Part 1) + production-ready systems grading guide (Part 2) + Week 4 project context (Part 3) + 5/5 checklists for Technical Execution / Communication / Critical Thinking (Part 4)
- `README.md` at repo root — updated to point at `provided/` layout

### What is built

**Docs only — no code yet.** Everything above is design documentation:
- Architecture fully specified (schema + auth + project structure)
- Submission workbook assembled (what to hand in + how it's graded + how to hit 5/5)
- Directory organized (provided/ vs work/)
- All internal references in docs pointing at the right places

### What is tested (which of the 8 scenarios, and the result)

None yet — no running system. The test plan is written into `backend/tests/` in the architecture doc (§9.2): test_intake, test_source_grounding, test_evaluation_loop, test_human_approval_gate, test_channel_formatting, test_publishing_queue, test_failure_handling, test_auth — each mapped 1:1 to the 8 required scenarios.

### What is not yet built

- Backend code (FastAPI app, worker, Claude service, auth module)
- Supabase schema (migrations from §3 of architecture.md)
- Frontend code (Next.js app + components)
- Any running system, any sample output, any Loom video

### Open decisions

- ~~Claude model selection for v1~~ **Decided 2026-09-14:** tiered by step. Sonnet for `generate` and `evaluate` (quality-sensitive, drives the revision loop and the rubric scoring). Haiku for `research` (source summarization/excerpt selection) and `adapt` (channel formatting is mostly rule application, not creative quality). Recorded in `backend/claude/models.py` as the model router.
- ~~Which scraping/retrieval tool~~ **Decided 2026-09-14:** Firecrawl API. Handles JS-rendered pages without custom extraction code; requires `FIRECRAWL_API_KEY` in env. `sources.retrieval_method = 'url_provided'` rows will additionally note the tool used if needed later.
- Whether frontend uses Supabase Storage for intake image uploads (lib/supabase.ts with anon key) or handles media another way — only affects one frontend lib, no architecture impact
- Whether to generate frontend types from FastAPI OpenAPI spec or hand-write them (§9.4) — hand-write is fine for v1 if backed by a shape-matching assertion in tests

### Errors encountered and how they were resolved

None at the code level — no code written yet. Doc-level: the original `docs/` had everything flat (PRD, assets/, architecture.md, SUBMISSION_WORKBOOK.md mixed together). Resolved by splitting into `provided/` (project-owned, never edited) and `work/` (ours), and moving PROJECT_SUMMARY.md from repo root into `docs/work/`. Updated all `assets/` references in README.md and PROJECT_SUMMARY.md to `../provided/assets/`.

### Model used and why (for reflections)

Not yet decided / not yet used. To be filled in once the Claude service is wired and we've made the actual model choice. The architecture document leaves this open deliberately (§9.2, `claude/models.py` is the model router) so the choice is explicit and recorded in code, not implicit in each call.

### Edge cases handled (for reflections)

Not yet built, so none handled at runtime. The design accounts for these at the schema/structure level (to be reflected on later):
- Multiple source URLs + image attachments per request (intake_attachments table, not a single source_url column)
- Revision history preserved structurally (article_drafts append-only + parent_draft_id lineage, not overwrite)
- Failure visibility structural (stage_events append-only log, not app logs)
- Publishing as a queue by default, not a live integration (publishing_queue + mock adapter)
- Source traceability as a first-class relationship (source_ids_used array + sources table, not a text blob)
- Allowlist not enumerable (request-code returns same response either way)
- OTP invalidated after use (consumed_at field)
- Session is opaque + server-side + immediate revocation on logout (delete row, no revoked_at needed)

### One thing to do differently next time (for reflections)

To be filled in after building. Likely candidate: the architecture doc §9.7 lists what's deferred (RLS, real publishing, pgvector, configurable backoff) — once we've built v1 and seen where the actual friction was, this field gets the honest answer.

### Clarifying questions (for reflections)

To be filled in after building, but the project brief already implies these (to be sharpened):
- What does "publish" actually mean for this team — do they have real LinkedIn/X/newsletter integrations today, or is "saved into a publishing queue" the real deliverable for v1?
- Who is the content manager audience for the front-end — one person, a small team, external reviewers? (Drives whether auth is domain-wide allowlist vs. individual emails, and whether the one-pager should address multiple user roles.)
- What's the expected volume — a few requests per week, or enough that cost-per-run and retry behavior matter materially? (Drives model selection and whether to invest in caching/reuse.)
- Are there brand voice / tone guidelines beyond what the rubric and channel-formatting-rules capture — a style guide document, example posts, a brandbook? (Drives whether the Claude prompts need a voice section beyond "match the brand.")
- What does the human reviewer do today when they reject or ask for a revision — do they rewrite themselves, or do they give written feedback the author acts on? (Drives whether `human_reviews.notes` should feed back into a revision job automatically or just sit as a record.)

### Things to verify before submitting

- [ ] Front-end link loads from another machine and is still live
- [ ] No keys in repo, video, or front-end
- [ ] Content sample pack has: input, article, LinkedIn post, X post, email newsletter, source list
- [ ] Testing evidence table is filled in for all 8 scenarios
- [ ] One-pager exists and covers: header, purpose & success criteria, how it works, how to use it, appendix
- [ ] Video covers: who you are, business problem, solution, happy path demo, failure/edge case demo, key artefacts, reflections
- [ ] Reflection sheet answers all 5 questions, including model choice with alternative and trade-offs
- [ ] Workflow is runnable, not broken, includes error handling, safe to run more than once
- [ ] Submission form URL is the correct one: https://docs.google.com/forms/d/e/1FAIpQLSfnFXF2X4L8T4L8T4D8BBAX3GoJcV_XaPYv8Ejrq7bZQjtPAjWDtA/viewform

---

*Next session: create a new dated section at the top, keeping this one as the historical record. Copy the template structure from this section.*
