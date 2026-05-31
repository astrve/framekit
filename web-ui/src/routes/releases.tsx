import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Film } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getReleaseOperations, listReleases } from "@/lib/api/endpoints";
import type { Release } from "@/lib/api/schemas";

function statusVariant(status: Release["status"]): "success" | "danger" | "warning" | "secondary" | "default" {
  switch (status) {
    case "done":
    case "uploaded": return "success";
    case "failed": return "danger";
    case "processing": return "warning";
    case "on_seedbox": return "secondary";
    default: return "default";
  }
}

function statusLabel(status: Release["status"]): string {
  switch (status) {
    case "local": return "Local";
    case "processing": return "Processing";
    case "done": return "Done";
    case "failed": return "Failed";
    case "on_seedbox": return "On seedbox";
    case "uploaded": return "Uploaded";
    default: return status;
  }
}

function formatAge(dateStr: string): string {
  const ms = Date.now() - new Date(dateStr).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ReleaseDetail({ release }: { release: Release }) {
  const opsQuery = useQuery({
    queryKey: ["release-operations", release.id],
    queryFn: () => getReleaseOperations(release.id),
  });

  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-sm space-y-2">
      <p className="text-xs text-muted-foreground font-mono break-all">{release.path}</p>
      {opsQuery.data?.operations && opsQuery.data.operations.length > 0 ? (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="text-left pb-1 font-medium">Module</th>
              <th className="text-left pb-1 font-medium">Result</th>
              <th className="text-left pb-1 font-medium">Time</th>
              <th className="text-left pb-1 font-medium">Job</th>
            </tr>
          </thead>
          <tbody>
            {opsQuery.data.operations.map((op) => (
              <tr key={op.id} className="border-t border-border/50">
                <td className="py-1 font-mono">{op.module}</td>
                <td className="py-1">
                  <Badge variant={op.result_ok ? "success" : "danger"} className="text-[10px]">
                    {op.result_ok ? "ok" : "failed"}
                  </Badge>
                </td>
                <td className="py-1 text-muted-foreground">{formatAge(op.timestamp)}</td>
                <td className="py-1">
                  <Link to="/jobs/$jobId" params={{ jobId: op.job_id }} className="text-primary hover:underline font-mono text-[10px]">
                    {op.job_id.slice(0, 8)}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-xs text-muted-foreground">No operations recorded.</p>
      )}
    </div>
  );
}

export function ReleasesPage() {
  const releasesQuery = useQuery({
    queryKey: ["releases"],
    queryFn: () => listReleases(50),
    refetchInterval: 10_000,
  });

  const releases = releasesQuery.data?.releases ?? [];

  return (
    <div className="space-y-6 ops-reveal">
      <section className="rounded-lg border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Film className="h-5 w-5 text-primary" />
          Releases
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Semantic per-release records. Populated automatically from pipeline and batch jobs.
        </p>
      </section>

      {releasesQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : releases.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            No releases yet. Run a pipeline job to populate this list.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {releases.map((release) => (
            <Card key={release.id}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between gap-2 text-base">
                  <span className="font-mono truncate">{release.folder_name}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    {release.detected_kind !== "unknown" && (
                      <Badge variant="secondary" className="text-xs capitalize">{release.detected_kind}</Badge>
                    )}
                    <Badge variant={statusVariant(release.status)}>{statusLabel(release.status)}</Badge>
                    <span className="text-xs text-muted-foreground">{formatAge(release.updated_at)}</span>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ReleaseDetail release={release} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
