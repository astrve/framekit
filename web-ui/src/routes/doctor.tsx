import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Server } from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api/client";
import { getDoctorPayload, getHealth, getSystemInfo } from "@/lib/api/endpoints";
import type { DoctorCheck } from "@/lib/api/schemas";

function statusToVariant(status: DoctorCheck["status"]): "success" | "warning" | "danger" {
  if (status === "ok") return "success";
  if (status === "warn") return "warning";
  return "danger";
}

function statusLabel(status: DoctorCheck["status"]): string {
  if (status === "ok") return "OK";
  if (status === "warn") return "Warning";
  return "Error";
}

export function DoctorPage() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });
  const systemInfoQuery = useQuery({
    queryKey: ["system-info"],
    queryFn: getSystemInfo,
  });
  const doctorQuery = useQuery({
    queryKey: ["doctor"],
    queryFn: getDoctorPayload,
  });

  const statusCounts = useMemo(() => {
    const checks = doctorQuery.data?.checks ?? [];
    return {
      ok: checks.filter((check) => check.status === "ok").length,
      warn: checks.filter((check) => check.status === "warn").length,
      err: checks.filter((check) => check.status === "err").length,
    };
  }, [doctorQuery.data?.checks]);

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <section className="rounded-2xl border border-border bg-card p-5">
          <h1 className="text-2xl font-semibold tracking-tight">System Diagnostics</h1>
          <p className="mt-1 text-sm text-muted-foreground">Real-time health check for your Swirrl installation. Read-only — no files are modified.</p>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Server className="h-4 w-4 text-primary" />
                API Status
              </CardTitle>
              <CardDescription>Local backend connection</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant={healthQuery.data?.status === "ok" ? "success" : "danger"}>
                {healthQuery.data?.status === "ok" ? "Online" : (healthQuery.data?.status ?? "Offline")}
              </Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Versions</CardTitle>
              <CardDescription>Swirrl and Python</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <p>Swirrl: <span className="font-medium">{systemInfoQuery.data?.version ?? "…"}</span></p>
              <p>Python: <span className="font-medium">{systemInfoQuery.data?.python_version ?? "…"}</span></p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Summary</CardTitle>
              <CardDescription>Last scan results</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Badge variant="success">{statusCounts.ok} passed</Badge>
              <Badge variant="warning">{statusCounts.warn} warnings</Badge>
              <Badge variant="danger">{statusCounts.err} errors</Badge>
            </CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Run Diagnostic</CardTitle>
            <CardDescription>Read-only check. Does not modify any files.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => doctorQuery.refetch()} disabled={doctorQuery.isFetching}>
              {doctorQuery.isFetching ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : null}
              Rerun
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Check Results</CardTitle>
              <CardDescription>Detailed results by section</CardDescription>
            </div>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="secondary">Raw JSON</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Raw API Response</DialogTitle>
                  <DialogDescription>Full JSON payload from the diagnostics endpoint.</DialogDescription>
                </DialogHeader>
                <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
                  {JSON.stringify(doctorQuery.data ?? {}, null, 2)}
                </pre>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent className="space-y-2">
            {doctorQuery.isError ? (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {doctorQuery.error instanceof ApiError
                  ? `Connection error (${doctorQuery.error.status}): ${doctorQuery.error.body || "unknown"}`
                  : `Error: ${doctorQuery.error instanceof Error ? doctorQuery.error.message : "unknown"}`}
              </p>
            ) : null}
            {doctorQuery.isPending ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : null}
            {(doctorQuery.data?.checks ?? []).map((check) => (
              <div key={`${check.section}:${check.name}`} className="grid gap-2 rounded-md border border-border p-3 md:grid-cols-[180px_1fr_auto]">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{check.section}</p>
                <p className="text-sm">{check.name}: {check.detail}</p>
                <Badge variant={statusToVariant(check.status)}>{statusLabel(check.status)}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
