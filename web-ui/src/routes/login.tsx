import { useMutation, useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authLogin, authSetup, getAuthStatus } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const statusQuery = useQuery({ queryKey: ["auth-status"], queryFn: getAuthStatus });
  const isSetup = statusQuery.data && !statusQuery.data.has_users;

  const loginMutation = useMutation({
    mutationFn: () => (isSetup ? authSetup(username, password) : authLogin(username, password)),
    onSuccess: (data) => {
      login(data.access_token, data.user);
      setDone(true);
      // Redirect via full reload to reset router auth state
      window.location.href = "/";
    },
    onError: (err: Error) => {
      setError(err.message || "Invalid credentials");
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    loginMutation.mutate();
  }

  if (done) return null;

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <img src="/logo.svg" alt="Ouro" className="h-10 w-10" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Ouro</h1>
          <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
            Self-hosted media workflow automation
          </p>
          <p className="text-sm text-muted-foreground">
            {isSetup ? "Create first admin account to continue." : "Sign in to continue."}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Username</label>
            <Input
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              required
              disabled={loginMutation.isPending}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Password</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              disabled={loginMutation.isPending}
            />
            {isSetup && (
              <p className="text-xs text-muted-foreground">Minimum 8 characters.</p>
            )}
          </div>

          {error && (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={loginMutation.isPending}>
            <Lock className="mr-2 h-4 w-4" />
            {loginMutation.isPending
              ? "Please wait…"
              : isSetup
              ? "Create account"
              : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  );
}
