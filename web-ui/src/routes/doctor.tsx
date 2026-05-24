import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { Info, RefreshCw, Server } from "lucide-react";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { getDoctorPayload, getHealth, getSystemInfo } from "@/lib/api/endpoints";
import type { DoctorCheck } from "@/lib/api/schemas";

const formSchema = z.object({
  scope: z.string().min(2),
});

type FormValues = z.infer<typeof formSchema>;

function statusToVariant(status: DoctorCheck["status"]): "success" | "warning" | "danger" {
  if (status === "ok") {
    return "success";
  }
  if (status === "warn") {
    return "warning";
  }
  return "danger";
}

export function DoctorPage() {
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });
  const systemInfoQuery = useQuery({
    queryKey: ["system-info"],
    queryFn: getSystemInfo,
  });
  const doctorQuery = useQuery({
    queryKey: ["doctor"],
    queryFn: getDoctorPayload,
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { scope: "full" },
  });

  const statusCounts = useMemo(() => {
    const checks = doctorQuery.data?.checks ?? [];
    return {
      ok: checks.filter((check) => check.status === "ok").length,
      warn: checks.filter((check) => check.status === "warn").length,
      err: checks.filter((check) => check.status === "err").length,
    };
  }, [doctorQuery.data?.checks]);

  const onSubmit = async (): Promise<void> => {
    await doctorQuery.refetch();
    toast.success("Doctor relancé.");
  };
  const scopeInputId = "doctor-scope";

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <section className="rounded-2xl border border-border bg-card p-5">
          <h1 className="text-2xl font-semibold tracking-tight">Doctor Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">Diagnostic runtime Framekit via API locale.</p>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Server className="h-4 w-4 text-primary" />
                Health
              </CardTitle>
              <CardDescription>Etat backend FastAPI</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant={healthQuery.data?.status === "ok" ? "success" : "danger"}>
                {healthQuery.data?.status ?? "unknown"}
              </Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">System</CardTitle>
              <CardDescription>Version Framekit / Python</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <p>Framekit: {systemInfoQuery.data?.version ?? "..."}</p>
              <p>Python: {systemInfoQuery.data?.python_version ?? "..."}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Doctor summary</CardTitle>
              <CardDescription>Résultat dernier run</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Badge variant="success">ok: {statusCounts.ok}</Badge>
              <Badge variant="warning">warn: {statusCounts.warn}</Badge>
              <Badge variant="danger">err: {statusCounts.err}</Badge>
            </CardContent>
          </Card>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Run doctor</CardTitle>
            <CardDescription>Action non destructive. Paramètre scope préparé pour extension API future.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="flex flex-wrap items-end gap-3" onSubmit={form.handleSubmit(onSubmit)}>
              <label className="space-y-1 text-sm" htmlFor={scopeInputId}>
                Scope
                <Input id={scopeInputId} {...form.register("scope")} className="w-52" />
              </label>
              <Button type="submit" disabled={doctorQuery.isFetching}>
                {doctorQuery.isFetching ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : null}
                Relancer
              </Button>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button type="button" variant="outline" onClick={() => doctorQuery.refetch()}>
                    <Info className="mr-2 h-4 w-4" />
                    Refresh brut
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Requête GET /api/v1/doctor directe</TooltipContent>
              </Tooltip>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Checks</CardTitle>
              <CardDescription>Etat détaillé par section</CardDescription>
            </div>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="secondary">Voir payload brut</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Doctor JSON</DialogTitle>
                  <DialogDescription>Contrat validé côté frontend via Zod.</DialogDescription>
                </DialogHeader>
                <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
                  {JSON.stringify(doctorQuery.data ?? {}, null, 2)}
                </pre>
              </DialogContent>
            </Dialog>
          </CardHeader>
          <CardContent className="space-y-2">
            {doctorQuery.isError ? (
              <p className="rounded-md border border-rose-400/60 bg-rose-500/10 p-3 text-sm text-rose-800">Erreur API doctor.</p>
            ) : null}
            {(doctorQuery.data?.checks ?? []).slice(0, 30).map((check) => (
              <div key={`${check.section}:${check.name}`} className="grid gap-2 rounded-md border border-border p-3 md:grid-cols-[180px_1fr_auto]">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{check.section}</p>
                <p className="text-sm">{check.name}: {check.detail}</p>
                <Badge variant={statusToVariant(check.status)}>{check.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
