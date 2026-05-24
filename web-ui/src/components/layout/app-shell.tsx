import { Link, useRouterState } from "@tanstack/react-router";
import { ChevronDown, LayoutDashboard } from "lucide-react";
import type React from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Home" },
  { to: "/doctor", label: "Doctor" },
  { to: "/modules", label: "Modules" },
  { to: "/settings-setup", label: "Settings" },
  { to: "/seedbox", label: "Seedbox" },
  { to: "/upload", label: "Upload" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/batch", label: "Batch" },
  { to: "/studios", label: "Studios" },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_var(--color-surface),_var(--color-bg))] text-foreground">
      <header className="border-b border-border/80 bg-card/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="rounded-md border border-border bg-primary/20 p-2 text-primary">
              <LayoutDashboard className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold">Framekit Web</p>
              <p className="text-xs text-muted-foreground">V1 local dashboard</p>
            </div>
          </div>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent",
                  pathname === item.to ? "bg-accent text-accent-foreground" : "text-muted-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <DropdownMenu>
            <DropdownMenuTrigger className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-2 text-sm md:hidden">
              Navigation
              <ChevronDown className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Pages</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {navItems.map((item) => (
                <DropdownMenuItem key={item.to} asChild>
                  <Link to={item.to}>{item.label}</Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  );
}
