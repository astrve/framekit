# Batch

Runs the full pipeline over multiple release folders in one command. Displays a live dashboard and produces a summary report.

---

## Usage

```bash
fk batch /path/to/releases/ [OPTIONS]
fk batch /path/to/releases/ --auto --pipeline-preset multi_fr
fk batch /path/to/releases/ --workers 2
fk batch /path/to/releases/ --dry-run
```

---

## Options

| Option | Description |
|--------|-------------|
| `--auto` | Fully automatic; no prompts |
| `--pipeline-preset NAME` | Apply preset to every release |
| `--workers N` | Parallel workers (default: 1) |
| `--no-dashboard` | Use plain progress output instead of live dashboard |
| `--dry-run` | Preview without processing |
| `--json` | Emit batch summary as JSON |

---

## Detection

Batch scans the root directory for release folders. A subfolder is treated as a release if it contains at least one `.mkv` file. Framekit auto-detects whether each release is a movie, TV series, or episode pack.

---

## Dashboard

The live dashboard shows:
- Current release being processed
- Per-release status: pending / processing / success / failed / skipped
- Step-level progress for the active release
- ETA based on completed releases

Disable with `--no-dashboard` for clean log output in CI/unattended runs.

---

## Summary report

After all releases are processed, Batch prints a table:

```
Release                       Status    Details
─────────────────────────────────────────────
Movie.2024.1080p.BluRay       ✓ Done    6 steps
Series.S01.1080p.WEB          ✓ Done    6 steps
Documentary.2023.720p.AMZN    ✗ Failed  metadata: no match found
```

---

## Error handling

Failed releases do not stop the batch. Framekit logs the error, marks the release as failed, and continues with the next one. Check `fk logs --last` for details.

---

## Queue persistence

The batch queue is saved between runs in `~/.local/share/framekit/batch_queue.json`. If the process is interrupted, re-run the same command to resume — already-completed releases are skipped.
