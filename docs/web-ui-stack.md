# Web UI Stack Reference

Reference for Framekit web interface technical baseline.

## Scope

- Local development first.
- No production auth/hardening in V1.
- CLI behavior must remain unchanged.

## Frozen Stack

- Frontend: React, TypeScript strict, Vite.
- UI: Tailwind CSS v4, shadcn-style component layer, Radix primitives, lucide icons.
- Data: TanStack Query, typed fetch wrapper, Zod runtime validation.
- Forms: React Hook Form + Zod resolver.
- Routing: TanStack Router (SPA).
- Quality: ESLint + Prettier.
- Tests: Vitest + Testing Library + Playwright (+ Axe in smoke).

## Version / Pinning Policy

- Use semver ranges pinned at major level in `web-ui/package.json`.
- Upgrade policy:
  - Patch/minor updates allowed in maintenance PRs.
  - Major upgrades only in dedicated migration PR with test rerun.
- For critical frontend infra packages (`react`, `vite`, `@tanstack/*`, `zod`, `tailwindcss`), include short upgrade note in PR description.

## Frontend Conventions

- Source root: `web-ui/src`.
- Aliases: `@/* -> src/*`.
- Structure:
  - `lib/api/*`: fetch wrapper + schemas + endpoints.
  - `components/ui/*`: design-system primitives.
  - `routes/*`: page-level route components.
  - `test/*`: test setup.
- Route components loaded with `lazyRouteComponent` for bundle splitting.
- No direct untyped `fetch(...).json()` in routes/components. Always go through `lib/api/client.ts` + Zod schema parse.

## Backend Contract (V1)

- `GET /healthz`
- `GET /api/v1/system/info`
- `GET /api/v1/doctor`
- `GET /api/v1/modules/catalog`
- `GET /api/v1/modules/presets`
- `POST /api/v1/modules/run`
- `POST /api/v1/modules/jobs`
- `GET /api/v1/modules/jobs`
- `GET /api/v1/modules/jobs/{job_id}`
- `DELETE /api/v1/modules/jobs/{job_id}`
- `POST /api/v1/modules/jobs/{job_id}/rerun`
- `GET /api/v1/settings/summary`
- `POST /api/v1/settings/patch`
- `GET /api/v1/seedbox/list`
- `GET /api/v1/seedbox/history`
- `GET /api/v1/upload/trackers`
- `GET /api/v1/upload/state`
- `POST /api/v1/upload/state`
- `GET /api/v1/upload/history`

Response validation must be represented in frontend Zod schemas under `src/lib/api/schemas.ts`.

`POST /api/v1/modules/run` rules:
- Module must be allow-listed in backend catalog.
- Destructive module execution requires explicit `confirm_destructive=true`.
- `dry_run=true` is default at UI level.

Async jobs:
- Backed by in-memory queue + SQLite persistence.
- Status lifecycle: `pending -> running -> completed|failed|cancelled`.
- Persisted in `get_cache_dir()/web/module_jobs.sqlite3` (`FRAMEKIT_CACHE_DIR` override supported).
- Jobs recovered at backend startup; `pending/running` jobs from previous process are marked failed (`Interrupted by backend restart.`).
- Cancellation supported for `pending` and `running` jobs.
- Rerun endpoint creates a new job from a previous job request payload.
- UI exposes `limit`, `status` filter, text search, and incremental `Charger plus`.
- UI exposes job detail route (`/modules/:jobId`) with timestamps, duration, outputs, command copy.
- UI job detail includes live logs `follow/pause` mode and text filtering.
- UI exposes guided launchers for `pipeline` and `batch` (args builder).
- UI shows detailed API error messages (`HTTP code + detail`).
- Dedicated pages available: `settings/setup`, `seedbox`, `upload`, `pipeline`, `batch`, studios index (`/studios`), dedicated module pages (`/module/:moduleSlug`), and module-studio (`/studio/:module`).

## Minimal Test Strategy (Required)

- Every functional change:
  - `npm run typecheck`
  - `npm run lint`
  - `npm run test`
- For routing/API-view changes:
  - `npm run test:e2e`
- Keep e2e baseline green:
  - smoke path: home load + doctor render.
  - modules path: async create + cancel + rerun.
  - modules detail path: open job detail route and validate result visibility.
  - dedicated pages path: settings/setup + seedbox + upload + module-studio basic execution.
  - studios path: studios index + one dedicated module execution.

## Non-goals (V1)

- No SSR/SEO layer.
- No user auth/session.
- No destructive workflow actions from UI.
