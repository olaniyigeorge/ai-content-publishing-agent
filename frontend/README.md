# Koya Content Agent — Frontend

Next.js (App Router) client for the content request/review/publishing pipeline.
Talks to the FastAPI backend in `../backend` over cookie-based sessions.

## Setup

```bash
npm install
cp .env.example .env.local   # point NEXT_PUBLIC_API_URL at the running backend
npm run dev
```

Requires the backend running (see `../backend/README.md` or `make api` from
the repo root) and CORS on the backend configured to allow this origin
(`CORS_ALLOW_ORIGINS` in `backend/.env`).

## Structure

- `src/app/login` — OTP request/verify
- `src/app/(app)` — authenticated shell: requests list, new request form,
  request detail (sources, drafts, evaluations, human review, adaptations,
  publishing queue), global publishing queue
- `src/lib/api.ts` — typed fetch client for the backend API
- `src/lib/types.ts` — TS types mirroring `backend/shared/models.py` /
  `backend/shared/enums.py` (kept in sync by hand — see `docs/work/DECISIONS.md`)
- `src/lib/auth-context.tsx` — session state + auth guard for the app shell
