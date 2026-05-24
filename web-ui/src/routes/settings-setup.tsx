import { useQuery } from "@tanstack/react-query";
import { useMutation } from "@tanstack/react-query";
import { ServerCog, Settings2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getSeedboxList, getSettingsSummary, getUploadTrackers, runModule } from "@/lib/api/endpoints";
import type { RunModuleResult } from "@/lib/api/schemas";

export function SettingsSetupPage() {
  const [moduleName, setModuleName] = useState<"setup" | "settings" | "watch" | "logs">("settings");
  const [argsText, setArgsText] = useState("doctor --json");
  const [confirmDestructive, setConfirmDestructive] = useState(false);

  const settingsQuery = useQuery({
    queryKey: ["settings-summary"],
    queryFn: getSettingsSummary,
  });
  const seedboxesQuery = useQuery({
    queryKey: ["seedbox-list"],
    queryFn: getSeedboxList,
  });
  const trackersQuery = useQuery({
    queryKey: ["upload-trackers"],
    queryFn: getUploadTrackers,
  });
  const runMutation = useMutation({
    mutationFn: runModule,
  });
  const runResult: RunModuleResult | null = runMutation.data ?? null;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Settings & Setup</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vue centralisée configuration locale, seedboxes, trackers upload.
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-4 w-4 text-primary" />
            Runtime config
          </CardTitle>
          <CardDescription>Chemins actifs et snapshot settings redacted.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>Settings file: {settingsQuery.data?.settings_path ?? "-"}</p>
          <p>Config dir: {settingsQuery.data?.config_dir ?? "-"}</p>
          <p>Cache dir: {settingsQuery.data?.cache_dir ?? "-"}</p>
          <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            {settingsQuery.data ? JSON.stringify(settingsQuery.data.settings, null, 2) : "Loading..."}
          </pre>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ServerCog className="h-4 w-4 text-primary" />
              Seedboxes
            </CardTitle>
            <CardDescription>Configuration disponible pour push/pull.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(seedboxesQuery.data?.seedboxes ?? []).map((item) => (
              <div key={item.name} className="rounded-md border border-border p-3">
                <p className="font-medium">
                  {item.name} {item.is_default ? "(default)" : ""}
                </p>
                <p>{item.rclone_remote}:{item.remote_base_path}</p>
                <p>transfers: {item.max_concurrent_uploads ?? "-"}</p>
              </div>
            ))}
            {(seedboxesQuery.data?.seedboxes ?? []).length === 0 ? (
              <p className="text-muted-foreground">Aucun seedbox configuré.</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload trackers</CardTitle>
            <CardDescription>Trackers connus côté settings.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {(trackersQuery.data?.trackers ?? []).map((item) => (
              <div key={`${item.name}-${item.url}`} className="rounded-md border border-border p-3">
                <p className="font-medium">{item.name}</p>
                <p>{item.type}</p>
                <p>{item.url}</p>
                <p>enabled: {item.enabled ? "yes" : "no"}</p>
              </div>
            ))}
            {(trackersQuery.data?.trackers ?? []).length === 0 ? (
              <p className="text-muted-foreground">Aucun tracker upload configuré.</p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Actions settings/setup</CardTitle>
          <CardDescription>Exécute flux clés sans quitter l’UI.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm" htmlFor="settings-action-module">
              Module
              <select
                id="settings-action-module"
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={moduleName}
                onChange={(event) => {
                  const value = event.target.value as "setup" | "settings" | "watch" | "logs";
                  setModuleName(value);
                  if (value === "settings") {
                    setArgsText("doctor --json");
                  } else if (value === "setup") {
                    setArgsText("--mode normal");
                  } else if (value === "watch") {
                    setArgsText("status");
                  } else {
                    setArgsText("analyze");
                  }
                }}
              >
                <option value="settings">settings</option>
                <option value="setup">setup</option>
                <option value="watch">watch</option>
                <option value="logs">logs</option>
              </select>
            </label>
            <label className="space-y-1 text-sm" htmlFor="settings-action-confirm">
              Confirm destructive
              <select
                id="settings-action-confirm"
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={confirmDestructive ? "yes" : "no"}
                onChange={(event) => {
                  setConfirmDestructive(event.target.value === "yes");
                }}
              >
                <option value="no">no</option>
                <option value="yes">yes</option>
              </select>
            </label>
            <label className="space-y-1 text-sm md:col-span-2" htmlFor="settings-action-args">
              Arguments
              <Input
                id="settings-action-args"
                value={argsText}
                onChange={(event) => {
                  setArgsText(event.target.value);
                }}
              />
            </label>
          </div>

          <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            framekit {moduleName} {argsText}
          </pre>

          <Button
            type="button"
            onClick={() => {
              runMutation.mutate({
                module: moduleName,
                args_text: argsText,
                dry_run: false,
                auto_yes: false,
                confirm_destructive: confirmDestructive,
              });
            }}
          >
            Exécuter
          </Button>

          {runResult ? (
            <div className="space-y-2">
              <Badge variant={runResult.ok ? "success" : "danger"}>
                {runResult.ok ? "success" : "failed"} - {runResult.returncode}
              </Badge>
              <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
                {runResult.stdout || "(stdout empty)"}
              </pre>
              {runResult.stderr ? (
                <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                  {runResult.stderr}
                </pre>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
