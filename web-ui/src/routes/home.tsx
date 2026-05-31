import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Film,
  HardDriveDownload,
  Layers,
  LoaderCircle,
  OctagonX,
  Play,
  ScrollText,
  Server,
  Stethoscope,
  Upload,
} from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getDoctorPayload,
  getServiceStatus,
  getSettingsSummary,
  getSeedboxList,
  getUploadHistory,
  getUploadState,
  getUploadTrackers,
  getVaultStatus,
  listModuleJobs,
  listReleases,
} from "@/lib/api/endpoints";
import type { ModuleJob } from "@/lib/api/schemas";
import { cn } from "@/lib/utils";

// ── helpers ──────────────────────────────────────────────────────────────────

function formatDuration(
  startedAt: string | null | undefined,
  finishedAt: string | null | undefined,
): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) return "—";
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  if (Number.isNaN(end) || end < start) return "—";
  const totalSeconds = Math.floor((end - start) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes === 0 ? `${seconds}s` : `${minutes}m ${seconds}s`;
}

function formatAge(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  const ms = Date.now() - new Date(dateStr).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function getJobModule(job: ModuleJob): string {
  return String(job.request.module ?? "unknown");
}

// Extract the first path-like token from args_text for human-readable display.
// Falls back to truncated raw args if no path separator found.
function getJobDisplayPath(job: ModuleJob): string {
  const args = String(job.request.args_text ?? "").trim();
  if (!args) return "";
  const firstToken = args.split(/\s+/)[0] ?? "";
  if (firstToken.includes("/") || firstToken.includes("\\")) {
    return firstToken.replace(/\\/g, "/").split("/").at(-1) ?? firstToken;
  }
  return args.length > 44 ? `${args.slice(0, 41)}…` : args;
}

// Returns a compact failure hint for failed jobs: "exit N · first stderr line".
function getJobFailureHint(job: ModuleJob): string | null {
  if (job.status !== "failed") return null;
  const rc = job.result?.returncode;
  const raw = (job.result?.stderr ?? job.error ?? "").trim();
  const firstLine = raw.split("\n").find((l) => l.trim().length > 0)?.trim();
  const prefix = rc !== undefined && rc !== null && rc !== 0 ? `exit ${rc}` : null;
  if (prefix && firstLine) return `${prefix} · ${firstLine.slice(0, 48)}`;
  if (prefix) return prefix;
  return firstLine ? firstLine.slice(0, 60) : null;
}

function isToday(dateStr: string | null | undefined): boolean {
  if (!dateStr) return false;
  return new Date(dateStr).toDateString() === new Date().toDateString();
}

function getOriginLink(moduleName: string, jobId: string) {
  const cls = "shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline";
  if (moduleName === "pipeline") return <Link to="/pipeline" className={cls}>↗</Link>;
  if (moduleName === "batch") return <Link to="/batch" className={cls}>↗</Link>;
  if (moduleName === "upload") return <Link to="/upload" className={cls}>↗</Link>;
  if (moduleName === "seedbox") return <Link to="/seedbox" className={cls}>↗</Link>;
  return <Link to="/jobs/$jobId" params={{ jobId }} className={cls}>→</Link>;
}

// ── quick actions config ─────────────────────────────────────────────────────

const QUICK_ACTIONS = [
  { icon: Play, label: "Pipeline", to: "/pipeline" },
  { icon: Layers, label: "Batch", to: "/batch" },
  { icon: Upload, label: "Upload", to: "/upload" },
  { icon: HardDriveDownload, label: "Seedbox", to: "/seedbox" },
  { icon: ScrollText, label: "Logs", to: "/logs" },
  { icon: Stethoscope, label: "Diagnostics", to: "/doctor" },
] as const;

// ── component ────────────────────────────────────────────────────────────────

export function HomePage() {
  // ── queries ──────────────────────────────────────────────────────────────

  const jobsQuery = useQuery({
    queryKey: ["dashboard-jobs"],
    queryFn: () => listModuleJobs(100),
    refetchInterval: 3000,
    staleTime: 0,
  });

  const doctorQuery = useQuery({
    queryKey: ["dashboard-doctor"],
    queryFn: getDoctorPayload,
    staleTime: 60_000,
  });

  const uploadStateQuery = useQuery({
    queryKey: ["dashboard-upload-state"],
    queryFn: getUploadState,
    staleTime: 30_000,
  });

  const uploadHistoryQuery = useQuery({
    queryKey: ["dashboard-upload-history"],
    queryFn: () => getUploadHistory(1),
    staleTime: 60_000,
  });

  const seedboxQuery = useQuery({
    queryKey: ["dashboard-seedbox"],
    queryFn: getSeedboxList,
    staleTime: 60_000,
  });

  const vaultQuery = useQuery({
    queryKey: ["dashboard-vault"],
    queryFn: getVaultStatus,
    staleTime: 60_000,
  });

  const releasesQuery = useQuery({
    queryKey: ["dashboard-releases"],
    queryFn: () => listReleases(5),
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const settingsQuery = useQuery({
    queryKey: ["dashboard-settings"],
    queryFn: getSettingsSummary,
    staleTime: 120_000,
  });

  const serviceQuery = useQuery({
    queryKey: ["dashboard-service"],
    queryFn: getServiceStatus,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const trackersQuery = useQuery({
    queryKey: ["dashboard-trackers"],
    queryFn: getUploadTrackers,
    staleTime: 60_000,
  });

  // ── stable derived state (doctor/upload/vault — independent of job poll) ─

  const { errCount, warnCount, okCount, uploadEnabled, warnings } = useMemo(() => {
    const checks = doctorQuery.data?.checks ?? [];
    const errCount = checks.filter((c) => c.status === "err").length;
    const warnCount = checks.filter((c) => c.status === "warn").length;
    const okCount = checks.filter((c) => c.status === "ok").length;

    const uploadEnabled = uploadStateQuery.data?.enabled ?? false;
    const enabledTrackerCount =
      trackersQuery.data?.trackers.filter((t) => t.enabled).length ?? 0;

    const warnings: Array<{ msg: string; to: string }> = [];

    if (doctorQuery.data && errCount > 0) {
      warnings.push({
        msg: `${errCount} diagnostic error${errCount > 1 ? "s" : ""} — view Diagnostics`,
        to: "/doctor",
      });
    }
    if (
      uploadStateQuery.data &&
      uploadEnabled &&
      trackersQuery.data &&
      enabledTrackerCount === 0
    ) {
      warnings.push({ msg: "Upload active but no trackers configured", to: "/upload" });
    }
    if (vaultQuery.data?.error || vaultQuery.isError) {
      warnings.push({
        msg: "Vault offline — encrypted settings unavailable",
        to: "/settings-setup",
      });
    }
    if (uploadStateQuery.isError) {
      warnings.push({ msg: "Upload service unavailable", to: "/upload" });
    }
    const setupSettings = settingsQuery.data?.settings as Record<string, unknown> | undefined;
    const setupCompleted = setupSettings?.["setup"]?.["completed" as never] ?? setupSettings?.["setup.completed"];
    if (settingsQuery.data && !setupCompleted) {
      warnings.push({ msg: "Setup not complete — configure tools, trackers, and seedbox", to: "/settings-setup" });
    }

    return { errCount, warnCount, okCount, uploadEnabled, warnings };
  }, [
    doctorQuery.data,
    uploadStateQuery.data,
    uploadStateQuery.isError,
    trackersQuery.data,
    vaultQuery.data,
    vaultQuery.isError,
    settingsQuery.data,
  ]);

  // ── jobs-derived state (updates every 3s) ───────────────────────────────

  const allJobs = jobsQuery.data?.jobs ?? [];
  const activeJobs = allJobs.filter(
    (j) => j.status === "pending" || j.status === "running",
  );
  // Cancelled jobs suppressed unless very recent (< 30 min) — they add noise
  // without useful context. Limit to 8 for dashboard readability.
  const CANCELLED_WINDOW_MS = 30 * 60 * 1000;
  const recentJobs = allJobs
    .filter((j) => {
      if (j.status === "completed" || j.status === "failed") return true;
      if (j.status === "cancelled") {
        const age = Date.now() - new Date(j.created_at).getTime();
        return !Number.isNaN(age) && age < CANCELLED_WINDOW_MS;
      }
      return false;
    })
    .slice(0, 8);
  const completedToday = allJobs.filter(
    (j) => isToday(j.created_at) && j.status === "completed",
  ).length;
  const failedToday = allJobs.filter(
    (j) => isToday(j.created_at) && j.status === "failed",
  ).length;
  const hasRunning = activeJobs.some((j) => j.status === "running");

  // ── seedbox / upload history ─────────────────────────────────────────────

  const defaultSeedbox = seedboxQuery.data?.seedboxes.find((s) => s.is_default);
  const lastUploadEntry = uploadHistoryQuery.data?.entries[0];
  const lastUploadTs = lastUploadEntry?.timestamp ?? "";
  const serviceState = serviceQuery.data?.status ?? "unknown";

  // ── render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 ops-reveal">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight text-primary">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">Self-hosted media workflow automation</p>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5">
          <div className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Active</span>
            <span className="font-bold tabular-nums">{activeJobs.length}</span>
          </div>
          <div className="h-4 w-px bg-border" />
          <Badge variant={serviceState === "running" ? "success" : "secondary"}>
            {serviceState === "running" ? "running" : serviceState}
          </Badge>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Today</span>
            <span className="font-bold tabular-nums">{completedToday + failedToday}</span>
          </div>
        </div>
      </section>

      {/* ── Warnings banner ──────────────────────────────────────────────── */}
      {warnings.length > 0 && (
        <div className="surface-enter rounded-xl border border-accent/50 bg-accent/10 px-4 py-3 space-y-2">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-accent">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            Attention required
          </p>
          {warnings.map((w, i) => (
            <div key={i} className="flex items-center justify-between gap-4">
              <p className="text-sm text-foreground">{w.msg}</p>
              <Link
                to={w.to}
                className="shrink-0 text-xs font-medium text-accent underline-offset-2 hover:underline"
              >
                View →
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* ── Active operations ────────────────────────────────────────────── */}
      <section className="surface-enter">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <Activity className="h-4 w-4 text-muted-foreground" />
            Active Operations
            {activeJobs.length > 0 && (
              <Badge
                variant={hasRunning ? "danger" : "secondary"}
                className="ml-0.5"
              >
                {activeJobs.length}
              </Badge>
            )}
          </h2>
          <Link
            to="/jobs"
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            All jobs →
          </Link>
        </div>

        <div
          className={cn(
            "rounded-xl border bg-card overflow-hidden",
            hasRunning ? "border-primary/40" : "border-border",
          )}
        >
          {activeJobs.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">
              {jobsQuery.isLoading ? "Loading…" : "No active operations"}
            </p>
          ) : (
            <div className="divide-y divide-border/60">
              {activeJobs.map((job) => (
                <div key={job.id} className="flex items-center gap-3 px-4 py-3">
                  <LoaderCircle
                    className={cn(
                      "h-3.5 w-3.5 animate-spin shrink-0",
                      job.status === "running"
                        ? "text-primary"
                        : "text-muted-foreground",
                    )}
                  />
                  <span className="w-20 shrink-0 truncate font-mono text-xs font-medium text-foreground">
                    {getJobModule(job)}
                  </span>
                  <span className="flex-1 truncate text-xs text-muted-foreground">
                    {getJobDisplayPath(job)}
                  </span>
                  <span className="shrink-0 tabular-nums text-xs text-muted-foreground">
                    {formatDuration(job.started_at, null)}
                  </span>
                  <Badge
                    variant={job.status === "running" ? "info" : "warning"}
                    className="shrink-0 text-[10px]"
                  >
                    {job.status}
                  </Badge>
                  {getOriginLink(getJobModule(job), job.id)}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── Stat cards ───────────────────────────────────────────────────── */}
      <section className="surface-enter grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {/* System Health */}
        <Card
          className={cn(
            "border-border/60",
            doctorQuery.data && errCount > 0 && "border-destructive/40",
            doctorQuery.data &&
              errCount === 0 &&
              warnCount > 0 &&
              "border-accent/40",
            doctorQuery.data &&
              errCount === 0 &&
              warnCount === 0 &&
              okCount > 0 &&
              "border-accent/40",
          )}
        >
          <CardHeader className="px-4 pb-2 pt-4">
            <CardTitle className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Stethoscope className="h-3.5 w-3.5" />
              System Health
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {doctorQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : doctorQuery.isError ? (
              <p className="text-sm text-destructive">Unavailable</p>
            ) : (
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                {errCount > 0 && (
                  <span className="text-sm font-semibold text-destructive">
                    {errCount} error{errCount > 1 ? "s" : ""}
                  </span>
                )}
                {warnCount > 0 && (
                  <span className="text-sm font-semibold text-warning">
                    {warnCount} warning{warnCount > 1 ? "s" : ""}
                  </span>
                )}
                {errCount === 0 && warnCount === 0 && (
                  <span className="text-sm font-semibold text-success">
                    All checks OK
                  </span>
                )}
                {(errCount > 0 || warnCount > 0) && okCount > 0 && (
                  <span className="text-xs text-muted-foreground">{okCount} ok</span>
                )}
              </div>
            )}
            <Link
              to="/doctor"
              className="mt-2 block text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              View Diagnostics →
            </Link>
          </CardContent>
        </Card>

        {/* Upload */}
        <Card className="border-border/60">
          <CardHeader className="px-4 pb-2 pt-4">
            <CardTitle className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Upload className="h-3.5 w-3.5" />
              Upload
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {uploadStateQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : uploadStateQuery.isError ? (
              <p className="text-sm text-destructive">Unavailable</p>
            ) : (
              <div className="space-y-1.5">
                <Badge variant={uploadEnabled ? "success" : "secondary"}>
                  {uploadEnabled ? "Enabled" : "Disabled"}
                </Badge>
                <p className="text-xs text-muted-foreground">
                  {lastUploadTs ? `Last: ${formatAge(lastUploadTs)}` : "No uploads yet"}
                </p>
              </div>
            )}
            <Link
              to="/upload"
              className="mt-2 block text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              Manage Upload →
            </Link>
          </CardContent>
        </Card>

        {/* Seedbox */}
        <Card className="border-border/60">
          <CardHeader className="px-4 pb-2 pt-4">
            <CardTitle className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <HardDriveDownload className="h-3.5 w-3.5" />
              Seedbox
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {seedboxQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : seedboxQuery.isError ? (
              <p className="text-sm text-destructive">Unavailable</p>
            ) : defaultSeedbox ? (
              <div className="space-y-0.5">
                <p className="truncate text-sm font-semibold">{defaultSeedbox.name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {defaultSeedbox.rclone_remote}
                </p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No default configured</p>
            )}
            <Link
              to="/seedbox"
              className="mt-2 block text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              Manage Seedbox →
            </Link>
          </CardContent>
        </Card>

        {/* Service */}
        <Card
          className={cn(
            "border-border/60",
            serviceQuery.data?.status === "running" && "border-success/40",
          )}
        >
          <CardHeader className="px-4 pb-2 pt-4">
            <CardTitle className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Server className="h-3.5 w-3.5" />
              Service
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {serviceQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : serviceQuery.isError || !serviceQuery.data ? (
              <Badge variant="secondary">Unknown</Badge>
            ) : serviceQuery.data.status === "running" ? (
              <div className="space-y-1.5">
                <Badge variant="success">Running</Badge>
                {serviceQuery.data.uptime_seconds != null && (
                  <p className="text-xs text-muted-foreground">
                    Up {Math.floor(serviceQuery.data.uptime_seconds / 60)}m
                  </p>
                )}
                {serviceQuery.data.watcher?.status === "running" && (
                  <p className="text-xs text-muted-foreground">
                    Watch: {serviceQuery.data.watcher.folders_active} folder{serviceQuery.data.watcher.folders_active !== 1 ? "s" : ""}
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-1.5">
                <Badge variant="secondary">Stopped</Badge>
                <p className="text-xs text-muted-foreground">
                  Run <code className="font-mono">swirrl serve</code>
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Jobs Today */}
        <Card className="border-border/60">
          <CardHeader className="px-4 pb-2 pt-4">
            <CardTitle className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Layers className="h-3.5 w-3.5" />
              Jobs Today
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {jobsQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <div className="flex items-baseline gap-3">
                <span className="text-2xl font-bold tabular-nums">
                  {completedToday + failedToday}
                </span>
                <div>
                  {completedToday > 0 && (
                    <p className="text-xs text-accent">{completedToday} completed</p>
                  )}
                  {failedToday > 0 && (
                    <p className="text-xs text-destructive">{failedToday} failed</p>
                  )}
                  {completedToday === 0 && failedToday === 0 && (
                    <p className="text-xs text-muted-foreground">None yet today</p>
                  )}
                </div>
              </div>
            )}
            <Link
              to="/jobs"
              className="mt-2 block text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              View all jobs →
            </Link>
          </CardContent>
        </Card>
      </section>

      {/* ── Recent results ───────────────────────────────────────────────── */}
      <section className="surface-enter">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Recent Results</h2>
          <Link
            to="/jobs"
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Full history →
          </Link>
        </div>

        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {jobsQuery.isLoading ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">Loading…</p>
          ) : recentJobs.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">
              No recent results — run Pipeline, Batch, or any module to see job history here.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Module
                  </th>
                  <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Status
                  </th>
                  <th className="hidden px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground sm:table-cell">
                    Duration
                  </th>
                  <th className="hidden px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-muted-foreground md:table-cell">
                    Time
                  </th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {recentJobs.map((job) => {
                  const displayPath = getJobDisplayPath(job);
                  const failureHint = getJobFailureHint(job);
                  return (
                    <tr
                      key={job.id}
                      className={cn(
                        "group border-l-2 transition-colors hover:bg-secondary/40",
                        job.status === "completed" ? "border-l-success" :
                        job.status === "failed" ? "border-l-destructive" :
                        "border-l-transparent",
                      )}
                    >
                      {/* Module + path */}
                      <td className="px-4 py-2.5 max-w-[10rem] lg:max-w-[14rem]">
                        <p className="font-mono text-xs font-medium">
                          {getJobModule(job)}
                        </p>
                        {displayPath && (
                          <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                            {displayPath}
                          </p>
                        )}
                      </td>
                      {/* Status + failure hint */}
                      <td className="px-4 py-2.5">
                        {job.status === "completed" ? (
                          <div className="flex items-center gap-1.5">
                            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-success" />
                            <span className="text-xs text-success">done</span>
                          </div>
                        ) : job.status === "failed" ? (
                          <div>
                            <div className="flex items-center gap-1.5">
                              <OctagonX className="h-3.5 w-3.5 shrink-0 text-destructive" />
                              <span className="text-xs text-destructive">failed</span>
                            </div>
                            {failureHint && (
                              <p className="mt-0.5 max-w-[16rem] truncate text-[11px] text-destructive/70">
                                {failureHint}
                              </p>
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5">
                            <OctagonX className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">
                              {job.status}
                            </span>
                          </div>
                        )}
                      </td>
                      <td className="hidden px-4 py-2.5 sm:table-cell">
                        <span className="tabular-nums text-xs text-muted-foreground">
                          {formatDuration(job.started_at, job.finished_at)}
                        </span>
                      </td>
                      <td className="hidden px-4 py-2.5 text-right md:table-cell">
                        <span className="text-xs text-muted-foreground">
                          {formatAge(job.finished_at ?? job.created_at)}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Link
                          to="/jobs/$jobId"
                          params={{ jobId: job.id }}
                          className="text-xs text-muted-foreground opacity-0 underline-offset-2 transition-opacity hover:text-foreground hover:underline group-hover:opacity-100"
                        >
                          Debug →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* ── Recent releases ──────────────────────────────────────────────── */}
      <section className="surface-enter">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold">Recent Releases</h2>
          <Link to="/releases" className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
            View all →
          </Link>
        </div>
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {releasesQuery.isLoading ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">Loading…</p>
          ) : (releasesQuery.data?.releases ?? []).length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">No releases yet. Run a pipeline job to start tracking.</p>
          ) : (
            <table className="w-full text-sm">
              <tbody>
                {(releasesQuery.data?.releases ?? []).map((release) => (
                  <tr key={release.id} className="border-b border-border/50 last:border-b-0">
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <Film className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <Link to="/releases" className="font-mono text-xs hover:underline truncate max-w-[18rem]">
                          {release.folder_name}
                        </Link>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge
                        variant={
                          release.status === "done" || release.status === "uploaded" ? "success" :
                          release.status === "failed" ? "danger" :
                          release.status === "processing" ? "warning" :
                          "secondary"
                        }
                      >
                        {release.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground text-right">
                      {formatAge(release.updated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* ── Quick actions ────────────────────────────────────────────────── */}
      <section className="surface-enter">
        <h2 className="mb-3 text-base font-semibold">Quick Launch</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
          {QUICK_ACTIONS.map(({ icon: Icon, label, to }) => (
            <Link
              key={to}
              to={to}
              className="group flex flex-col items-center gap-2.5 rounded-xl border border-border bg-card px-3 py-5 text-center transition-all duration-150 hover:border-primary/60 hover:bg-secondary"
            >
              <div className="rounded-lg bg-primary/15 p-2.5 transition-colors group-hover:bg-primary/25">
                <Icon className="h-5 w-5 text-primary" />
              </div>
              <span className="text-xs font-semibold">{label}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

