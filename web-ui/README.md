# Framekit Web UI

Frontend SPA for local Framekit dashboard.

## Stack

- React + TypeScript strict
- Vite
- Tailwind CSS v4
- shadcn/ui-style components + Radix UI
- TanStack Router + TanStack Query
- Zod + React Hook Form
- Vitest + Testing Library + Playwright

## Features V1

- Home dashboard
- Doctor dashboard (`/api/v1/doctor`)
- Modules workbench (catalog + execution API)
- Presets for frequent module commands
- Async module job queue with live status polling + rerun
- Job cancellation from UI
- Job history persisted in backend SQLite cache
- Job list controls: limit, status filter, search, load-more
- Guided launchers for pipeline and batch argument building
- API errors rendered with HTTP status + backend detail

## Commands

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run test
npm run test:e2e
npm run build
```

## API Base URL

Default API base URL: `http://127.0.0.1:8000`.

Override:

```bash
VITE_FRAMEKIT_API_BASE_URL=http://127.0.0.1:9000
```
