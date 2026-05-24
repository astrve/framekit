import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Copy, Play } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createModuleJob, runModule } from "@/lib/api/endpoints";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";

export type ModulePreset = {
  id: string;
  label: string;
  args: string;
};

export function DedicatedModuleLauncher(props: {
  moduleName: string;
  title: string;
  description: string;
  presets: ModulePreset[];
  requiredFlags?: string[];
  requiredText?: string[];
}) {
  const { moduleName, title, description, presets, requiredFlags = [], requiredText = [] } = props;
  const navigate = useNavigate();
  const [argsText, setArgsText] = useState<string>(presets[0]?.args ?? "");
  const [asyncRun, setAsyncRun] = useState(true);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lastJob, setLastJob] = useState<ModuleJob | null>(null);

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({ mutationFn: createModuleJob, onSuccess: (job) => setLastJob(job) });

  const previewCommand = useMemo(() => `framekit ${moduleName} ${argsText.trim()}`.trim(), [argsText, moduleName]);
  const runResult: RunModuleResult | null = runMutation.data ?? null;

  function validateArgs(value: string): string | null {
    const trimmed = value.trim();
    for (const flag of requiredFlags) {
      if (!trimmed.includes(flag)) {
        return `Argument requis: ${flag}`;
      }
    }
    for (const text of requiredText) {
      if (!trimmed.includes(text)) {
        return `Contenu requis: ${text}`;
      }
    }
    return null;
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-4 w-4 text-primary" />
            Lancement
          </CardTitle>
          <CardDescription>Commande dédiée au module {moduleName}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <Button key={preset.id} type="button" variant="outline" size="sm" onClick={() => setArgsText(preset.args)}>
                {preset.label}
              </Button>
            ))}
          </div>

          <label className="space-y-1 text-sm" htmlFor={`${moduleName}-args`}>
            Arguments
            <Input id={`${moduleName}-args`} value={argsText} onChange={(e) => setArgsText(e.target.value)} />
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
                const validationError = validateArgs(argsText);
                if (validationError) {
                  setLocalError(validationError);
                  return;
                }
                setLocalError(null);
                const payload = {
                  module: moduleName,
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
            <Button type="button" variant="ghost" onClick={() => setArgsText(presets[0]?.args ?? "")}>
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
            <CardTitle>Résultat</CardTitle>
            <CardDescription>Return code: {runResult.returncode}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Badge variant={runResult.ok ? "success" : "danger"}>{runResult.ok ? "success" : "failed"}</Badge>
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{runResult.stdout || "(stdout empty)"}</pre>
            {runResult.stderr ? <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">{runResult.stderr}</pre> : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
