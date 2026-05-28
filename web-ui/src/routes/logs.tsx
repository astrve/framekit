import { useQuery } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Toggle } from "@/components/ui/toggle";
import { getLogsRead } from "@/lib/api/endpoints";
import type { LogEntry } from "@/lib/api/schemas";

const LEVEL_CONFIG: Record<string, { text: string; badge: string }> = {
  DEBUG:    { text: "text-slate-400 dark:text-slate-500",            badge: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400" },
  INFO:     { text: "text-foreground",                                badge: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" },
  SUCCESS:  { text: "text-emerald-600 dark:text-emerald-400",        badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" },
  WARNING:  { text: "text-amber-600 dark:text-amber-400",            badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300" },
  ERROR:    { text: "text-red-600 dark:text-red-400",                badge: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" },
  CRITICAL: { text: "text-red-700 dark:text-red-400 font-semibold", badge: "bg-red-200 text-red-800 dark:bg-red-900/60 dark:text-red-200 font-bold" },
};

function levelCfg(level: string): { text: string; badge: string } {
  return LEVEL_CONFIG[level.toUpperCase()] ?? LEVEL_CONFIG["INFO"] ?? { text: "text-foreground", badge: "bg-muted text-muted-foreground" };
}

function formatMsg(entry: LogEntry): string {
  const time = entry.time ? String(entry.time).slice(0, 23).replace("T", " ") : "";
  const msg = String(entry.message ?? "");
  return time ? `${time}  ${msg}` : msg;
}

export function LogsPage() {
  const [level, setLevel] = useState("");
  const [lines, setLines] = useState(200);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const preRef = useRef<HTMLDivElement>(null);

  const logsQuery = useQuery({
    queryKey: ["logs-read", level, lines],
    queryFn: () => getLogsRead(lines, level || undefined),
    refetchInterval: autoRefresh ? 3000 : false,
  });

  const entries = logsQuery.data?.entries ?? [];

  function exportLogs() {
    const text = entries.map((e) => JSON.stringify(e)).join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `framekit-logs-${new Date().toISOString().slice(0, 10)}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Logs</h1>
        <p className="mt-1 text-sm text-muted-foreground">Live view of the Framekit log file with level filtering and export.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className={`h-4 w-4 text-primary ${logsQuery.isFetching ? "animate-spin" : ""}`} />
            Log Viewer
          </CardTitle>
          <CardDescription>
            {entries.length} line{entries.length !== 1 ? "s" : ""} shown
            {logsQuery.dataUpdatedAt ? ` · last updated ${new Date(logsQuery.dataUpdatedAt).toLocaleTimeString()}` : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Controls */}
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
                <option value={150}>150</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
              </select>
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
              <Button type="button" variant="outline" size="sm" onClick={exportLogs} disabled={entries.length === 0}>
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export JSONL
              </Button>
            </div>
          </div>

          {/* Error state */}
          {logsQuery.isError ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
              Error loading logs — is the API running?
            </p>
          ) : null}

          {/* Empty state */}
          {entries.length === 0 && !logsQuery.isFetching ? (
            <p className="rounded-md border border-border bg-muted p-3 text-sm text-muted-foreground">
              No log entries found{level ? ` at level ${level}` : ""}. The log file may not exist yet.
            </p>
          ) : null}

          {/* Log output */}
          {entries.length > 0 ? (
            <div className="relative">
              <div
                ref={preRef}
                className="max-h-[60vh] overflow-auto rounded-md border border-border bg-card p-3 font-mono text-[13px] leading-6 antialiased dark:bg-muted space-y-0.5"
              >
                {entries.map((entry, i) => {
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
                {["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"].map((lvl) => {
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

          {/* Level counts */}
          {entries.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const).map((lvl) => {
                const count = entries.filter((e) => String(e.level ?? "").toUpperCase() === lvl).length;
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
