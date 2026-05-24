import { Link } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DEDICATED_MODULE_CONFIGS } from "@/routes/dedicated-modules-config";

export function StudiosPage() {
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Studios modules</h1>
        <p className="mt-1 text-sm text-muted-foreground">Pages dédiées module par module avec presets exécution.</p>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {DEDICATED_MODULE_CONFIGS.map((item) => (
          <Card key={item.slug}>
            <CardHeader>
              <CardTitle>{item.title}</CardTitle>
              <CardDescription>{item.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild size="sm">
                <Link to="/module/$moduleSlug" params={{ moduleSlug: item.slug }}>
                  Ouvrir {item.slug}
                </Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
