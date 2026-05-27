import { useMutation, useQuery } from "@tanstack/react-query";
import { Copy, Play } from "lucide-react";
import { type Dispatch, type SetStateAction, useEffect, useMemo, useState } from "react";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { createModuleJob, getModulesResources, getSettingsSummary, runModule } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";

const PIPELINE_MODULES = [
  "renamer",
  "cleanmkv",
  "metadata",
  "nfo",
  "torrent",
  "prez",
  "encode",
  "screenshot",
  "seedbox",
  "upload",
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

export function PipelinePage() {
  const resourcesQuery = useQuery({ queryKey: ["modules-resources"], queryFn: getModulesResources });
  const settingsQuery = useQuery({ queryKey: ["settings-summary"], queryFn: getSettingsSummary });
  const [releasePath, setReleasePath] = useState("");
  const [nfoLocale, setNfoLocale] = useState<"auto" | "en" | "fr" | "es">("auto");
  const [announce, setAnnounce] = useState("");
  const [pipelinePreset, setPipelinePreset] = useState("");
  const [prezPreset, setPrezPreset] = useState("");
  const [removeTermInput, setRemoveTermInput] = useState("");
  const [removeTerms, setRemoveTerms] = useState<string[]>([]);
  const settingsEnabledModules = (() => {
    const s = settingsQuery.data?.settings;
    const m = typeof s?.["modules"] === "object" && s["modules"] !== null ? (s["modules"] as Record<string, unknown>) : undefined;
    const p = typeof m?.["pipeline"] === "object" && m["pipeline"] !== null ? (m["pipeline"] as Record<string, unknown>) : undefined;
    return p?.["enabled_modules"];
  })();
  const [enabledModules, setEnabledModules] = useState<string[]>(["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"]);

  useEffect(() => {
    if (Array.isArray(settingsEnabledModules) && settingsEnabledModules.length > 0) {
      setEnabledModules(settingsEnabledModules as string[]);
    }
  }, [settingsEnabledModules]);
  const [autoMode, setAutoMode] = useState(true);
  const [previewMode, setPreviewMode] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [selectTemplates, setSelectTemplates] = useState(false);
  const [selectTerms, setSelectTerms] = useState(false);
  const [confirmDestructive, setConfirmDestructive] = useState(true);
  const [asyncRun, setAsyncRun] = useState(true);
  const [copied, setCopied] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job) => setJobId(job.id),
  });
  const result: RunModuleResult | null = runMutation.data ?? null;

  const argsText = useMemo(() => {
    const args: string[] = [];
    const pathArg = quoteArg(releasePath);
    if (pathArg) {
      args.push(pathArg);
    }
    if (nfoLocale !== "auto") {
      args.push("--nfo-locale", nfoLocale);
    }
    if (announce.trim()) {
      args.push("--announce", quoteArg(announce));
    }
    if (pipelinePreset.trim()) {
      args.push("--pipeline-preset", quoteArg(pipelinePreset));
    }
    if (prezPreset.trim()) {
      args.push("--preset", quoteArg(prezPreset));
    }
    if (previewMode) {
      args.push("--preview");
    }
    if (dryRun) {
      args.push("--dry-run");
    }
    if (autoMode) {
      args.push("--auto");
    }
    if (selectTemplates) {
      args.push("--select-templates");
    }
    if (selectTerms) {
      args.push("--select-terms");
    }
    for (const item of removeTerms) {
      args.push("--remove-term", quoteArg(item));
    }
    for (const moduleName of enabledModules) {
      args.push("--modules", moduleName);
    }
    return args.join(" ").trim();
  }, [announce, autoMode, dryRun, enabledModules, nfoLocale, pipelinePreset, prezPreset, previewMode, releasePath, removeTerms, selectTemplates, selectTerms]);

  const previewCommand = useMemo(() => `framekit pipeline ${argsText}`.trim(), [argsText]);

  function toggleModule(moduleName: string, checked: boolean) {
    if (checked) {
      setEnabledModules((prev) => Array.from(new Set([...prev, moduleName])));
      return;
    }
    setEnabledModules((prev) => prev.filter((item) => item !== moduleName));
  }

  function runNow() {
    if (!releasePath.trim()) {
      setLocalError("Release Path Required.");
      return;
    }
    if (!argsText.trim()) {
      setLocalError("No Command Options Selected.");
      return;
    }
    setLocalError(null);
    const payload = {
      module: "pipeline",
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
        <h1 className="text-2xl font-semibold tracking-tight">Pipeline</h1>
        <p className="mt-1 text-sm text-muted-foreground">Process a release end-to-end with your chosen steps.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Configure Pipeline
          </CardTitle>
          <CardDescription>Set your options — no command-line knowledge needed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm md:col-span-2">
              Release folder
              <Input value={releasePath} placeholder="C:/Releases/My.Release" onChange={(event) => setReleasePath(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              NFO language
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={nfoLocale} onChange={(event) => setNfoLocale(event.target.value as "auto" | "en" | "fr" | "es")}>
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
          </div>

          <div className="rounded-md border border-border p-4">
            <p className="mb-3 text-sm font-medium">Steps to run</p>
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {PIPELINE_MODULES.map((item) => {
                const checked = enabledModules.includes(item);
                return (
                  <Toggle
                    key={item}
                    checked={checked}
                    onChange={(v) => toggleModule(item, v)}
                    label={item}
                    className="capitalize"
                  />
                );
              })}
            </div>
          </div>

          <div className="rounded-md border border-border p-4">
            <p className="mb-2 text-sm font-medium">Title terms to remove</p>
            <div className="flex gap-2">
              <Input value={removeTermInput} placeholder="e.g. REPACK" onChange={(event) => setRemoveTermInput(event.target.value)} />
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const term = removeTermInput.trim();
                  if (!term) return;
                  setRemoveTerms((prev) => (prev.includes(term) ? prev : [...prev, term]));
                  setRemoveTermInput("");
                }}
              >
                Add
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {removeTerms.map((term) => (
                <button
                  key={term}
                  type="button"
                  className="rounded-full border border-border px-3 py-1 text-xs transition-colors hover:border-destructive/60 hover:text-destructive"
                  onClick={() => setRemoveTerms((prev) => prev.filter((item) => item !== term))}
                >
                  {term} ×
                </button>
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
              [previewMode, setPreviewMode, "Preview only (no changes)"],
              [dryRun, setDryRun, "Simulation (no file writes)"],
              [selectTemplates, setSelectTemplates, "Choose templates interactively"],
              [selectTerms, setSelectTerms, "Choose terms interactively"],
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
              Run Pipeline
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
          moduleName="pipeline"
          onRerun={(newJob: ModuleJob) => setJobId(newJob.id)}
        />
      ) : null}

      {!asyncRun && result ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={result.ok ? "success" : "danger"}>{result.ok ? "Completed" : "Failed"}</Badge>
              Pipeline result
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
