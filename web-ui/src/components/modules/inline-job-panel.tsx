import { Link } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, OctagonX, RotateCcw, Square } from "lucide-react";
import { useMemo } from "react";

import { RunTimeline } from "@/components/modules/run-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cancelModuleJob, getModuleJob, rerunModuleJob } from "@/lib/api/endpoints";
import type { ModuleJob } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";
import { parseSubSteps, runTimeline } from "@/lib/progress";

// ── helpers ──────────────────────────────────────────────────────────────────

function formatDuration(
  startedAt: string | null | undefined,
  finishedAt: string | null | undefined,
): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) return "—";
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  if (Number.isNaN(end) || end < start) return "—";
  const totalSeconds = Math.floor((end - start) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes === 0 ? `${seconds}s` : `${minutes}m ${seconds}s`;
}

function lastLines(text: string, n: number): string {
  return text
    .split("\n")
    .filter((l) => l.trim().length > 0)
    .slice(-n)
    .join("\n");
}

function statusBadgeVariant(
  status: string | undefined,
): "success" | "danger" | "secondary" {
  if (status === "completed") return "success";
  if (status === "failed" || status === "cancelled") return "danger";
  return "secondary";
}

// ── types ────────────────────────────────────────────────────────────────────

export interface InlineJobPanelProps {
  /**
   * ID of the job to track.
   * Null means no job has been started yet — the panel renders nothing.
   */
  jobId: string | null;
  /**
   * Module name forwarded to parseSubSteps for progress extraction from stdout.
   * Must match the module name used in the job request (e.g. "pipeline", "renamer").
   */
  moduleName: string;
  /**
   * Called with the newly created job when the user triggers a rerun.
   * The parent should update its jobId state to the new job's ID.
   */
  onRerun?: (newJob: ModuleJob) => void;
  className?: string;
}

// ── component ────────────────────────────────────────────────────────────────

/**
 * InlineJobPanel — reusable inline execution status component.
 *
 * Polls GET /api/v1/modules/jobs/:id while the job is pending or running,
 * then stops. Shows status, duration, a 3-step RunTimeline, sub-steps parsed
 * from live stdout, a live output tail, and stderr/error on failure.
 *
 * Cancel and Rerun are inline actions.
 * The "Debug →" link navigates to the full job detail page (/modules/:jobId).
 *
 * Renders nothing when jobId is null (no job started yet).
 *
 * Example usage:
 *   const [jobId, setJobId] = useState<string | null>(null);
 *   // after createModuleJob resolves: setJobId(job.id);
 *   <InlineJobPanel
 *     jobId={jobId}
 *     moduleName="pipeline"
 *     onRerun={(newJob) => setJobId(newJob.id)}
 *   />
 */
export function InlineJobPanel({
  jobId,
  moduleName,
  onRerun,
  className,
}: InlineJobPanelProps) {
  // ── polling query ────────────────────────────────────────────────────────

  const jobQuery = useQuery({
    queryKey: ["inline-job", jobId],
    queryFn: () => getModuleJob(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 1500 : false;
    },
  });

  const cancelMutation = useMutation({
    mutationFn: cancelModuleJob,
    onSuccess: () => {
      void jobQuery.refetch();
    },
  });

  const rerunMutation = useMutation({
    mutationFn: rerunModuleJob,
    onSuccess: (newJob) => {
      onRerun?.(newJob);
    },
  });

  // ── derived state ────────────────────────────────────────────────────────

  const job = jobQuery.data;
  const isRunning = job?.status === "pending" || job?.status === "running";
  const isTerminal =
    job?.status === "completed" ||
    job?.status === "failed" ||
    job?.status === "cancelled";

  // While pending/running: show live_stdout tail.
  // After terminal: show the final captured result.stdout tail.
  const outputText = useMemo(() => {
    if (!job) return "";
    const raw = isTerminal
      ? (job.result?.stdout ?? "")
      : (job.live_stdout ?? "");
    return lastLines(raw, 20);
  }, [job, isTerminal]);

  // Same logic for stderr.
  const stderrText = useMemo(() => {
    if (!job) return "";
    return isTerminal
      ? (job.result?.stderr ?? "")
      : (job.live_stderr ?? "");
  }, [job, isTerminal]);

  // Sub-steps parsed from combined stdout+stderr via module-specific regex patterns.
  // Returns [] when no patterns match — no sub-steps section is rendered.
  const subSteps = useMemo(() => {
    if (!job) return [];
    const stdout = job.live_stdout ?? job.result?.stdout ?? "";
    const stderr = job.live_stderr ?? job.result?.stderr ?? "";
    return parseSubSteps(moduleName, stdout, stderr);
  }, [job, moduleName]);

  const timelineItems = runTimeline(job);

  // ── early return ─────────────────────────────────────────────────────────

  if (jobId === null) return null;

  // ── border color driven by status ────────────────────────────────────────

  const borderClass =
    job?.status === "failed" || job?.status === "cancelled"
      ? "border-destructive/40"
      : job?.status === "completed"
        ? "border-emerald-500/40"
        : "border-border";

  // ── render ───────────────────────────────────────────────────────────────

  return (
    <div
      className={cn(
        "rounded-2xl border bg-card overflow-hidden",
        borderClass,
        className,
      )}
    >
      {/* ── Status bar ──────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2.5 px-4 py-3 border-b border-border/60">

        {/* Animated status icon */}
        {(!job || job.status === "pending") && (
          <LoaderCircle className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />
        )}
        {job?.status === "running" && (
          <LoaderCircle className="h-4 w-4 animate-spin text-blue-500 shrink-0" />
        )}
        {job?.status === "completed" && (
          <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
        )}
        {(job?.status === "failed" || job?.status === "cancelled") && (
          <OctagonX className="h-4 w-4 text-destructive shrink-0" />
        )}

        {/* Status badge */}
        <Badge variant={statusBadgeVariant(job?.status)}>
          {job?.status ?? "pending"}
        </Badge>

        {/* Elapsed / total duration */}
        <span className="text-xs text-muted-foreground">
          {formatDuration(job?.started_at, job?.finished_at)}
        </span>

        {/* Non-zero exit code — visible only after terminal */}
        {isTerminal && job?.result && job.result.returncode !== 0 && (
          <span className="text-xs text-destructive font-mono">
            exit {job.result.returncode}
          </span>
        )}

        {/* Action buttons + debug link — pushed to the right */}
        <div className="ml-auto flex items-center gap-2 shrink-0">
          {isRunning && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                cancelMutation.mutate(jobId);
              }}
              disabled={cancelMutation.isPending}
            >
              <Square className="h-3.5 w-3.5" />
              Cancel
            </Button>
          )}
          {isTerminal && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                rerunMutation.mutate(jobId);
              }}
              disabled={rerunMutation.isPending}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Rerun
            </Button>
          )}
          {/* Always visible — secondary debug path */}
          <Link
            to="/modules/$jobId"
            params={{ jobId }}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Debug →
          </Link>
        </div>
      </div>

      {/* ── 3-step RunTimeline (Queued → Running → Done/Failed) ──────────── */}
      <div className="px-4 pt-4 pb-3">
        <RunTimeline items={timelineItems} />
      </div>

      {/* ── Sub-steps — only shown when parseSubSteps finds matches ─────── */}
      {subSteps.length > 0 && (
        <div className="px-4 pb-3 space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Steps
          </p>
          {subSteps.map((step, index) => (
            <div
              key={`${step.label}-${index}`}
              className="flex items-center gap-2"
            >
              <span
                className={cn(
                  "text-[11px] font-bold w-3 text-center shrink-0 leading-none",
                  step.status === "done"
                    ? "text-emerald-500"
                    : step.status === "failed"
                      ? "text-destructive"
                      : "text-blue-500",
                )}
              >
                {step.status === "done" ? "✓" : step.status === "failed" ? "✗" : "●"}
              </span>
              <span className="text-sm text-foreground/80 truncate">{step.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Live stdout tail / final output ─────────────────────────────── */}
      {outputText && (
        <div className="px-4 pb-4 space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {isRunning ? "Live output" : "Output"}
          </p>
          <pre className="max-h-48 overflow-auto rounded-md border border-border bg-muted px-3 py-2 text-[11px] leading-relaxed font-mono">
            {outputText}
          </pre>
        </div>
      )}

      {/* ── Stderr / job-level error ─────────────────────────────────────── */}
      {(stderrText || job?.error) && (
        <div className="px-4 pb-4 space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-destructive/70">
            {!stderrText && job?.error ? "Error" : "Stderr"}
          </p>
          <pre className="max-h-36 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-[11px] text-destructive leading-relaxed font-mono">
            {lastLines(stderrText || job?.error || "", 15)}
          </pre>
        </div>
      )}

      {/* ── Query/network error (no job data available) ──────────────────── */}
      {jobQuery.isError && !job && (
        <div className="px-4 pb-4">
          <p className="text-sm text-destructive">
            Failed to load job status.
          </p>
        </div>
      )}
    </div>
  );
}
