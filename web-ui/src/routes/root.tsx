import { createRootRoute, Outlet, useNavigate, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { AppToaster } from "@/components/ui/toaster";
import { useAuth } from "@/lib/auth";
import { getAuthStatus } from "@/lib/api/endpoints";

const RouterDevtools =
  import.meta.env.DEV
    ? lazy(async () => {
        const mod = await import("@tanstack/react-router-devtools");
        return { default: mod.TanStackRouterDevtools };
      })
    : null;

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading: tokenLoading } = useAuth();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();

  const statusQuery = useQuery({
    queryKey: ["auth-status"],
    queryFn: getAuthStatus,
    staleTime: 60_000,
  });

  const isLoginPage = pathname === "/login";
  const settled = !tokenLoading && !statusQuery.isPending;
  const hasUsers = statusQuery.data?.has_users ?? false;
  const needsLogin = settled && hasUsers && !user && !isLoginPage;

  useEffect(() => {
    if (needsLogin) {
      navigate({ to: "/login" });
    }
  }, [needsLogin, navigate]);

  if (!settled || needsLogin) {
    return null;
  }

  return <>{children}</>;
}

function RootLayout() {
  return (
    <AuthGuard>
      <AppShell>
        <Outlet />
      </AppShell>
      <AppToaster />
      {RouterDevtools ? (
        <Suspense fallback={null}>
          <RouterDevtools />
        </Suspense>
      ) : null}
    </AuthGuard>
  );
}

export const rootRoute = createRootRoute({
  component: RootLayout,
});
