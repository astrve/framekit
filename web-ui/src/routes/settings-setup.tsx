import { useQuery } from "@tanstack/react-query";
import { ServerCog, Settings2 } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getSeedboxList, getSettingsSummary, getUploadTrackers } from "@/lib/api/endpoints";

export function SettingsSetupPage() {
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
    </div>
  );
}
