import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { changeAuthUserPassword, createAuthUser, deleteAuthUser, disableAuthUser, enableAuthUser, getAuthUsers } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth";
import type { AuthUser } from "@/lib/api/schemas";

export function UsersPage() {
  const { token, user: me } = useAuth();
  const qc = useQueryClient();

  const usersQuery = useQuery({
    queryKey: ["auth-users"],
    queryFn: () => getAuthUsers(token!),
    enabled: !!token,
  });

  const [addOpen, setAddOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"viewer" | "admin">("viewer");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [pwdOpen, setPwdOpen] = useState<string | null>(null);
  const [pwdInput, setPwdInput] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createAuthUser(token!, { username: newUsername, password: newPassword, role: newRole }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["auth-users"] });
      setNewUsername("");
      setNewPassword("");
      setNewRole("viewer");
      setAddOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAuthUser(token!, id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["auth-users"] });
      setConfirmDelete(null);
    },
  });

  const enableMutation = useMutation({
    mutationFn: (id: string) => enableAuthUser(token!, id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["auth-users"] }),
  });

  const disableMutation = useMutation({
    mutationFn: (id: string) => disableAuthUser(token!, id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["auth-users"] }),
  });

  const changePwdMutation = useMutation({
    mutationFn: ({ id, pwd }: { id: string; pwd: string }) => changeAuthUserPassword(token!, id, pwd),
    onSuccess: () => { setPwdOpen(null); setPwdInput(""); },
  });

  if (!token || me?.role !== "admin") {
    return (
      <div className="space-y-6">
        <section className="rounded-2xl border border-border bg-card p-5">
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="mt-1 text-sm text-destructive">Admin access required.</p>
        </section>
      </div>
    );
  }

  const users: AuthUser[] = usersQuery.data?.users ?? [];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" />
          Users
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage accounts and access roles. Logged in as <strong>{me.username}</strong>.
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Plus className="h-4 w-4 text-primary" />
            Add user
          </CardTitle>
          <CardDescription>Create a new account with viewer or admin access.</CardDescription>
        </CardHeader>
        <CardContent>
          {addOpen ? (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium">Username</label>
                  <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="username" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">Password</label>
                  <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="min 8 chars" />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">Role</label>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                    value={newRole}
                    onChange={(e) => setNewRole(e.target.value as "viewer" | "admin")}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
              </div>
              {createMutation.isError && (
                <p className="text-xs text-destructive">{String((createMutation.error as Error)?.message)}</p>
              )}
              <div className="flex gap-2">
                <Button size="sm" onClick={() => createMutation.mutate()}
                  disabled={!newUsername || !newPassword || createMutation.isPending}>
                  Create
                </Button>
                <Button size="sm" variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <Button size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />Add user
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">All users ({users.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {usersQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : users.length === 0 ? (
            <p className="text-sm text-muted-foreground">No users found.</p>
          ) : (
            <div className="divide-y divide-border">
              {users.map((u) => (
                <div key={u.id} className="flex items-center gap-3 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{u.username}</span>
                      {u.id === me.id && <Badge variant="secondary" className="text-xs">You</Badge>}
                      <Badge variant={u.role === "admin" ? "default" : "secondary"} className="text-xs">
                        {u.role}
                      </Badge>
                      {!u.enabled && <Badge variant="secondary" className="text-xs opacity-60">Disabled</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Created {new Date(u.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {/* Change password */}
                    {pwdOpen === u.id ? (
                      <div className="flex items-center gap-1">
                        <Input
                          type="password"
                          value={pwdInput}
                          onChange={(e) => setPwdInput(e.target.value)}
                          placeholder="New password"
                          className="h-7 w-32 text-xs"
                        />
                        <Button size="sm" className="h-7 text-xs"
                          onClick={() => changePwdMutation.mutate({ id: u.id, pwd: pwdInput })}
                          disabled={!pwdInput.trim() || changePwdMutation.isPending}>Set</Button>
                        <Button size="sm" variant="outline" className="h-7 text-xs"
                          onClick={() => { setPwdOpen(null); setPwdInput(""); }}>Cancel</Button>
                      </div>
                    ) : (
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-muted-foreground"
                        title="Change password"
                        onClick={() => { setPwdOpen(u.id); setPwdInput(""); }}>
                        <KeyRound className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {/* Enable / Disable (not self) */}
                    {u.id !== me.id && pwdOpen !== u.id && (
                      <Button size="sm" variant="ghost" className="h-7 text-xs px-2"
                        onClick={() => u.enabled
                          ? disableMutation.mutate(u.id)
                          : enableMutation.mutate(u.id)}
                        disabled={enableMutation.isPending || disableMutation.isPending}
                        title={u.enabled ? "Disable account" : "Enable account"}>
                        {u.enabled ? "Disable" : "Enable"}
                      </Button>
                    )}
                    {/* Delete (not self) */}
                    {u.id !== me.id && pwdOpen !== u.id && (
                      confirmDelete === u.id ? (
                        <>
                          <span className="text-xs text-destructive mr-1">Delete?</span>
                          <Button size="sm" variant="destructive" className="h-7"
                            onClick={() => deleteMutation.mutate(u.id)}
                            disabled={deleteMutation.isPending}>Yes</Button>
                          <Button size="sm" variant="outline" className="h-7"
                            onClick={() => setConfirmDelete(null)}>No</Button>
                        </>
                      ) : (
                        <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                          onClick={() => setConfirmDelete(u.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )
                    )}
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
