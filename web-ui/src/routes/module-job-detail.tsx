import { Link, useParams } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Copy, LoaderCircle, OctagonX } from "lucide-react";
import { useMemo, useState } from "react";

import { RunTimeline } from "@/components/modules/run-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getModuleJob } from "@/lib/api/endpoints";
import { parseSubSteps, runTimeline } from "@/lib/progress";

function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatDuration(startedAt: string | null | undefined, finishedAt: string | null | undefined): string {
  if (!startedAt) {
    return "-";
  }
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) {
    return "-";
  }
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  if (Number.isNaN(end) || end < start) {
    return "-";
  }
  const totalSeconds = Math.floor((end - start) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

export function ModuleJobDetailPage() {
  const { jobId } = useParams({ from: "/jobs/$jobId" });
  const [copied, setCopied] = useState(false);
  const [followLogs, setFollowLogs] = useState(true);
  const [logFilter, setLogFilter] = useState("");
  const [pausedSnapshot, setPausedSnapshot] = useState<{ stdout: string; stderr: string }>({
    stdout: "",
    stderr: "",
  });
  const jobQuery = useQuery({
    queryKey: ["module-job-detail", jobId],
    queryFn: () => getModuleJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "pending" || status === "running") {
        return 1200;
      }
      return false;
    },
  });

  const job = jobQuery.data;
  const commandText = job?.result?.argv.join(" ") ?? "";
  const liveStdout = job?.status === "pending" || job?.status === "running" ? (job.live_stdout ?? "") : "";
  const liveStderr = job?.status === "pending" || job?.status === "running" ? (job.live_stderr ?? "") : "";
  const stdoutView = followLogs ? liveStdout : pausedSnapshot.stdout;
  const stderrView = followLogs ? liveStderr : pausedSnapshot.stderr;

  const filteredStdout = useMemo(() => {
    const pattern = logFilter.trim().toLowerCase();
    if (!pattern) {
      return stdoutView;
    }
    return stdoutView
      .split("\n")
      .filter((line) => line.toLowerCase().includes(pattern))
      .join("\n");
  }, [logFilter, stdoutView]);
  const filteredStderr = useMemo(() => {
    const pattern = logFilter.trim().toLowerCase();
    if (!pattern) {
      return stderrView;
    }
    return stderrView
      .split("\n")
      .filter((line) => line.toLowerCase().includes(pattern))
      .join("\n");
  }, [logFilter, stderrView]);
  const timelineItems = runTimeline(job);
  const subSteps = parseSubSteps(String(job?.request["module"] ?? ""), stdoutView, stderrView);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Job Detail</h1>
        <p className="mt-1 text-sm text-muted-foreground">{jobId}</p>
        <div className="mt-3">
          <Button asChild variant="outline">
            <Link to="/jobs">Back to Jobs</Link>
          </Button>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Run Timeline</CardTitle>
          <CardDescription>Live Progress While Queued Or Running.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <RunTimeline items={timelineItems} />
          {jobQuery.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
          {jobQuery.error ? (
            <p className="rounded-md border border-rose-300 bg-rose-100 p-3 text-sm text-rose-800">
              Failed to load job.
            </p>
          ) : null}
          {job ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={
                    job.status === "completed"
                      ? "success"
                      : job.status === "failed" || job.status === "cancelled"
                        ? "danger"
                        : "secondary"
                  }
                >
                  {job.status}
                </Badge>
                {job.status === "running" || job.status === "pending" ? (
                  <LoaderCircle className="h-4 w-4 animate-spin text-muted-foreground" />
                ) : null}
                {job.status === "completed" ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : null}
                {job.status === "failed" || job.status === "cancelled" ? (
                  <OctagonX className="h-4 w-4 text-rose-700" />
                ) : null}
              </div>

              <div className="grid gap-2 text-sm md:grid-cols-2">
                <p>Created: {formatTime(job.created_at)}</p>
                <p>Started: {formatTime(job.started_at)}</p>
                <p>Finished: {formatTime(job.finished_at)}</p>
                <p>Duration: {formatDuration(job.started_at, job.finished_at)}</p>
                <p>Module: {String(job.request["module"] ?? "-")}</p>
                <p>Attempts: {job.attempts}/{job.max_attempts}</p>
                <p>Retryable: {job.retryable ? "yes" : "no"}</p>
                <p>Last failure: {job.last_failure_kind ?? "-"}</p>
                <p>Next retry: {formatTime(job.next_retry_at)}</p>
              </div>
              {subSteps.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Detected Sub-Steps</p>
                  {subSteps.map((step, index) => (
                    <div key={`${step.label}-${index}`} className="rounded-md border border-border p-2 text-sm">
                      <span className="font-medium">{step.status.toUpperCase()}</span>: {step.label}
                    </div>
                  ))}
                </div>
              ) : null}

              {commandText ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Command</p>
                  <pre className="max-h-60 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
                    {commandText}
                  </pre>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(commandText);
                        setCopied(true);
                        setTimeout(() => {
                          setCopied(false);
                        }, 1200);
                      } catch {
                        setCopied(false);
                      }
                    }}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    {copied ? "Command copied" : "Copy command"}
                  </Button>
                </div>
              ) : null}

              {job.result ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Result</p>
                  <p className="text-sm">Return code: {job.result.returncode}</p>
                  <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
                    {job.result.stdout || "(stdout empty)"}
                  </pre>
                  {job.result.stderr ? (
                    <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                      {job.result.stderr}
                    </pre>
                  ) : null}
                </div>
              ) : null}

              {job && (job.status === "pending" || job.status === "running") ? (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">Logs live</p>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (followLogs) {
                          setPausedSnapshot({ stdout: liveStdout, stderr: liveStderr });
                          setFollowLogs(false);
                          return;
                        }
                        setFollowLogs(true);
                      }}
                    >
                      {followLogs ? "Pause follow" : "Resume follow"}
                    </Button>
                  </div>
                  <label className="space-y-1 text-sm" htmlFor="logs-filter">
                    Filter
                    <input
                      id="logs-filter"
                      className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                      value={logFilter}
                      onChange={(event) => setLogFilter(event.target.value)}
                      placeholder="contains..."
                    />
                  </label>
                  <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
                    {filteredStdout || "(stdout pending)"}
                  </pre>
                  {filteredStderr ? (
                    <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                      {filteredStderr}
                    </pre>
                  ) : null}
                </div>
              ) : null}

              {job.error ? (
                <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                  {job.error}
                </pre>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
