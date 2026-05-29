import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createModuleJob, runModule } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";

const STUDIO_MODULES = [
  "watch",
  "inspect",
  "renamer",
  "cleanmkv",
  "torrent",
  "nfo",
  "prez",
  "screenshot",
  "encode",
  "extract",
  "sort",
  "browse",
  "metadata",
  "validate",
  "logs",
] as const;

type StudioModule = (typeof STUDIO_MODULES)[number];

const DEFAULT_ACTION_BY_MODULE: Record<StudioModule, string> = {
  watch: "list",
  inspect: "",
  renamer: "",
  cleanmkv: "",
  torrent: "",
  nfo: "",
  prez: "",
  screenshot: "",
  encode: "run",
  extract: "subtitle",
  sort: "",
  browse: "",
  metadata: "doctor",
  validate: "",
  logs: "tail --lines 120",
};

function asStudioModule(value: string): StudioModule | null {
  return STUDIO_MODULES.includes(value as StudioModule) ? (value as StudioModule) : null;
}

function buildArgs(moduleName: StudioModule, actionText: string, pathA: string, pathB: string, extra: string): string {
  const args: string[] = [];
  const action = actionText.trim();
  if (action) {
    args.push(action);
  }
  if (pathA.trim()) {
    args.push(`"${pathA.trim()}"`);
  }
  if (pathB.trim()) {
    args.push(`"${pathB.trim()}"`);
  }
  if (extra.trim()) {
    args.push(extra.trim());
  }
  if ((moduleName === "renamer" || moduleName === "cleanmkv" || moduleName === "torrent") && !args.includes("--dry-run")) {
    args.push("--dry-run");
  }
  return args.join(" ").trim();
}

export function ModuleStudioPage() {
  const navigate = useNavigate();
  const { module } = useParams({ from: "/studio/$module" });
  const studioModule = asStudioModule(module);
  const [actionText, setActionText] = useState(studioModule ? DEFAULT_ACTION_BY_MODULE[studioModule] : "");
  const [pathA, setPathA] = useState("");
  const [pathB, setPathB] = useState("");
  const [extra, setExtra] = useState("");
  const [asyncRun, setAsyncRun] = useState(true);
  const [lastJob, setLastJob] = useState<ModuleJob | null>(null);

  const runMutation = useMutation({
    mutationFn: runModule,
  });
  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job) => setLastJob(job),
  });

  const builtArgs = useMemo(() => {
    if (!studioModule) {
      return "";
    }
    return buildArgs(studioModule, actionText, pathA, pathB, extra);
  }, [actionText, extra, pathA, pathB, studioModule]);

  if (!studioModule) {
    return (
      <div className="space-y-4">
        <p>Unknown module studio: {module}</p>
        <Link to="/jobs">Retour modules</Link>
      </div>
    );
  }

  const runResult: RunModuleResult | null = runMutation.data ?? null;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Module Studio: {studioModule}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Page dédiée pour module avec args guidés + preview commande.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Launcher
          </CardTitle>
          <CardDescription>Génère commande `framekit {studioModule} ...`</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm" htmlFor="studio-action">
              Action / subcommand
              <Input id="studio-action" value={actionText} onChange={(e) => setActionText(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm" htmlFor="studio-extra">
              Extra flags
              <Input id="studio-extra" value={extra} onChange={(e) => setExtra(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm md:col-span-2" htmlFor="studio-path-a">
              Path A
              <Input id="studio-path-a" value={pathA} onChange={(e) => setPathA(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm md:col-span-2" htmlFor="studio-path-b">
              Path B
              <Input id="studio-path-b" value={pathB} onChange={(e) => setPathB(e.target.value)} />
            </label>
          </div>

          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={asyncRun} onChange={(e) => setAsyncRun(e.target.checked)} />
            async job
          </label>

          <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            framekit {studioModule} {builtArgs}
          </pre>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => {
                const payload = {
                  module: studioModule,
                  args_text: builtArgs,
                  dry_run: false,
                  auto_yes: false,
                  confirm_destructive: true,
                };
                if (asyncRun) {
                  createJobMutation.mutate(payload);
                } else {
                  runMutation.mutate(payload);
                }
              }}
            >
              Exécuter
            </Button>
            {lastJob ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  void navigate({ to: "/jobs/$jobId", params: { jobId: lastJob.id } });
                }}
              >
                Ouvrir dernier job
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {runResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
            <CardDescription>Return code: {runResult.returncode}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Badge variant={runResult.ok ? "success" : "danger"}>{runResult.ok ? "success" : "failed"}</Badge>
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
              {runResult.stdout || "(stdout empty)"}
            </pre>
            {runResult.stderr ? (
              <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                {runResult.stderr}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Autres studios</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {STUDIO_MODULES.map((name) => (
            <Button key={name} asChild variant={name === studioModule ? "default" : "outline"} size="sm">
              <Link to="/studio/$module" params={{ module: name }}>
                {name}
              </Link>
            </Button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
