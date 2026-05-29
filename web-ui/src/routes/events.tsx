import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  LoaderCircle,
  PauseCircle,
  PlayCircle,
  Power,
  RefreshCw,
  Signal,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import { ApiError } from "@/lib/api/client";
import {
  getRecentServiceEvents,
  getServiceStatus,
  streamServiceEvents,
} from "@/lib/api/endpoints";
import type { ServiceEvent } from "@/lib/api/schemas";
import { useServiceControls } from "@/lib/service-controls";

type LiveState = "connecting" | "live" | "degraded" | "paused";
type LevelFilter = "all" | "debug" | "info" | "warning" | "error" | "critical";

function getLevelBadgeVariant(level: string): "success" | "danger" | "warning" | "secondary" {
  const normalized = level.toLowerCase();
  if (normalized === "error" || normalized === "critical") return "danger";
  if (normalized === "warning" || normalized === "warn") return "warning";
  if (normalized === "debug") return "secondary";
  return "success";
}

function parseEventId(rawId: string): number {
  const parsed = Number.parseInt(rawId, 10);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function formatEventTime(ts: string): string {
  const parsed = new Date(ts);
  if (Number.isNaN(parsed.getTime())) return ts;
  return parsed.toLocaleString();
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

export function EventsPage() {
  const [liveEvents, setLiveEvents] = useState<ServiceEvent[]>([]);
  const [liveState, setLiveState] = useState<LiveState>("connecting");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [showRecentFallback, setShowRecentFallback] = useState(true);
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");
  const [typeFilter, setTypeFilter] = useState("");
  const [searchFilter, setSearchFilter] = useState("");
  const lastEventIdRef = useRef<string | null>(null);

  const recentQuery = useQuery({
    queryKey: ["service-events-recent"],
    queryFn: () => getRecentServiceEvents(150),
    refetchInterval: liveState === "degraded" ? 15_000 : false,
    staleTime: 5_000,
    retry: false,
  });

  const serviceQuery = useQuery({
    queryKey: ["service-status-events-page"],
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
    refreshSecondary: recentQuery.refetch,
  });

  useEffect(() => {
    if (paused) {
      setLiveState("paused");
      return undefined;
    }

    const controller = new AbortController();

    async function runStreamLoop(): Promise<void> {
      while (!controller.signal.aborted) {
        setLiveState((prev) => (prev === "live" ? prev : "connecting"));
        try {
          await streamServiceEvents({
            signal: controller.signal,
            lastEventId: lastEventIdRef.current,
            onEvent: (event) => {
              lastEventIdRef.current = event.id;
              setLiveEvents((prev) => [event, ...prev].slice(0, 350));
              setLiveState("live");
              setStreamError(null);
            },
          });
        } catch (err) {
          if (controller.signal.aborted) return;
          setLiveState("degraded");
          setStreamError(extractApiError(err));
        }
        if (controller.signal.aborted) return;
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
    }

    void runStreamLoop();
    return () => {
      controller.abort();
    };
  }, [paused]);

  const baseEvents = useMemo(() => {
    const merged = showRecentFallback
      ? [...liveEvents, ...(recentQuery.data?.events ?? [])]
      : [...liveEvents];
    const deduped = new Map<string, ServiceEvent>();
    for (const item of merged) {
      if (!deduped.has(item.id)) {
        deduped.set(item.id, item);
      }
    }
    return Array.from(deduped.values())
      .sort((a, b) => parseEventId(b.id) - parseEventId(a.id))
      .slice(0, 200);
  }, [liveEvents, recentQuery.data?.events, showRecentFallback]);

  const filteredEvents = useMemo(() => {
    const typeNeedle = typeFilter.trim().toLowerCase();
    const textNeedle = searchFilter.trim().toLowerCase();

    return baseEvents.filter((event) => {
      const level = event.level.toLowerCase();
      if (levelFilter !== "all" && level !== levelFilter) return false;
      if (typeNeedle && !event.type.toLowerCase().includes(typeNeedle)) return false;
      if (!textNeedle) return true;

      const payloadText = event.data ? JSON.stringify(event.data).toLowerCase() : "";
      return (
        event.message.toLowerCase().includes(textNeedle) ||
        event.type.toLowerCase().includes(textNeedle) ||
        payloadText.includes(textNeedle)
      );
    });
  }, [baseEvents, levelFilter, typeFilter, searchFilter]);

  const counters = useMemo(() => {
    const totals = { total: filteredEvents.length, warning: 0, error: 0 };
    for (const event of filteredEvents) {
      const normalized = event.level.toLowerCase();
      if (normalized === "warning" || normalized === "warn") totals.warning += 1;
      if (normalized === "error" || normalized === "critical") totals.error += 1;
    }
    return totals;
  }, [filteredEvents]);

  const serviceState = serviceQuery.data?.status ?? "unknown";
  const watcherState = serviceQuery.data?.watcher?.status ?? "unknown";
  const queuePending = serviceQuery.data?.queue?.pending ?? 0;
  const queueRunning = serviceQuery.data?.queue?.running ?? 0;

  const liveStateBadge =
    liveState === "live" ? (
      <Badge variant="success">Live</Badge>
    ) : liveState === "paused" ? (
      <Badge variant="secondary">Paused</Badge>
    ) : liveState === "connecting" ? (
      <Badge variant="secondary">Connecting…</Badge>
    ) : (
      <Badge variant="warning">Degraded</Badge>
    );

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              <Signal className="h-6 w-6 text-primary" />
              Service Events
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Real-time service telemetry and operator controls.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {liveStateBadge}
            <Badge variant={serviceState === "running" ? "success" : "secondary"}>
              service: {serviceState}
            </Badge>
            <Badge variant={watcherState === "running" ? "success" : "secondary"}>
              watcher: {watcherState}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void recentQuery.refetch()}
              disabled={recentQuery.isFetching}
            >
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              Refresh recent
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Queue</CardTitle>
            <CardDescription>Current workload</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Pending: <span className="font-semibold">{queuePending}</span></p>
            <p>Running: <span className="font-semibold">{queueRunning}</span></p>
            <p>Drain: <span className="font-semibold">{isDraining ? "enabled" : "disabled"}</span></p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Filtered Events</CardTitle>
            <CardDescription>Current view counters</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>Total: <span className="font-semibold">{counters.total}</span></p>
            <p>Warnings: <span className="font-semibold">{counters.warning}</span></p>
            <p>Errors: <span className="font-semibold">{counters.error}</span></p>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">Service Controls</CardTitle>
            <CardDescription>Safe operational actions from the UI</CardDescription>
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
                Reload service
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
          <CardTitle className="text-sm">Filters</CardTitle>
          <CardDescription>Reduce noise and isolate incidents quickly</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <label className="space-y-1 text-sm">
              Level
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                value={levelFilter}
                onChange={(event) => setLevelFilter(event.target.value as LevelFilter)}
              >
                <option value="all">All</option>
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </label>
            <label className="space-y-1 text-sm">
              Type contains
              <Input
                value={typeFilter}
                onChange={(event) => setTypeFilter(event.target.value)}
                placeholder="job.failed, service.reload..."
              />
            </label>
            <label className="space-y-1 text-sm">
              Search message/data
              <Input
                value={searchFilter}
                onChange={(event) => setSearchFilter(event.target.value)}
                placeholder="job id, folder, tracker..."
              />
            </label>
          </div>

          <div className="flex flex-wrap gap-3">
            <Toggle
              checked={paused}
              onChange={setPaused}
              label="Pause live stream"
            />
            <Toggle
              checked={showRecentFallback}
              onChange={setShowRecentFallback}
              label="Merge recent fallback"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent Events ({filteredEvents.length})</CardTitle>
          <CardDescription>
            SSE stream (`/api/v1/events/stream`) + optional fallback (`/api/v1/events/recent`).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {streamError ? (
            <p className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-3.5 w-3.5" />
              Live stream issue: {streamError}
            </p>
          ) : null}

          {recentQuery.isError ? (
            <p className="text-xs text-destructive">
              Recent events failed: {extractApiError(recentQuery.error)}
            </p>
          ) : null}

          {recentQuery.isLoading && filteredEvents.length === 0 ? (
            <p className="flex items-center gap-1 text-sm text-muted-foreground">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Loading events…
            </p>
          ) : filteredEvents.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events for current filters.</p>
          ) : (
            <div className="divide-y divide-border">
              {filteredEvents.map((event) => {
                const jobId = typeof event.data?.job_id === "string" ? event.data.job_id : null;
                const sourceId = typeof event.data?.source_id === "string" ? event.data.source_id : null;

                return (
                  <div key={event.id} className="flex items-start gap-3 py-3">
                    <div className="pt-0.5">
                      <Activity className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={getLevelBadgeVariant(event.level)} className="text-[10px] uppercase">
                          {event.level}
                        </Badge>
                        <span className="font-mono text-xs text-muted-foreground">{event.type}</span>
                        <Badge variant="secondary" className="text-[10px]">id:{event.id}</Badge>
                        {jobId ? <Badge variant="secondary" className="text-[10px]">job:{jobId}</Badge> : null}
                        {sourceId ? <Badge variant="secondary" className="text-[10px]">source:{sourceId}</Badge> : null}
                      </div>
                      <p className="text-sm">{event.message}</p>
                      {event.data ? (
                        <pre className="max-h-28 overflow-auto rounded-md border border-border bg-muted px-2 py-1 text-[11px] text-muted-foreground">
                          {JSON.stringify(event.data, null, 2)}
                        </pre>
                      ) : null}
                      <p className="text-xs text-muted-foreground">{formatEventTime(event.ts)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
