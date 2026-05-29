import { useQuery } from "@tanstack/react-query";
import { Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getSystemInfo } from "@/lib/api/endpoints";

export function AboutPage() {
  const infoQuery = useQuery({ queryKey: ["system-info"], queryFn: getSystemInfo });
  const info = infoQuery.data;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">About</h1>
        <p className="mt-1 text-sm text-muted-foreground">Self-hosted media workflow automation.</p>
        <p className="text-xs text-muted-foreground">Operator-focused tooling for release preparation and publishing.</p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-4 w-4 text-primary" />
            Ouro
          </CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              <tr>
                <td className="py-2 pr-6 text-muted-foreground font-medium w-40">Application</td>
                <td className="py-2 font-semibold">Ouro</td>
              </tr>
              <tr>
                <td className="py-2 pr-6 text-muted-foreground font-medium">Version</td>
                <td className="py-2 font-mono">
                  {info ? (
                    <Badge variant="secondary">{info.version}</Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
              <tr>
                <td className="py-2 pr-6 text-muted-foreground font-medium">Python</td>
                <td className="py-2 font-mono text-xs">{info?.python_version ?? "—"}</td>
              </tr>
              <tr>
                <td className="py-2 pr-6 text-muted-foreground font-medium">API status</td>
                <td className="py-2">
                  {infoQuery.isLoading ? (
                    <Badge variant="secondary">Checking…</Badge>
                  ) : infoQuery.isError ? (
                    <Badge variant="danger">Unreachable</Badge>
                  ) : (
                    <Badge variant="success">Online</Badge>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">License</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-1">
          <p>Ouro is proprietary software.</p>
          <p>Unauthorized distribution or modification is prohibited.</p>
        </CardContent>
      </Card>
    </div>
  );
}
