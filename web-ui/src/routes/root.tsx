import { createRootRoute, Outlet } from "@tanstack/react-router";
import { lazy, Suspense } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { AppToaster } from "@/components/ui/toaster";

const RouterDevtools =
  import.meta.env.DEV
    ? lazy(async () => {
        const mod = await import("@tanstack/react-router-devtools");
        return { default: mod.TanStackRouterDevtools };
      })
    : null;

function RootLayout() {
  return (
    <>
      <AppShell>
        <Outlet />
      </AppShell>
      <AppToaster />
      {RouterDevtools ? (
        <Suspense fallback={null}>
          <RouterDevtools />
        </Suspense>
      ) : null}
    </>
  );
}

export const rootRoute = createRootRoute({
  component: RootLayout,
});
