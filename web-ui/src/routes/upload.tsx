import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { CloudUpload, Copy } from "lucide-react";
import { useState } from "react";

import { RunTimeline } from "@/components/modules/run-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { createModuleJob, getModuleJob, getUploadHistory, getUploadState, getUploadTrackerInfo, getUploadTrackers, runModule, setUploadState } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult, UploadState } from "@/lib/api/schemas";
import { runTimeline } from "@/lib/progress";

type UploadAction = "setup" | "list-trackers" | "show-tracker" | "run" | "history";

const ACTION_BUTTONS: Array<{ value: UploadAction; label: string }> = [
  { value: "list-trackers", label: "View Trackers" },
  { value: "show-tracker", label: "Tracker Details" },
  { value: "run", label: "Upload Now" },
  { value: "history", label: "History" },
  { value: "setup", label: "Setup" },
];

export function UploadPage() {
  const navigate = useNavigate();
  const [action, setAction] = useState<UploadAction>("list-trackers");
  const [tracker, setTracker] = useState("");
  const [torrentPath, setTorrentPath] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lastJob, setLastJob] = useState<ModuleJob | null>(null);

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({ mutationFn: createModuleJob, onSuccess: (job) => setLastJob(job) });
  const stateQuery = useQuery({ queryKey: ["upload-state"], queryFn: getUploadState });
  const historyQuery = useQuery({ queryKey: ["upload-history"], queryFn: () => getUploadHistory(20) });
  const trackersQuery = useQuery({ queryKey: ["upload-trackers-page"], queryFn: getUploadTrackers });
  const trackerInfoQuery = useQuery({
    queryKey: ["upload-tracker-info", tracker],
    queryFn: () => getUploadTrackerInfo(tracker.trim()),
    enabled: tracker.trim().length > 0,
  });
  const setStateMutation = useMutation({
    mutationFn: setUploadState,
    onSuccess: (_state: UploadState) => {
      stateQuery.refetch().catch(() => undefined);
      setLocalError(null);
    },
  });

  const jobPollQuery = useQuery({
    queryKey: ["upload-job", lastJob?.id],
    queryFn: ({ queryKey }) => getModuleJob(queryKey[1] as string),
    enabled: !!lastJob,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return !status || ["completed", "failed", "cancelled"].includes(status) ? false : 1500;
    },
  });
  const timelineSource = jobPollQuery.data ?? lastJob ?? null;

  const buildArgs = (): string => {
    const args: string[] = [action];
    if (action === "show-tracker" && tracker.trim()) {
      args.push(`"${tracker.trim()}"`);
    }
    if (action === "run") {
      if (torrentPath.trim()) args.push(`"${torrentPath.trim()}"`);
      if (tracker.trim()) args.push("--tracker", `"${tracker.trim()}"`);
      if (name.trim()) args.push("--name", `"${name.trim()}"`);
      if (description.trim()) args.push("--description", `"${description.trim()}"`);
      if (dryRun) args.push("--dry-run");
    }
    if (action === "history") args.push("--limit", "20");
    return args.join(" ");
  };

  const result: RunModuleResult | null = runMutation.data ?? null;

  const validateAction = (): string | null => {
    if (action === "show-tracker" && !tracker.trim()) return "Tracker name required.";
    if (action === "run") {
      if (!torrentPath.trim()) return "Release or .torrent file path required.";
      if (!tracker.trim()) return "Tracker name required.";
    }
    return null;
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">
          Upload{" "}
          <span className="ml-1 rounded-full bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary">BETA</span>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">Push releases to configured trackers and manage upload history.</p>
      </section>

      {timelineSource ? (
        <Card>
          <CardHeader>
            <CardTitle>Run Timeline</CardTitle>
            <CardDescription>Upload job progress.</CardDescription>
          </CardHeader>
          <CardContent>
            <RunTimeline items={runTimeline(timelineSource)} />
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudUpload className="h-4 w-4 text-primary" />
            Upload action
          </CardTitle>
          <CardDescription>Choose what you want to do.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {ACTION_BUTTONS.map(({ value, label }) => (
              <Button
                key={value}
                type="button"
                variant={action === value ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setAction(value);
                  if (value !== "run") {
                    setName("");
                    setDescription("");
                    setDryRun(true);
                  }
                }}
              >
                {label}
              </Button>
            ))}
          </div>

          {stateQuery.data ? (
            <div className="flex items-center gap-3">
              <Badge variant={stateQuery.data.enabled ? "success" : "warning"}>
                {stateQuery.data.enabled ? "Upload active" : "Upload disabled"}
              </Badge>
              {stateQuery.data.auto_upload ? <Badge variant="secondary">Auto-upload on</Badge> : null}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  const current = stateQuery.data;
                  if (!current) return;
                  setStateMutation.mutate({ enabled: !current.enabled, auto_upload: current.auto_upload });
                }}
              >
                {stateQuery.data.enabled ? "Disable" : "Enable"}
              </Button>
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="flex items-center gap-0">Tracker name<InfoTooltip text="Short identifier of the configured upload tracker (e.g. BHD, PTP, HDB)" /></span>
              <Input value={tracker} placeholder="e.g. mytracker" onChange={(e) => setTracker(e.target.value)} />
            </label>
            {action === "run" ? (
              <>
                <label className="space-y-1 text-sm md:col-span-2">
                  <span className="flex items-center gap-0">Release or .torrent file path<InfoTooltip text="Path to the release folder or .torrent file to submit to the tracker" /></span>
                  <Input value={torrentPath} placeholder="C:/Releases/My.Release" onChange={(e) => setTorrentPath(e.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="flex items-center gap-0">Upload title (optional)<InfoTooltip text="Override the release title sent to the tracker — defaults to the folder/file name" /></span>
                  <Input value={name} placeholder="Override release name" onChange={(e) => setName(e.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="flex items-center gap-0">Description (optional)<InfoTooltip text="Short description appended to the upload form submission" /></span>
                  <Input value={description} placeholder="Short description" onChange={(e) => setDescription(e.target.value)} />
                </label>
              </>
            ) : null}
          </div>

          {action === "run" ? (
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
              <button
                type="button"
                role="checkbox"
                aria-checked={dryRun}
                onClick={() => setDryRun(!dryRun)}
                className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors ${dryRun ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background hover:border-primary/60"}`}
              >
                {dryRun ? <span className="text-[10px] font-bold leading-none">✓</span> : null}
              </button>
              Simulation (no upload)
              <InfoTooltip text="Dry-run — validate the upload payload and show what would be submitted without actually sending to the tracker" />
            </label>
          ) : null}

          <details className="rounded-md border border-border">
            <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
              Advanced — show generated command
            </summary>
            <pre className="max-h-40 overflow-auto border-t border-border bg-muted p-3 text-xs">framekit upload {buildArgs()}</pre>
          </details>

          {localError ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">{localError}</p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={runMutation.isPending || createJobMutation.isPending}
              onClick={() => {
                const issue = validateAction();
                setLocalError(issue);
                if (issue) return;
                const payload = {
                  module: "upload",
                  args_text: buildArgs(),
                  dry_run: false,
                  auto_yes: false,
                  confirm_destructive: true,
                };
                if (action === "run") {
                  createJobMutation.mutate(payload);
                } else {
                  runMutation.mutate(payload);
                }
              }}
            >
              Run
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                await navigator.clipboard.writeText(`framekit upload ${buildArgs()}`.trim());
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1400);
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy Command
            </Button>
            {copied ? <Badge variant="success">Copied</Badge> : null}
            {lastJob ? (
              <Button type="button" variant="outline" onClick={() => void navigate({ to: "/modules/$jobId", params: { jobId: lastJob.id } })}>
                View Job
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured trackers</CardTitle>
          <CardDescription>Available upload destinations.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(trackersQuery.data?.trackers ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No trackers configured.</p>
          ) : (
            <div className="grid gap-2">
              {(trackersQuery.data?.trackers ?? []).map((item) => (
                <div key={item.name} className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3 text-sm">
                  <button type="button" className="font-medium text-foreground transition-colors hover:text-primary" onClick={() => setTracker(item.name)}>
                    {item.name}
                  </button>
                  <span className="text-muted-foreground">{item.type}</span>
                  <span className="truncate text-xs text-muted-foreground">{item.url}</span>
                  <Badge variant={item.enabled ? "success" : "warning"}>{item.enabled ? "Enabled" : "Disabled"}</Badge>
                </div>
              ))}
            </div>
          )}
          {trackerInfoQuery.data && tracker.trim() ? (
            <div className="rounded-md border border-border p-3 text-sm">
              <p className="mb-2 font-medium">Details for {tracker}</p>
              <div className="grid gap-1">
                {Object.entries(trackerInfoQuery.data.tracker).map(([key, value]) => (
                  <div key={key} className="grid grid-cols-[140px_1fr] gap-2 text-xs">
                    <span className="text-muted-foreground">{key}</span>
                    <span className="break-all font-mono">{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={result.ok ? "success" : "danger"}>{result.ok ? "Completed" : "Failed"}</Badge>
              Upload result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{result.stdout || "(no output)"}</pre>
            {result.stderr ? (
              <pre className="max-h-72 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{result.stderr}</pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Upload history</CardTitle>
          <CardDescription>Recent uploads across all trackers.</CardDescription>
        </CardHeader>
        <CardContent>
          {(historyQuery.data?.entries ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No uploads recorded yet.</p>
          ) : (
            <div className="space-y-2">
              {(historyQuery.data?.entries ?? []).map((entry, index) => (
                <div key={index} className="rounded-md border border-border p-3 text-sm">
                  <div className="grid gap-1">
                    {Object.entries(entry).map(([key, value]) => (
                      <div key={key} className="grid grid-cols-[120px_1fr] gap-2 text-xs">
                        <span className="text-muted-foreground capitalize">{key.replace(/_/g, " ")}</span>
                        <span className="break-all font-mono">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
