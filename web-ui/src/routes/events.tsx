import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, LoaderCircle, RefreshCw, Signal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getRecentServiceEvents, streamServiceEvents } from "@/lib/api/endpoints";
import type { ServiceEvent } from "@/lib/api/schemas";

type LiveState = "connecting" | "live" | "degraded";

function getLevelBadgeVariant(level: string): "success" | "danger" | "secondary" {
  const normalized = level.toLowerCase();
  if (normalized === "error") return "danger";
  if (normalized === "warning" || normalized === "warn") return "secondary";
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
  const lastEventIdRef = useRef<string | null>(null);

  const recentQuery = useQuery({
    queryKey: ["service-events-recent"],
    queryFn: () => getRecentServiceEvents(100),
    refetchInterval: liveState === "degraded" ? 15_000 : false,
    staleTime: 5_000,
    retry: false,
  });

  useEffect(() => {
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
              setLiveEvents((prev) => [event, ...prev].slice(0, 300));
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
  }, []);

  const events = useMemo(() => {
    const merged = [...liveEvents, ...(recentQuery.data?.events ?? [])];
    const deduped = new Map<string, ServiceEvent>();
    for (const item of merged) {
      if (!deduped.has(item.id)) {
        deduped.set(item.id, item);
      }
    }
    return Array.from(deduped.values())
      .sort((a, b) => parseEventId(b.id) - parseEventId(a.id))
      .slice(0, 150);
  }, [liveEvents, recentQuery.data?.events]);

  const headerBadge =
    liveState === "live"
      ? <Badge variant="success">Live</Badge>
      : liveState === "connecting"
        ? <Badge variant="secondary">Connecting…</Badge>
        : <Badge variant="secondary">Degraded</Badge>;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Signal className="h-6 w-6 text-primary" />
          Service Events
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Live event stream for service, jobs, watcher, and intake. Falls back to recent polling if stream fails.
        </p>
      </section>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <CardTitle className="text-sm">Stream status</CardTitle>
            <CardDescription>Uses SSE (`/api/v1/events/stream`) with keepalive pings.</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {headerBadge}
            <Button size="sm" variant="outline" onClick={() => void recentQuery.refetch()} disabled={recentQuery.isFetching}>
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              Refresh recent
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {streamError ? (
            <p className="text-xs text-amber-600 flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              Live stream unavailable: {streamError}
            </p>
          ) : null}
          {recentQuery.isError ? (
            <p className="text-xs text-destructive">Recent events failed: {extractApiError(recentQuery.error)}</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Recent events ({events.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {recentQuery.isLoading && events.length === 0 ? (
            <p className="text-sm text-muted-foreground flex items-center gap-1">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Loading events…
            </p>
          ) : events.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events yet.</p>
          ) : (
            <div className="divide-y divide-border">
              {events.map((event) => {
                const jobId = typeof event.data?.job_id === "string" ? event.data.job_id : null;
                const sourceId = typeof event.data?.source_id === "string" ? event.data.source_id : null;
                return (
                  <div key={event.id} className="py-3 flex items-start gap-3">
                    <div className="pt-0.5">
                      <Activity className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant={getLevelBadgeVariant(event.level)} className="text-[10px] uppercase">
                          {event.level}
                        </Badge>
                        <span className="font-mono text-xs text-muted-foreground">{event.type}</span>
                        {jobId ? <Badge variant="secondary" className="text-[10px]">job:{jobId}</Badge> : null}
                        {sourceId ? <Badge variant="secondary" className="text-[10px]">source:{sourceId}</Badge> : null}
                      </div>
                      <p className="text-sm">{event.message}</p>
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

