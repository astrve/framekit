import { Link, useRouterState } from "@tanstack/react-router";
import {
  ActivitySquare,
  Bolt,
  BookMarked,
  ChevronDown,
  Clapperboard,
  FileCog,
  Info,
  LayoutDashboard,
  Layers,
  LogOut,
  Moon,
  ScrollText,
  Server,
  Settings,
  ShieldCheck,
  Stethoscope,
  Sun,
  Terminal,
  Upload,
  Webhook,
} from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { DEDICATED_MODULE_CONFIGS } from "@/routes/dedicated-modules-config";

// ─── top nav ─────────────────────────────────────────────────────────────────

const topNav = [
  { to: "/", label: "Home", icon: LayoutDashboard },
  { to: "/pipeline", label: "Pipeline", icon: Bolt },
  { to: "/batch", label: "Batch", icon: Layers },
  { to: "/seedbox", label: "Seedbox", icon: Server },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/presets", label: "Presets & Profiles", icon: FileCog },
  { to: "/aliases", label: "Aliases", icon: BookMarked },
  { to: "/logs", label: "Logs", icon: ScrollText },
  { to: "/doctor", label: "Diagnostics", icon: Stethoscope },
  { to: "/cli", label: "Terminal", icon: Terminal },
  { to: "/modules", label: "Jobs", icon: ActivitySquare },
  { to: "/about", label: "About", icon: Info },
] as const;

// ─── contextual sidebar definitions ──────────────────────────────────────────

const SETTINGS_SECTIONS = [
  { id: "s-profiles", label: "Profiles" },
  { id: "s-general", label: "General" },
  { id: "s-file-locations", label: "File Locations" },
  { id: "s-logging", label: "Logging" },
  { id: "s-tools", label: "External Tools" },
  { id: "s-metadata", label: "Metadata" },
  { id: "s-upload", label: "Upload" },
  { id: "s-seedbox", label: "Seedbox" },
  { id: "s-watch", label: "Watch" },
  { id: "s-pipeline", label: "Pipeline" },
  { id: "s-nfo", label: "NFO" },
  { id: "s-torrent", label: "Torrent" },
  { id: "s-prez", label: "Prez" },
  { id: "s-cleanmkv", label: "CleanMKV" },
  { id: "s-renamer", label: "Renamer" },
  { id: "s-screenshot", label: "Screenshot" },
  { id: "s-encoder", label: "Encoder" },
  { id: "s-security", label: "Security & Vault" },
];

const PRESETS_SECTIONS = [
  { id: "p-pipeline", label: "Pipeline Presets" },
  { id: "p-prez", label: "Prez Presets" },
  { id: "p-nfo", label: "NFO Templates" },
  { id: "p-prez-templates", label: "Prez Templates" },
  { id: "p-cleanmkv", label: "CleanMKV Presets" },
  { id: "p-renamer", label: "Renamer Profiles" },
  { id: "p-announces", label: "Announces" },
  { id: "p-tokens", label: "API Tokens" },
  { id: "p-renamer-rules", label: "Renamer Rules" },
];

// ─── helpers ──────────────────────────────────────────────────────────────────

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function FramekitLogo() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="19" fill="none" viewBox="0 0 48 46" aria-hidden="true" className="text-primary">
      <path fill="currentColor" d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" />
    </svg>
  );
}

// ─── contextual sidebar ───────────────────────────────────────────────────────

function ContextualSidebar({ pathname }: { pathname: string }) {
  const isSettings = pathname === "/settings-setup";
  const isPresets = pathname === "/presets";
  const isModules = pathname === "/modules" || pathname === "/studios" || pathname === "/configuration";

  if (!isSettings && !isPresets && !isModules) return null;

  return (
    <aside className="hidden lg:flex w-[192px] shrink-0 flex-col border-r border-border/60 bg-card/40 sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto">
      <nav className="px-2 py-4 space-y-0.5">
        {isSettings && (
          <>
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Settings</p>
            {SETTINGS_SECTIONS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => scrollToSection(s.id)}
                className="flex w-full items-center rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground text-left"
              >
                {s.label}
              </button>
            ))}
            <div className="pt-2 mt-1 border-t border-border/60">
              <Link to="/logs" className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
                <ScrollText className="h-3.5 w-3.5" />
                Logs
              </Link>
            </div>
          </>
        )}

        {isPresets && (
          <>
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Presets & Profiles</p>
            {PRESETS_SECTIONS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => scrollToSection(s.id)}
                className="flex w-full items-center rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground text-left"
              >
                {s.label}
              </button>
            ))}
          </>
        )}

        {isModules && (
          <>
            <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Modules</p>
            {DEDICATED_MODULE_CONFIGS.map((m) => (
              <Link
                key={m.slug}
                to="/module/$moduleSlug"
                params={{ moduleSlug: m.slug }}
                className="flex items-center rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                {m.title}
              </Link>
            ))}
            <div className="pt-2 mt-1 border-t border-border/60">
              <Link to="/studios" className="flex items-center rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground">
                Browse all →
              </Link>
            </div>
          </>
        )}
      </nav>
    </aside>
  );
}

// ─── app shell ────────────────────────────────────────────────────────────────

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user: authUser, logout } = useAuth();
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [dark]);

  const hasContextualSidebar =
    pathname === "/settings-setup" ||
    pathname === "/presets" ||
    pathname === "/modules" ||
    pathname === "/studios" ||
    pathname === "/configuration";

  return (
    <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_left,_var(--color-surface),_var(--color-bg))] text-foreground">
      {/* ── Top nav ────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 border-b border-border/60 bg-card/80 backdrop-blur">
        <div className="flex h-14 items-center gap-2 px-4">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 transition-opacity hover:opacity-80 shrink-0 mr-1">
            <div className="rounded-md border border-primary/30 bg-primary/10 p-1.5">
              <FramekitLogo />
            </div>
            <span className="hidden sm:block text-sm font-bold tracking-tight">Framekit</span>
          </Link>

          {/* Nav links — horizontally scrollable, hidden on small screens */}
          <nav className="hidden md:flex items-center gap-0.5 overflow-x-auto flex-1 scrollbar-none">
            {topNav.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "shrink-0 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors whitespace-nowrap",
                  "hover:bg-secondary hover:text-foreground",
                  pathname === item.to || (item.to === "/modules" && pathname === "/configuration")
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground",
                )}
              >
                {item.label}
              </Link>
            ))}

            {/* Modules dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger className={cn(
                "shrink-0 inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                "hover:bg-secondary hover:text-foreground",
                pathname.startsWith("/module/") ? "bg-secondary text-foreground" : "text-muted-foreground",
              )}>
                <Clapperboard className="h-3.5 w-3.5" />
                Modules
                <ChevronDown className="h-3 w-3" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48">
                <DropdownMenuLabel>All Modules</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {DEDICATED_MODULE_CONFIGS.map((item) => (
                  <DropdownMenuItem key={item.slug} asChild>
                    <Link to="/module/$moduleSlug" params={{ moduleSlug: item.slug }}>
                      {item.title}
                    </Link>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/studios">Browse all →</Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Link
              to="/settings-setup"
              className={cn(
                "shrink-0 inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                "hover:bg-secondary hover:text-foreground",
                pathname === "/settings-setup" ? "bg-secondary text-foreground" : "text-muted-foreground",
              )}
            >
              <Settings className="h-3.5 w-3.5" />
              Settings
            </Link>
          </nav>

          <div className="flex-1 md:hidden" />

          {/* Theme toggle */}
          <button
            type="button"
            aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
            onClick={() => setDark(!dark)}
            className="shrink-0 rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          {/* Auth controls */}
          {authUser && (
            <>
              {authUser.role === "admin" && (
                <>
                  <Link
                    to="/webhooks"
                    className="shrink-0 rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                    title="Webhooks"
                  >
                    <Webhook className="h-4 w-4" />
                  </Link>
                  <Link
                    to="/users"
                    className="shrink-0 rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                    title="Users"
                  >
                    <ShieldCheck className="h-4 w-4" />
                  </Link>
                </>
              )}
              <button
                type="button"
                onClick={logout}
                title={`Sign out (${authUser.username})`}
                className="shrink-0 rounded-md border border-border p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </>
          )}

          {/* Mobile hamburger */}
          <DropdownMenu>
            <DropdownMenuTrigger className="shrink-0 inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm md:hidden">
              Menu
              <ChevronDown className="h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel>Navigation</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {topNav.map((item) => (
                <DropdownMenuItem key={item.to} asChild>
                  <Link to={item.to}>{item.label}</Link>
                </DropdownMenuItem>
              ))}
              <DropdownMenuItem asChild>
                <Link to="/settings-setup">Settings</Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Modules</DropdownMenuLabel>
              {DEDICATED_MODULE_CONFIGS.map((item) => (
                <DropdownMenuItem key={item.slug} asChild>
                  <Link to="/module/$moduleSlug" params={{ moduleSlug: item.slug }}>{item.title}</Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <div className={cn("flex", hasContextualSidebar && "min-h-[calc(100vh-3.5rem)]")}>
        <ContextualSidebar pathname={pathname} />
        <main className={cn(
          "flex-1 min-w-0 py-8",
          hasContextualSidebar ? "px-6" : "px-4 mx-auto max-w-6xl w-full",
        )}>
          {children}
        </main>
      </div>
    </div>
  );
}
