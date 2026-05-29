Enough data. Writing plan now.

---

# Ouro Web UI v1.0 — Revised Plan (Application-First)

---

## 1. Product UX Principles

1. **Run on the page, see the result on the page.** Every workflow surface — pipeline, module, seedbox, upload — shows its own inline progress and result. Users never need to navigate to the Jobs page as part of a normal workflow.
2. **Jobs is a debug surface, not a workflow surface.** The Jobs page exists for history, rerun, cancel, and log inspection — not as the destination after clicking Run.
3. **One reusable execution component, used everywhere.** A single `InlineJobPanel` component drives the status/progress/result display for every module page and every workflow page. Module pages stop being UI wrappers around a raw command form.
4. **Show what happened, not just whether it succeeded.** Result summaries are human-readable: files renamed, tracks cleaned, torrent created, screenshots taken — not just "Completed" or stdout dump.
5. **Structure over decoration.** The UI adds value by interpreting output (file counts, step progress, warnings), not by beautifying the terminal.

---

## 2. Universal Module Execution UX Pattern

This pattern applies everywhere a user can trigger a CLI module. It must be implemented as one component.

---

### 2.1 Form

**What's shown:**
- Path input (file/folder) for modules that need one
- CLI options as typed form fields (using `CliCommandForm` — already exists)
- Preset chips for quick config (already in DedicatedModuleLauncher)
- Dry-run toggle for destructive modules (already flagged in `ModuleSpec.supports_dry_run`)
- "Advanced — show command" collapsed details (keep — useful for power users)

**What changes:**
- Form is always visible and re-editable after a run (currently the form persists but result card appears below, disconnected)
- Dry-run should be the **default on** for all modules where `supports_dry_run=True` and `destructive=True`. Currently: DedicatedModuleLauncher hardcodes `dry_run: false` regardless.
- Path field is type=text today. No file browser. Mark as **backend-needed** improvement (not blocking v1.0).

---

### 2.2 Validation

**Before submission:**
- Required flags checked (already: `requiredFlags` prop in DedicatedModuleLauncher)
- Empty path blocked for path-required modules
- `confirm_destructive` never silently enabled when `dry_run=false` + destructive module — show a confirmation prompt first

**What's missing:**
- No path existence check (backend-needed: `GET /api/v1/fs/stat?path=...`)
- No tracker/seedbox existence pre-check before submitting upload/push jobs
- Confirm dialog for destructive run (module is flagged `destructive=True` in ModuleSpec, UI ignores this today)

---

### 2.3 Run State

**Immediately after clicking Run:**
- Button goes disabled with spinner label ("Running…")
- `InlineJobPanel` appears inline (see §2.4) — no navigation
- Form becomes visually dimmed but remains visible for re-run

**Current behavior:** DedicatedModuleLauncher navigates via "View Job" button. Pipeline/Batch show a separate Progress card that only shows 3-step RunTimeline (Queued/Running/Done). No live output inline on the page.

---

### 2.4 Progress (`InlineJobPanel` component)

**Polls:** `GET /api/v1/modules/jobs/:id` — 1.5s when pending/running, stops when terminal. Already exists in job detail page logic; needs extracting into a reusable component.

**Displays:**
```
┌─────────────────────────────────────────────────────┐
│  ● Running    [Queued ✓] → [Running ●] → [Result]   │
│                                                      │
│  Sub-steps (from parseSubSteps):                    │
│    ✓ Renamer                                        │
│    ✓ CleanMKV                                       │
│    ● Metadata                                       │
│                                                      │
│  Live output (last 30 lines, auto-scroll):          │
│  [INFO] Processing track 2...                       │
│                                                      │
│  [Cancel]  [Debug →]                                │
└─────────────────────────────────────────────────────┘
```

**What's available from job API (all already exist):**
- `status` — for status badge + timeline coloring
- `live_stdout` + `live_stderr` — for scrolling output (available while running)
- `result.ok`, `result.returncode` — for final state
- `result.parsed_kind`, `result.parsed_payload` — for structured result
- `started_at`, `finished_at` — for duration display
- `error` — for crash messages

**Sub-step parsing (`parseSubSteps`):** already exists for pipeline, batch, cleanmkv, torrent, upload. Needs extension for renamer, nfo, prez, screenshot, extract.

**Live output:** show last 30 lines of `live_stdout`. Collapse to 10 lines when done. Filter toggle. This is all existing API data.

**Actions during run:**
- Cancel (`DELETE /api/v1/modules/jobs/:id`) — already API exists
- "Debug →" link → `/jobs/:jobId` (secondary action, small)

---

### 2.5 Result Summary

**After completion**, `InlineJobPanel` transitions to a compact result card that replaces the live output view:

```
┌─────────────────────────────────────────────────────┐
│  ✓ Completed   3m 42s   returncode 0               │
│                                                      │
│  [module-specific summary]                          │
│                                                      │
│  [Rerun]  [Rerun with changes]  [Debug →]           │
└─────────────────────────────────────────────────────┘
```

**Module-specific summaries** (parsed from stdout or structured payload):

| Module | Summary to show | Source |
|---|---|---|
| pipeline | Steps completed + any warnings | `parseSubSteps` from stdout |
| batch | N releases processed + fail count | `parseSubSteps` from stdout |
| renamer | "N files renamed" | parse `Renamed:` lines in stdout |
| cleanmkv | "N tracks removed across M files" | parse stdout `Processing MKV` block |
| torrent | Torrent file path (if visible in stdout) | parse `Created:` or similar |
| nfo | NFO output path | parse stdout |
| prez | Output files generated | parse stdout |
| screenshot | "N screenshots captured" | parse stdout count |
| encode | Output file + duration | parse stdout |
| extract | Extracted track count | parse stdout |
| inspect | Structured: title, kind, size, completeness | `parsed_payload` if JSON, else parse stdout |
| validate | Check count: N ok, N warn, N err | `parsed_payload` if JSON |
| metadata | Status summary | parse stdout |
| upload | Tracker + status | `parsed_payload` if JSON |
| seedbox | Transfer size + file count | parse stdout |
| sort | "N items sorted" | parse stdout |
| rollback | "N operations reverted" | parse stdout |

**What needs backend work:** `parsed_kind="json"` + `parsed_payload` currently only populated for modules that output structured JSON (doctor, inspect with `--json`). Needs extension to more modules — **backend-needed**. In the meantime, parse stdout text patterns client-side.

---

### 2.6 Errors

**Validation error (before submission):** Inline red text under the field or form. Never a toast.

**API/network error:** Inline red card in the form area.

**Job failed (returncode != 0):** Result summary shows failure badge + first lines of stderr + link to full logs in "Debug →".

**No toast for long-running results.** Only toasts for quick fire-and-forget mutations (alias toggle, tracker enable, seedbox set-default).

---

### 2.7 Full Logs / Debug Link

In `InlineJobPanel`, a secondary "Debug →" button always links to `/jobs/:jobId`. That page has:
- Full unfiltered stdout/stderr
- Full metadata (all timestamps, argv, full request)
- Rerun from that exact config
- Copy CLI command

The Jobs page detail is the power user's debug surface. Normal users never need to go there.

---

## 3. Module Category Map

### Category A — Workflow Modules
**Pipeline**, **Batch**

Multi-step, long-running, path-required. Always async. Central to Ouro's purpose.

### Category B — Media Transformation Modules
**Renamer**, **CleanMKV**, **Sort**, **Extract**, **Encode**, **Screenshot**, **Rename-Parent**

Operate on files. Destructive (all have `destructive=True`). Dry-run is the safe default for most.

### Category C — Metadata / Presentation Modules
**Metadata**, **NFO**, **Prez**, **Inspect**, **Validate**

Read+enrich, write output files or display analysis. Some destructive (NFO writes files), some read-only (inspect, validate).

### Category D — Transfer / Publish Modules
**Upload**, **Seedbox** (push/pull)

Network operations against external systems. Always async. Results depend on tracker/seedbox availability.

### Category E — Maintenance / Admin Modules
**Watch** (daemon + folders), **Rollback**, **Aliases**, **Profiles**, **Doctor**, **Logs**

Configuration management and operational history. Not typically run as ad-hoc jobs.

### Category F — Debug / Dev Modules
**About**, **Setup**, **Init**, **Config explain/doctor**, **Examples**

One-shot utilities. Setup/init are first-run only. Config/examples are informational.

---

## 4. Category-Level Design Briefs

---

### Category A — Workflow (Pipeline, Batch)

**Ideal page layout:**
```
Header: title, description, active-profile chip
───────────────────────────────────
Configuration card:
  - Path input (full width)
  - Presets row (pipeline/prez profile selects)
  - Module step toggles (chip grid, not toggle row)
  - Announce select
  - Flags row (auto, dry-run, preview)
  [Run Pipeline button]  [Copy Command]
───────────────────────────────────
InlineJobPanel: (appears/replaces empty state on run)
  status timeline → sub-steps → live output → result summary
```

**Inline progress/result:**
- Sub-steps from `parseSubSteps(pipeline|batch, stdout, stderr)` — already works
- Timeline 3-step: Queued → Running → Done/Failed
- Result: summary of which steps completed, any warnings found in stdout

**Required API/job data (all exist):**
- `POST /api/v1/modules/jobs` → jobId
- `GET /api/v1/modules/jobs/:id` → status, live_stdout, result
- `DELETE /api/v1/modules/jobs/:id` → cancel
- `GET /api/v1/modules/resources` → presets, announces

**Missing backend fields:**
- Sub-step pattern for batch per-release progress (currently "Processing N of M: name" — already in parseSubSteps, works)
- No per-step OK/fail breakdown returned in structured form — stdout parsing only

**Current gaps:**
- Progress card shows before any job exists (shows empty 3-step timeline immediately on page load)
- Pipeline and Batch are two nearly identical pages — should be one page with a workflow mode switch (Pipeline / Batch)

---

### Category B — Media Transformation

**Ideal page layout for dedicated module pages:**
```
Header: module name, description, destructive badge if applicable
───────────────────────────────────
Form card:
  - Path input (or subcommand select for multi-subcommand modules)
  - CliCommandForm auto-generated fields
  - Preset chips row
  - Dry-run toggle (default ON for destructive modules)
  [Run]  [Copy Command]
───────────────────────────────────
InlineJobPanel (appears on run)
```

**Inline progress/result:**
- RunTimeline 3-step (generic — no sub-steps for these modules currently)
- Result summary: module-specific parsed count (files renamed, tracks removed)
- For dry-run: show a "preview diff" result card — what would change

**Required API/job data:**
- `POST /api/v1/modules/jobs` (async, all these can be long)
- `GET /api/v1/modules/jobs/:id` → status, live_stdout, result

**Missing backend fields:**
- `parsed_kind="json"` not emitted for renamer, cleanmkv, encode, extract — stdout only. Needs backend `--json` output mode for structured result data (backend-needed, P2)
- Sub-step patterns in `parseSubSteps` not defined for renamer, extract, encode, screenshot — would need extending

**Current gaps:**
- DedicatedModuleLauncher shows "View Job" button that navigates away — no inline tracking
- `dry_run: false` hardcoded in DedicatedModuleLauncher payload — ignores `supports_dry_run` flag
- `confirm_destructive: true` hardcoded unconditionally — no user confirmation for destructive modules

---

### Category C — Metadata / Presentation

**Inspect:**
- Primary use: read-only analysis of a release folder
- Ideal: path input → run → result card shows structured info (title, kind, size, episode completeness, track list)
- `inspect --json` outputs structured JSON — `parsed_payload` should be populated
- Already has `parseSubSteps` not configured (no regex for inspect)

**Validate:**
- Like inspect but checklist-based (ok/warn/err per check)
- `parsed_payload` should carry checks array if `--json` output exists
- renderStructuredPayload in modules.tsx already handles checks format

**Metadata:**
- Runs TMDB fetch/validation
- Output: provider status, match results
- No structured JSON output currently (stdout only)

**NFO/Prez:**
- Write files, show output path in result
- Dry-run: preview the generated content in a card (backend-needed: would need stdout to contain preview text, which it may)

**Page layout** (same as Category B):
- Form → InlineJobPanel
- For inspect/validate: result card shows structured check table, not raw stdout

**Current gap:** `parsed_kind` populated only for `--json` flagged modules. DedicatedModuleLauncher does not pass `--json` to inspect/validate, so result is raw stdout.

**Backend-needed:** `ouro inspect --json` structured output → backend parses → `parsed_payload` in job result.

---

### Category D — Transfer / Publish (Upload, Seedbox)

**Upload page:**

```
Header: Upload, active upload state badge [Enable/Disable]
────────────────────────────────────
Trackers card:
  Tracker list as rows: name, type, url, status badge
  [Select] per row — selects tracker into the run form
────────────────────────────────────
Upload Now card:
  - Release path input
  - Tracker select (pre-filled from row click above)
  - Title override, description (optional, collapsible)
  - Dry-run toggle (default ON)
  [Upload]  [Copy Command]
────────────────────────────────────
InlineJobPanel (appears on run)
────────────────────────────────────
History card: table with tracker, release, time, status columns
```

**Seedbox page (two tabs):**

**Transfer tab:**
```
Active seedbox: profile name chip, rclone remote, base path
────────────────────────────────────
Push form: source path, destination override (optional)
  OR
Pull form: remote path, local destination
────────────────────────────────────
InlineJobPanel (appears on run)
────────────────────────────────────
History section (recent transfers, compact)
```

**Manage tab:**
- Seedbox profile cards (name, remote, base, bandwidth, concurrency)
- Add/Set default/Remove actions inline per card
- Profile-to-settings-profile binding

**Missing backend field:** Upload history `entries` is `z.record(z.string(), z.unknown())` — untyped dict. Need structured schema (tracker, release_name, timestamp, status, returncode). **Backend-needed.**

---

### Category E — Maintenance / Admin

**Watch:**
- Currently: folder CRUD only. Watch daemon start/stop has no API.
- Ideal: folder list + daemon status card (running/stopped, PID, uptime) + start/stop button
- **Backend-needed:** `GET /api/v1/watch/service` (status + pid), `POST /api/v1/watch/service/start`, `POST /api/v1/watch/service/stop`

**Rollback:**
- Currently: module runner only (pass `run_id` as arg)
- The run ledger file exists at `{config_dir}/runs/ledger.ndjson` with fields: run_id, action, src, dst, module, timestamp
- **Backend-needed:** `GET /api/v1/runs` (reads ledger, returns entries grouped by run_id), `POST /api/v1/runs/:run_id/rollback` (wraps rollback module command)
- Ideal page: table of recent run operations (run_id, module, file count, timestamp) → expand row to show files → [Rollback] button → InlineJobPanel shows rollback progress

**Doctor, Logs:** Currently functional. Add summary card on dashboard (existing data).

**Aliases:** Already functional CRUD. No changes planned.

**Profiles:** Settings profiles CRUD is available via API. Promote active profile indicator to app header.

---

### Category F — Debug / Dev

These are run via the `/cli` terminal page (raw command builder). No dedicated pages needed.

Exception: **Setup** (`/module/setup`) keeps its dedicated page — it's the first-run onboarding path.

---

## 5. CLI → Web UI Parity Matrix

| Command | Current UI | Ideal UX Surface | Inline job/result | Backend gaps | Priority |
|---|---|---|---|---|---|
| `pipeline` | `/pipeline` dedicated page — Progress card empty on load, no inline output | `/pipeline` with unified InlineJobPanel replacing RunTimeline card | Exists: yes (polling), but only 3-step — extend sub-steps | parseSubSteps works, no structured payload | P0 |
| `batch` | `/batch` dedicated page — same issues as pipeline | Merge with pipeline as mode tabs or keep separate, add InlineJobPanel | Same as pipeline | Same as pipeline | P0 |
| `upload` | `/upload` — action tabs wrap CLI commands | Restructure: tracker list → upload form → InlineJobPanel → history table | job tracking exists, result summary raw | History schema untyped | P0 |
| `seedbox push/pull` | `/seedbox` — Transfer section uses module runner, no inline result | Tab: Transfer with InlineJobPanel | job tracking exists | History schema untyped | P0 |
| `seedbox add/use/remove` | `/seedbox` Manage section — CRUD works | Keep in Manage tab, add inline success feedback | N/A (not job-based) | None | P1 |
| `inspect` | `/module/inspect` via DedicatedModuleLauncher — no inline tracking | Same page + InlineJobPanel — result as structured card (title, kind, size) | After H2 patch | `inspect --json` not parsed by backend | P1 |
| `renamer` | `/module/renamer` — no inline tracking, `dry_run=false` hardcoded | Same + InlineJobPanel, dry_run default ON | After H2 patch | No structured payload for rename diff | P1 |
| `cleanmkv` | `/module/cleanmkv` — no inline tracking | Same + InlineJobPanel | After H2 patch (sub-step pattern exists) | None | P1 |
| `torrent` | `/module/torrent` — no inline tracking | Same + InlineJobPanel | After H2 patch (sub-step pattern exists) | None | P1 |
| `nfo` | `/module/nfo` — no inline tracking | Same + InlineJobPanel | After H2 patch | None | P1 |
| `prez` | `/module/prez` — no inline tracking | Same + InlineJobPanel | After H2 patch | None | P1 |
| `screenshot` | `/module/screenshot` — no inline tracking | Same + InlineJobPanel | After H2 patch | No sub-step pattern | P1 |
| `encode` | `/module/encode` — no inline tracking | Same + InlineJobPanel | After H2 patch | No sub-step pattern | P1 |
| `extract` | `/module/extract` — no inline tracking | Same + InlineJobPanel | After H2 patch | No sub-step pattern | P1 |
| `validate` | `/module/validate` — no inline tracking | Same + InlineJobPanel — result as check table | After H2 patch | `validate --json` not parsed | P1 |
| `metadata` | `/module/metadata` — no inline tracking | Same + InlineJobPanel | After H2 patch | No structured payload | P1 |
| `rename-parent` | `/module/rename-parent` — no inline tracking | Same + InlineJobPanel | After H2 patch | None | P2 |
| `sort` | `/module/sort` — no inline tracking | Same + InlineJobPanel | After H2 patch | None | P2 |
| `browse` | `/module/browse` — output only, raw stdout | Module runner for now; structured browser page is backend-needed | After H2 (raw stdout) | No browse API | P2 |
| `watch` (folders) | `/settings-setup` watch section — folder CRUD | Keep in Settings; surface folder list on Watch module page | N/A — not job-based | Watch daemon start/stop API needed | P2 |
| `watch` (daemon) | Not in UI | Watch module page: daemon status card + start/stop | Would need new API | `GET/POST /api/v1/watch/service` needed | P2 |
| `rollback` | Module runner only (manual run_id entry) | `/rollback` page: ledger table → rollback action → InlineJobPanel | After H2 (module runner) | `GET /api/v1/runs` ledger read API needed | P2 |
| `alias` | `/aliases` — full CRUD | Keep — works well | N/A | None | P2 |
| `profile` | Settings profiles section | Promote active profile to nav chip; keep section in Settings | N/A | None | P1 |
| `settings` | `/settings-setup` — full coverage | Keep | N/A | Language picker missing | P1 |
| `doctor` | `/doctor` page | Keep; add summary card to dashboard | N/A | None | P0 (dashboard) |
| `logs` | `/logs` page | Keep; add level segmented control | N/A | No SSE streaming | P1 |
| `config explain/doctor` | `/module/config` | Keep as module runner | After H2 | None | P2 |
| `setup` | `/module/setup` | Keep as dedicated first-run page | After H2 | None | P1 |
| `language` | Not exposed | Add to Settings → General section | N/A | PATCH allowlist check needed | P1 |
| `init` | Not in UI | CLI-only | N/A | N/A | P3 |
| `examples` | Not in UI | CLI-only | N/A | N/A | P3 |
| `about` | `/about` page | Keep | N/A | None | P3 |

---

## 6. Dashboard Design

The dashboard is the application's operational overview — it answers "what is happening right now and what happened recently."

---

### Active Operations Overview (top of page)

A live feed of any jobs currently `pending` or `running`.

```
┌─────────────────────────────────────────────────────────────┐
│ Active Operations                              [2 running]   │
│─────────────────────────────────────────────────────────────│
│ ● pipeline   Running   /Releases/Movie.mkv    2m 14s  [→]  │
│ ● batch      Pending   /Releases/             0s      [→]  │
└─────────────────────────────────────────────────────────────┘
```

- Source: `GET /api/v1/modules/jobs?limit=50` — filter `status=pending|running` client-side
- Polling: 3s
- Each row links to the originating page (pipeline → `/pipeline`) or to job detail
- When zero active: collapsed to a single line "No active operations"

---

### Status Cards (second row)

Four compact metric cards:

| Card | Metric | Source |
|---|---|---|
| System Health | ok/warn/err counts | `GET /api/v1/doctor` (cached, refetch on load) |
| Upload | Enabled/disabled + last upload time | `GET /api/v1/upload/state` + `GET /api/v1/upload/history?limit=1` |
| Seedbox | Active profile name + last transfer | `GET /api/v1/seedbox/list` + `GET /api/v1/seedbox/history?limit=1` |
| Jobs Today | Count of completed/failed today | `GET /api/v1/modules/jobs?limit=100` — client filter by date |

---

### Recent Results (main section)

Table of last 15 completed or failed jobs:

```
Module      Status      Duration   Time         Path / Args
pipeline    ✓ done      4m 03s     12 min ago   /Releases/Movie
cleanmkv    ✗ failed    0m 12s     1h ago       returncode 1
batch       ✓ done      18m 22s    3h ago       /Releases/
```

- Source: `GET /api/v1/modules/jobs?limit=50` — filter out pending/running, take last 15
- Click row → links to originating page or job detail (secondary)

---

### Warnings Banner (conditional, top of page if any warnings exist)

Show when:
- Doctor has `err` checks → "N diagnostic errors — view Diagnostics"
- Upload enabled but no trackers configured → "Upload active but no trackers configured"
- Vault unavailable (error in vault status) → "Vault offline — encrypted settings unavailable"
- Upload state returns error → "Upload service unavailable"

Sources: `GET /api/v1/doctor`, `GET /api/v1/upload/state`, `GET /api/v1/upload/trackers`, `GET /api/v1/security/vault`

**Do not** show warning banner for every minor config gap (missing TMDB token, etc.) — only actionable system-level issues.

---

### Quick Actions (sidebar or bottom strip)

Six icon + label buttons:
- **Run Pipeline** → `/pipeline`
- **Run Batch** → `/batch`
- **Upload** → `/upload`
- **Seedbox Push** → `/seedbox`
- **View Logs** → `/logs`
- **Diagnostics** → `/doctor`

---

## 7. Jobs Page Role

---

### What belongs on the Jobs page

- **Full job history** — all statuses, all modules, paginated
- **Advanced filtering** — by module, status, date range, search
- **Job detail access** — timestamps, full argv, returncode, full stdout/stderr, sub-steps
- **Rerun** — re-submit exact same request
- **Cancel** — cancel a pending or running job
- **Bulk clear** — delete all completed/failed jobs
- **CLI command copy** — copy the exact `ouro ...` command for debugging

The Jobs page is where you go when something went wrong and you want to understand why.

---

### What should move out of the Jobs page

Currently `/modules` (which shows "Configuration" as its title) contains:
- Pipeline builder form → move to `/pipeline`
- Batch builder form → move to `/batch`
- Preset shortcuts → move to `/cli` or keep in `/presets`
- Raw command form → move to `/cli`
- Recent jobs card → KEEP (job list stays)

After this split, the Jobs page contains only the job list and job detail link. It is not a workflow surface.

---

### How Jobs supports debugging without becoming the main UX

**Pattern:**
1. User runs pipeline on `/pipeline` → sees inline result
2. Pipeline fails → `InlineJobPanel` shows failure summary + stderr snippet
3. User clicks "Debug →" small link → lands on `/jobs/:id` with full detail
4. On job detail: sees full stdout, copies CLI command, runs it manually to debug
5. Fixes config issue → returns to `/pipeline`, reruns

The Jobs page is always accessible from:
- "Debug →" in any `InlineJobPanel`
- Nav → Jobs badge (with count)
- Dashboard recent results table (secondary click)

It is never the primary post-run destination.

---

## 8. Navigation / Page Architecture

```
[Logo]  Pipeline  Upload  Seedbox  Modules▾  [Jobs ●2]  [Theme]  [User▾]
```

**Primary nav (top bar, 4 main items):**
- Pipeline (covers Pipeline + Batch as tabs or separate)
- Upload
- Seedbox
- Modules▾ (dropdown)

**Modules dropdown:**
```
─── Workflow ─────────────────
  Pipeline
  Batch
─── Transform ────────────────
  Renamer, CleanMKV, Sort, Extract, Encode, Screenshot, Rename Parent
─── Metadata / Presentation ──
  Inspect, Validate, Metadata, NFO, Prez
─── Maintenance ──────────────
  Watch, Rollback, Aliases, Doctor, Logs
─── Dev ──────────────────────
  Setup, Config, Terminal
```

**Jobs badge:** always visible, count of pending+running, red dot when any running, links to `/jobs`

**User menu (top right):** profile chip (active profile name), Settings, Users (admin), Webhooks (admin), Sign Out

**Settings** moved from top nav item to user menu — it's configuration, not a workflow.

**Contextual sidebar:** keep for `/settings-setup`, `/presets`, `/jobs` (per existing pattern).

---

### Route structure (v1.0 target)

```
/                        Dashboard
/pipeline                Pipeline + Batch (tabs or separate)
/batch                   Batch (if kept separate)
/upload                  Upload
/seedbox                 Seedbox (Transfer + Manage tabs)
/jobs                    Jobs list (renamed from /modules)
/jobs/:jobId             Job detail (renamed from /modules/:jobId)
/module/:slug            All dedicated module pages
/studios                 All modules browser
/rollback                Rollback ledger (backend-needed for API)
/presets                 Presets & profiles
/aliases                 Aliases
/logs                    Logs
/doctor                  Diagnostics
/cli                     Terminal / raw command builder
/settings-setup          Settings
/users                   Users (admin)
/webhooks                Webhooks (admin)
/login                   Auth
/about                   About
```

---

## 9. Implementation Roadmap

---

### Batch H1 — Dashboard Active Operations (2 days)

**Goal:** Replace home link-grid with real operational dashboard.

1. Dashboard stat cards (jobs running, doctor summary, upload state, seedbox profile) — client-side aggregation of existing API calls
2. Active operations live feed (pending/running jobs from job list API, 3s poll)
3. Recent results table (last 15 completed/failed)
4. Warnings banner (doctor errors, vault status, upload state)
5. Quick actions strip

**APIs used (all exist):** `GET /api/v1/modules/jobs`, `GET /api/v1/doctor`, `GET /api/v1/upload/state`, `GET /api/v1/upload/history`, `GET /api/v1/seedbox/list`, `GET /api/v1/security/vault`, `GET /api/v1/upload/trackers`

**Files changed:** `home.tsx` (full rewrite), no new API needed.

---

### Batch H2 — `InlineJobPanel` Component (2 days)

**Goal:** Build the reusable inline execution panel. This is the foundation for H3 and H4.

**Component props:**
```typescript
InlineJobPanel({
  jobId: string | null,
  moduleName: string,
  onReset: () => void,
  // optional: structured result renderer
  resultRenderer?: (result: RunModuleResult) => ReactNode
})
```

**Component behavior:**
- Polls `GET /api/v1/modules/jobs/:id` at 1.5s while running
- Shows RunTimeline (Queued/Running/Done)
- Shows sub-steps from `parseSubSteps` (extend patterns for renamer, screenshot, extract, nfo, prez)
- Shows live_stdout last 30 lines, auto-scrolling, collapsible
- Shows result summary on completion (ok badge + module-specific parse function)
- Shows stderr snippet + "Debug →" link on failure
- Shows [Cancel] during pending/running
- Shows [Rerun] after terminal state
- Shows [Debug →] always (small, secondary)

**Files changed:** new `web-ui/src/components/modules/inline-job-panel.tsx`, extend `progress.ts` sub-step patterns.

---

### Batch H3 — Apply `InlineJobPanel` to All Module Pages (1–2 days)

**Goal:** DedicatedModuleLauncher stops navigating away. Every module page shows its own inline result.

**Changes to `DedicatedModuleLauncher`:**
1. Add `InlineJobPanel` below the form card, shown when `lastJob` is set
2. Remove "View Job" primary button (keep "Debug →" inside the panel)
3. Fix: `dry_run` default — respect `ModuleSpec.supports_dry_run` (fetch from `GET /api/v1/modules/catalog`)
4. Fix: show confirmation dialog when `destructive=true` and `dry_run=false`
5. Remove standalone result card (now inside InlineJobPanel)

**Module pages affected (all via DedicatedModuleLauncher):**
inspect, renamer, cleanmkv, torrent, nfo, prez, screenshot, encode, extract, sort, browse, metadata, validate, rename-parent, config, setup, watch, rollback (once API exists)

**Files changed:** `dedicated-module-launcher.tsx` (significant refactor), `inline-job-panel.tsx` (new, from H2).

---

### Batch H4 — Apply to Pipeline / Batch / Upload / Seedbox (2 days)

**Goal:** Workflow pages use `InlineJobPanel` instead of separate Progress cards.

**Pipeline page:**
1. Replace standalone Progress card with `InlineJobPanel` (shown only when job exists)
2. Inline result renders pipeline sub-steps summary (already parses from stdout)
3. Merge Pipeline + Batch as tabs on one `/pipeline` page (or keep as siblings — decide at implementation)
4. Remove empty RunTimeline (only show after Run is clicked)

**Batch page:**
1. Same as pipeline — use `InlineJobPanel`
2. Batch sub-step shows "Processing N of M: release_name" from existing pattern

**Upload page:**
1. Restructure: tracker cards → upload form → `InlineJobPanel`
2. History table: typed columns (tracker, release, time, status) — **partially backend-needed**

**Seedbox page:**
1. Transfer tab: push/pull form → `InlineJobPanel`
2. Manage tab: profile CRUD (keep existing, no changes)

**Files changed:** `pipeline.tsx`, `batch.tsx`, `upload.tsx`, `seedbox.tsx`

---

### Batch H5 — Jobs Page Cleanup and Rename (0.5 days)

**Goal:** Jobs page is clean, focused, accurate.

1. Rename page title "Configuration" → "Jobs" everywhere
2. Remove Pipeline/Batch builders from `/modules` → they belong on `/pipeline`, `/batch`, `/cli`
3. Remove preset buttons from `/modules` → keep in `/cli` and `/presets`
4. Keep: job list with filters, status filter, search, load more, job detail link
5. Update nav: `/modules` route stays, label in nav changes from "Jobs" confusion to "Jobs"
6. Add [Clear history] button for completed/failed bulk delete

**Files changed:** `modules.tsx` (remove builders), `app-shell.tsx` (nav label), `router.tsx` (optional rename)

---

### Batch H6 — Settings / Nav Polish (1 day)

**Goal:** Settings accessible, profile visible in nav, language exposed.

1. Move Settings from top nav link to user menu (unless user prefers nav item — keep if tested)
2. Active profile chip in user menu or nav right area
3. Add language picker to Settings → General section (`PATCH /api/v1/settings/patch`)
4. Confirm patch allowlist covers `language` key

**Files changed:** `app-shell.tsx`, `settings-setup.tsx`

---

### Batch I — Backend: Rollback Ledger API (1–2 days backend)

**Goal:** Surface rollback in web UI.

1. `GET /api/v1/runs` — read `ledger.ndjson`, return entries grouped by `run_id` (fields: run_id, module, file_count, timestamp, actions array)
2. Rollback module runner already works via `POST /api/v1/modules/jobs` with `module=rollback args_text=<run_id>` — no new endpoint needed for execution
3. Frontend: `/rollback` page — ledger table → select run → confirm → `InlineJobPanel` shows result

**Files changed (backend):** `web/app.py` (new GET /api/v1/runs), `web/modules.py` (ledger reader function)
**Files changed (frontend):** new `web-ui/src/routes/rollback.tsx`

---

### Batch J — Backend: Watch Service API (2 days backend)

**Goal:** Watch daemon visible and controllable from web UI.

1. `GET /api/v1/watch/service` — return status: running/stopped, pid, uptime, watched folders count
2. `POST /api/v1/watch/service/start` — spawn watch process
3. `POST /api/v1/watch/service/stop` — signal watch process
4. Frontend: Watch module page adds daemon status card + start/stop buttons at top; folders remain below

**Note:** Watch daemon is a long-running subprocess; starting via web API carries lifecycle management complexity. Mark as **medium-risk backend work**.

---

### Batch K — Backend: Structured Result Payloads (2–3 days backend)

**Goal:** Enable rich result summaries for key modules.

1. `ouro inspect --json` → backend parses JSON stdout → `parsed_kind="inspect"`, `parsed_payload={title, kind, size, episodes, completeness, tracks}`
2. `ouro validate --json` → same pattern → `parsed_kind="checks"` (already defined for doctor)
3. Extend `parseSubSteps` client-side for: renamer (parse rename count), nfo (parse NFO path), prez (parse output files)
4. Upload history schema: add typed fields to `list_upload_history` return value

---

### Batch L — Regression Tests (1 day)

1. Test `InlineJobPanel` renders correctly for all statuses (pending, running, completed, failed)
2. Test dry_run defaults correctly for destructive vs non-destructive modules
3. Test dashboard warning banner conditions
4. Test Jobs page renders without pipeline/batch builders
5. `npx tsc --noEmit` clean on all modified files

---

## 10. Visual Direction

**Direction B remains the recommendation.** No full redesign. The application-first UX is achieved by component behavior, not visual overhaul.

---

### What makes Direction B polished and application-like

**Execution state:** The transformation is in `InlineJobPanel` — status transitions feel native to the page instead of a redirect. Color: blue ring while running, green border on success, red on failure. The panel appears with a subtle slide-in (CSS transition, no library needed).

**Status feedback:**
- Running: spinner in the Run button label (`Running…`) + pulsing dot in the panel header
- Success: green checkmark badge + result summary line in muted text
- Failure: red badge + 2–3 lines of stderr + `Debug →` link

**Form ↔ result interaction:** After completion, the form stays visible and editable. The InlineJobPanel sits below the form card with a thin separator. Rerun resets the panel and re-enables the button. This feels like a real application, not a page reload.

**Result summaries replace raw stdout dumps.** Instead of a `<pre>` block for renamer result, show:
```
✓ 4 files renamed    renamer-20250601093012-a1b2c3d4    [Rollback]
```
The stdout `<pre>` lives inside a "Full output" collapsed details, accessible but not primary.

**Active profile chip (Direction B enhancement):**
- In nav right area: `[films]` chip showing active settings profile name
- Click → settings profiles section
- Keeps users aware of which configuration context they're operating in

**Jobs badge behavior:**
- Shows count when > 0, pulsing dot when any running
- Badge click → `/jobs` page
- This is the only global live indicator beyond the dashboard

**Typography / spacing:** No changes to current Tailwind classes. No color palette changes. The "application-like" feel comes from consistent state transitions and structured result cards, not new design tokens.

**Responsive:** Direction B's top nav becomes a `Menu` dropdown on mobile (already implemented). `InlineJobPanel` stacks vertically on small screens naturally.

---

**Summary of what this plan adds vs. the previous plan:**

| Before | After |
|---|---|
| "View Job" navigates user away from every module page | `InlineJobPanel` keeps progress/result on the page |
| DedicatedModuleLauncher ignores `dry_run` and `destructive` flags | Dry-run default ON for destructive modules; confirmation on override |
| Pipeline Progress card is always visible (even empty) | Panel appears only after Run is clicked |
| Jobs page doubles as command builder AND history | Jobs page is history/debug only |
| Dashboard is a link grid | Dashboard shows live operations, recent results, warnings |
| Result = raw stdout `<pre>` | Result = human summary + collapsed full output |
| Sub-steps only for pipeline/batch/cleanmkv/torrent/upload | Sub-steps extended to remaining modules |