import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Activity,
  AlertTriangle,
  Download,
  Gauge,
  PauseCircle,
  PlayCircle,
  Power,
  RefreshCw,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { ApiError } from "@/lib/api/client";
import {
  getLogsRead,
  getServiceStatus,
} from "@/lib/api/endpoints";
import type { LogEntry } from "@/lib/api/schemas";
import { useServiceControls } from "@/lib/service-controls";

const LEVEL_CONFIG: Record<string, { text: string; badge: string }> = {
  DEBUG:    { text: "text-muted-foreground", badge: "bg-secondary text-secondary-foreground" },
  INFO:     { text: "text-foreground", badge: "bg-secondary text-secondary-foreground" },
  SUCCESS:  { text: "text-accent", badge: "bg-accent/20 text-accent-foreground" },
  WARNING:  { text: "text-accent", badge: "bg-accent/30 text-accent-foreground" },
  ERROR:    { text: "text-primary", badge: "bg-primary/20 text-primary" },
  CRITICAL: { text: "text-primary font-semibold", badge: "bg-primary text-primary-foreground font-bold" },
};

function levelCfg(level: string): { text: string; badge: string } {
  return LEVEL_CONFIG[level.toUpperCase()] ?? LEVEL_CONFIG["INFO"] ?? { text: "text-foreground", badge: "bg-muted text-muted-foreground" };
}

function formatMsg(entry: LogEntry): string {
  const time = entry.time ? String(entry.time).slice(0, 23).replace("T", " ") : "";
  const msg = String(entry.message ?? "");
  return time ? `${time}  ${msg}` : msg;
}

function extractApiError(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.body) as { detail?: string };
      return parsed.detail ?? err.message;
    } catch {
      return err.message;
    }
  }
  return err instanceof Error ? err.message : String(err);
}

function formatUptime(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "n/a";
  const mins = Math.floor(seconds / 60);
  if (mins < 1) return `${Math.floor(seconds)}s`;
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remMin = mins % 60;
  return `${hours}h ${remMin}m`;
}

export function LogsPage() {
  const [level, setLevel] = useState("");
  const [lines, setLines] = useState(200);
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const logsQuery = useQuery({
    queryKey: ["logs-read", level, lines],
    queryFn: () => getLogsRead(lines, level || undefined),
    refetchInterval: autoRefresh ? 3000 : false,
  });

  const serviceQuery = useQuery({
    queryKey: ["logs-service-status"],
    queryFn: getServiceStatus,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const isDraining =
    serviceQuery.data?.queue?.draining ?? serviceQuery.data?.draining ?? false;

  const {
    actionState,
    confirmShutdown,
    setConfirmShutdown,
    requestReload,
    requestDrain,
    requestShutdown,
    isPending: isServiceActionPending,
  } = useServiceControls({
    refreshPrimary: serviceQuery.refetch,
    refreshSecondary: logsQuery.refetch,
  });

  const entries = logsQuery.data?.entries ?? [];
  const visibleEntries = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return entries;
    return entries.filter((entry) => {
      const msg = String(entry.message ?? "").toLowerCase();
      if (msg.includes(needle)) return true;
      return JSON.stringify(entry).toLowerCase().includes(needle);
    });
  }, [entries, search]);

  const levelCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const entry of visibleEntries) {
      const lvl = String(entry.level ?? "INFO").toUpperCase();
      counts[lvl] = (counts[lvl] ?? 0) + 1;
    }
    return counts;
  }, [visibleEntries]);

  function exportLogs() {
    const text = visibleEntries.map((e) => JSON.stringify(e)).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ouro-logs-${new Date().toISOString().slice(0, 10)}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const serviceState = serviceQuery.data?.status ?? "unknown";
  const watcherState = serviceQuery.data?.watcher?.status ?? "unknown";
  const queuePending = serviceQuery.data?.queue?.pending ?? 0;
  const queueRunning = serviceQuery.data?.queue?.running ?? 0;
  const queuePaused = serviceQuery.data?.queue?.paused ?? 0;
  const metrics = serviceQuery.data?.metrics;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              <Activity className="h-6 w-6 text-primary" />
              Logs
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Operational log stream with service supervision controls.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant={serviceState === "running" ? "success" : "secondary"}>
              service: {serviceState}
            </Badge>
            <Badge variant={watcherState === "running" ? "success" : "secondary"}>
              watcher: {watcherState}
            </Badge>
            <Badge variant="secondary">
              queue: {queuePending} pending
            </Badge>
            <Link
              to="/events"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Open Events
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Service Snapshot</CardTitle>
            <CardDescription>Current supervisor and queue state</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>PID: <span className="font-semibold">{serviceQuery.data?.pid ?? "n/a"}</span></p>
            <p>Uptime: <span className="font-semibold">{formatUptime(serviceQuery.data?.uptime_seconds)}</span></p>
            <p>Pending: <span className="font-semibold">{queuePending}</span></p>
            <p>Running: <span className="font-semibold">{queueRunning}</span></p>
            <p>Paused: <span className="font-semibold">{queuePaused}</span></p>
            <p>Drain: <span className="font-semibold">{isDraining ? "enabled" : "disabled"}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Gauge className="h-4 w-4 text-primary" />
              Service Metrics
            </CardTitle>
            <CardDescription>Cumulative counters from service mode</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Queued: <span className="font-semibold">{metrics?.queued ?? 0}</span></p>
            <p>Running: <span className="font-semibold">{metrics?.running ?? 0}</span></p>
            <p>Completed: <span className="font-semibold">{metrics?.completed ?? 0}</span></p>
            <p>Failed: <span className="font-semibold">{metrics?.failed ?? 0}</span></p>
            <p>Retried: <span className="font-semibold">{metrics?.retried ?? 0}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Service Controls</CardTitle>
            <CardDescription>Safe actions without leaving observability</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={requestReload}
                disabled={isServiceActionPending}
              >
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                Reload
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => requestDrain(!isDraining)}
                disabled={isServiceActionPending}
              >
                {isDraining ? <PlayCircle className="mr-1.5 h-3.5 w-3.5" /> : <PauseCircle className="mr-1.5 h-3.5 w-3.5" />}
                {isDraining ? "Disable drain" : "Enable drain"}
              </Button>
              <Button
                type="button"
                variant={confirmShutdown ? "destructive" : "outline"}
                onClick={() => {
                  if (!confirmShutdown) {
                    setConfirmShutdown(true);
                    return;
                  }
                  requestShutdown();
                }}
                disabled={isServiceActionPending}
              >
                <Power className="mr-1.5 h-3.5 w-3.5" />
                {confirmShutdown ? "Confirm shutdown" : "Request shutdown"}
              </Button>
              {confirmShutdown ? (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setConfirmShutdown(false)}
                >
                  Cancel
                </Button>
              ) : null}
            </div>

            {actionState ? (
              <p className={`text-xs ${actionState.kind === "error" ? "text-destructive" : "text-muted-foreground"}`}>
                {actionState.message}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className={`h-4 w-4 text-primary ${logsQuery.isFetching ? "animate-spin" : ""}`} />
            Log Viewer
          </CardTitle>
          <CardDescription>
            {visibleEntries.length} line{visibleEntries.length !== 1 ? "s" : ""} shown
            {logsQuery.dataUpdatedAt ? ` · last updated ${new Date(logsQuery.dataUpdatedAt).toLocaleTimeString()}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="space-y-1 text-sm">
              <span className="flex items-center gap-0 font-medium">
                Level filter
                <InfoTooltip text="Show only log entries at this severity level" />
              </span>
              <select
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
                value={level}
                onChange={(e) => setLevel(e.target.value)}
              >
                <option value="">All levels</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="SUCCESS">SUCCESS</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="flex items-center gap-0 font-medium">
                Lines
                <InfoTooltip text="Number of most-recent log lines to load (max 5000)" />
              </span>
              <select
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
                value={lines}
                onChange={(e) => setLines(Number(e.target.value))}
              >
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="flex items-center gap-0 font-medium">
                Search
                <InfoTooltip text="Filter visible lines by message or payload text" />
              </span>
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="error id, source, job..."
              />
            </label>

            <Toggle
              checked={autoRefresh}
              onChange={setAutoRefresh}
              label="Auto-refresh (3 s)"
              tooltip={<InfoTooltip text="Reload log entries every 3 seconds automatically" />}
              className="self-end pb-0.5"
            />

            <div className="flex gap-2 self-end">
              <Button type="button" variant="outline" size="sm" onClick={() => void logsQuery.refetch()}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                Refresh
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={exportLogs} disabled={visibleEntries.length === 0}>
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export JSONL
              </Button>
            </div>
          </div>

          {serviceQuery.isError ? (
            <p className="flex items-center gap-1 rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-sm text-amber-700 dark:text-amber-300">
              <AlertTriangle className="h-3.5 w-3.5" />
              Service status unavailable: {extractApiError(serviceQuery.error)}
            </p>
          ) : null}

          {logsQuery.isError ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
              Error loading logs: {extractApiError(logsQuery.error)}
            </p>
          ) : null}

          {visibleEntries.length === 0 && !logsQuery.isFetching ? (
            <p className="rounded-md border border-border bg-muted p-3 text-sm text-muted-foreground">
              No log entries found{level ? ` at level ${level}` : ""}{search ? " for this search." : "."}
            </p>
          ) : null}

          {visibleEntries.length > 0 ? (
            <div className="relative">
              <div
                className="max-h-[60vh] overflow-auto rounded-md border border-border bg-card p-3 font-mono text-[13px] leading-6 antialiased dark:bg-muted space-y-0.5"
              >
                {visibleEntries.map((entry, i) => {
                  const lvl = String(entry.level ?? "INFO").toUpperCase();
                  const cfg = levelCfg(lvl);
                  return (
                    <div key={i} className={`flex items-start gap-2 rounded px-1 py-0.5 ${cfg.text}`}>
                      <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold leading-none tracking-wide ${cfg.badge}`}>
                        {lvl}
                      </span>
                      <span className="break-all whitespace-pre-wrap">{formatMsg(entry)}</span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                {["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"].map((lvl) => {
                  const cfg = levelCfg(lvl);
                  return (
                    <span key={lvl} className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 ${cfg.badge} text-[10px] font-semibold`}>
                      {lvl}
                    </span>
                  );
                })}
              </div>
            </div>
          ) : null}

          {visibleEntries.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const).map((lvl) => {
                const count = levelCounts[lvl] ?? 0;
                if (!count) return null;
                return (
                  <Badge key={lvl} variant="secondary" className="text-xs">
                    {lvl}: {count}
                  </Badge>
                );
              })}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
