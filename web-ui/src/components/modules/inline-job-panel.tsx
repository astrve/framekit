import { Link } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, MessageSquare, OctagonX, RotateCcw, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { RunTimeline } from "@/components/modules/run-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cancelModuleJob, getJobCheckpoint, getModuleJob, respondJobCheckpoint, rerunModuleJob } from "@/lib/api/endpoints";
import type { JobCheckpoint, ModuleJob } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";
import { parseSubSteps, runTimeline } from "@/lib/progress";

// ── payload helpers ───────────────────────────────────────────────────────────

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function formatBytes(bytes: unknown): string {
  const n = Number(bytes);
  if (!n || Number.isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatMs(ms: unknown): string {
  const n = Number(ms);
  if (!n || Number.isNaN(n)) return "—";
  const totalSeconds = Math.floor(n / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function dash(v: unknown): string {
  const s = String(v ?? "");
  return s && s !== "null" && s !== "undefined" ? s : "—";
}

// ── structured result sub-components ─────────────────────────────────────────

function InspectResult({ payload }: { payload: Record<string, unknown> }) {
  const rows: [string, string][] = [
    ["Title", dash(payload.release_title)],
    ["Series", dash(payload.series_title)],
    ["Year", dash(payload.year)],
    ["Media kind", dash(payload.media_kind)],
    ["Episodes", String(payload.episode_count ?? "—")],
    ["Completeness", dash(payload.completeness_label)],
    [
      "Missing",
      Array.isArray(payload.missing_codes) && payload.missing_codes.length > 0
        ? (payload.missing_codes as string[]).join(", ")
        : "—",
    ],
    ["Size", formatBytes(payload.size_bytes)],
    ["Duration", formatMs(payload.duration_ms)],
    ["Source", dash(payload.source)],
    ["Resolution", dash(payload.resolution)],
    ["Video", dash(payload.video_tag)],
    ["Audio", dash(payload.audio_tag)],
    ["Language", dash(payload.language_tag)],
  ];
  return (
    <div className="rounded-md border border-border overflow-hidden text-xs">
      <p className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/60 border-b border-border/60">
        Release inspection
      </p>
      <div className="divide-y divide-border/40">
        {rows.map(([label, value]) => (
          <div key={label} className="grid grid-cols-[130px_1fr] px-3 py-1.5">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono break-all">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

type ValidateIssue = { severity: string; category: string; message: string; suggestion: string };

function ValidateResult({ payload }: { payload: Record<string, unknown> }) {
  const passed = Number(payload.checks_passed ?? 0);
  const warned = Number(payload.checks_warned ?? 0);
  const failed = Number(payload.checks_failed ?? 0);
  const issues = (Array.isArray(payload.issues) ? payload.issues : []) as ValidateIssue[];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3 text-xs font-medium">
        <span className="text-emerald-600 dark:text-emerald-400">✓ {passed} passed</span>
        {warned > 0 && (
          <span className="text-amber-600 dark:text-amber-400">
            ⚠ {warned} warning{warned !== 1 ? "s" : ""}
          </span>
        )}
        {failed > 0 && (
          <span className="text-destructive">
            ✗ {failed} error{failed !== 1 ? "s" : ""}
          </span>
        )}
      </div>
      {issues.length > 0 && (
        <div className="space-y-1.5">
          {issues.map((issue, i) => (
            <div
              key={i}
              className={`rounded-md border px-3 py-2 text-xs ${
                issue.severity === "error"
                  ? "border-destructive/40 bg-destructive/5 text-destructive"
                  : "border-amber-500/40 bg-amber-500/5 text-amber-700 dark:text-amber-400"
              }`}
            >
              <span className="font-semibold capitalize">{issue.category}</span>
              {" — "}
              {issue.message}
              {issue.suggestion && (
                <span className="block mt-0.5 opacity-70">{issue.suggestion}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
  /**
   * Called once when the job transitions to "completed".
   * Useful for auto-advancing a wizard step after a module finishes.
   */
  onComplete?: (job: ModuleJob) => void;
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
 * The "Debug →" link navigates to the full job detail page (/jobs/$jobId).
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
  onComplete,
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

  const [checkpointPending, setCheckpointPending] = useState(false);

  const completedFiredRef = useRef(false);
  useEffect(() => { completedFiredRef.current = false; }, [jobId]);
  useEffect(() => {
    if (jobQuery.data?.status === "completed" && !completedFiredRef.current) {
      completedFiredRef.current = true;
      onComplete?.(jobQuery.data);
    }
  }, [jobQuery.data, onComplete]);

  const checkpointQuery = useQuery({
    queryKey: ["job-checkpoint", jobId],
    queryFn: () => getJobCheckpoint(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const jobStatus = jobQuery.data?.status;
      if (jobStatus !== "running") return false;
      const cp = query.state.data as JobCheckpoint | undefined;
      return cp?.pending ? 800 : 1200;
    },
    staleTime: 0,
  });

  const checkpoint = checkpointQuery.data?.pending ? checkpointQuery.data : null;

  const respondMutation = useMutation({
    mutationFn: ({ idx }: { idx: number }) => respondJobCheckpoint(jobId as string, idx),
    onSuccess: () => {
      setCheckpointPending(false);
      void checkpointQuery.refetch();
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
          <LoaderCircle className="h-4 w-4 animate-spin text-primary shrink-0" />
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
        {job ? (
          <span className="text-xs text-muted-foreground font-mono">
            {job.attempts}/{job.max_attempts}
          </span>
        ) : null}
        {job?.last_failure_kind ? (
          <span className="text-xs text-amber-600 dark:text-amber-400 font-mono">
            {job.last_failure_kind}
          </span>
        ) : null}
        {job?.next_retry_at ? (
          <span className="text-xs text-primary">
            retry {new Date(job.next_retry_at).toLocaleTimeString()}
          </span>
        ) : null}

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
            to="/jobs/$jobId"
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

      {/* ── Checkpoint — step_confirm: Approve/Skip/Back/Abort per pipeline step ─ */}
      {checkpoint?.type === "step_confirm" && (
        <div className="mx-4 mb-3 rounded-xl border border-primary/40 bg-primary/8 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground">{checkpoint.title ?? `Step: ${checkpoint.step}`}</p>
              {checkpoint.summary && checkpoint.summary !== checkpoint.title && (
                <p className="text-xs text-muted-foreground mt-0.5">{checkpoint.summary}</p>
              )}
            </div>
            {checkpoint.step_index && checkpoint.step_total ? (
              <Badge variant="secondary" className="ml-auto text-[10px] shrink-0">
                Step {checkpoint.step_index}/{checkpoint.step_total}
              </Badge>
            ) : (
              <Badge variant="secondary" className="ml-auto text-[10px] shrink-0">Waiting</Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {(checkpoint.options ?? [{ index: 0, label: "Approve", hint: "" }]).map((opt) => {
              const lower = opt.label.toLowerCase();
              const isApprove = lower === "approve";
              const isAbort = lower === "abort";
              return (
                <button
                  key={opt.index}
                  type="button"
                  title={opt.hint || undefined}
                  disabled={respondMutation.isPending || checkpointPending}
                  onClick={() => { setCheckpointPending(true); respondMutation.mutate({ idx: opt.index }); }}
                  className={cn(
                    "rounded-md border px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50",
                    isApprove && "flex-1 border-primary/50 bg-primary/10 text-foreground hover:bg-primary/20",
                    isAbort && "border-destructive/50 bg-destructive/10 text-destructive hover:bg-destructive/20",
                    !isApprove && !isAbort && "border-border bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                  )}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Checkpoint selector — select_one: pick from list of options ──── */}
      {checkpoint && checkpoint.type !== "step_confirm" && (
        <div className="mx-4 mb-3 rounded-xl border border-primary/40 bg-primary/8 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary shrink-0" />
            <p className="text-sm font-semibold text-foreground">{checkpoint.title ?? "Select an option"}</p>
            <Badge variant="secondary" className="ml-auto text-[10px]">Waiting</Badge>
          </div>
          <div className="space-y-1.5">
            {(checkpoint.options ?? []).map((opt) => {
              const isDefault = opt.index === (checkpoint.default_index ?? 0);
              return (
                <button
                  key={opt.index}
                  type="button"
                  disabled={respondMutation.isPending || checkpointPending}
                  onClick={() => {
                    setCheckpointPending(true);
                    respondMutation.mutate({ idx: opt.index });
                  }}
                  className={cn(
                    "w-full rounded-md border px-3 py-2 text-left text-sm transition-colors",
                    isDefault
                      ? "border-primary/50 bg-primary/10 text-foreground hover:bg-primary/20"
                      : "border-border bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                  )}
                >
                  <span className="font-medium">{opt.label}</span>
                  {opt.hint && <span className="ml-2 text-xs text-muted-foreground">· {opt.hint}</span>}
                  {isDefault && <span className="ml-2 text-[10px] text-primary">default</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}

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
                      : "text-primary",
                )}
              >
                {step.status === "done" ? "✓" : step.status === "failed" ? "✗" : "●"}
              </span>
              <span className="text-sm text-foreground/80 truncate">{step.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Structured result card (inspect / validate with parsed payload) ─ */}
      {isTerminal && job?.result?.parsed_payload && isRecord(job.result.parsed_payload) &&
        (moduleName === "inspect" || moduleName === "validate") ? (
        <div className="px-4 pb-4 space-y-2">
          {moduleName === "inspect" && (
            <InspectResult payload={job.result.parsed_payload} />
          )}
          {moduleName === "validate" && (
            <ValidateResult payload={job.result.parsed_payload} />
          )}
          {outputText && (
            <details className="group">
              <summary className="cursor-pointer text-[11px] text-muted-foreground hover:text-foreground list-none flex items-center gap-1">
                <span className="transition-transform group-open:rotate-90 inline-block">▶</span>
                Raw output
              </summary>
              <pre className="mt-1.5 max-h-40 overflow-auto rounded-md border border-border bg-muted px-3 py-2 text-[11px] leading-relaxed font-mono">
                {outputText}
              </pre>
            </details>
          )}
        </div>
      ) : outputText ? (
        /* ── Normal live / final output for all other modules ──────────── */
        <div className="px-4 pb-4 space-y-1.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {isRunning ? "Live output" : "Output"}
          </p>
          <pre className="max-h-48 overflow-auto rounded-md border border-border bg-muted px-3 py-2 text-[11px] leading-relaxed font-mono">
            {outputText}
          </pre>
        </div>
      ) : null}

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
