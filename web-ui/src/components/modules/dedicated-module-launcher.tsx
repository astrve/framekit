import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Copy, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CliCommandForm } from "@/components/modules/cli-command-form";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { createModuleJob, getModulesCliSpec, runModule } from "@/lib/api/endpoints";
import type { CliCommandSpec, ModuleJob, RunModuleResult } from "@/lib/api/schemas";
import { buildArgsFromState, initValuesFromSpec } from "@/lib/cli-form";

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
  const [commandValues, setCommandValues] = useState<Record<string, unknown>>({});

  const runMutation = useMutation({ mutationFn: runModule });
  const createJobMutation = useMutation({ mutationFn: createModuleJob, onSuccess: (job) => setLastJob(job) });
  const specQuery = useQuery({
    queryKey: ["cli-spec", moduleName],
    queryFn: getModulesCliSpec,
  });
  const cliCommand: CliCommandSpec | null = useMemo(() => {
    const modules = specQuery.data?.modules ?? [];
    return modules.find((item) => item.name === moduleName) ?? null;
  }, [moduleName, specQuery.data?.modules]);
  useEffect(() => {
    if (!cliCommand) {
      return;
    }
    const initial = initValuesFromSpec(cliCommand);
    setCommandValues(initial);
    setArgsText(buildArgsFromState(cliCommand, initial));
  }, [cliCommand, moduleName]);

  const previewCommand = useMemo(() => `framekit ${moduleName} ${argsText.trim()}`.trim(), [argsText, moduleName]);
  const runResult: RunModuleResult | null = runMutation.data ?? null;

  function validateArgs(value: string): string | null {
    const trimmed = value.trim();
    for (const flag of requiredFlags) {
      if (!trimmed.includes(flag)) {
        return `Required flag missing: ${flag}`;
      }
    }
    for (const text of requiredText) {
      if (!trimmed.includes(text)) {
        return `Required argument missing: ${text}`;
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
            Launch
          </CardTitle>
          <CardDescription>Configure and run the {title} module.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <Button key={preset.id} type="button" variant="outline" size="sm" onClick={() => setArgsText(preset.args)}>
                {preset.label}
              </Button>
            ))}
          </div>

          {cliCommand ? (
            <CliCommandForm
              command={cliCommand}
              values={commandValues}
              onChange={(name, value) => {
                const next = { ...commandValues, [name]: value };
                setCommandValues(next);
                setArgsText(buildArgsFromState(cliCommand, next));
              }}
              onReset={() => {
                const initial = initValuesFromSpec(cliCommand);
                setCommandValues(initial);
                setArgsText(buildArgsFromState(cliCommand, initial));
              }}
            />
          ) : (
            <label className="space-y-1 text-sm" htmlFor={`${moduleName}-args`}>
              Arguments
              <Input id={`${moduleName}-args`} value={argsText} onChange={(e) => setArgsText(e.target.value)} />
            </label>
          )}

          <label className="inline-flex cursor-pointer items-center gap-2 text-sm">
            <button
              type="button"
              role="checkbox"
              aria-checked={asyncRun}
              onClick={() => setAsyncRun(!asyncRun)}
              className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors ${asyncRun ? "border-primary bg-primary text-primary-foreground" : "border-input bg-background hover:border-primary/60"}`}
            >
              {asyncRun ? <span className="text-[10px] font-bold leading-none">✓</span> : null}
            </button>
            Run in background
            <InfoTooltip text="Queue as async job — result appears in the Jobs tab without blocking the UI" />
          </label>

          <details className="rounded-md border border-border">
            <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground">
              Advanced — show generated command
            </summary>
            <pre className="max-h-40 overflow-auto border-t border-border bg-muted p-3 text-xs">{previewCommand}</pre>
          </details>

          {localError ? <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">{localError}</p> : null}

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
              Run
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
            <Button type="button" variant="ghost" onClick={() => setArgsText(presets[0]?.args ?? "")}>
              Reset
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

      {runResult ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Badge variant={runResult.ok ? "success" : "danger"}>{runResult.ok ? "Completed" : "Failed"}</Badge>
              Result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">{runResult.stdout || "(no output)"}</pre>
            {runResult.stderr ? <pre className="max-h-72 overflow-auto rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{runResult.stderr}</pre> : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
