import { Link } from "@tanstack/react-router";
import { Clapperboard, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DEDICATED_MODULE_CONFIGS } from "@/routes/dedicated-modules-config";

export function StudiosPage() {
  const [search, setSearch] = useState("");
  const [safeOnly, setSafeOnly] = useState(false);

  const allModules = DEDICATED_MODULE_CONFIGS;
  const safeByDefaultCount = allModules.filter((item) => item.requiredFlags?.includes("--dry-run")).length;

  const visibleModules = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return allModules.filter((item) => {
      if (safeOnly && !item.requiredFlags?.includes("--dry-run")) {
        return false;
      }
      if (!needle) return true;
      return (
        item.slug.toLowerCase().includes(needle) ||
        item.title.toLowerCase().includes(needle) ||
        item.description.toLowerCase().includes(needle)
      );
    });
  }, [allModules, safeOnly, search]);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              <Clapperboard className="h-6 w-6 text-primary" />
              Modules
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">Dedicated pages for each CLI module.</p>
          </div>
          <Link
            to="/jobs"
            className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
          >
            Open Jobs
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Module Pages</CardTitle>
            <CardDescription>Total dedicated surfaces</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{allModules.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Safe by Default</CardTitle>
            <CardDescription>Require `--dry-run` in presets</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{safeByDefaultCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Visible</CardTitle>
            <CardDescription>After current filters</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{visibleModules.length}</p>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Search className="h-4 w-4 text-primary" />
            Filters
          </CardTitle>
          <CardDescription>Find the right module page quickly.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search module name or description..."
          />
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={safeOnly ? "outline" : "default"}
              size="sm"
              onClick={() => setSafeOnly(false)}
            >
              All
            </Button>
            <Button
              type="button"
              variant={safeOnly ? "default" : "outline"}
              size="sm"
              onClick={() => setSafeOnly(true)}
            >
              Safe by default only
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleModules.map((item) => (
          <Card key={item.slug}>
            <CardHeader>
              <CardTitle>{item.title}</CardTitle>
              <CardDescription className="space-y-1">
                <span>{item.description}</span>
                <span className="block text-xs text-muted-foreground">
                  {item.requiredFlags?.includes("--dry-run")
                    ? "Safe default: dry-run required"
                    : "Live mode available"}
                </span>
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild size="sm">
                <Link to="/module/$moduleSlug" params={{ moduleSlug: item.slug }}>
                  Open {item.slug}
                </Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      {visibleModules.length === 0 ? (
        <p className="rounded-md border border-border bg-muted p-3 text-sm text-muted-foreground">
          No module matches current filters.
        </p>
      ) : null}
    </div>
  );
}
