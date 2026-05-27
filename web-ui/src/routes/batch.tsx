import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Copy, Play } from "lucide-react";
import { type Dispatch, type SetStateAction, useMemo, useState } from "react";

import { RunTimeline } from "@/components/modules/run-timeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { createModuleJob, getModuleJob, getModulesResources, runModule } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";
import { runTimeline } from "@/lib/progress";

const BATCH_MODULES = [
  "renamer",
  "cleanmkv",
  "metadata",
  "nfo",
  "torrent",
  "prez",
  "encode",
  "screenshot",
  "seedbox",
  "rename-parent",
] as const;

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

export function BatchPage() {
  const navigate = useNavigate();
  const resourcesQuery = useQuery({ queryKey: ["modules-resources"], queryFn: getModulesResources });
  const [parentPath, setParentPath] = useState("");
  const [pipelinePreset, setPipelinePreset] = useState("");
  const [prezPreset, setPrezPreset] = useState("");
  const [locale, setLocale] = useState<"auto" | "en" | "fr" | "es">("auto");
  const [announce, setAnnounce] = useState("");
  const [enabledModules, setEnabledModules] = useState<string[]>(["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"]);
  const [autoMode, setAutoMode] = useState(true);
  const [manualMode, setManualMode] = useState(false);
  const [dashboard, setDashboard] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [confirmDestructive, setConfirmDestructive] = useState(true);
  const [asyncRun, setAsyncRun] = useState(true);
  const [copied, setCopied] = useState(false);
  const [lastJob, setLastJob] = useState<ModuleJob | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({ mutationFn: createModuleJob, onSuccess: (job) => setLastJob(job) });
  const result: RunModuleResult | null = runMutation.data ?? null;

  const jobPollQuery = useQuery({
    queryKey: ["batch-job", lastJob?.id],
    queryFn: ({ queryKey }) => getModuleJob(queryKey[1] as string),
    enabled: !!lastJob,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return !status || ["completed", "failed", "cancelled"].includes(status) ? false : 1500;
    },
  });
  const timelineSource = jobPollQuery.data ?? lastJob ?? null;

  const argsText = useMemo(() => {
    const args: string[] = [];
    const pathArg = quoteArg(parentPath);
    if (pathArg) {
      args.push(pathArg);
    }
    if (autoMode) {
      args.push("--auto");
    }
    if (manualMode) {
      args.push("--manual");
    }
    if (dashboard) {
      args.push("--dashboard");
    }
    if (dryRun) {
      args.push("--dry-run");
    }
    if (pipelinePreset.trim()) {
      args.push("--pipeline-preset", quoteArg(pipelinePreset));
    }
    if (prezPreset.trim()) {
      args.push("--preset", quoteArg(prezPreset));
    }
    if (locale !== "auto") {
      args.push("--locale", locale);
    }
    if (announce.trim()) {
      args.push("--announce", quoteArg(announce));
    }
    for (const moduleName of enabledModules) {
      args.push("--modules", moduleName);
    }
    return args.join(" ").trim();
  }, [announce, autoMode, dashboard, dryRun, enabledModules, locale, manualMode, parentPath, pipelinePreset, prezPreset]);

  const previewCommand = useMemo(() => `framekit batch ${argsText}`.trim(), [argsText]);

  function toggleModule(moduleName: string, checked: boolean) {
    if (checked) {
      setEnabledModules((prev) => Array.from(new Set([...prev, moduleName])));
      return;
    }
    setEnabledModules((prev) => prev.filter((item) => item !== moduleName));
  }

  function runNow() {
    if (!parentPath.trim()) {
      setLocalError("Parent Path Required.");
      return;
    }
    setLocalError(null);
    const payload = {
      module: "batch",
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
        <h1 className="text-2xl font-semibold tracking-tight">Batch Processing</h1>
        <p className="mt-1 text-sm text-muted-foreground">Run the full pipeline across an entire folder of releases.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Progress</CardTitle>
          <CardDescription>Queued · Running · Done</CardDescription>
        </CardHeader>
        <CardContent>
          <RunTimeline items={runTimeline(timelineSource)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Configure Batch
          </CardTitle>
          <CardDescription>Set your options — no command-line knowledge needed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm md:col-span-2">
              Releases folder
              <Input value={parentPath} placeholder="C:/Releases" onChange={(event) => setParentPath(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              Workflow profile
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={pipelinePreset} onChange={(event) => setPipelinePreset(event.target.value)}>
                <option value="">— Default —</option>
                {(resourcesQuery.data?.pipeline_presets ?? []).map((item) => (
                  <option key={item.name} value={item.name}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              Presentation profile
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={prezPreset} onChange={(event) => setPrezPreset(event.target.value)}>
                <option value="">— Default —</option>
                {(resourcesQuery.data?.prez_presets ?? []).map((item) => (
                  <option key={item.name} value={item.name}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              NFO language
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={locale} onChange={(event) => setLocale(event.target.value as "auto" | "en" | "fr" | "es")}>
                <option value="auto">Auto-detect</option>
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="es">Spanish</option>
              </select>
            </label>
            <label className="space-y-1 text-sm">
              Tracker announce URL
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={announce} onChange={(event) => setAnnounce(event.target.value)}>
                <option value="">— Select tracker —</option>
                {(resourcesQuery.data?.announces ?? []).map((item) => (
                  <option key={item.value} value={item.value}>{item.value}{item.is_selected ? " ✓" : ""}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="rounded-md border border-border p-4">
            <p className="mb-3 text-sm font-medium">Steps to run</p>
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {BATCH_MODULES.map((item) => (
                <Toggle
                  key={item}
                  checked={enabledModules.includes(item)}
                  onChange={(v) => toggleModule(item, v)}
                  label={item}
                  className="capitalize"
                />
              ))}
            </div>
          </div>

          {(resourcesQuery.data?.banner_previews ?? []).length > 0 ? (
            <div className="rounded-md border border-border p-4">
              <p className="mb-2 text-sm font-medium">Banner assets</p>
              <div className="grid gap-2 md:grid-cols-3">
                {(resourcesQuery.data?.banner_previews ?? []).slice(0, 12).map((banner) => (
                  <Button key={banner.name} type="button" variant="outline" size="sm" onClick={() => window.open(banner.preview_url, "_blank", "noopener,noreferrer")}>
                    Preview {banner.name}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-4">
            {([
              [autoMode, setAutoMode, "Automatic mode"],
              [manualMode, setManualMode, "Manual confirmation"],
              [dashboard, setDashboard, "Show live dashboard"],
              [dryRun, setDryRun, "Simulation (no file writes)"],
              [confirmDestructive, setConfirmDestructive, "Allow file changes"],
              [asyncRun, setAsyncRun, "Run in background"],
            ] as Array<[boolean, Dispatch<SetStateAction<boolean>>, string]>).map(([checked, setter, label]) => (
              <Toggle key={label} checked={checked} onChange={setter} label={label} />
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
              <Play className="mr-2 h-4 w-4" />
              Run Batch
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
            {lastJob ? (
              <Button type="button" variant="outline" onClick={() => void navigate({ to: "/modules/$jobId", params: { jobId: lastJob.id } })}>
                View Job
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={result.ok ? "success" : "danger"}>{result.ok ? "Completed" : "Failed"}</Badge>
              Batch result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{result.stdout || "(no output)"}</pre>
            {result.stderr ? <pre className="max-h-72 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{result.stderr}</pre> : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
