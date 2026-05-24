import { Link } from "@tanstack/react-router";
import { Activity, ServerCog, ShieldCheck } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const cards = [
  {
    icon: Activity,
    title: "Observabilité rapide",
    description: "Lancer diagnostics doctor et suivre statuts ok/warn/err sans terminal.",
  },
  {
    icon: ServerCog,
    title: "API typée",
    description: "Contrats frontend/backend validés runtime avec schémas Zod.",
  },
  {
    icon: ShieldCheck,
    title: "Base maintenable",
    description: "TypeScript strict, tests Vitest/Playwright, lint a11y prêt pour futures features.",
  },
];

export function HomePage() {
  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-border/80 bg-card p-6 shadow-sm">
        <p className="text-sm uppercase tracking-[0.18em] text-primary">Framekit stack must</p>
        <h1 className="mt-2 text-3xl font-semibold leading-tight text-balance">Interface web locale moderne, fiable, testable.</h1>
        <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
          Cette base V1 prépare terrain pour workflows Framekit tout en gardant CLI intacte.
        </p>
        <div className="mt-6">
          <div className="flex flex-wrap gap-2">
            <Link to="/doctor" className="inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              Ouvrir diagnostic Doctor
            </Link>
            <Link to="/modules" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Modules Workbench
            </Link>
            <Link to="/settings-setup" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Settings/Setup
            </Link>
            <Link to="/seedbox" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Seedbox
            </Link>
            <Link to="/upload" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Upload
            </Link>
            <Link to="/pipeline" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Pipeline
            </Link>
            <Link to="/batch" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Batch
            </Link>
            <Link to="/studios" className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent">
              Ouvrir Studios
            </Link>
            <Link
              to="/studio/$module"
              params={{ module: "watch" }}
              className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent"
            >
              Ouvrir Module Studio
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {cards.map(({ icon: Icon, title, description }) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Icon className="h-4 w-4 text-primary" />
                {title}
              </CardTitle>
              <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent />
          </Card>
        ))}
      </section>
    </div>
  );
}
