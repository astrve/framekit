import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Clock3, Pause, Play, Square } from "lucide-react";
import { useMemo, useState } from "react";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  cancelModuleJob,
  clearModuleJobs,
  listModuleJobs,
  pauseQueueJob,
  resumeQueueJob,
} from "@/lib/api/endpoints";
import type { ModuleJob } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";

type JobStatusFilter = "all" | "pending" | "running" | "completed" | "failed" | "cancelled";

function mutationErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const parsed = JSON.parse(error.body) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return `HTTP ${error.status}: ${parsed.detail}`;
      }
    } catch {
      if (error.body.trim()) {
        return `HTTP ${error.status}: ${error.body}`;
      }
    }
    return `HTTP ${error.status}: API request failed`;
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Unknown error.";
}

export function ModulesPage() {
  const navigate = useNavigate();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState<string>("pipeline");
  const [jobsLimit, setJobsLimit] = useState(20);
  const [statusFilter, setStatusFilter] = useState<JobStatusFilter>("all");
  const [searchText, setSearchText] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);

  const jobsQuery = useQuery({
    queryKey: ["modules-jobs", jobsLimit],
    queryFn: () => listModuleJobs(jobsLimit),
    refetchInterval: 3000,
  });

  const cancelJobMutation = useMutation({
    mutationFn: cancelModuleJob,
    onSuccess: () => void jobsQuery.refetch(),
  });
  const pauseJobMutation = useMutation({
    mutationFn: pauseQueueJob,
    onSuccess: () => void jobsQuery.refetch(),
  });
  const resumeJobMutation = useMutation({
    mutationFn: resumeQueueJob,
    onSuccess: () => void jobsQuery.refetch(),
  });
  const clearJobsMutation = useMutation({
    mutationFn: clearModuleJobs,
    onSuccess: () => {
      setConfirmClear(false);
      setSelectedJobId(null);
      void jobsQuery.refetch();
    },
  });

  const filteredJobs = useMemo(() => {
    const list = jobsQuery.data?.jobs ?? [];
    const needle = searchText.trim().toLowerCase();
    return list.filter((job) => {
      if (statusFilter !== "all" && job.status !== statusFilter) {
        return false;
      }
      if (!needle) {
        return true;
      }
      const moduleName = String(job.request["module"] ?? "").toLowerCase();
      return (
        job.id.toLowerCase().includes(needle) ||
        moduleName.includes(needle) ||
        job.status.toLowerCase().includes(needle)
      );
    });
  }, [jobsQuery.data?.jobs, searchText, statusFilter]);

  const mutationError = cancelJobMutation.error ?? clearJobsMutation.error;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Central queue and execution history. Filter, inspect, cancel, and rerun from one place.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link to="/pipeline">Run Pipeline</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link to="/batch">Run Batch</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link to="/studios">Open Modules</Link>
          </Button>
        </div>
      </section>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-primary" />
              Queue and history
            </CardTitle>
            <CardDescription>All background jobs with retry metadata and direct drilldown.</CardDescription>
          </div>
          {confirmClear ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-destructive">Clear completed/failed jobs?</span>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={clearJobsMutation.isPending}
                onClick={() => { void clearJobsMutation.mutateAsync(); }}
              >
                Yes
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => { setConfirmClear(false); }}>
                No
              </Button>
            </div>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={clearJobsMutation.isPending}
              onClick={() => { setConfirmClear(true); }}
            >
              Clear history
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid gap-2 md:grid-cols-[120px_160px_1fr_auto]">
            <label className="space-y-1 text-sm" htmlFor="jobs-limit">
              Limit
              <select
                id="jobs-limit"
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={jobsLimit}
                onChange={(event) => { setJobsLimit(Number(event.target.value)); }}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
            <label className="space-y-1 text-sm" htmlFor="jobs-status">
              Status
              <select
                id="jobs-status"
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={statusFilter}
                onChange={(event) => { setStatusFilter(event.target.value as JobStatusFilter); }}
              >
                <option value="all">All</option>
                <option value="pending">Pending</option>
                <option value="running">Running</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
            <label className="space-y-1 text-sm md:col-span-2" htmlFor="jobs-search">
              Search
              <Input
                id="jobs-search"
                value={searchText}
                onChange={(event) => { setSearchText(event.target.value); }}
                placeholder="id / module / status"
              />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            Showing: {filteredJobs.length} / {jobsQuery.data?.jobs.length ?? 0}
          </p>

          {filteredJobs.length === 0 ? (
            <p className="rounded-md border border-border bg-secondary/25 px-3 py-6 text-center text-sm text-muted-foreground">
              No jobs match the current filters.
            </p>
          ) : (
            <div className="overflow-hidden rounded-md border border-border">
              <table className="w-full text-sm">
                <thead className="bg-secondary/35">
                  <tr className="border-b border-border/70 text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="px-3 py-2 font-semibold">Job</th>
                    <th className="px-3 py-2 font-semibold">Module</th>
                    <th className="px-3 py-2 font-semibold">Status</th>
                    <th className="px-3 py-2 font-semibold">Retry</th>
                    <th className="px-3 py-2 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/70">
                  {filteredJobs.map((job) => (
                    <tr
                      key={job.id}
                      className={cn(
                        "hover:bg-secondary/35",
                        selectedJobId === job.id ? "bg-primary/5" : "",
                      )}
                    >
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          className="text-left font-mono text-xs text-muted-foreground hover:text-foreground"
                          onClick={() => { setSelectedJobId(job.id); setSelectedModule(String(job.request["module"] ?? "pipeline")); }}
                        >
                          {job.id}
                        </button>
                      </td>
                      <td className="px-3 py-2 font-medium">
                        {String((job.request["module"] as string) ?? "-")}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-1.5">
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
                          {job.origin ? (
                            <Badge variant="secondary" className="font-mono text-[10px]">
                              {job.origin}
                            </Badge>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-1.5 text-xs">
                          <span className="font-mono text-muted-foreground">
                            {job.attempts}/{job.max_attempts}
                          </span>
                          {job.last_failure_kind ? (
                            <Badge variant="warning" className="font-mono text-[10px]">
                              {job.last_failure_kind}
                            </Badge>
                          ) : null}
                          {job.next_retry_at ? (
                            <Badge variant="secondary" className="font-mono text-[10px]">
                              {new Date(job.next_retry_at).toLocaleTimeString()}
                            </Badge>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex justify-end gap-1.5">
                          {job.status === "pending" && (
                            job.paused ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                title="Resume queued job"
                                disabled={resumeJobMutation.isPending && resumeJobMutation.variables === job.id}
                                onClick={(e) => { e.stopPropagation(); void resumeJobMutation.mutateAsync(job.id); }}
                              >
                                <Play className="h-3 w-3" />
                              </Button>
                            ) : (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                title="Pause queued job (before it runs)"
                                disabled={pauseJobMutation.isPending && pauseJobMutation.variables === job.id}
                                onClick={(e) => { e.stopPropagation(); void pauseJobMutation.mutateAsync(job.id); }}
                              >
                                <Pause className="h-3 w-3" />
                              </Button>
                            )
                          )}
                          {(job.status === "pending" || job.status === "running") && (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="text-destructive hover:text-destructive"
                              disabled={cancelJobMutation.isPending && cancelJobMutation.variables === job.id}
                              onClick={(e) => { e.stopPropagation(); void cancelJobMutation.mutateAsync(job.id); }}
                            >
                              <Square className="h-3 w-3" />
                            </Button>
                          )}
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => { void navigate({ to: "/jobs/$jobId", params: { jobId: job.id } }); }}
                          >
                            Details
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(jobsQuery.data?.jobs.length ?? 0) >= jobsLimit && jobsLimit < 100 ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => { setJobsLimit((value) => Math.min(100, value + 10)); }}
            >
              Load more
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {selectedJobId ? (
        <section className="surface-enter">
          <h2 className="mb-2 text-sm font-semibold">Job Detail</h2>
          <InlineJobPanel
            jobId={selectedJobId}
            moduleName={selectedModule}
            onRerun={(j: ModuleJob) => { setSelectedJobId(j.id); void jobsQuery.refetch(); }}
          />
        </section>
      ) : null}

      {mutationError ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {mutationErrorMessage(mutationError)}
        </p>
      ) : null}
    </div>
  );
}
