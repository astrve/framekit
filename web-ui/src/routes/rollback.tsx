import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { useState } from "react";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createModuleJob, getRuns } from "@/lib/api/endpoints";
import type { ModuleJob, RunSummary } from "@/lib/api/schemas";

function formatTimestamp(ts: string): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function RunRow({
  run,
  onRollback,
  isRollingBack,
}: {
  run: RunSummary;
  onRollback: (runId: string) => void;
  isRollingBack: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border border-border">
      <div className="grid items-center gap-2 p-3 md:grid-cols-[1fr_auto_auto_auto_auto]">
        <div>
          <p className="font-mono text-xs text-muted-foreground">{run.run_id}</p>
          <p className="text-sm font-medium">{run.module}</p>
        </div>
        <Badge variant="secondary">{run.file_count} file{run.file_count !== 1 ? "s" : ""}</Badge>
        <p className="text-xs text-muted-foreground whitespace-nowrap">{formatTimestamp(run.timestamp)}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          {expanded ? "Hide" : "Show"} files
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={isRollingBack}
          onClick={() => onRollback(run.run_id)}
        >
          <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
          Rollback
        </Button>
      </div>
      {expanded && run.actions.length > 0 && (
        <div className="border-t border-border bg-muted/40 p-3 space-y-1">
          {run.actions.map((action, index) => (
            <div
              key={`${action.action}-${index}`}
              className="grid grid-cols-[60px_1fr] gap-2 text-xs"
            >
              <Badge variant="outline" className="h-fit w-fit">{action.action}</Badge>
              <div className="min-w-0">
                <p className="truncate text-muted-foreground" title={action.src}>{action.src}</p>
                <p className="truncate" title={action.dst}>→ {action.dst}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function RollbackPage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const runsQuery = useQuery({
    queryKey: ["runs-ledger"],
    queryFn: () => getRuns(50),
  });

  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job) => setJobId(job.id),
  });

  function handleRollback(runId: string) {
    setActiveRunId(runId);
    setJobId(null);
    createJobMutation.mutate({
      module: "rollback",
      args_text: runId,
      dry_run: false,
      auto_yes: true,
      confirm_destructive: true,
    });
  }

  const runs = runsQuery.data?.runs ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Rollback</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Undo tracked file operations. Each run shows the files moved — select one to revert.
        </p>
      </section>

      {jobId !== null ? (
        <InlineJobPanel
          jobId={jobId}
          moduleName="rollback"
          onRerun={(newJob: ModuleJob) => setJobId(newJob.id)}
        />
      ) : null}

      {createJobMutation.error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {createJobMutation.error instanceof Error
            ? createJobMutation.error.message
            : "Failed to start rollback job."}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RotateCcw className="h-4 w-4 text-primary" />
            Recent runs
          </CardTitle>
          <CardDescription>
            Operations tracked in the run ledger. Rollback reverses all file moves in a run.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {runsQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No runs recorded yet. Operations appear here after renamer, cleanmkv, or pipeline runs that apply changes.
            </p>
          ) : (
            runs.map((run) => (
              <RunRow
                key={run.run_id}
                run={run}
                onRollback={handleRollback}
                isRollingBack={
                  createJobMutation.isPending && activeRunId === run.run_id
                }
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
