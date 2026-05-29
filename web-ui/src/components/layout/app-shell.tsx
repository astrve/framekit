import { useQuery } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  ActivitySquare,
  BookMarked,
  ChevronDown,
  Clapperboard,
  FileCog,
  Info,
  KeyRound,
  LayoutDashboard,
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

import { getSettingsProfiles } from "@/lib/api/endpoints";
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

type NavGroup = {
  title: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Run",
    items: [
      { to: "/", label: "Home", icon: LayoutDashboard },
      { to: "/pipeline", label: "Pipeline", icon: Workflow },
      { to: "/batch", label: "Batch", icon: Layers },
      { to: "/jobs", label: "Jobs", icon: ActivitySquare },
      { to: "/studios", label: "Modules", icon: Clapperboard },
      { to: "/rollback", label: "Rollback", icon: RotateCcw },
    ],
  },
  {
    title: "Transfer",
    items: [
      { to: "/upload", label: "Upload", icon: Upload },
      { to: "/seedbox", label: "Seedbox", icon: Server },
      { to: "/intake", label: "Intake", icon: KeyRound, adminOnly: true },
    ],
  },
  {
    title: "Observe",
    items: [
      { to: "/events", label: "Events", icon: Signal },
      { to: "/logs", label: "Logs", icon: ScrollText },
      { to: "/doctor", label: "Diagnostics", icon: Stethoscope },
      { to: "/cli", label: "Terminal", icon: Terminal },
    ],
  },
  {
    title: "Configure",
    items: [
      { to: "/settings-setup", label: "Settings", icon: Settings },
      { to: "/presets", label: "Presets", icon: FileCog },
      { to: "/aliases", label: "Aliases", icon: BookMarked },
    ],
  },
  {
    title: "System",
    items: [
      { to: "/webhooks", label: "Webhooks", icon: Webhook, adminOnly: true },
      { to: "/users", label: "Users", icon: ShieldCheck, adminOnly: true },
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

function isActive(pathname: string, target: string): boolean {
  if (target === "/") {
    return pathname === "/";
  }
  return pathname === target || pathname.startsWith(`${target}/`);
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function OuroLogo() {
  return <img src="/logo.svg" alt="Ouro" className="h-5 w-5" />;
}

function SidebarNav({
  pathname,
  isAdmin,
}: {
  pathname: string;
  isAdmin: boolean;
}) {
  const groups = useMemo(
    () =>
      NAV_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => !item.adminOnly || isAdmin),
      })).filter((group) => group.items.length > 0),
    [isAdmin],
  );

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border/80 bg-card/65 backdrop-blur-sm">
      <nav className="sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto px-3 py-5">
        <div className="space-y-6">
          {groups.map((group) => (
            <div key={group.title} className="space-y-2">
              <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                {group.title}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(pathname, item.to);
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={cn(
                        "interactive-lift nav-item flex items-center gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors",
                        active
                          ? "border-primary/30 bg-primary/10 text-foreground"
                          : "border-transparent text-muted-foreground hover:border-border/70 hover:bg-secondary/45 hover:text-foreground",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          {pathname === "/settings-setup" ? (
            <div className="space-y-2 border-t border-border/70 pt-4">
              <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Settings Sections
              </p>
              <div className="space-y-1">
                {SETTINGS_SECTIONS.map((section) => (
                  <button
                    key={section.id}
                    type="button"
                    onClick={() => scrollToSection(section.id)}
                    className="interactive-lift flex w-full items-center justify-between rounded-lg border border-transparent px-2.5 py-1.5 text-left text-sm text-muted-foreground hover:border-border/70 hover:bg-secondary/45 hover:text-foreground"
                  >
                    {section.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </nav>
    </aside>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user: authUser, logout } = useAuth();
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  const profilesQuery = useQuery({
    queryKey: ["settings-profiles-nav"],
    queryFn: getSettingsProfiles,
    staleTime: 30_000,
    enabled: pathname !== "/login",
    retry: false,
  });

  const activeProfile = profilesQuery.data?.active ?? null;
  const isAdmin = authUser?.role === "admin";
  const isLoginPage = pathname === "/login";

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
      <div className="min-h-screen bg-background text-foreground">
        {children}
      </div>
    );
  }

  return (
    <div className="min-h-screen text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/80 bg-background/85 backdrop-blur-lg">
        <div className="flex h-14 items-center gap-2 px-3 lg:px-5">
          <Link to="/" className="interactive-lift flex items-center gap-2 rounded-lg px-1 py-1 transition-opacity hover:opacity-85">
            <div className="rounded-md border border-primary/35 bg-card p-1.5 shadow-sm">
              <OuroLogo />
            </div>
            <img src="/logo-wordmark.svg" alt="Ouro" className="hidden sm:block h-4 w-auto" />
          </Link>

          <div className="hidden md:flex items-center gap-1.5">
            <Link to="/pipeline" className="interactive-lift rounded-md border border-border/70 bg-secondary/50 px-2.5 py-1 text-xs font-medium text-foreground hover:border-primary/30 hover:bg-secondary">
              Run Pipeline
            </Link>
            <Link to="/jobs" className="interactive-lift rounded-md border border-border/70 bg-secondary/50 px-2.5 py-1 text-xs font-medium text-foreground hover:border-primary/30 hover:bg-secondary">
              Open Jobs
            </Link>
            <Link to="/events" className="interactive-lift rounded-md border border-border/70 bg-secondary/50 px-2.5 py-1 text-xs font-medium text-foreground hover:border-primary/30 hover:bg-secondary">
              Service Events
            </Link>
          </div>

          <div className="ml-auto flex items-center gap-2">
            {activeProfile ? (
              <Link
                to="/settings-setup"
                title="Active settings profile"
                className="hidden md:inline-flex rounded-full border border-border bg-secondary/70 px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:text-foreground"
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

            <DropdownMenu>
              <DropdownMenuTrigger className="interactive-lift inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm lg:hidden">
                Menu
                <ChevronDown className="h-4 w-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                {NAV_GROUPS.map((group, index) => {
                  const items = group.items.filter((item) => !item.adminOnly || isAdmin);
                  if (items.length === 0) return null;
                  return (
                    <div key={group.title}>
                      {index > 0 ? <DropdownMenuSeparator /> : null}
                      <DropdownMenuLabel>{group.title}</DropdownMenuLabel>
                      {items.map((item) => (
                        <DropdownMenuItem key={item.to} asChild>
                          <Link to={item.to}>{item.label}</Link>
                        </DropdownMenuItem>
                      ))}
                    </div>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1640px]">
        <SidebarNav pathname={pathname} isAdmin={isAdmin} />
        <main className="w-full min-w-0 px-4 py-6 md:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
