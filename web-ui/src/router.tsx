import { createRoute, createRouter, lazyRouteComponent } from "@tanstack/react-router";
import { rootRoute } from "@/routes/root";

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: lazyRouteComponent(() => import("@/routes/home"), "HomePage"),
});

const doctorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/doctor",
  component: lazyRouteComponent(() => import("@/routes/doctor"), "DoctorPage"),
});

const modulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/modules",
  component: lazyRouteComponent(() => import("@/routes/modules"), "ModulesPage"),
});

const routeTree = rootRoute.addChildren([homeRoute, doctorRoute, modulesRoute]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
