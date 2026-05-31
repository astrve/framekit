import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CloudUpload, Copy } from "lucide-react";
import { useMemo, useState } from "react";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { createModuleJob, getUploadHistory, getUploadState, getUploadTrackerInfo, getUploadTrackers, removeUploadTracker, runModule, setUploadState, setUploadTrackerEnabled } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult, UploadState } from "@/lib/api/schemas";

type UploadAction = "setup" | "list-trackers" | "show-tracker" | "run" | "history";

const ACTION_BUTTONS: Array<{ value: UploadAction; label: string }> = [
  { value: "list-trackers", label: "View Trackers" },
  { value: "show-tracker", label: "Tracker Details" },
  { value: "run", label: "Upload Now" },
  { value: "history", label: "History" },
  { value: "setup", label: "Setup" },
];

function formatRelativeTime(ts: string | undefined): string {
  if (!ts) return "n/a";
  const time = new Date(ts).getTime();
  if (Number.isNaN(time)) return "n/a";
  const delta = Date.now() - time;
  if (delta < 60_000) return "just now";
  const mins = Math.floor(delta / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function UploadPage() {
  const [action, setAction] = useState<UploadAction>("list-trackers");
  const [tracker, setTracker] = useState("");
  const [torrentPath, setTorrentPath] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job) => setJobId(job.id),
  });
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
  const toggleTrackerMutation = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) => setUploadTrackerEnabled(name, enabled),
    onSuccess: () => { trackersQuery.refetch().catch(() => undefined); },
    onError: (err: unknown) => setLocalError(err instanceof Error ? err.message : "Failed to update tracker."),
  });
  const removeTrackerMutation = useMutation({
    mutationFn: (name: string) => removeUploadTracker(name),
    onSuccess: () => {
      trackersQuery.refetch().catch(() => undefined);
      setLocalError(null);
    },
    onError: (err: unknown) => setLocalError(err instanceof Error ? err.message : "Failed to remove tracker."),
  });

  const result: RunModuleResult | null = runMutation.data ?? null;
  const enabledTrackers = (trackersQuery.data?.trackers ?? []).filter((item) => item.enabled).length;
  const historyEntries = historyQuery.data?.entries ?? [];
  const recentStats = useMemo(() => {
    const stats = { success: 0, failed: 0 };
    for (const entry of historyEntries.slice(0, 20)) {
      if (entry.success) stats.success += 1;
      else stats.failed += 1;
    }
    return stats;
  }, [historyEntries]);
  const lastUploadTs = historyEntries[0]?.timestamp;

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
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Upload</h1>
            <p className="mt-1 text-sm text-muted-foreground">Push releases to configured trackers and manage upload history.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/logs"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Open Logs
            </Link>
            <Link
              to="/events"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Service Events
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Upload State</CardTitle>
            <CardDescription>Current service toggle</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Enabled: <span className="font-semibold">{stateQuery.data?.enabled ? "yes" : "no"}</span></p>
            <p>Auto upload: <span className="font-semibold">{stateQuery.data?.auto_upload ? "on" : "off"}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Trackers</CardTitle>
            <CardDescription>Configured destinations</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Total: <span className="font-semibold">{(trackersQuery.data?.trackers ?? []).length}</span></p>
            <p>Enabled: <span className="font-semibold">{enabledTrackers}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Recent Uploads</CardTitle>
            <CardDescription>Last 20 entries</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Success: <span className="font-semibold">{recentStats.success}</span></p>
            <p>Failed: <span className="font-semibold">{recentStats.failed}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Last Activity</CardTitle>
            <CardDescription>Most recent upload timestamp</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>{formatRelativeTime(lastUploadTs)}</p>
            <p className="text-xs text-muted-foreground">{lastUploadTs ? new Date(lastUploadTs).toLocaleString() : "No history yet"}</p>
          </CardContent>
        </Card>
      </section>

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
            <Toggle
              checked={dryRun}
              onChange={setDryRun}
              label="Simulation (no upload)"
              tooltip={<InfoTooltip text="Dry-run — validate the upload payload and show what would be submitted without actually sending to the tracker" />}
            />
          ) : null}

          <details className="rounded-md border border-border">
            <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
              Advanced — show generated command
            </summary>
            <pre className="max-h-40 overflow-auto border-t border-border bg-muted p-3 text-xs">swirrl upload {buildArgs()}</pre>
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
                await navigator.clipboard.writeText(`swirrl upload ${buildArgs()}`.trim());
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1400);
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy Command
            </Button>
            {copied ? <Badge variant="success">Copied</Badge> : null}
          </div>
        </CardContent>
      </Card>

      {jobId !== null ? (
        <InlineJobPanel
          jobId={jobId}
          moduleName="upload"
          onRerun={(newJob: ModuleJob) => setJobId(newJob.id)}
        />
      ) : null}

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
                  <div className="ml-auto flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={toggleTrackerMutation.isPending}
                      onClick={() => toggleTrackerMutation.mutate({ name: item.name, enabled: !item.enabled })}
                    >
                      {item.enabled ? "Disable" : "Enable"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="border-destructive/40 text-destructive hover:bg-destructive/10"
                      disabled={removeTrackerMutation.isPending}
                      onClick={() => {
                        if (window.confirm(`Remove tracker "${item.name}"? This deletes it from settings.`)) {
                          removeTrackerMutation.mutate(item.name);
                        }
                      }}
                    >
                      Remove
                    </Button>
                  </div>
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
                <div key={index} className="rounded-md border border-border p-3 text-sm space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={entry.success ? "success" : "danger"}>
                      {entry.success ? "Success" : "Failed"}
                    </Badge>
                    <span className="font-medium">{entry.tracker}</span>
                    {entry.torrent && (
                      <span className="text-muted-foreground text-xs truncate max-w-xs">{entry.torrent}</span>
                    )}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ""}
                    </span>
                  </div>
                  {entry.url && (
                    <p className="text-xs text-muted-foreground break-all">{entry.url}</p>
                  )}
                  {entry.message && (
                    <p className="text-xs text-muted-foreground">{entry.message}</p>
                  )}
                  {entry.errors.length > 0 && (
                    <ul className="text-xs text-destructive space-y-0.5">
                      {entry.errors.map((err, i) => <li key={i}>{err}</li>)}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
