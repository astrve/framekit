# Interactive Pipeline Plan
_Written 2026-05-31. Supersedes SWIRRL_V1.md for the interactive pipeline/batch feature._

---

## Goal

Transform `/pipeline` (and later `/batch`) into a guided, real-data wizard where:

1. A **header** shows release identity + progress the whole time.
2. Each **step** shows actual data from _this_ release (not generic info).
3. Each step exposes **all relevant CLI options** (full parity with `swirrl pipeline`).
4. Each step **executes immediately** when the user confirms ("apply as you go").
5. No page navigation — single scrolling surface with step cards.

---

## Current state audit

### What works in pipeline.tsx today

- Step wizard: path → modules → renamer → cleanmkv → nfo → prez → torrent → execute
- Path step: scans folder via `getPipelineInspect` → returns renamer preview + track data
- Renamer step: term picker (add/remove), rename preview table with real filenames
- CleanMKV step: displays all audio/subtitle tracks per MKV file
- Prez step: preset selector using `res.prez_presets`
- Torrent step: announce URL selector using `res.announces`
- Resources endpoint already returns: `cleanmkv_presets`, `renamer_profiles`, `nfo_templates`, `prez_templates.bbcode`, `prez_templates.html`

### What is missing

| Step | Missing vs CLI |
|---|---|
| **Header** | No release dashboard at all |
| **Renamer** | `--lang`, `--force-lang`, `--profile`, `--insert-after` not exposed |
| **CleanMKV** | `res.cleanmkv_presets` not wired; no "what will be removed" preview |
| **Metadata** | Entire step absent — no TMDB check, no locale, no title confirm |
| **NFO** | `res.nfo_templates` not wired; `--mode` (global/per_file/both); `--with-metadata` toggle |
| **Prez** | Format (bbcode/html/both); `--html-template`; `--bbcode-template`; `--mediainfo-mode` |
| **Torrent** | `--private/--public`; `--piece-length` |
| **All steps** | Per-step execution — today all config is collected then one pipeline job fires at the end |

---

## Architecture

### Per-step execution model

Each step's **Apply** button calls `createModuleJob({ module: "<step>", args_text: "..." })` and
shows `InlineJobPanel` inline inside the step card. The next step unlocks when `job.status === "completed"`.
A "Continue without applying" link remains for skipping a step.

This replaces the single "Run Pipeline" job at the execute step. The execute step becomes a
summary + "Run remaining" fallback for unmodified steps.

### Args generation per step

| Step | Key args |
|---|---|
| Renamer | `"<path>" --apply [--profile X] [--lang X] [--force-lang] [--remove-term T]... [--insert-after A B]...` |
| CleanMKV | `"<path>" --apply [--preset X]` |
| Metadata | `"<path>" [--auto-accept]` |
| NFO | `"<path>" --write [--template X] [--locale X] [--mode X] [--with-metadata\|--no-metadata]` |
| Prez | `"<path>" [--preset X] [--format X] [--html-template X] [--bbcode-template X] [--mediainfo-mode X]` |
| Torrent | `"<path>" [--announce X] [--private\|--public] [--piece-length X]` |

### Config state additions (extend existing `Config` interface)

```typescript
// Renamer
lang: string;
forceLang: boolean;
renamerProfile: string;
insertAfterPairs: Array<{ after: string; insert: string }>;

// CleanMKV
cleanmkvPreset: string;

// Metadata (new step)
metadataAutoAccept: boolean;

// NFO
nfoTemplate: string;
nfoMode: "global" | "per_file" | "both";
nfoWithMetadata: boolean;

// Prez
prezFormat: "both" | "bbcode" | "html";
prezHtmlTemplate: string;
prezBbcodeTemplate: string;
prezMediainfoMode: "none" | "spoiler" | "only";

// Torrent
torrentPrivate: boolean;
torrentPieceLength: string;  // "auto" | "512K" | "1M" | "2M"
```

---

## Phases

Each phase is self-contained. Start every session by reading the files listed.

---

### P1 — Dashboard header
**Files:** `web-ui/src/routes/pipeline.tsx`

Add a prominent card **above the step list** showing:
- Release folder name (large text)
- Detected kind badge: movie / series / unknown (from `inspection` after scan)
- File count + MKV count
- Step progress row: numbered dots with active/done/locked state, matching the step cards below

**Verify:** Header renders after scan; folder name + kind appear; dots update as steps complete.

---

### P2 — Renamer step: full option parity
**Files:** `web-ui/src/routes/pipeline.tsx`
**APIs already available:** `res.renamer_profiles` from `getModulesResources`

Add inside the Renamer step card:
- **Profile selector**: `TemplateList` using `res.renamer_profiles` → `cfg.renamerProfile`; placeholder = "Default"
- **Lang override**: small text input → `cfg.lang`; label "Language tag (e.g. FRENCH)"
- **Force-lang toggle**: replaces existing lang even if one is already in the filename → `cfg.forceLang`
- **Insert-after pairs**: repeatable row UI: `After:` text + `Insert:` text + remove button → `cfg.insertAfterPairs`

Build a `buildRenamerArgs(cfg, path)` helper that produces the full args string.

**Verify:** `--profile`, `--lang`, `--force-lang`, `--insert-after` appear in args. Reinspect updates preview.

---

### P3 — CleanMKV step: preset selector
**Files:** `web-ui/src/routes/pipeline.tsx`
**APIs already available:** `res.cleanmkv_presets` from `getModulesResources`

Add inside the CleanMKV step card:
- **Preset selector**: `TemplateList` using `res.cleanmkv_presets` → `cfg.cleanmkvPreset`; placeholder = "Default (from settings)"

The track list display (audio + subs per file) already exists — keep it.

**Optional / separate session:** Add `POST /api/v1/cleanmkv/preview` endpoint (body: `{ path, preset }`)
that runs `CleanMkvService` in dry-run mode and returns `{ files: [{ filename, keep_ids, remove_ids }] }`.
Frontend would label each track row "keep" or "remove" based on preset prediction.

**Verify:** Preset selector renders with real preset names. Args include `--preset X` when selected.

---

### P4 — Metadata step (new)
**Files:** `web-ui/src/routes/pipeline.tsx`

Add `"metadata"` to `StepId` and `activeSteps()`. Insert between CleanMKV and NFO when `modules.includes("metadata")`.

Step card content:
- Detected title / year / kind from `inspection` (read-only info row)
- **Auto-accept toggle**: skip interactive confirmation → `cfg.metadataAutoAccept` (default: true in wizard context)
- Info note: "Metadata fetches from TMDB. Token must be configured in Settings."

_Note: `swirrl metadata` has no `--tmdb-id` CLI option yet. Manual TMDB ID override requires a future CLI addition._

**Verify:** Step appears when metadata selected; auto-accept toggle wires to args.

---

### P5 — NFO step: template + mode + metadata flag
**Files:** `web-ui/src/routes/pipeline.tsx`
**APIs already available:** `res.nfo_templates` from `getModulesResources`

Add inside the NFO step card:
- **Template selector**: `TemplateList` using `res.nfo_templates` → `cfg.nfoTemplate`
- **Mode picker**: global / per_file / both using `OptionPills`
- **With-metadata toggle**: fetch fresh TMDB data during NFO generation → `cfg.nfoWithMetadata`

Existing locale + detail level stay.

**Verify:** `--template`, `--mode`, `--with-metadata` appear in args.

---

### P6 — Prez step: format + templates + mediainfo
**Files:** `web-ui/src/routes/pipeline.tsx`
**APIs already available:** `res.prez_templates.bbcode`, `res.prez_templates.html`

Add inside the Prez step card:
- **Format selector**: bbcode / html / both using `OptionPills` → `cfg.prezFormat`
- **HTML template selector** (shown when format is "html" or "both"): `TemplateList` using `res.prez_templates.html`
- **BBCode template selector** (shown when format is "bbcode" or "both"): `TemplateList` using `res.prez_templates.bbcode`
- **Mediainfo mode**: none / spoiler / only using `OptionPills`

Existing preset selector stays.

**Verify:** Template selectors show/hide based on format choice. Args include `--format`, `--html-template`, `--bbcode-template`, `--mediainfo-mode`.

---

### P7 — Torrent step: private flag + piece length
**Files:** `web-ui/src/routes/pipeline.tsx`

Add inside the Torrent step card:
- **Private toggle**: `Toggle` → `cfg.torrentPrivate` (default: true — most trackers require it)
- **Piece-length selector**: auto / 512K / 1M / 2M using `OptionPills` → `cfg.torrentPieceLength`

**Verify:** `--private`/`--public` and `--piece-length` appear in args.

---

### P8 — Per-step execution (apply-as-you-go)
**Files:** `web-ui/src/routes/pipeline.tsx`

This is the core change. Each step card body gets an **Apply step** button (primary) and a **Skip** link:

```
[  Apply step  ]   Skip →
```

- **Apply step**: calls `createModuleJob({ module: <step>, args_text: buildStepArgs(cfg) })` for that module
- The job ID is stored in `stepJobs[stepId]`
- `InlineJobPanel` renders below the controls for that step once `stepJobs[stepId]` is set
- When `job.status === "completed"` → `advance(stepId)` is called automatically
- When `job.status === "failed"` → stay on step; error visible in InlineJobPanel; user can fix config and retry
- **Skip**: calls `advance(stepId)` without creating a job (existing behavior)

**State additions:**
```typescript
const [stepJobs, setStepJobs] = useState<Record<string, string>>({});
```

**Execute step changes:**
- Remove "Run Pipeline" single-job button
- If all steps applied individually → show "All steps applied" summary
- If some steps were skipped → show "Run remaining steps" button that fires a pipeline job for skipped modules only
- Keep "Copy Command" and "Preview Plan" buttons for reference

**Verify:**
1. Apply renamer → InlineJobPanel appears → job completes → CleanMKV step unlocks
2. Skip cleanmkv → jumps to next step immediately
3. Job failure keeps user on current step; retry works

---

### P9 — Batch page parity
**Files:** `web-ui/src/routes/batch.tsx`
**Defer** until P1–P8 are stable.

Apply the same structure to batch: same steps, same config fields, same per-step execution model.
Difference: path is a parent folder containing multiple releases; each module runs on all releases.

---

## Verification checklist per session

- TypeScript changed: `npx tsc --noEmit`
- Python changed (backend): `python -m pytest tests/ -x -q`
- New API route: verify route / Pydantic model / Zod schema / TS type / endpoint caller in same batch
- UI behavior: describe the tested user path (apply step → job completes → next step unlocks)

---

## Open questions

1. `--tmdb-id` CLI option: does not exist yet. Metadata step cannot override TMDB ID until CLI adds it.
2. CleanMKV "what preset removes" preview: optional endpoint for P3, can be a follow-up.
3. Batch parity (P9): deferred.
4. The `interactive` toggle (runtime checkpoint Approve/Skip/Back/Abort) added in a prior session is a separate mechanism that controls the pipeline subprocess. Consider removing it from the Execute step once P8 is done — it conflicts with the wizard's per-step execution model and creates confusion.
