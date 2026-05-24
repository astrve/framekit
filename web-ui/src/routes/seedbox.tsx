import { useMutation } from "@tanstack/react-query";
import { Copy, HardDriveDownload } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { runModule } from "@/lib/api/endpoints";
import type { RunModuleResult } from "@/lib/api/schemas";

type SeedboxAction = "list" | "status" | "doctor" | "history" | "push" | "pull";

export function SeedboxPage() {
  const [action, setAction] = useState<SeedboxAction>("status");
  const [pathA, setPathA] = useState("");
  const [pathB, setPathB] = useState("");
  const [seedboxName, setSeedboxName] = useState("");
  const [category, setCategory] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [verbose, setVerbose] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const runMutation = useMutation({
    mutationFn: runModule,
  });

  const buildArgs = (): string => {
    const args: string[] = [action];
    if (seedboxName.trim()) {
      args.push("--seedbox", `"${seedboxName.trim()}"`);
    }
    if (action === "history") {
      args.push("--limit", "50");
    }
    if (action === "push" || action === "pull") {
      if (pathA.trim()) {
        args.push(`"${pathA.trim()}"`);
      }
      if (action === "pull" && pathB.trim()) {
        args.push(`"${pathB.trim()}"`);
      }
      if (category.trim() && action === "push") {
        args.push("--category", `"${category.trim()}"`);
      }
      if (dryRun) {
        args.push("--dry-run");
      }
      if (verbose) {
        args.push("--verbose");
      }
    }
    return args.join(" ");
  };

  const result: RunModuleResult | null = runMutation.data ?? null;

  const validateAction = (): string | null => {
    if (action === "push" && !pathA.trim()) {
      return "Push requiert Path A (source local).";
    }
    if (action === "pull" && !pathA.trim()) {
      return "Pull requiert Path A (remote path).";
    }
    return null;
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Seedbox</h1>
        <p className="mt-1 text-sm text-muted-foreground">Parité CLI stricte via actions core seedbox.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDriveDownload className="h-4 w-4 text-primary" />
            Action
          </CardTitle>
          <CardDescription>Construit commande `framekit seedbox ...`</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <label className="space-y-1 text-sm" htmlFor="seedbox-action">
              Action
              <select
                id="seedbox-action"
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={action}
                onChange={(event) => {
                  setAction(event.target.value as SeedboxAction);
                  if (event.target.value === "list") {
                    setPathA("");
                    setPathB("");
                    setCategory("");
                  }
                }}
              >
                <option value="list">list</option>
                <option value="status">status</option>
                <option value="doctor">doctor</option>
                <option value="history">history</option>
                <option value="push">push</option>
                <option value="pull">pull</option>
              </select>
            </label>
            <label className="space-y-1 text-sm" htmlFor="seedbox-name">
              Seedbox
              <Input id="seedbox-name" value={seedboxName} onChange={(e) => setSeedboxName(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm" htmlFor="seedbox-category">
              Category (push)
              <Input id="seedbox-category" value={category} onChange={(e) => setCategory(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm md:col-span-3" htmlFor="seedbox-path-a">
              Path A (source/remote path)
              <Input id="seedbox-path-a" value={pathA} onChange={(e) => setPathA(e.target.value)} />
            </label>
            <label className="space-y-1 text-sm md:col-span-3" htmlFor="seedbox-path-b">
              Path B (pull local dest)
              <Input id="seedbox-path-b" value={pathB} onChange={(e) => setPathB(e.target.value)} />
            </label>
          </div>

          <div className="flex flex-wrap gap-4 text-sm">
            <label className="inline-flex items-center gap-2">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              dry-run
            </label>
            <label className="inline-flex items-center gap-2">
              <input type="checkbox" checked={verbose} onChange={(e) => setVerbose(e.target.checked)} />
              verbose
            </label>
          </div>

          <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            framekit seedbox {buildArgs()}
          </pre>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => {
                const issue = validateAction();
                setLocalError(issue);
                if (issue) {
                  return;
                }
                runMutation.mutate({
                  module: "seedbox",
                  args_text: buildArgs(),
                  dry_run: false,
                  auto_yes: false,
                  confirm_destructive: true,
                });
              }}
            >
              Exécuter
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                await navigator.clipboard.writeText(`framekit seedbox ${buildArgs()}`.trim());
                setCopied(true);
                setTimeout(() => setCopied(false), 1000);
              }}
            >
              <Copy className="mr-2 h-4 w-4" />
              {copied ? "Copié" : "Copier commande"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAction("status");
                setPathA("");
                setPathB("");
                setSeedboxName("");
                setCategory("");
                setDryRun(true);
                setVerbose(false);
                setLocalError(null);
              }}
            >
              Reset
            </Button>
          </div>

          {localError ? (
            <p className="rounded-md border border-rose-400/60 bg-rose-500/10 p-3 text-sm text-rose-800">
              {localError}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
            <CardDescription>Return code: {result.returncode}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Badge variant={result.ok ? "success" : "danger"}>{result.ok ? "success" : "failed"}</Badge>
            <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
              {result.stdout || "(stdout empty)"}
            </pre>
            {result.stderr ? (
              <pre className="max-h-72 overflow-auto rounded-md border border-rose-300 bg-rose-100 p-3 text-xs text-rose-800">
                {result.stderr}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
