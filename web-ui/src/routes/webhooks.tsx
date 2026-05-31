import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Trash2, Webhook, X, Zap } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import {
  addWebhook,
  getWebhooks,
  removeWebhook,
  testWebhook,
  testWebhookPayload,
  updateWebhook,
} from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth";
import type { WebhookConfig } from "@/lib/api/schemas";

const ALL_EVENTS = [
  { id: "job.started", label: "Job started" },
  { id: "job.completed", label: "Job completed" },
  { id: "job.failed", label: "Job failed" },
  { id: "watch.file_detected", label: "File detected" },
];

type TestState = { status: "idle" } | { status: "pending" } | { status: "ok" } | { status: "err"; msg: string };

function TestFeedback({ state }: { state: TestState }) {
  if (state.status === "pending") return <span className="text-xs text-muted-foreground">Sending…</span>;
  if (state.status === "ok") return <span className="text-xs text-green-600 flex items-center gap-1"><Check className="h-3 w-3" />Sent</span>;
  if (state.status === "err") return <span className="text-xs text-destructive">{state.msg || "Test failed"}</span>;
  return null;
}

interface EditForm {
  name: string;
  url: string;
  discord: boolean;
  events: string[];
  title_template: string;
  body_template: string;
}

const PLACEHOLDER_HINT = "Available: {event}, {module}, {args}, {path}, {returncode}, {error}, {timestamp}, {job_id}";

function EventCheckboxes({ events, onChange }: { events: string[]; onChange: (events: string[]) => void }) {
  function toggle(id: string) {
    onChange(events.includes(id) ? events.filter((e) => e !== id) : [...events, id]);
  }
  return (
    <div className="flex flex-wrap gap-3">
      {ALL_EVENTS.map((ev) => (
        <Toggle
          key={ev.id}
          checked={events.includes(ev.id)}
          onChange={() => toggle(ev.id)}
          label={ev.label}
        />
      ))}
    </div>
  );
}

export function WebhooksPage() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const isAdmin = me?.role === "admin";

  const webhooksQuery = useQuery({ queryKey: ["webhooks"], queryFn: getWebhooks });
  const webhooks: WebhookConfig[] = webhooksQuery.data?.webhooks ?? [];

  // Add form state
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState<EditForm>({
    name: "",
    url: "",
    discord: false,
    events: ALL_EVENTS.map((e) => e.id),
    title_template: "",
    body_template: "",
  });
  const [addTestState, setAddTestState] = useState<TestState>({ status: "idle" });

  // Per-webhook state
  const [editId, setEditId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditForm>({ name: "", url: "", discord: false, events: [], title_template: "", body_template: "" });
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [testStates, setTestStates] = useState<Record<string, TestState>>({});

  function setTestState(id: string, state: TestState) {
    setTestStates((prev) => ({ ...prev, [id]: state }));
  }

  const addMutation = useMutation({
    mutationFn: () =>
      addWebhook({
        name: addForm.name,
        url: addForm.url,
        discord: addForm.discord,
        events: addForm.events,
        title_template: addForm.title_template,
        body_template: addForm.body_template,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["webhooks"] });
      setAddForm({ name: "", url: "", discord: false, events: ALL_EVENTS.map((e) => e.id), title_template: "", body_template: "" });
      setAddTestState({ status: "idle" });
      setAddOpen(false);
    },
  });

  const [toggleError, setToggleError] = useState<string | null>(null);
  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => updateWebhook(id, { enabled }),
    onSuccess: () => { setToggleError(null); void qc.invalidateQueries({ queryKey: ["webhooks"] }); },
    onError: (err) => setToggleError((err as Error)?.message || "Failed to update"),
  });

  const saveMutation = useMutation({
    mutationFn: ({ id, form }: { id: string; form: EditForm }) =>
      updateWebhook(id, {
        name: form.name,
        url: form.url,
        discord: form.discord,
        events: form.events,
        title_template: form.title_template,
        body_template: form.body_template,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["webhooks"] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => removeWebhook(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["webhooks"] });
      setConfirmDelete(null);
    },
  });

  function openEdit(wh: WebhookConfig) {
    setEditId(wh.id);
    setEditForm({
      name: wh.name,
      url: wh.url,
      discord: wh.discord,
      events: [...wh.events],
      title_template: wh.title_template ?? "",
      body_template: wh.body_template ?? "",
    });
    setConfirmDelete(null);
  }

  async function handleTest(id: string) {
    setTestState(id, { status: "pending" });
    try {
      await testWebhook(id);
      setTestState(id, { status: "ok" });
    } catch (err) {
      setTestState(id, { status: "err", msg: String((err as Error).message || "Test failed") });
    }
  }

  async function handleAddTest() {
    setAddTestState({ status: "pending" });
    try {
      await testWebhookPayload({
        url: addForm.url,
        discord: addForm.discord,
        events: addForm.events,
        title_template: addForm.title_template,
        body_template: addForm.body_template,
      });
      setAddTestState({ status: "ok" });
    } catch (err) {
      setAddTestState({ status: "err", msg: String((err as Error).message || "Test failed") });
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Webhook className="h-6 w-6 text-primary" />
          Webhooks
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Fire HTTP callbacks on Swirrl events. Discord embeds supported.
        </p>
      </section>

      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Plus className="h-4 w-4 text-primary" />
              Add webhook
            </CardTitle>
            <CardDescription>Register a new HTTP endpoint to receive event notifications.</CardDescription>
          </CardHeader>
          <CardContent>
            {addOpen ? (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium">Name</label>
                    <Input
                      value={addForm.name}
                      onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                      placeholder="My webhook"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium">URL</label>
                    <Input
                      value={addForm.url}
                      onChange={(e) => setAddForm((f) => ({ ...f, url: e.target.value }))}
                      placeholder="https://…"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium">Events</p>
                  <EventCheckboxes
                    events={addForm.events}
                    onChange={(events) => setAddForm((f) => ({ ...f, events }))}
                  />
                </div>
                <Toggle
                  checked={addForm.discord}
                  onChange={(v) => setAddForm((f) => ({ ...f, discord: v }))}
                  label="Discord embed format"
                />
                {addForm.discord && (
                  <div className="space-y-2 rounded-md border border-border p-3 bg-muted/40">
                    <p className="text-xs font-medium">Discord embed customization <span className="text-muted-foreground font-normal">(optional)</span></p>
                    <p className="text-xs text-muted-foreground">{PLACEHOLDER_HINT}</p>
                    <div className="space-y-1">
                      <label className="text-xs font-medium">Title</label>
                      <Input
                        value={addForm.title_template}
                        onChange={(e) => setAddForm((f) => ({ ...f, title_template: e.target.value }))}
                        placeholder="Swirrl — Job Completed"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium">Message</label>
                      <textarea
                        value={addForm.body_template}
                        onChange={(e) => setAddForm((f) => ({ ...f, body_template: e.target.value }))}
                        placeholder="`swirrl {module} {args}`"
                        rows={3}
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
                      />
                    </div>
                  </div>
                )}
                {addMutation.isError && (
                  <p className="text-xs text-destructive">
                    {String((addMutation.error as Error)?.message ?? "Failed")}
                  </p>
                )}
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    size="sm"
                    onClick={() => addMutation.mutate()}
                    disabled={!addForm.name.trim() || !addForm.url.trim() || addForm.events.length === 0 || addMutation.isPending}
                  >
                    Add
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void handleAddTest()}
                    disabled={!addForm.url.trim() || addTestState.status === "pending"}
                  >
                    <Zap className="mr-1.5 h-3.5 w-3.5" />Test
                  </Button>
                  <TestFeedback state={addTestState} />
                  <Button size="sm" variant="ghost" onClick={() => { setAddOpen(false); setAddTestState({ status: "idle" }); }}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />Add webhook
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Registered webhooks ({webhooks.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {toggleError && (
            <p className="mb-2 text-xs text-destructive">{toggleError}</p>
          )}
          {webhooksQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : webhooks.length === 0 ? (
            <p className="text-sm text-muted-foreground">No webhooks registered.</p>
          ) : (
            <div className="divide-y divide-border">
              {webhooks.map((wh) => {
                const ts = testStates[wh.id] ?? { status: "idle" };
                const isEditing = editId === wh.id;
                return (
                  <div key={wh.id} className="py-3 space-y-2">
                    {isEditing ? (
                      <div className="space-y-3">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="space-y-1">
                            <label className="text-xs font-medium">Name</label>
                            <Input
                              value={editForm.name}
                              onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs font-medium">URL</label>
                            <Input
                              value={editForm.url}
                              onChange={(e) => setEditForm((f) => ({ ...f, url: e.target.value }))}
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <p className="text-xs font-medium">Events</p>
                          <EventCheckboxes
                            events={editForm.events}
                            onChange={(events) => setEditForm((f) => ({ ...f, events }))}
                          />
                        </div>
                        <Toggle
                          checked={editForm.discord}
                          onChange={(v) => setEditForm((f) => ({ ...f, discord: v }))}
                          label="Discord embed format"
                        />
                        {editForm.discord && (
                          <div className="space-y-2 rounded-md border border-border p-3 bg-muted/40">
                            <p className="text-xs font-medium">Discord embed customization <span className="text-muted-foreground font-normal">(optional)</span></p>
                            <p className="text-xs text-muted-foreground">{PLACEHOLDER_HINT}</p>
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Title</label>
                              <Input
                                value={editForm.title_template}
                                onChange={(e) => setEditForm((f) => ({ ...f, title_template: e.target.value }))}
                                placeholder="Swirrl — Job Completed"
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium">Message</label>
                              <textarea
                                value={editForm.body_template}
                                onChange={(e) => setEditForm((f) => ({ ...f, body_template: e.target.value }))}
                                placeholder="`swirrl {module} {args}`"
                                rows={3}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
                              />
                            </div>
                          </div>
                        )}
                        {saveMutation.isError && (
                          <p className="text-xs text-destructive">
                            {String((saveMutation.error as Error)?.message ?? "Save failed")}
                          </p>
                        )}
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            onClick={() => saveMutation.mutate({ id: wh.id, form: editForm })}
                            disabled={!editForm.name.trim() || !editForm.url.trim() || editForm.events.length === 0 || saveMutation.isPending}
                          >
                            Save
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => setEditId(null)}>
                            <X className="mr-1 h-3.5 w-3.5" />Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-sm">{wh.name}</span>
                            {wh.discord && <Badge variant="secondary" className="text-xs">Discord</Badge>}
                            {!wh.enabled && <Badge variant="secondary" className="text-xs opacity-60">Disabled</Badge>}
                          </div>
                          <p className="text-xs text-muted-foreground truncate mt-0.5">{wh.url}</p>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {wh.events.map((ev) => (
                              <span key={ev} className="text-xs bg-muted rounded px-1.5 py-0.5">
                                {ALL_EVENTS.find((e) => e.id === ev)?.label ?? ev}
                              </span>
                            ))}
                          </div>
                        </div>
                        {isAdmin && (
                          <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
                            <Button
                              size="sm" variant="ghost" className="h-7 w-7 p-0 text-muted-foreground"
                              title="Send test event"
                              disabled={ts.status === "pending"}
                              onClick={() => void handleTest(wh.id)}
                            >
                              <Zap className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              size="sm" variant="ghost" className="h-7 w-7 p-0 text-muted-foreground"
                              title="Edit webhook"
                              onClick={() => openEdit(wh)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Toggle
                              checked={wh.enabled}
                              onChange={(v) => toggleMutation.mutate({ id: wh.id, enabled: v })}
                              label=""
                            />
                            {confirmDelete === wh.id ? (
                              <>
                                <span className="text-xs text-destructive">Delete?</span>
                                {deleteMutation.isError && (
                                  <span className="text-xs text-destructive">
                                    {String((deleteMutation.error as Error)?.message ?? "Failed")}
                                  </span>
                                )}
                                <Button size="sm" variant="destructive" className="h-7"
                                  onClick={() => deleteMutation.mutate(wh.id)}
                                  disabled={deleteMutation.isPending}>Yes</Button>
                                <Button size="sm" variant="outline" className="h-7"
                                  onClick={() => setConfirmDelete(null)}>No</Button>
                              </>
                            ) : (
                              <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                                onClick={() => setConfirmDelete(wh.id)}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    {ts.status !== "idle" && !isEditing && (
                      <div className="pl-0">
                        <TestFeedback state={ts} />
                      </div>
                    )}
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
