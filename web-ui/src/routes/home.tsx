import { Link } from "@tanstack/react-router";
import { ArrowRight, Code2, HardDriveDownload, Layers, Play, ScrollText, Settings, Stethoscope, Upload, Wrench } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const features = [
  {
    icon: Play,
    title: "Pipeline",
    description: "Process a single release end-to-end: rename, clean, metadata, NFO, torrent, presentation.",
    to: "/pipeline",
  },
  {
    icon: Layers,
    title: "Batch",
    description: "Run the full pipeline across an entire folder of releases automatically.",
    to: "/batch",
  },
  {
    icon: HardDriveDownload,
    title: "Seedbox",
    description: "Send and receive files from your remote seedbox with one click.",
    to: "/seedbox",
  },
  {
    icon: Upload,
    title: "Upload",
    description: "Push releases to configured trackers and manage upload history.",
    to: "/upload",
  },
  {
    icon: Wrench,
    title: "Presets & Profiles",
    description: "Browse and manage presets, templates, and profiles for all modules.",
    to: "/presets",
  },
  {
    icon: Wrench,
    title: "Modules",
    description: "Run any individual tool: inspect, rename, clean MKV, screenshot, encode, and more.",
    to: "/studios",
  },
  {
    icon: ScrollText,
    title: "Logs",
    description: "Live view of the Framekit log file with level filtering and export.",
    to: "/logs",
  },
  {
    icon: Stethoscope,
    title: "Diagnostics",
    description: "Run health checks on your configuration and tool dependencies.",
    to: "/doctor",
  },
  {
    icon: Settings,
    title: "Jobs",
    description: "Monitor running and completed module jobs in real time.",
    to: "/modules",
  },
  {
    icon: Settings,
    title: "Settings",
    description: "Manage language, log level, upload preferences, and seedbox profiles.",
    to: "/settings-setup",
  },
] as const;

export function HomePage() {
  return (
    <div className="space-y-8">
      {/* Main hero */}
      <section className="overflow-hidden rounded-2xl border border-primary/20 bg-card p-6 shadow-sm">
        <div className="flex items-start gap-4">
          <div className="rounded-xl border border-primary/30 bg-primary/10 p-3">
            <Play className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Framekit</p>
            <h1 className="mt-1 text-2xl font-bold leading-tight tracking-tight">Your local media workflow hub</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Build, process, and distribute releases from one interface — no terminal required.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Link
                to="/pipeline"
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Open Pipeline
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                to="/batch"
                className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-secondary"
              >
                Open Batch
              </Link>
              <Link
                to="/presets"
                className="inline-flex rounded-md border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-secondary"
              >
                Presets & Profiles
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* GitHub card */}
      <a
        href="https://github.com/astrve/framekit"
        target="_blank"
        rel="noopener noreferrer"
        className="group flex items-center gap-4 rounded-2xl border border-border/60 bg-card px-5 py-4 transition-colors hover:border-primary/40 hover:bg-secondary/40"
      >
        <div className="rounded-md border border-primary/20 bg-primary/10 p-2 transition-colors group-hover:bg-primary/20">
          <Code2 className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold">astrve/framekit</p>
          <p className="text-xs text-muted-foreground">Source code, issues, and releases on GitHub</p>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </a>

      {/* Feature cards */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {features.map(({ icon: Icon, title, description, to }) => (
          <Link key={to} to={to} className="group block">
            <Card className="h-full border-border/60 transition-colors hover:border-primary/40 hover:bg-secondary/40">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <div className="rounded-md border border-primary/20 bg-primary/10 p-1.5 transition-colors group-hover:bg-primary/20">
                    <Icon className="h-4 w-4 text-primary" />
                  </div>
                  {title}
                </CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="inline-flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  Open <ArrowRight className="h-3 w-3" />
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
}
