import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Copy, HardDriveDownload } from "lucide-react";
import { useMemo, useState } from "react";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { addSeedbox, createModuleJob, getSettingsProfiles, getSeedboxHistory, getSeedboxList, removeSeedbox, runModule, useSeedbox } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";

type SeedboxAction = "list" | "status" | "doctor" | "history" | "push" | "pull";

function quoteArg(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  if (/[\s"]/.test(trimmed)) {
    return `"${trimmed.replaceAll('"', '\\"')}"`;
  }
  return trimmed;
}

function compact(value: unknown): string {
  if (value === undefined || value === null) {
    return "-";
  }
  const text = String(value).trim();
  return text || "-";
}

function formatRelativeTime(ts: string | null): string {
  if (!ts) return "n/a";
  const parsed = new Date(ts).getTime();
  if (Number.isNaN(parsed)) return "n/a";
  const delta = Date.now() - parsed;
  if (delta < 60_000) return "just now";
  const mins = Math.floor(delta / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function SeedboxPage() {
  const [action, setAction] = useState<SeedboxAction>("status");
  const [seedboxName, setSeedboxName] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [destinationPath, setDestinationPath] = useState("");
  const [remotePath, setRemotePath] = useState("");
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState(50);
  const [dryRun, setDryRun] = useState(true);
  const [verbose, setVerbose] = useState(false);
  const [allowCwd, setAllowCwd] = useState(false);
  const [confirmDestructive, setConfirmDestructive] = useState(true);
  const [asyncRun, setAsyncRun] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const [addName, setAddName] = useState("");
  const [addRemote, setAddRemote] = useState("");
  const [addBasePath, setAddBasePath] = useState("/");
  const [addTransfers, setAddTransfers] = useState("3");
  const [addBandwidth, setAddBandwidth] = useState("");
  const [bindProfile, setBindProfile] = useState("");
  const [bindSeedbox, setBindSeedbox] = useState("");

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job) => setJobId(job.id),
  });
  const listQuery = useQuery({ queryKey: ["seedbox-list-page"], queryFn: getSeedboxList });
  const historyQuery = useQuery({ queryKey: ["seedbox-history", seedboxName, limit], queryFn: () => getSeedboxHistory(limit, seedboxName) });
  const profilesQuery = useQuery({ queryKey: ["settings-profiles"], queryFn: getSettingsProfiles });
  const addMutation = useMutation({ mutationFn: addSeedbox, onSuccess: () => void listQuery.refetch() });
  const useMutationSeedbox = useMutation({ mutationFn: ({ name, profileName }: { name: string; profileName?: string }) => useSeedbox(name, profileName), onSuccess: () => void listQuery.refetch() });
  const removeMutationSeedbox = useMutation({ mutationFn: removeSeedbox, onSuccess: () => void listQuery.refetch() });

  const argsText = useMemo(() => {
    const args: string[] = [action];
    if (seedboxName.trim() && ["push", "pull", "status", "history"].includes(action)) {
      args.push("--seedbox", quoteArg(seedboxName));
    }
    if (action === "history") {
      args.push("--limit", String(limit));
    }
    if (action === "status" || action === "history") {
      return args.join(" ").trim();
    }
    if (action === "push") {
      if (sourcePath.trim()) {
        args.push(quoteArg(sourcePath));
      }
      if (remotePath.trim()) {
        args.push("--remote-path", quoteArg(remotePath));
      }
      if (category.trim()) {
        args.push("--category", quoteArg(category));
      }
      if (dryRun) {
        args.push("--dry-run");
      }
      if (verbose) {
        args.push("--verbose");
      }
      if (allowCwd) {
        args.push("--cwd");
      }
      return args.join(" ").trim();
    }
    if (action === "pull") {
      if (sourcePath.trim()) {
        args.push(quoteArg(sourcePath));
      }
      if (destinationPath.trim()) {
        args.push(quoteArg(destinationPath));
      }
      if (remotePath.trim()) {
        args.push("--remote-path", quoteArg(remotePath));
      }
      if (dryRun) {
        args.push("--dry-run");
      }
      if (verbose) {
        args.push("--verbose");
      }
      if (allowCwd) {
        args.push("--cwd");
      }
      return args.join(" ").trim();
    }
    return args.join(" ").trim();
  }, [action, allowCwd, category, destinationPath, dryRun, limit, remotePath, seedboxName, sourcePath, verbose]);

  const previewCommand = useMemo(() => `ouro seedbox ${argsText}`.trim(), [argsText]);
  const result: RunModuleResult | null = runMutation.data ?? null;
  const seedboxes = listQuery.data?.seedboxes ?? [];
  const historyEntries = historyQuery.data?.entries ?? [];
  const defaultSeedboxName = seedboxes.find((item) => item.is_default)?.name ?? "-";
  const firstHistoryEntry = historyEntries[0] as Record<string, unknown> | undefined;
  const firstHistoryTs = firstHistoryEntry?.["timestamp"];
  const historyFailed = historyEntries.filter((entry) => {
    const statusText = compact((entry as Record<string, unknown>).status).toLowerCase();
    return statusText.includes("fail") || statusText.includes("error");
  }).length;
  const lastHistoryTs = typeof firstHistoryTs === "string" && firstHistoryTs.trim()
    ? firstHistoryTs
    : null;

  function validateAction(): string | null {
    if (action === "push" && !sourcePath.trim()) {
      return "Source path required for push.";
    }
    if (action === "pull" && !sourcePath.trim()) {
      return "Remote source path required for pull.";
    }
    return null;
  }

  function runNow() {
    const issue = validateAction();
    setLocalError(issue);
    if (issue) {
      return;
    }
    const payload = {
      module: "seedbox",
      args_text: argsText,
      dry_run: dryRun,
      auto_yes: false,
      confirm_destructive: confirmDestructive,
    };
    if (asyncRun) {
      createJobMutation.mutate(payload);
      return;
    }
    runMutation.mutate(payload);
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Seedbox</h1>
            <p className="mt-1 text-sm text-muted-foreground">Send and receive files from your remote seedbox.</p>
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
            <CardTitle className="text-sm">Profiles</CardTitle>
            <CardDescription>Configured seedboxes</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Total: <span className="font-semibold">{seedboxes.length}</span></p>
            <p>Default: <span className="font-semibold">{defaultSeedboxName}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">History Window</CardTitle>
            <CardDescription>Entries currently loaded</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Entries: <span className="font-semibold">{historyEntries.length}</span></p>
            <p>Failed: <span className="font-semibold">{historyFailed}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Mode</CardTitle>
            <CardDescription>Current run settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Dry run: <span className="font-semibold">{dryRun ? "on" : "off"}</span></p>
            <p>Background: <span className="font-semibold">{asyncRun ? "on" : "off"}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Last Activity</CardTitle>
            <CardDescription>Most recent history timestamp</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>{formatRelativeTime(lastHistoryTs)}</p>
            <p className="text-xs text-muted-foreground">{lastHistoryTs ? new Date(lastHistoryTs).toLocaleString() : "No history yet"}</p>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDriveDownload className="h-4 w-4 text-primary" />
            {action === "push" ? "Seedbox Upload" : action === "pull" ? "Seedbox Download" : "Seedbox Actions"}
          </CardTitle>
          <CardDescription>Compartmented flow: Upload / Download / Manage / History.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant={action === "push" ? "default" : "outline"} size="sm" onClick={() => setAction("push")}>Send Files</Button>
            <Button type="button" variant={action === "pull" ? "default" : "outline"} size="sm" onClick={() => setAction("pull")}>Receive Files</Button>
            <Button type="button" variant={action === "history" ? "default" : "outline"} size="sm" onClick={() => setAction("history")}>History</Button>
            <Button type="button" variant={action === "status" ? "default" : "outline"} size="sm" onClick={() => setAction("status")}>Status</Button>
            <Button type="button" variant={action === "doctor" ? "default" : "outline"} size="sm" onClick={() => setAction("doctor")}>Check Health</Button>
            <Button type="button" variant={action === "list" ? "default" : "outline"} size="sm" onClick={() => setAction("list")}>List</Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="flex items-center gap-0">Seedbox profile<InfoTooltip text="Name of the configured seedbox profile to target — leave blank to use the default" /></span>
              <Input value={seedboxName} placeholder="main-seedbox" onChange={(event) => setSeedboxName(event.target.value)} />
            </label>
            {(action === "push" || action === "pull") ? (
              <label className="space-y-1 text-sm md:col-span-2">
                <span className="flex items-center gap-0">
                  {action === "push" ? "Local folder to send" : "Remote folder to receive from"}
                  <InfoTooltip text={action === "push" ? "Absolute path to the local release folder to upload to the seedbox" : "Absolute path on the remote seedbox to pull files from"} />
                </span>
                <Input value={sourcePath} placeholder={action === "push" ? "C:/Releases/My.Release" : "/downloads/release"} onChange={(event) => setSourcePath(event.target.value)} />
              </label>
            ) : null}
            {action === "pull" ? (
              <label className="space-y-1 text-sm md:col-span-2">
                <span className="flex items-center gap-0">Save to (local destination)<InfoTooltip text="Local path where pulled files will be saved" /></span>
                <Input value={destinationPath} placeholder="C:/Downloads" onChange={(event) => setDestinationPath(event.target.value)} />
              </label>
            ) : null}
            {(action === "push" || action === "pull") ? (
              <label className="space-y-1 text-sm">
                <span className="flex items-center gap-0">Custom remote path (optional)<InfoTooltip text="Override the default remote base path from the seedbox profile for this transfer" /></span>
                <Input value={remotePath} placeholder="/target/path" onChange={(event) => setRemotePath(event.target.value)} />
              </label>
            ) : null}
            {action === "push" ? (
              <label className="space-y-1 text-sm">
                <span className="flex items-center gap-0">Category<InfoTooltip text="Remote subdirectory category — files are placed under &lt;base_path&gt;/&lt;category&gt;" /></span>
                <Input value={category} placeholder="movies, series, anime" onChange={(event) => setCategory(event.target.value)} />
              </label>
            ) : null}
            {action === "history" ? (
              <label className="space-y-1 text-sm">
                <span className="flex items-center gap-0">Number of entries<InfoTooltip text="How many recent seedbox transfer history entries to display" /></span>
                <Input type="number" value={String(limit)} onChange={(event) => setLimit(Math.max(1, Number.parseInt(event.target.value || "50", 10)))} />
              </label>
            ) : null}
          </div>

          {(action === "push" || action === "pull") ? (
            <div className="flex flex-wrap gap-4 text-sm">
              {([
                [dryRun, setDryRun, "Simulation (no transfers)", "Dry-run — preview what would be transferred without actually moving any files"],
                [verbose, setVerbose, "Detailed output", "Show per-file rclone progress and transfer details in the output"],
                [allowCwd, setAllowCwd, "Allow current directory", "Allow using the current working directory as the source path"],
              ] as Array<[boolean, (v: boolean) => void, string, string]>).map(([checked, setter, label, tooltip]) => (
                <Toggle
                  key={label}
                  checked={checked}
                  onChange={setter}
                  label={label}
                  tooltip={<InfoTooltip text={tooltip} />}
                />
              ))}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-4 text-sm">
            {([
              [confirmDestructive, setConfirmDestructive, "Allow file changes", "Permit overwrite and delete operations during the transfer"],
              [asyncRun, setAsyncRun, "Run in background", "Queue as async job — result appears inline without blocking the UI"],
            ] as Array<[boolean, (v: boolean) => void, string, string]>).map(([checked, setter, label, tooltip]) => (
              <Toggle
                key={label}
                checked={checked}
                onChange={setter}
                label={label}
                tooltip={<InfoTooltip text={tooltip} />}
              />
            ))}
          </div>

          <details className="rounded-md border border-border">
            <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
              Advanced — show generated command
            </summary>
            <pre className="max-h-48 overflow-auto border-t border-border bg-muted p-3 text-xs">{previewCommand}</pre>
          </details>

          {localError ? <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">{localError}</p> : null}

          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={runNow} disabled={createJobMutation.isPending || runMutation.isPending}>
              {action === "push" ? "Send" : action === "pull" ? "Receive" : "Run"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                await navigator.clipboard.writeText(previewCommand);
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

      {asyncRun && jobId !== null ? (
        <InlineJobPanel
          jobId={jobId}
          moduleName="seedbox"
          onRerun={(newJob: ModuleJob) => setJobId(newJob.id)}
        />
      ) : null}

      {!asyncRun && result ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={result.ok ? "success" : "danger"}>{result.ok ? "Completed" : "Failed"}</Badge>
              Result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{result.stdout || "(no output)"}</pre>
            {result.stderr ? <pre className="max-h-72 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{result.stderr}</pre> : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Seedbox Profiles</CardTitle>
          <CardDescription>Add, configure, and switch between seedbox connections.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">Profiles</p>
              <p className="text-2xl font-semibold">{(listQuery.data?.seedboxes ?? []).length}</p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">Default</p>
              <p className="text-sm font-semibold">
                {(listQuery.data?.seedboxes ?? []).find((item) => item.is_default)?.name ?? "-"}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">History Entries</p>
              <p className="text-2xl font-semibold">{(historyQuery.data?.entries ?? []).length}</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm">
              Profile name
              <Input value={addName} onChange={(event) => setAddName(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              rclone connection name
              <Input value={addRemote} onChange={(event) => setAddRemote(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              Base remote folder
              <Input value={addBasePath} onChange={(event) => setAddBasePath(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              Concurrent transfers
              <Input type="number" value={addTransfers} onChange={(event) => setAddTransfers(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              Bandwidth limit (optional)
              <Input value={addBandwidth} onChange={(event) => setAddBandwidth(event.target.value)} placeholder="10M, 500K — blank = unlimited" />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (!addName.trim() || !addRemote.trim()) {
                  setLocalError("Name and rclone remote are required.");
                  return;
                }
                addMutation.mutate({
                  name: addName.trim(),
                  rclone_remote: addRemote.trim(),
                  remote_base_path: addBasePath.trim() || "/",
                  max_concurrent_uploads: Number.parseInt(addTransfers, 10) || 3,
                  bandwidth_limit: addBandwidth.trim() || "",
                });
              }}
            >
              Add
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (!addName.trim()) {
                  setLocalError("Name is required to set default.");
                  return;
                }
                useMutationSeedbox.mutate({ name: addName.trim() });
              }}
            >
              Use Default
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (!addName.trim()) {
                  setLocalError("Name is required to remove.");
                  return;
                }
                removeMutationSeedbox.mutate(addName.trim());
              }}
            >
              Remove
            </Button>
          </div>

          {(listQuery.data?.seedboxes ?? []).length === 0 ? (
            <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">No seedbox profiles yet.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {(listQuery.data?.seedboxes ?? []).map((item) => (
                <div
                  key={item.name}
                  className={`rounded-xl border p-4 shadow-sm ${
                    item.is_default ? "border-emerald-400 bg-emerald-50/40" : "border-border bg-card"
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div>
                      <p className="text-base font-semibold">{item.name}</p>
                      <p className="text-xs text-muted-foreground">{compact(item.rclone_remote)}</p>
                    </div>
                    <Badge variant={item.is_default ? "success" : "secondary"}>
                      {item.is_default ? "Default" : "Profile"}
                    </Badge>
                  </div>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <p>Remote folder: <span className="text-foreground">{compact(item.remote_base_path)}</span></p>
                    <p>Concurrent transfers: <span className="text-foreground">{compact(item.max_concurrent_uploads)}</span></p>
                    <p>Speed limit: <span className="text-foreground">{compact(item.bandwidth_limit) === "-" ? "Unlimited" : compact(item.bandwidth_limit)}</span></p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {!item.is_default ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => useMutationSeedbox.mutate({ name: item.name })}
                      >
                        Set Default
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSeedboxName(item.name);
                        setAction("status");
                      }}
                    >
                      Open Status
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => removeMutationSeedbox.mutate(item.name)}
                    >
                      Remove
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Profile Bindings</CardTitle>
          <CardDescription>Map a Ouro settings profile to a specific seedbox. When that profile is active, this seedbox is used automatically.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {Object.keys(listQuery.data?.default_by_profile ?? {}).length > 0 && (
            <div className="divide-y divide-border rounded-md border border-border">
              {Object.entries(listQuery.data?.default_by_profile ?? {}).map(([profile, sb]) => (
                <div key={profile} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span className="font-medium">{profile}</span>
                  <span className="text-muted-foreground">→</span>
                  <span>{sb}</span>
                </div>
              ))}
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm">
              Ouro profile
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                value={bindProfile}
                onChange={(e) => setBindProfile(e.target.value)}
              >
                <option value="">Select profile…</option>
                {(profilesQuery.data?.profiles ?? []).map((p) => (
                  <option key={p.name} value={p.name}>{p.name}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              Seedbox
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                value={bindSeedbox}
                onChange={(e) => setBindSeedbox(e.target.value)}
              >
                <option value="">Select seedbox…</option>
                {(listQuery.data?.seedboxes ?? []).map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={!bindProfile || !bindSeedbox || useMutationSeedbox.isPending}
            onClick={() => {
              if (!bindProfile || !bindSeedbox) return;
              useMutationSeedbox.mutate({ name: bindSeedbox, profileName: bindProfile });
            }}
          >
            Bind profile → seedbox
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Seedbox History</CardTitle>
          <CardDescription>Readable activity feed by profile.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {(historyQuery.data?.entries ?? []).length === 0 ? (
            <p className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">No History Entries.</p>
          ) : (
            <div className="overflow-auto rounded-md border border-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-3 py-2 font-medium">Time</th>
                    <th className="px-3 py-2 font-medium">Action</th>
                    <th className="px-3 py-2 font-medium">Seedbox</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium">Source</th>
                    <th className="px-3 py-2 font-medium">Destination</th>
                  </tr>
                </thead>
                <tbody>
                  {(historyQuery.data?.entries ?? []).map((entry, index) => {
                    const statusText = compact((entry as Record<string, unknown>).status);
                    const failed = statusText.toLowerCase().includes("fail") || statusText.toLowerCase().includes("error");
                    return (
                      <tr key={`${compact((entry as Record<string, unknown>).timestamp)}-${index}`} className="border-t border-border">
                        <td className="px-3 py-2">{compact((entry as Record<string, unknown>).timestamp)}</td>
                        <td className="px-3 py-2">{compact((entry as Record<string, unknown>).action)}</td>
                        <td className="px-3 py-2">{compact((entry as Record<string, unknown>).seedbox)}</td>
                        <td className="px-3 py-2">
                          <Badge variant={failed ? "danger" : "secondary"}>{statusText}</Badge>
                        </td>
                        <td className="px-3 py-2">{compact((entry as Record<string, unknown>).source)}</td>
                        <td className="px-3 py-2">{compact((entry as Record<string, unknown>).destination)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
