import { describe, expect, it } from "vitest";

import { parseSubSteps, runTimeline } from "@/lib/progress";
import type { ModuleJob } from "@/lib/api/schemas";

// ── parseSubSteps ─────────────────────────────────────────────────────────────

describe("parseSubSteps", () => {
  it("returns empty array for unknown module", () => {
    expect(parseSubSteps("unknown-module", "some output line", "")).toEqual([]);
  });

  it("returns empty array for empty stdout and stderr", () => {
    expect(parseSubSteps("pipeline", "", "")).toEqual([]);
  });

  // pipeline ──────────────────────────────────────────────────────────────────

  it("parses pipeline sub-step from [INFO] ... in progress line", () => {
    const stdout = "[INFO] Renamer in progress";
    const steps = parseSubSteps("pipeline", stdout, "");
    expect(steps).toHaveLength(1);
    expect(steps[0]!.label).toContain("Renamer");
    expect(steps[0]!.status).toBe("running");
  });

  it("parses multiple pipeline sub-steps", () => {
    const stdout = [
      "[INFO] Renamer in progress",
      "[INFO] Torrent in progress",
    ].join("\n");
    const steps = parseSubSteps("pipeline", stdout, "");
    expect(steps).toHaveLength(2);
  });

  // batch ─────────────────────────────────────────────────────────────────────

  it("parses batch per-release line (EN)", () => {
    const stdout = "Processing 2 of 5: Movie.2024.BluRay";
    const steps = parseSubSteps("batch", stdout, "");
    expect(steps).toHaveLength(1);
    expect(steps[0]!.label).toContain("Movie.2024.BluRay");
  });

  it("parses batch per-release line (FR)", () => {
    const stdout = "Traitement 1 sur 3 : Release.Name";
    const steps = parseSubSteps("batch", stdout, "");
    expect(steps).toHaveLength(1);
    expect(steps[0]!.label).toContain("Release.Name");
  });

  // renamer (added in Batch K) ────────────────────────────────────────────────

  it("parses renamer 'Rename operation completed' line", () => {
    const stdout = "[OK]   Rename operation completed.";
    const steps = parseSubSteps("renamer", stdout, "");
    expect(steps.length).toBeGreaterThan(0);
    expect(steps[0]!.label).toMatch(/[Rr]ename/);
  });

  it("parses renamer 'Planned changes' count — label is the digit", () => {
    const stdout = "[INFO] Planned changes: 4";
    const steps = parseSubSteps("renamer", stdout, "");
    expect(steps.length).toBeGreaterThan(0);
    expect(steps[0]!.label).toBe("4");
  });

  it("parses renamer 'Modified' count — label is the digit", () => {
    const stdout = "[INFO] Modified: 7";
    const steps = parseSubSteps("renamer", stdout, "");
    expect(steps.length).toBeGreaterThan(0);
    expect(steps[0]!.label).toBe("7");
  });

  it("parses renamer dry-run completed line", () => {
    const stdout = "[OK]   Dry-run completed.";
    const steps = parseSubSteps("renamer", stdout, "");
    expect(steps.length).toBeGreaterThan(0);
  });

  // nfo (added in Batch K) ────────────────────────────────────────────────────

  it("parses nfo written path — label contains filename", () => {
    const stdout = "[OK]   NFO written: /releases/Movie.nfo";
    const steps = parseSubSteps("nfo", stdout, "");
    expect(steps).toHaveLength(1);
    expect(steps[0]!.label).toContain("Movie.nfo");
  });

  it("parses multiple nfo written lines into multiple steps", () => {
    const stdout = [
      "[OK]   NFO written: /releases/A/Movie.nfo",
      "[OK]   NFO written: /releases/B/Show.nfo",
    ].join("\n");
    const steps = parseSubSteps("nfo", stdout, "");
    expect(steps).toHaveLength(2);
  });

  // prez (added in Batch K) ───────────────────────────────────────────────────

  it("parses prez output path — label contains filename", () => {
    const stdout = "[INFO] Output: /releases/prez.html";
    const steps = parseSubSteps("prez", stdout, "");
    expect(steps).toHaveLength(1);
    expect(steps[0]!.label).toContain("prez.html");
  });

  it("parses prez 'Presentation generated' line", () => {
    const stdout = "[OK]   Presentation generated.";
    const steps = parseSubSteps("prez", stdout, "");
    expect(steps.length).toBeGreaterThan(0);
  });

  it("parses prez 'Presentation dry-run completed' line", () => {
    const stdout = "[OK]   Presentation dry-run completed.";
    const steps = parseSubSteps("prez", stdout, "");
    expect(steps.length).toBeGreaterThan(0);
  });

  // other existing patterns ───────────────────────────────────────────────────

  it("parses cleanmkv processing line", () => {
    const steps = parseSubSteps("cleanmkv", "Processing MKV files in folder", "");
    expect(steps.length).toBeGreaterThan(0);
  });

  it("parses screenshot extracting line", () => {
    const steps = parseSubSteps("screenshot", "Extracting 6 screenshots per video", "");
    expect(steps.length).toBeGreaterThan(0);
  });

  it("matches from stderr when stdout is empty", () => {
    const steps = parseSubSteps("extract", "", "Processing 2 file(s)...");
    expect(steps.length).toBeGreaterThan(0);
  });

  // safety ────────────────────────────────────────────────────────────────────

  it("limits returned steps to at most 10", () => {
    const lines = Array.from(
      { length: 20 },
      (_, i) => `Processing ${i + 1} of 20: Release${i}`,
    );
    const steps = parseSubSteps("batch", lines.join("\n"), "");
    expect(steps.length).toBeLessThanOrEqual(10);
  });

  it("truncates labels at 120 chars", () => {
    const long = "A".repeat(200);
    const stdout = `[OK]   NFO written: ${long}`;
    const steps = parseSubSteps("nfo", stdout, "");
    if (steps.length > 0) {
      expect(steps[0]!.label.length).toBeLessThanOrEqual(120);
    }
  });
});

// ── runTimeline ───────────────────────────────────────────────────────────────

describe("runTimeline", () => {
  function job(status: string): ModuleJob {
    return {
      id: "j1",
      status: status as ModuleJob["status"],
      created_at: new Date().toISOString(),
      started_at: null,
      finished_at: null,
      request: {},
      priority: 0,
    };
  }

  it("null input: queued active, others inactive and not done", () => {
    const items = runTimeline(null);
    expect(items[0].active).toBe(true);
    expect(items[0].done).toBe(false);
    expect(items[1].active).toBe(false);
    expect(items[2].active).toBe(false);
  });

  it("pending: queued active, not yet done", () => {
    const items = runTimeline(job("pending"));
    expect(items[0].active).toBe(true);
    expect(items[0].done).toBe(false);
    expect(items[1].active).toBe(false);
  });

  it("running: queued done, running active, result not done", () => {
    const items = runTimeline(job("running"));
    expect(items[0].done).toBe(true);
    expect(items[1].active).toBe(true);
    expect(items[1].done).toBe(false);
    expect(items[2].done).toBe(false);
  });

  it("completed: all done, last label is 'Completed'", () => {
    const items = runTimeline(job("completed"));
    expect(items[0].done).toBe(true);
    expect(items[1].done).toBe(true);
    expect(items[2].done).toBe(true);
    expect(items[2].failed).toBe(false);
    expect(items[2].label).toBe("Completed");
  });

  it("failed: running and result nodes marked failed, last label is 'Failed'", () => {
    const items = runTimeline(job("failed"));
    expect(items[1].failed).toBe(true);
    expect(items[2].failed).toBe(true);
    expect(items[2].label).toBe("Failed");
  });

  it("cancelled: last label is 'Cancelled', result node failed", () => {
    const items = runTimeline(job("cancelled"));
    expect(items[2].label).toBe("Cancelled");
    expect(items[2].failed).toBe(true);
  });

  it("always returns exactly 3 items for any status", () => {
    for (const status of ["pending", "running", "completed", "failed", "cancelled"]) {
      expect(runTimeline(job(status))).toHaveLength(3);
    }
    expect(runTimeline(null)).toHaveLength(3);
  });
});
