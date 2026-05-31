import { useQuery } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  ActivitySquare,
  BookMarked,
  Clapperboard,
  Film,
  FileCog,
  Info,
  KeyRound,
  Layers,
  LogOut,
  Moon,
  RotateCcw,
  ScrollText,
  Server,
  Settings,
  ShieldCheck,
  Signal,
  Stethoscope,
  Sun,
  Terminal,
  Upload,
  Webhook,
  Workflow,
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useState } from "react";

import { getSettingsProfiles, listModuleJobs } from "@/lib/api/endpoints";
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

type NavItem = {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
};

type TopSection = {
  id: string;
  label: string;
  href: string;
  prefixes: string[];
  sidebarItems: NavItem[];
};

const TOP_SECTIONS: TopSection[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    href: "/",
    prefixes: ["/"],
    sidebarItems: [],
  },
  {
    id: "modules",
    label: "Modules",
    href: "/pipeline",
    prefixes: ["/pipeline", "/batch", "/jobs", "/studios", "/rollback", "/releases", "/module/"],
    sidebarItems: [
      { to: "/pipeline", label: "Pipeline", icon: Workflow },
      { to: "/batch", label: "Batch", icon: Layers },
      { to: "/jobs", label: "Jobs", icon: ActivitySquare },
      { to: "/releases", label: "Releases", icon: Film },
      { to: "/studios", label: "All Modules", icon: Clapperboard },
      { to: "/rollback", label: "Rollback", icon: RotateCcw },
    ],
  },
  {
    id: "transfer",
    label: "Transfer",
    href: "/upload",
    prefixes: ["/upload", "/seedbox", "/intake"],
    sidebarItems: [
      { to: "/upload", label: "Upload", icon: Upload },
      { to: "/seedbox", label: "Seedbox", icon: Server },
      { to: "/intake", label: "Intake", icon: KeyRound, adminOnly: true },
    ],
  },
  {
    id: "observe",
    label: "Observe",
    href: "/events",
    prefixes: ["/events", "/logs", "/doctor", "/cli"],
    sidebarItems: [
      { to: "/events", label: "Events", icon: Signal },
      { to: "/logs", label: "Logs", icon: ScrollText },
      { to: "/doctor", label: "Diagnostics", icon: Stethoscope },
      { to: "/cli", label: "Terminal", icon: Terminal },
    ],
  },
  {
    id: "settings",
    label: "Settings",
    href: "/settings-setup",
    prefixes: ["/settings-setup", "/presets", "/aliases", "/webhooks", "/users"],
    sidebarItems: [
      { to: "/settings-setup", label: "Settings", icon: Settings },
      { to: "/presets", label: "Presets", icon: FileCog },
      { to: "/aliases", label: "Aliases", icon: BookMarked },
      { to: "/webhooks", label: "Webhooks", icon: Webhook, adminOnly: true },
      { to: "/users", label: "Users", icon: ShieldCheck, adminOnly: true },
    ],
  },
  {
    id: "about",
    label: "About",
    href: "/about",
    prefixes: ["/about"],
    sidebarItems: [
      { to: "/about", label: "About", icon: Info },
    ],
  },
];

const SETTINGS_SECTIONS = [
  { id: "s-profiles", label: "Profiles" },
  { id: "s-general", label: "General" },
  { id: "s-file-locations", label: "Locations" },
  { id: "s-logging", label: "Logging" },
  { id: "s-tools", label: "Tools" },
  { id: "s-metadata", label: "Metadata" },
  { id: "s-upload", label: "Upload" },
  { id: "s-seedbox", label: "Seedbox" },
  { id: "s-watch", label: "Watch" },
  { id: "s-service", label: "Service" },
  { id: "s-pipeline", label: "Pipeline" },
  { id: "s-security", label: "Security" },
];

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function getActiveSection(pathname: string): TopSection | undefined {
  if (pathname === "/") return TOP_SECTIONS.find((s) => s.id === "dashboard");
  return TOP_SECTIONS.find(
    (s) =>
      s.id !== "dashboard" &&
      s.prefixes.some(
        (p) => pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p),
      ),
  );
}

function isItemActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(`${to}/`);
}

function SidebarNav({
  pathname,
  isAdmin,
  activeJobCount,
}: {
  pathname: string;
  isAdmin: boolean;
  activeJobCount: number;
}) {
  const activeSection = getActiveSection(pathname);
  const sidebarItems = useMemo(
    () => (activeSection?.sidebarItems ?? []).filter((item) => !item.adminOnly || isAdmin),
    [activeSection, isAdmin],
  );

  if (!activeSection || sidebarItems.length === 0) return null;

  return (
    <aside className="hidden lg:flex w-56 shrink-0 flex-col border-r border-border bg-card/60">
      <nav className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto px-3 py-4">
        <div className="space-y-0.5">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground/50">
            {activeSection.label}
          </p>
          {sidebarItems.map((item) => {
            const Icon = item.icon;
            const active = isItemActive(pathname, item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150",
                  active
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
                {item.to === "/jobs" && activeJobCount > 0 && (
                  <span
                    className={cn(
                      "ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums",
                      active ? "bg-white/20 text-white" : "bg-primary/20 text-primary",
                    )}
                  >
                    {activeJobCount}
                  </span>
                )}
              </Link>
            );
          })}

          {pathname === "/settings-setup" && (
            <div className="mt-5 space-y-1 border-t border-border/50 pt-4">
              <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/60">
                Sections
              </p>
              {SETTINGS_SECTIONS.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => scrollToSection(section.id)}
                  className="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-muted-foreground transition-colors duration-150 hover:bg-secondary hover:text-foreground"
                >
                  {section.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </nav>
    </aside>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user: authUser, logout } = useAuth();
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") return true;
    if (saved === "light") return false;
    return true;
  });

  const profilesQuery = useQuery({
    queryKey: ["settings-profiles-nav"],
    queryFn: getSettingsProfiles,
    staleTime: 30_000,
    enabled: pathname !== "/login",
    retry: false,
  });

  const jobsNavQuery = useQuery({
    queryKey: ["nav-jobs-count"],
    queryFn: () => listModuleJobs(50),
    refetchInterval: 5_000,
    staleTime: 0,
    enabled: pathname !== "/login",
    retry: false,
  });

  const activeProfile = profilesQuery.data?.active ?? null;
  const isAdmin = authUser?.role === "admin";
  const isLoginPage = pathname === "/login";
  const activeJobCount = (jobsNavQuery.data?.jobs ?? []).filter(
    (j) => j.status === "pending" || j.status === "running",
  ).length;

  const activeSection = getActiveSection(pathname);

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

  if (isLoginPage) {
    return (
      <div className="swirrl-shell min-h-screen bg-background text-foreground">
        {children}
      </div>
    );
  }

  return (
    <div className="swirrl-shell min-h-screen text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-background/96 backdrop-blur-md">
        <div className="flex h-14 items-center px-3 lg:px-5 gap-1">
          {/* Logo */}
          <Link
            to="/"
            className="interactive-lift mr-3 shrink-0 rounded-lg px-1 py-1 transition-opacity hover:opacity-80"
          >
            <img src="/logo-wordmark.svg" alt="Swirrl" className="h-8 w-auto" />
          </Link>

          {/* Top nav — desktop */}
          <nav className="hidden lg:flex items-center gap-0.5 flex-1">
            {TOP_SECTIONS.map((section) => {
              const isActive =
                section.id === "dashboard"
                  ? pathname === "/"
                  : activeSection?.id === section.id;
              return (
                <Link
                  key={section.id}
                  to={section.href}
                  className={cn(
                    "relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                    isActive
                      ? "text-foreground after:absolute after:inset-x-1 after:-bottom-[9px] after:h-[2px] after:rounded-full after:bg-primary"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {section.label}
                  {section.id === "modules" && activeJobCount > 0 && (
                    <span className="ml-1.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-primary/20 px-1 text-[10px] font-bold text-primary tabular-nums">
                      {activeJobCount}
                    </span>
                  )}
                </Link>
              );
            })}
            <span className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground/35 cursor-default select-none">
              Docs
            </span>
          </nav>

          {/* Right controls */}
          <div className="ml-auto flex items-center gap-2">
            {activeProfile ? (
              <Link
                to="/settings-setup"
                title="Active settings profile"
                className="hidden md:inline-flex rounded-full border border-border bg-secondary/60 px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                {activeProfile}
              </Link>
            ) : null}

            <button
              type="button"
              aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
              onClick={() => setDark(!dark)}
              className="interactive-lift rounded-md border border-border p-2 text-muted-foreground hover:bg-secondary hover:text-foreground"
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>

            {authUser ? (
              <button
                type="button"
                onClick={logout}
                title={`Sign out (${authUser.username})`}
                className="interactive-lift rounded-md border border-border p-2 text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
              </button>
            ) : null}

            {/* Mobile dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger className="interactive-lift inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm lg:hidden">
                Menu
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                {TOP_SECTIONS.map((section, index) => {
                  const items = section.sidebarItems.filter(
                    (item) => !item.adminOnly || isAdmin,
                  );
                  return (
                    <div key={section.id}>
                      {index > 0 ? <DropdownMenuSeparator /> : null}
                      <DropdownMenuLabel>{section.label}</DropdownMenuLabel>
                      {items.length > 0 ? (
                        items.map((item) => (
                          <DropdownMenuItem key={item.to} asChild>
                            <Link to={item.to}>{item.label}</Link>
                          </DropdownMenuItem>
                        ))
                      ) : (
                        <DropdownMenuItem asChild>
                          <Link to={section.href}>{section.label}</Link>
                        </DropdownMenuItem>
                      )}
                    </div>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1640px]">
        <SidebarNav pathname={pathname} isAdmin={isAdmin} activeJobCount={activeJobCount} />
        <main className="w-full min-w-0 px-4 py-6 md:px-6 lg:px-8 ops-reveal">
          {children}
        </main>
      </div>
    </div>
  );
}
