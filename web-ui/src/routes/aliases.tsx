import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookMarked, Check, Loader2, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { addAlias, disableAlias, enableAlias, getAliases, removeAlias } from "@/lib/api/endpoints";
import type { AliasItem } from "@/lib/api/schemas";

const QK = ["aliases"];

export function AliasesPage() {
  const qc = useQueryClient();
  const aliasesQuery = useQuery({ queryKey: QK, queryFn: getAliases });
  const aliases = aliasesQuery.data?.aliases ?? [];

  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCommand, setNewCommand] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: QK });

  const addMutation = useMutation({
    mutationFn: addAlias,
    onSuccess: () => {
      invalidate();
      setNewName("");
      setNewCommand("");
      setNewDesc("");
      setAddOpen(false);
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeAlias,
    onSuccess: invalidate,
  });

  const enableMutation = useMutation({
    mutationFn: enableAlias,
    onSuccess: invalidate,
  });

  const disableMutation = useMutation({
    mutationFn: disableAlias,
    onSuccess: invalidate,
  });

  const togglePending = (name: string) =>
    (enableMutation.isPending && enableMutation.variables === name) ||
    (disableMutation.isPending && disableMutation.variables === name);

  const userAliases = aliases.filter((a) => a.kind === "user");
  const builtinAliases = aliases.filter((a) => a.kind === "builtin");

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Aliases</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Command shortcuts that expand to full Framekit commands. User aliases can be created, enabled, or removed. Built-in aliases can only be toggled.
        </p>
      </section>

      {/* Add alias form */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <Plus className="h-4 w-4 text-primary" />
              Add User Alias
            </CardTitle>
            <Button type="button" variant="ghost" size="sm" onClick={() => setAddOpen((v) => !v)}>
              {addOpen ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            </Button>
          </div>
        </CardHeader>
        {addOpen && (
          <CardContent className="space-y-3 pt-0">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Name</label>
                <input
                  className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="my-alias"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Command</label>
                <input
                  className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  placeholder="pipeline --preset default"
                  value={newCommand}
                  onChange={(e) => setNewCommand(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Description (optional)</label>
              <input
                className="w-full h-8 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="Short description…"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
            </div>
            {addMutation.isError && (
              <p className="text-xs text-destructive">{String((addMutation.error as Error)?.message ?? "Error")}</p>
            )}
            <Button
              type="button"
              size="sm"
              disabled={!newName.trim() || !newCommand.trim() || addMutation.isPending}
              onClick={() =>
                addMutation.mutate({
                  name: newName.trim(),
                  command: newCommand.trim(),
                  description: newDesc.trim(),
                })
              }
            >
              {addMutation.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="mr-1.5 h-3.5 w-3.5" />
              )}
              Save alias
            </Button>
          </CardContent>
        )}
      </Card>

      {/* User aliases */}
      <AliasSection
        title="User Aliases"
        aliases={userAliases}
        loading={aliasesQuery.isLoading}
        emptyMessage="No user aliases defined."
        canDelete
        togglePending={togglePending}
        onToggle={(a) => (a.enabled ? disableMutation.mutate(a.name) : enableMutation.mutate(a.name))}
        onDelete={(a) => removeMutation.mutate(a.name)}
        deletePending={(name) => removeMutation.isPending && removeMutation.variables === name}
      />

      {/* Built-in aliases */}
      <AliasSection
        title="Built-in Aliases"
        aliases={builtinAliases}
        loading={aliasesQuery.isLoading}
        emptyMessage="No built-in aliases."
        canDelete={false}
        togglePending={togglePending}
        onToggle={(a) => (a.enabled ? disableMutation.mutate(a.name) : enableMutation.mutate(a.name))}
        onDelete={() => {}}
        deletePending={() => false}
      />
    </div>
  );
}

function AliasSection({
  title,
  aliases,
  loading,
  emptyMessage,
  canDelete,
  togglePending,
  onToggle,
  onDelete,
  deletePending,
}: {
  title: string;
  aliases: AliasItem[];
  loading: boolean;
  emptyMessage: string;
  canDelete: boolean;
  togglePending: (name: string) => boolean;
  onToggle: (a: AliasItem) => void;
  onDelete: (a: AliasItem) => void;
  deletePending: (name: string) => boolean;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <BookMarked className="h-4 w-4 text-primary" />
          {title}
          {!loading && (
            <Badge variant="secondary" className="ml-1 font-mono">
              {aliases.length}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : aliases.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        ) : (
          <div className="divide-y divide-border">
            {aliases.map((a) => (
              <div key={a.name} className="flex items-start gap-3 py-2.5">
                <button
                  type="button"
                  onClick={() => onToggle(a)}
                  disabled={togglePending(a.name)}
                  className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border bg-background transition-colors hover:bg-secondary disabled:opacity-50"
                  title={a.enabled ? "Disable" : "Enable"}
                >
                  {togglePending(a.name) ? (
                    <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  ) : a.enabled ? (
                    <Check className="h-3 w-3 text-primary" />
                  ) : null}
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold font-mono">{a.name}</span>
                    {!a.enabled && (
                      <Badge variant="secondary" className="text-xs">
                        disabled
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs font-mono text-muted-foreground truncate mt-0.5">{a.command}</p>
                  {a.description && (
                    <p className="text-xs text-muted-foreground mt-0.5">{a.description}</p>
                  )}
                </div>
                {canDelete && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-destructive hover:text-destructive shrink-0"
                    disabled={deletePending(a.name)}
                    onClick={() => onDelete(a)}
                  >
                    {deletePending(a.name) ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
