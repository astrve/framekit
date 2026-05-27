import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Clock3, Play, RotateCcw, Square } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch, type UseFormSetValue } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RunTimeline } from "@/components/modules/run-timeline";
import { Input } from "@/components/ui/input";
import { CliCommandForm } from "@/components/modules/cli-command-form";
import { ApiError } from "@/lib/api/client";
import {
  cancelModuleJob,
  createModuleJob,
  getModuleJob,
  getModulesCatalog,
  getModulesCliSpec,
  getModulesPresets,
  listModuleJobs,
  rerunModuleJob,
  runModule,
} from "@/lib/api/endpoints";
import type { CliCommandSpec, ModuleJob, RunModuleResult } from "@/lib/api/schemas";
import { buildArgsFromState, initValuesFromSpec } from "@/lib/cli-form";
import { runTimeline } from "@/lib/progress";

const formSchema = z.object({
  module: z.string().min(1),
  args_text: z.string(),
  dry_run: z.boolean(),
  auto_yes: z.boolean(),
  confirm_destructive: z.boolean(),
  async_run: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;
type JobStatusFilter = "all" | "pending" | "running" | "completed" | "failed" | "cancelled";
type MetadataMode = "inherit" | "enable" | "disable";

const PIPELINE_BATCH_MODULES = [
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
  "upload",
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

function buildPipelineArgs(input: {
  path: string;
  preview: boolean;
  dryRun: boolean;
  auto: boolean;
  allModules: boolean;
  withMetadata: MetadataMode;
  pipelinePreset: string;
  prezPreset: string;
  nfoLocale: string;
  announce: string;
  modulesCsv: string;
}): string {
  const args: string[] = [];
  const pathArg = quoteArg(input.path);
  if (pathArg) {
    args.push(pathArg);
  }
  if (input.preview) {
    args.push("--preview");
  }
  if (input.dryRun) {
    args.push("--dry-run");
  }
  if (input.auto) {
    args.push("--auto");
  }
  if (input.allModules) {
    args.push("--all");
  }
  if (input.withMetadata === "enable") {
    args.push("--with-metadata");
  } else if (input.withMetadata === "disable") {
    args.push("--no-metadata");
  }
  const pipelinePreset = input.pipelinePreset.trim();
  if (pipelinePreset) {
    args.push("--pipeline-preset", quoteArg(pipelinePreset));
  }
  const prezPreset = input.prezPreset.trim();
  if (prezPreset) {
    args.push("--preset", quoteArg(prezPreset));
  }
  const nfoLocale = input.nfoLocale.trim();
  if (nfoLocale) {
    args.push("--nfo-locale", quoteArg(nfoLocale));
  }
  const announce = input.announce.trim();
  if (announce) {
    args.push("--announce", quoteArg(announce));
  }
  const modules = input.modulesCsv
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  for (const moduleName of modules) {
    args.push("--modules", quoteArg(moduleName));
  }
  return args.join(" ").trim();
}

function buildBatchArgs(input: {
  parentPath: string;
  auto: boolean;
  manual: boolean;
  dashboard: "inherit" | "enable" | "disable";
  pipelinePreset: string;
  nfoLocale: string;
  announce: string;
  modulesCsv: string;
  allModules: boolean;
}): string {
  const args: string[] = [];
  const parentPathArg = quoteArg(input.parentPath);
  if (parentPathArg) {
    args.push(parentPathArg);
  }
  if (input.auto) {
    args.push("--auto");
  }
  if (input.manual) {
    args.push("--manual");
  }
  if (input.dashboard === "enable") {
    args.push("--dashboard");
  } else if (input.dashboard === "disable") {
    args.push("--no-dashboard");
  }
  const pipelinePreset = input.pipelinePreset.trim();
  if (pipelinePreset) {
    args.push("--pipeline-preset", quoteArg(pipelinePreset));
  }
  const nfoLocale = input.nfoLocale.trim();
  if (nfoLocale) {
    args.push("--locale", quoteArg(nfoLocale));
  }
  const announce = input.announce.trim();
  if (announce) {
    args.push("--announce", quoteArg(announce));
  }
  if (input.allModules) {
    args.push("--all");
  }
  const batchModules = input.modulesCsv.split(",").map((m) => m.trim()).filter(Boolean);
  for (const moduleName of batchModules) {
    args.push("--modules", quoteArg(moduleName));
  }
  return args.join(" ").trim();
}

function objectPayload(payload: unknown): Record<string, unknown> | null {
  if (!payload || Array.isArray(payload) || typeof payload !== "object") {
    return null;
  }
  return payload as Record<string, unknown>;
}

function renderStructuredPayload(payload: unknown) {
  const obj = objectPayload(payload);
  if (!obj) {
    return null;
  }

  const checksRaw = obj["checks"];
  const checks =
    Array.isArray(checksRaw) && checksRaw.every((item) => typeof item === "object" && item !== null)
      ? (checksRaw as Array<Record<string, unknown>>)
      : [];

  if (checks.length > 0) {
    const ok = checks.filter((item) => item["status"] === "ok").length;
    const warn = checks.filter((item) => item["status"] === "warn").length;
    const err = checks.filter((item) => item["status"] === "err").length;
    return (
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Badge variant="success">ok: {ok}</Badge>
          <Badge variant="warning">warn: {warn}</Badge>
          <Badge variant="danger">err: {err}</Badge>
        </div>
        <div className="space-y-2">
          {checks.slice(0, 25).map((item, index) => (
            <div
              key={`${String(item["section"])}-${String(item["name"])}-${index}`}
              className="grid gap-2 rounded-md border border-border p-3 md:grid-cols-[140px_1fr_auto]"
            >
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {String(item["section"] ?? "-")}
              </p>
              <p className="text-sm">
                {String(item["name"] ?? "-")}: {String(item["detail"] ?? "-")}
              </p>
              <Badge
                variant={
                  item["status"] === "ok"
                    ? "success"
                    : item["status"] === "warn"
                      ? "warning"
                      : "danger"
                }
              >
                {String(item["status"] ?? "unknown")}
              </Badge>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {Object.entries(obj)
        .slice(0, 12)
        .map(([key, value]) => (
          <div key={key} className="rounded-md border border-border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{key}</p>
            <p className="mt-1 text-sm">
              {typeof value === "string" ? value : JSON.stringify(value)}
            </p>
          </div>
        ))}
    </div>
  );
}

function resultFromJob(job: ModuleJob | null | undefined): RunModuleResult | null {
  return job?.result ?? null;
}

function applyJobRequestToForm(job: ModuleJob, setValue: UseFormSetValue<FormValues>) {
  const request = job.request;
  const moduleValue = request["module"];
  const argsTextValue = request["args_text"];
  const dryRunValue = request["dry_run"];
  const autoYesValue = request["auto_yes"];
  const confirmDestructiveValue = request["confirm_destructive"];
  if (typeof moduleValue === "string") {
    setValue("module", moduleValue);
  }
  if (typeof argsTextValue === "string") {
    setValue("args_text", argsTextValue);
  }
  if (typeof dryRunValue === "boolean") {
    setValue("dry_run", dryRunValue);
  }
  if (typeof autoYesValue === "boolean") {
    setValue("auto_yes", autoYesValue);
  }
  if (typeof confirmDestructiveValue === "boolean") {
    setValue("confirm_destructive", confirmDestructiveValue);
  }
}

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
  const [jobsLimit, setJobsLimit] = useState(20);
  const [statusFilter, setStatusFilter] = useState<JobStatusFilter>("all");
  const [searchText, setSearchText] = useState("");
  const [pipelinePath, setPipelinePath] = useState("");
  const [pipelinePreview, setPipelinePreview] = useState(true);
  const [pipelineDryRun, setPipelineDryRun] = useState(false);
  const [pipelineAuto, setPipelineAuto] = useState(false);
  const [pipelineAllModules, setPipelineAllModules] = useState(false);
  const [pipelineWithMetadata, setPipelineWithMetadata] = useState<MetadataMode>("inherit");
  const [pipelinePreset, setPipelinePreset] = useState("");
  const [pipelinePrezPreset, setPipelinePrezPreset] = useState("");
  const [pipelineLocale, setPipelineLocale] = useState("");
  const [pipelineAnnounce, setPipelineAnnounce] = useState("");
  const [pipelineModulesCsv, setPipelineModulesCsv] = useState("");
  const [batchParentPath, setBatchParentPath] = useState("");
  const [batchAuto, setBatchAuto] = useState(true);
  const [batchManual, setBatchManual] = useState(false);
  const [batchDashboard, setBatchDashboard] = useState<"inherit" | "enable" | "disable">("inherit");
  const [batchPipelinePreset, setBatchPipelinePreset] = useState("");
  const [batchLocale, setBatchLocale] = useState("");
  const [batchAnnounce, setBatchAnnounce] = useState("");
  const [batchModulesCsv, setBatchModulesCsv] = useState("");
  const [batchAllModules, setBatchAllModules] = useState(false);
  const catalogQuery = useQuery({
    queryKey: ["modules-catalog"],
    queryFn: getModulesCatalog,
  });
  const presetsQuery = useQuery({
    queryKey: ["modules-presets"],
    queryFn: getModulesPresets,
  });
  const cliSpecQuery = useQuery({
    queryKey: ["modules-cli-spec"],
    queryFn: getModulesCliSpec,
  });
  const jobsQuery = useQuery({
    queryKey: ["modules-jobs", jobsLimit],
    queryFn: () => listModuleJobs(jobsLimit),
    refetchInterval: 3000,
  });

  const runMutation = useMutation({
    mutationFn: runModule,
  });
  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
  });
  const cancelJobMutation = useMutation({
    mutationFn: cancelModuleJob,
    onSuccess: (job) => {
      setSelectedJobId(job.id);
      void jobStatusQuery.refetch();
      void jobsQuery.refetch();
    },
  });
  const rerunJobMutation = useMutation({
    mutationFn: rerunModuleJob,
    onSuccess: (job) => {
      setSelectedJobId(job.id);
      void jobStatusQuery.refetch();
      void jobsQuery.refetch();
    },
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      module: "inspect",
      args_text: "",
      dry_run: true,
      auto_yes: false,
      confirm_destructive: false,
      async_run: true,
    },
  });

  const activeJobId = selectedJobId;
  const asyncRunValue = useWatch({
    control: form.control,
    name: "async_run",
  });
  const jobStatusQuery = useQuery({
    queryKey: ["module-job-status", activeJobId],
    queryFn: () => getModuleJob(activeJobId as string),
    enabled: Boolean(activeJobId),
    refetchInterval: (query) => {
      const status = (query.state.data as ModuleJob | undefined)?.status;
      if (status === "pending" || status === "running") {
        return 1500;
      }
      return false;
    },
  });

  const onSubmit = (values: FormValues): void => {
    if (values.async_run) {
      createJobMutation.mutate(
        {
          module: values.module,
          args_text: values.args_text,
          dry_run: values.dry_run,
          auto_yes: values.auto_yes,
          confirm_destructive: values.confirm_destructive,
        },
        {
          onSuccess: (job) => {
            setSelectedJobId(job.id);
            jobsQuery.refetch().catch(() => undefined);
          },
        },
      );
      return;
    }
    runMutation.mutate({
      module: values.module,
      args_text: values.args_text,
      dry_run: values.dry_run,
      auto_yes: values.auto_yes,
      confirm_destructive: values.confirm_destructive,
    });
    setSelectedJobId(null);
  };

  const selectedResult =
    asyncRunValue || activeJobId
      ? resultFromJob(jobStatusQuery.data)
      : runMutation.data ?? null;
  const structuredResult =
    selectedResult?.parsed_kind === "json"
      ? renderStructuredPayload(selectedResult.parsed_payload)
      : null;
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
  const mutationError =
    runMutation.error ?? createJobMutation.error ?? cancelJobMutation.error ?? rerunJobMutation.error;
  const moduleName = form.watch("module");
  const selectedCommand = useMemo<CliCommandSpec | null>(() => {
    return (cliSpecQuery.data?.modules ?? []).find((item) => item.name === moduleName) ?? null;
  }, [cliSpecQuery.data?.modules, moduleName]);
  const [commandValues, setCommandValues] = useState<Record<string, unknown>>({});
  useEffect(() => {
    if (!selectedCommand) {
      return;
    }
    const next = initValuesFromSpec(selectedCommand);
    setCommandValues(next);
    form.setValue("args_text", buildArgsFromState(selectedCommand, next));
  }, [selectedCommand, form]);

  const canBuildFromSpec = selectedCommand !== null && selectedCommand.parameters.length > 0;

  const dryRunWatched = form.watch("dry_run");
  const autoYesWatched = form.watch("auto_yes");
  const confirmDestructiveWatched = form.watch("confirm_destructive");

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Configuration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Advanced command builder and execution center. Use this page to configure and run any CLI module when dedicated pages are not enough.
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Pipeline &amp; Batch Builders
          </CardTitle>
          <CardDescription>Build command arguments for complex workflows without memorizing flags.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-3 rounded-lg border border-border p-4">
            <p className="text-sm font-medium">Pipeline</p>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-1 text-sm md:col-span-2" htmlFor="pipeline-path">
                Release folder
                <Input
                  id="pipeline-path"
                  placeholder="C:/Releases/My.Release"
                  value={pipelinePath}
                  onChange={(event) => { setPipelinePath(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="pipeline-preset">
                Workflow profile
                <Input
                  id="pipeline-preset"
                  placeholder="films"
                  value={pipelinePreset}
                  onChange={(event) => { setPipelinePreset(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="pipeline-prez-preset">
                Presentation profile
                <Input
                  id="pipeline-prez-preset"
                  placeholder="default"
                  value={pipelinePrezPreset}
                  onChange={(event) => { setPipelinePrezPreset(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="pipeline-locale">
                NFO language
                <Input
                  id="pipeline-locale"
                  placeholder="fr"
                  value={pipelineLocale}
                  onChange={(event) => { setPipelineLocale(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="pipeline-announce">
                Announce URL
                <Input
                  id="pipeline-announce"
                  placeholder="https://tracker/announce"
                  value={pipelineAnnounce}
                  onChange={(event) => { setPipelineAnnounce(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm md:col-span-2" htmlFor="pipeline-modules-csv">
                Steps to run (comma-separated)
                <Input
                  id="pipeline-modules-csv"
                  placeholder={PIPELINE_BATCH_MODULES.join(",")}
                  value={pipelineModulesCsv}
                  onChange={(event) => { setPipelineModulesCsv(event.target.value); }}
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              {([
                [pipelinePreview, setPipelinePreview, "Preview only"],
                [pipelineDryRun, setPipelineDryRun, "Simulation (no file writes)"],
                [pipelineAuto, setPipelineAuto, "Automatic"],
                [pipelineAllModules, setPipelineAllModules, "All modules"],
              ] as Array<[boolean, (v: boolean) => void, string]>).map(([checked, setter, label]) => (
                <label key={label} className="inline-flex cursor-pointer items-center gap-2 text-sm">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={checked}
                    onClick={() => setter(!checked)}
                    className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors ${checked ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background hover:border-primary/60"}`}
                  >
                    {checked ? <span className="text-[10px] font-bold leading-none">✓</span> : null}
                  </button>
                  {label}
                </label>
              ))}
              <label className="inline-flex items-center gap-2 text-sm">
                Metadata
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 text-sm"
                  value={pipelineWithMetadata}
                  onChange={(event) => { setPipelineWithMetadata(event.target.value as MetadataMode); }}
                >
                  <option value="inherit">Default</option>
                  <option value="enable">Include metadata</option>
                  <option value="disable">Exclude metadata</option>
                </select>
              </label>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const args = buildPipelineArgs({
                  path: pipelinePath,
                  preview: pipelinePreview,
                  dryRun: pipelineDryRun,
                  auto: pipelineAuto,
                  allModules: pipelineAllModules,
                  withMetadata: pipelineWithMetadata,
                  pipelinePreset,
                  prezPreset: pipelinePrezPreset,
                  nfoLocale: pipelineLocale,
                  announce: pipelineAnnounce,
                  modulesCsv: pipelineModulesCsv,
                });
                form.setValue("module", "pipeline");
                form.setValue("args_text", args);
                form.setValue("confirm_destructive", true);
                form.setValue("dry_run", pipelineDryRun);
              }}
            >
              Fill Pipeline Form
            </Button>
          </div>

          <div className="space-y-3 rounded-lg border border-border p-4">
            <p className="text-sm font-medium">Batch</p>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-1 text-sm md:col-span-2" htmlFor="batch-parent-path">
                Releases folder
                <Input
                  id="batch-parent-path"
                  placeholder="C:/Releases"
                  value={batchParentPath}
                  onChange={(event) => { setBatchParentPath(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="batch-pipeline-preset">
                Workflow profile
                <Input
                  id="batch-pipeline-preset"
                  placeholder="films"
                  value={batchPipelinePreset}
                  onChange={(event) => { setBatchPipelinePreset(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="batch-locale">
                NFO language
                <Input
                  id="batch-locale"
                  placeholder="auto | en | fr | es"
                  value={batchLocale}
                  onChange={(event) => { setBatchLocale(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="batch-announce">
                Announce URL
                <Input
                  id="batch-announce"
                  placeholder="https://tracker/announce"
                  value={batchAnnounce}
                  onChange={(event) => { setBatchAnnounce(event.target.value); }}
                />
              </label>
              <label className="space-y-1 text-sm" htmlFor="batch-modules-csv">
                Steps to run (comma-separated)
                <Input
                  id="batch-modules-csv"
                  placeholder={PIPELINE_BATCH_MODULES.join(",")}
                  value={batchModulesCsv}
                  onChange={(event) => { setBatchModulesCsv(event.target.value); }}
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              {([
                [batchAuto, setBatchAuto, "Automatic"],
                [batchManual, setBatchManual, "Manual confirmation"],
                [batchAllModules, setBatchAllModules, "All modules"],
              ] as Array<[boolean, (v: boolean) => void, string]>).map(([checked, setter, label]) => (
                <label key={label} className="inline-flex cursor-pointer items-center gap-2 text-sm">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={checked}
                    onClick={() => setter(!checked)}
                    className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors ${checked ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background hover:border-primary/60"}`}
                  >
                    {checked ? <span className="text-[10px] font-bold leading-none">✓</span> : null}
                  </button>
                  {label}
                </label>
              ))}
              <label className="inline-flex items-center gap-2 text-sm">
                Live dashboard
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 text-sm"
                  value={batchDashboard}
                  onChange={(event) => { setBatchDashboard(event.target.value as "inherit" | "enable" | "disable"); }}
                >
                  <option value="inherit">Default</option>
                  <option value="enable">Show</option>
                  <option value="disable">Hide</option>
                </select>
              </label>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const args = buildBatchArgs({
                  parentPath: batchParentPath,
                  auto: batchAuto,
                  manual: batchManual,
                  dashboard: batchDashboard,
                  pipelinePreset: batchPipelinePreset,
                  nfoLocale: batchLocale,
                  announce: batchAnnounce,
                  modulesCsv: batchModulesCsv,
                  allModules: batchAllModules,
                });
                form.setValue("module", "batch");
                form.setValue("args_text", args);
                form.setValue("confirm_destructive", true);
              }}
            >
              Fill Batch Form
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Presets
          </CardTitle>
          <CardDescription>Quick presets for common operations.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {(presetsQuery.data?.presets ?? []).map((preset) => (
            <Button
              key={preset.id}
              variant="outline"
              type="button"
              onClick={() => {
                form.setValue("module", preset.module);
                form.setValue("args_text", preset.args_text);
                form.setValue("dry_run", preset.dry_run);
                form.setValue("auto_yes", preset.auto_yes);
                form.setValue("confirm_destructive", preset.confirm_destructive);
                const nextCommand = (cliSpecQuery.data?.modules ?? []).find((item) => item.name === preset.module);
                if (nextCommand) {
                  setCommandValues(initValuesFromSpec(nextCommand));
                }
              }}
            >
              {preset.label}
            </Button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Run module
          </CardTitle>
          <CardDescription>Background mode recommended for long operations.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-1 text-sm" htmlFor="module">
                Module
                <Input
                  id="module"
                  list="modules-list"
                  {...form.register("module")}
                  onChange={(event) => {
                    form.setValue("module", event.target.value);
                    const nextCommand = (cliSpecQuery.data?.modules ?? []).find((item) => item.name === event.target.value);
                    if (nextCommand) {
                      const initial = initValuesFromSpec(nextCommand);
                      setCommandValues(initial);
                      form.setValue("args_text", buildArgsFromState(nextCommand, initial));
                    }
                  }}
                />
              </label>
              <datalist id="modules-list">
                {(catalogQuery.data?.modules ?? []).map((item) => (
                  <option key={item.name} value={item.name} />
                ))}
              </datalist>

              {canBuildFromSpec ? (
                <div className="space-y-2 md:col-span-2">
                  <p className="text-sm font-medium">Command Options</p>
                  {selectedCommand ? (
                    <CliCommandForm
                      command={selectedCommand}
                      values={commandValues}
                      onChange={(name, value) => {
                        const next = { ...commandValues, [name]: value };
                        setCommandValues(next);
                        form.setValue("args_text", buildArgsFromState(selectedCommand, next));
                      }}
                      onReset={() => {
                        const initial = initValuesFromSpec(selectedCommand);
                        setCommandValues(initial);
                        form.setValue("args_text", buildArgsFromState(selectedCommand, initial));
                      }}
                    />
                  ) : null}
                </div>
              ) : null}

              <details className="rounded-md border border-border md:col-span-2">
                <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
                  Advanced — raw arguments
                </summary>
                <label className="mt-2 block space-y-1 px-4 pb-3 text-sm" htmlFor="args_text">
                  Arguments
                  <Input id="args_text" placeholder={'ex: "C:/Releases/My.Release"'} {...form.register("args_text")} />
                </label>
              </details>
            </div>

            <div className="flex flex-wrap gap-4 text-sm">
              {([
                [dryRunWatched, "dry_run", "Simulation (no file writes)"],
                [autoYesWatched, "auto_yes", "Confirm automatically"],
                [confirmDestructiveWatched, "confirm_destructive", "Allow destructive actions"],
                [asyncRunValue, "async_run", "Run in background"],
              ] as Array<[boolean, keyof FormValues, string]>).map(([checked, field, label]) => (
                <label key={field} className="inline-flex cursor-pointer items-center gap-2 text-sm">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={checked}
                    onClick={() => form.setValue(field, !checked)}
                    className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors ${checked ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background hover:border-primary/60"}`}
                  >
                    {checked ? <span className="text-[10px] font-bold leading-none">✓</span> : null}
                  </button>
                  {label}
                </label>
              ))}
            </div>

            <Button type="submit" disabled={runMutation.isPending || createJobMutation.isPending}>
              <Play className="mr-2 h-4 w-4" />
              Run
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-primary" />
            Recent Jobs
          </CardTitle>
          <CardDescription>Live tracking of background jobs.</CardDescription>
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

          {filteredJobs.map((job) => (
            <div
              key={job.id}
              className="grid w-full gap-2 rounded-md border border-border p-3 text-left md:grid-cols-[1fr_auto_auto_auto]"
            >
              <button type="button" className="text-left" onClick={() => { setSelectedJobId(job.id); }}>
                <p className="text-xs text-muted-foreground">{job.id}</p>
              </button>
              <p className="font-medium">{String((job.request["module"] as string) ?? "-")}</p>
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
              <Button
                type="button"
                variant="outline"
                onClick={() => { void navigate({ to: "/modules/$jobId", params: { jobId: job.id } }); }}
              >
                Details
              </Button>
            </div>
          ))}
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

      {activeJobId ? (
        <Card>
          <CardHeader>
            <CardTitle>Active Job</CardTitle>
            <CardDescription>{activeJobId}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <RunTimeline items={runTimeline(jobStatusQuery.data)} />
            <Badge
              variant={
                jobStatusQuery.data?.status === "completed"
                  ? "success"
                  : jobStatusQuery.data?.status === "failed" ||
                      jobStatusQuery.data?.status === "cancelled"
                    ? "danger"
                    : "secondary"
              }
            >
              {jobStatusQuery.data?.status ?? "pending"}
            </Badge>
            {jobStatusQuery.data &&
            (jobStatusQuery.data.status === "pending" ||
              jobStatusQuery.data.status === "running") ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => { void cancelJobMutation.mutateAsync(jobStatusQuery.data.id); }}
                disabled={cancelJobMutation.isPending}
              >
                <Square className="mr-2 h-4 w-4" />
                Cancel job
              </Button>
            ) : null}
            {jobStatusQuery.data ? (
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => { void navigate({ to: "/modules/$jobId", params: { jobId: jobStatusQuery.data.id } }); }}
                >
                  View Details
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => { applyJobRequestToForm(jobStatusQuery.data, form.setValue); }}
                >
                  Restore to Form
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => { void rerunJobMutation.mutateAsync(jobStatusQuery.data.id); }}
                  disabled={rerunJobMutation.isPending}
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Rerun
                </Button>
              </div>
            ) : null}
            {jobStatusQuery.data?.error ? (
              <pre className="max-h-72 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
                {jobStatusQuery.data.error}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {selectedResult ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={selectedResult.ok ? "success" : "danger"}>{selectedResult.ok ? "Completed" : "Failed"}</Badge>
              Execution result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {structuredResult ? (
              <div className="rounded-md border border-border bg-card p-3">
                <p className="mb-2 text-sm font-medium">Structured result</p>
                {structuredResult}
              </div>
            ) : null}
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
              {selectedResult.stdout || "(no output)"}
            </pre>
            {selectedResult.stderr ? (
              <pre className="max-h-72 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
                {selectedResult.stderr}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {mutationError ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {mutationErrorMessage(mutationError)}
        </p>
      ) : null}
    </div>
  );
}
