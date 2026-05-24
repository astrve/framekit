import { useMutation, useQuery } from "@tanstack/react-query";
import { CloudUpload, Copy } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getUploadHistory, getUploadState, getUploadTrackerInfo, getUploadTrackers, runModule, setUploadState } from "@/lib/api/endpoints";
import type { RunModuleResult, UploadState } from "@/lib/api/schemas";

type UploadAction = "setup" | "list-trackers" | "show-tracker" | "run" | "history" | "enable" | "disable";

export function UploadPage() {
  const [action, setAction] = useState<UploadAction>("list-trackers");
  const [tracker, setTracker] = useState("");
  const [torrentPath, setTorrentPath] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const runMutation = useMutation({
    mutationFn: runModule,
  });
  const stateQuery = useQuery({
    queryKey: ["upload-state"],
    queryFn: getUploadState,
  });
  const historyQuery = useQuery({
    queryKey: ["upload-history"],
    queryFn: () => getUploadHistory(20),
  });
  const trackersQuery = useQuery({
    queryKey: ["upload-trackers-page"],
    queryFn: getUploadTrackers,
  });
  const trackerInfoQuery = useQuery({
    queryKey: ["upload-tracker-info", tracker],
    queryFn: () => getUploadTrackerInfo(tracker.trim()),
    enabled: tracker.trim().length > 0,
  });
  const setStateMutation = useMutation({
    mutationFn: setUploadState,
    onSuccess: (state: UploadState) => {
      stateQuery.refetch().catch(() => undefined);
      setLocalError(null);
      if (state.enabled) {
        setAction("enable");
      } else {
        setAction("disable");
      }
    },
  });

  const buildArgs = (): string => {
    const args: string[] = [action];
    if (action === "show-tracker" && tracker.trim()) {
      args.push(`"${tracker.trim()}"`);
    }
    if (action === "run") {
      if (torrentPath.trim()) {
        args.push(`"${torrentPath.trim()}"`);
      }
      if (tracker.trim()) {
        args.push("--tracker", `"${tracker.trim()}"`);
      }
      if (name.trim()) {
        args.push("--name", `"${name.trim()}"`);
      }
      if (description.trim()) {
        args.push("--description", `"${description.trim()}"`);
      }
      if (dryRun) {
        args.push("--dry-run");
      }
    }
    if (action === "history") {
      args.push("--limit", "20");
    }
    return args.join(" ");
  };

  const result: RunModuleResult | null = runMutation.data ?? null;

  const validateAction = (): string | null => {
    if (action === "show-tracker" && !tracker.trim()) {
      return "show-tracker requiert le nom tracker.";
    }
    if (action === "run") {
      if (!torrentPath.trim()) {
        return "run requiert torrent/release path.";
      }
      if (!tracker.trim()) {
        return "run requiert --tracker.";
      }
    }
    return null;
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Upload</h1>
        <p className="mt-1 text-sm text-muted-foreground">Couverture core V1: setup/list/show/run/history/enable/disable.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudUpload className="h-4 w-4 text-primary" />
            Action
          </CardTitle>
          <CardDescription>Construit commande `framekit upload ...`</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm" htmlFor="upload-action">
              Action
              <select
                id="upload-action"
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={action}
                onChange={(event) => {
                  setAction(event.target.value as UploadAction);
                  if (event.target.value !== "run") {
                    setName("");
                    setDescription("");
                    setDryRun(true);
                  }
                }}
              >
                <option value="setup">setup</option>
                <option value="list-trackers">list-trackers</option>
                <option value="show-tracker">show-tracker</option>
                <option value="run">run</option>
                <option value="history">history</option>
                <option value="enable">enable</option>
                <option value="disable">disable</option>
              </select>
            </label>
            <label className="space-y-1 text-sm" htmlFor="upload-tracker">
              Tracker
              <Input id="upload-tracker" value={tracker} onChange={(e) => setTracker(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm md:col-span-2" htmlFor="upload-torrent-path">
              Torrent path / release path (run)
              <Input id="upload-torrent-path" value={torrentPath} onChange={(e) => setTorrentPath(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm" htmlFor="upload-name">
              Name (run)
              <Input id="upload-name" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm" htmlFor="upload-description">
              Description (run)
              <Input id="upload-description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
          </div>

          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
            dry-run
          </label>

          <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            framekit upload {buildArgs()}
          </pre>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => {
                const issue = validateAction();
                setLocalError(issue);
                if (issue) {
                  return;
                }
                runMutation.mutate({
                  module: "upload",
                  args_text: buildArgs(),
                  dry_run: false,
                  auto_yes: false,
                  confirm_destructive: true,
                });
              }}
            >
              Exécuter
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                await navigator.clipboard.writeText(`framekit upload ${buildArgs()}`.trim());
                setCopied(true);
                setTimeout(() => setCopied(false), 1000);
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              {copied ? "Copié" : "Copier commande"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const current = stateQuery.data;
                if (!current) {
                  return;
                }
                setStateMutation.mutate({
                  enabled: !current.enabled,
                  auto_upload: current.auto_upload,
                });
              }}
            >
              Toggle enabled
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAction("list-trackers");
                setTracker("");
                setTorrentPath("");
                setName("");
                setDescription("");
                setDryRun(true);
                setLocalError(null);
              }}
            >
              Reset
            </Button>
          </div>

          {localError ? (
            <p className="rounded-md border border-rose-400/60 bg-rose-500/10 p-3 text-sm text-rose-800">
              {localError}
            </p>
          ) : null}
          {stateQuery.data ? (
            <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
              Upload enabled: <strong>{stateQuery.data.enabled ? "yes" : "no"}</strong> | auto-upload:{" "}
              <strong>{stateQuery.data.auto_upload ? "yes" : "no"}</strong>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Trackers configured</CardTitle>
          <CardDescription>Liste + détail tracker sélectionné.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap gap-2">
            {(trackersQuery.data?.trackers ?? []).map((item) => (
              <Button key={item.name} type="button" size="sm" variant="outline" onClick={() => setTracker(item.name)}>
                {item.name}
              </Button>
            ))}
          </div>
          <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            {JSON.stringify(trackersQuery.data?.trackers ?? [], null, 2)}
          </pre>
          <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            {JSON.stringify(trackerInfoQuery.data?.tracker ?? {}, null, 2)}
          </pre>
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
            <CardDescription>Return code: {result.returncode}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Badge variant={result.ok ? "success" : "danger"}>{result.ok ? "success" : "failed"}</Badge>
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
              {result.stdout || "(stdout empty)"}
            </pre>
            {result.stderr ? (
              <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                {result.stderr}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Upload history</CardTitle>
          <CardDescription>20 dernières entrées.</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            {JSON.stringify(historyQuery.data?.entries ?? [], null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
