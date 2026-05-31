import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { createIntakeSource, deleteIntakeSource, getAuthStatus, listIntakeSources, submitIntakeRelease } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth";
import type { IntakeSource } from "@/lib/api/schemas";

function extractApiMessage(err: unknown): string {
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

type CopyState = "idle" | "copied" | "error";

export function IntakePage() {
  const { user: me } = useAuth();
  const qc = useQueryClient();

  const authStatusQuery = useQuery({
    queryKey: ["auth-status"],
    queryFn: getAuthStatus,
    staleTime: 60_000,
    retry: false,
  });

  const authEnabled = authStatusQuery.data?.enabled ?? false;
  const canManage = !authEnabled || me?.role === "admin";

  const sourcesQuery = useQuery({
    queryKey: ["intake-sources"],
    queryFn: listIntakeSources,
    enabled: !authStatusQuery.isPending && canManage,
    retry: false,
  });

  const sources: IntakeSource[] = sourcesQuery.data?.sources ?? [];

  const [newName, setNewName] = useState("");
  const [newSourceId, setNewSourceId] = useState("");
  const [newDefaultPreset, setNewDefaultPreset] = useState("");
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [createdSourceId, setCreatedSourceId] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createIntakeSource({
        name: newName,
        source_id: newSourceId,
        default_preset: newDefaultPreset.trim() ? newDefaultPreset.trim() : null,
      }),
    onSuccess: (created) => {
      void qc.invalidateQueries({ queryKey: ["intake-sources"] });
      setNewName("");
      setNewSourceId("");
      setNewDefaultPreset("");
      setCreatedToken(created.token ?? null);
      setCreatedSourceId(created.source_id);
      setCopyState("idle");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => deleteIntakeSource(sourceId),
    onSuccess: (_, sourceId) => {
      void qc.invalidateQueries({ queryKey: ["intake-sources"] });
      setConfirmDelete((current) => (current === sourceId ? null : current));
    },
  });

  const [testSource, setTestSource] = useState("");
  const [testPath, setTestPath] = useState("");
  const [testPreset, setTestPreset] = useState("");
  const submitMutation = useMutation({
    mutationFn: () =>
      submitIntakeRelease({
        source: testSource,
        path: testPath.trim(),
        preset: testPreset.trim() ? testPreset.trim() : null,
      }),
  });

  const createError = useMemo(() => {
    if (!createMutation.isError) return null;
    return extractApiMessage(createMutation.error);
  }, [createMutation.error, createMutation.isError]);

  const listError = useMemo(() => {
    if (!sourcesQuery.isError) return null;
    return extractApiMessage(sourcesQuery.error);
  }, [sourcesQuery.error, sourcesQuery.isError]);
  const enabledSources = sources.filter((source) => source.enabled).length;
  const latestCreatedAt = sources[0]?.created_at ?? null;

  async function copyToken(): Promise<void> {
    if (!createdToken) return;
    try {
      await navigator.clipboard.writeText(createdToken);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  }

  if (!authStatusQuery.isPending && authEnabled && me?.role !== "admin") {
    return (
      <div className="space-y-6">
        <section className="rounded-2xl border border-border bg-card p-5">
          <h1 className="text-2xl font-semibold tracking-tight">Intake</h1>
          <p className="mt-1 text-sm text-destructive">Admin access required.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
              <KeyRound className="h-6 w-6 text-primary" />
              Intake Sources
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Manage external intake tokens and source identities used by downloader/webhook integrations.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/events"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Service Events
            </Link>
            <Link
              to="/logs"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Open Logs
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Registered Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{sources.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Enabled Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{enabledSources}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Latest Source</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium">{latestCreatedAt ? new Date(latestCreatedAt).toLocaleString() : "n/a"}</p>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Security notice</CardTitle>
          <CardDescription>
            Intake tokens are sensitive credentials. Store them securely. A generated token may not be visible again.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Plus className="h-4 w-4 text-primary" />
            Create intake source
          </CardTitle>
          <CardDescription>
            Register a source identifier and optionally set a default preset for incoming releases.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <label className="text-xs font-medium">Name</label>
              <Input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="qBittorrent"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Source ID</label>
              <Input
                value={newSourceId}
                onChange={(e) => setNewSourceId(e.target.value)}
                placeholder="qbittorrent-main"
              />
              <p className="text-xs text-muted-foreground">Allowed: a-z, A-Z, 0-9, underscore, dash.</p>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Default preset (optional)</label>
              <Input
                value={newDefaultPreset}
                onChange={(e) => setNewDefaultPreset(e.target.value)}
                placeholder="default"
              />
            </div>
          </div>
          {createError ? (
            <p className="text-xs text-destructive">{createError}</p>
          ) : null}
          <Button
            size="sm"
            onClick={() => createMutation.mutate()}
            disabled={!newName.trim() || !newSourceId.trim() || createMutation.isPending}
          >
            Create source
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Plus className="h-4 w-4 text-primary" />
            Test submit a release
          </CardTitle>
          <CardDescription>
            Manually trigger the intake pipeline for a path under an allowed root — same flow downloaders use.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <label className="text-xs font-medium">Source</label>
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                value={testSource}
                onChange={(e) => setTestSource(e.target.value)}
              >
                <option value="">— Select source —</option>
                {sources.map((source) => (
                  <option key={source.source_id} value={source.source_id}>{source.source_id}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Release path</label>
              <Input value={testPath} onChange={(e) => setTestPath(e.target.value)} placeholder="/media/incoming/My.Release" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Preset (optional)</label>
              <Input value={testPreset} onChange={(e) => setTestPreset(e.target.value)} placeholder="override preset" />
            </div>
          </div>
          {submitMutation.isError ? (
            <p className="text-xs text-destructive">{extractApiMessage(submitMutation.error)}</p>
          ) : null}
          {submitMutation.data ? (
            <div className="rounded-md border border-primary/30 bg-primary/5 p-3 text-xs space-y-1">
              <p>
                <Badge variant={submitMutation.data.accepted ? "success" : "warning"}>
                  {submitMutation.data.accepted ? "Accepted" : "Rejected"}
                </Badge>
                {submitMutation.data.dedup_hit ? <span className="ml-2 text-muted-foreground">dedup hit</span> : null}
              </p>
              {submitMutation.data.job_id ? (
                <p>
                  Job:{" "}
                  <Link to="/jobs/$jobId" params={{ jobId: submitMutation.data.job_id }} className="text-primary hover:underline font-mono">
                    {submitMutation.data.job_id}
                  </Link>
                </p>
              ) : null}
            </div>
          ) : null}
          <Button
            size="sm"
            onClick={() => submitMutation.mutate()}
            disabled={!testSource.trim() || !testPath.trim() || submitMutation.isPending}
          >
            {submitMutation.isPending ? "Submitting…" : "Submit release"}
          </Button>
        </CardContent>
      </Card>

      {createdSourceId && createdToken ? (
        <Card className="border-primary/40">
          <CardHeader>
            <CardTitle className="text-sm">Token generated</CardTitle>
            <CardDescription>
              Store this token now for source <code>{createdSourceId}</code>. It may not be shown again.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input value={createdToken} readOnly className="font-mono text-xs" />
            <div className="flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => void copyToken()}>
                <Copy className="mr-1.5 h-3.5 w-3.5" />Copy token
              </Button>
              {copyState === "copied" ? <span className="text-xs text-green-600">Copied.</span> : null}
              {copyState === "error" ? <span className="text-xs text-destructive">Copy failed.</span> : null}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setCreatedToken(null);
                  setCreatedSourceId(null);
                  setCopyState("idle");
                }}
              >
                Dismiss
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Registered sources ({sources.length})</CardTitle>
          <CardDescription>Tokens are never returned in source listing.</CardDescription>
        </CardHeader>
        <CardContent>
          {sourcesQuery.isLoading || authStatusQuery.isPending ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : listError ? (
            <p className="text-sm text-destructive">{listError}</p>
          ) : sources.length === 0 ? (
            <p className="text-sm text-muted-foreground">No intake source registered.</p>
          ) : (
            <div className="divide-y divide-border">
              {sources.map((source) => (
                <div key={source.id} className="flex items-start gap-3 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{source.name}</span>
                      <Badge variant="secondary" className="text-xs font-mono">{source.source_id}</Badge>
                      <Badge variant={source.enabled ? "default" : "secondary"} className="text-xs">
                        {source.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Created {new Date(source.created_at).toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Default preset: {source.default_preset?.trim() ? source.default_preset : "(none)"}
                    </p>
                  </div>
                  <div className="shrink-0">
                    {confirmDelete === source.source_id ? (
                      <div className="flex items-center gap-1">
                        <span className="text-xs text-destructive">Delete?</span>
                        <Button
                          size="sm"
                          variant="destructive"
                          className="h-7"
                          onClick={() => deleteMutation.mutate(source.source_id)}
                          disabled={deleteMutation.isPending}
                        >
                          Yes
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7"
                          onClick={() => setConfirmDelete(null)}
                        >
                          No
                        </Button>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                        title="Delete source and revoke token"
                        onClick={() => setConfirmDelete(source.source_id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {deleteMutation.isError && confirmDelete === source.source_id ? (
                      <p className="mt-1 text-xs text-destructive">{extractApiMessage(deleteMutation.error)}</p>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
