import { useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Copy, ListChecks } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createModuleJob, runModule } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";

const BATCH_PRESETS = [
  { id: "scan-dir", label: "Scan dossier", args: "run --input-dir \"\" --pattern \"*.mkv\" --dry-run" },
  { id: "validate-only", label: "Validate only", args: "run --input-dir \"\" --validate-only --dry-run" },
  { id: "rename-batch", label: "Renamer", args: "run --input-dir \"\" --module renamer --dry-run" },
] as const;

function validateBatchArgs(argsText: string): string | null {
  const trimmed = argsText.trim();
  if (!trimmed) {
    return "Les arguments batch sont requis.";
  }
  if (!trimmed.includes("--input-dir")) {
    return "Ajoute --input-dir pour cibler le lot.";
  }
  return null;
}

export function BatchPage() {
  const navigate = useNavigate();
  const [argsText, setArgsText] = useState<string>(BATCH_PRESETS[0].args);
  const [asyncRun, setAsyncRun] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lastJob, setLastJob] = useState<ModuleJob | null>(null);

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({ mutationFn: createModuleJob, onSuccess: (job) => setLastJob(job) });

  const previewCommand = useMemo(() => `framekit batch ${argsText.trim()}`.trim(), [argsText]);
  const runResult: RunModuleResult | null = runMutation.data ?? null;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Batch Studio</h1>
        <p className="mt-1 text-sm text-muted-foreground">Exécutions en lot avec garde-fous minimaux et preview commande.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-primary" />
            Lancement batch
          </CardTitle>
          <CardDescription>Prépare et exécute `framekit batch ...`</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {BATCH_PRESETS.map((preset) => (
              <Button key={preset.id} type="button" variant="outline" size="sm" onClick={() => setArgsText(preset.args)}>
                {preset.label}
              </Button>
            ))}
          </div>

          <label className="space-y-1 text-sm" htmlFor="batch-args">
            Arguments
            <Input id="batch-args" value={argsText} onChange={(e) => setArgsText(e.target.value)} />
          </label>

          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={asyncRun} onChange={(e) => setAsyncRun(e.target.checked)} />
            async job
          </label>

          <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{previewCommand}</pre>

          {localError ? <p className="rounded-md border border-rose-300 bg-rose-100 p-2 text-sm text-rose-800">{localError}</p> : null}

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => {
                const validationError = validateBatchArgs(argsText);
                if (validationError) {
                  setLocalError(validationError);
                  return;
                }
                setLocalError(null);
                const payload = {
                  module: "batch",
                  args_text: argsText.trim(),
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
              Copier commande
            </Button>
            <Button type="button" variant="ghost" onClick={() => setArgsText(BATCH_PRESETS[0].args)}>
              Reset preset
            </Button>
            {copied ? <Badge variant="success">Copié</Badge> : null}
            {lastJob ? (
              <Button type="button" variant="outline" onClick={() => void navigate({ to: "/modules/$jobId", params: { jobId: lastJob.id } })}>
                Ouvrir dernier job
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {runResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Résultat batch</CardTitle>
            <CardDescription>Return code: {runResult.returncode}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Badge variant={runResult.ok ? "success" : "danger"}>{runResult.ok ? "success" : "failed"}</Badge>
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{runResult.stdout || "(stdout empty)"}</pre>
            {runResult.stderr ? <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">{runResult.stderr}</pre> : null}
          </CardContent>
        </Card>
      ) : null}

      <div className="text-sm text-muted-foreground">
        Besoin des options rares ? <Link to="/modules" className="text-primary underline">Workbench modules</Link>
      </div>
    </div>
  );
}
