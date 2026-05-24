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

const moduleJobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/modules/$jobId",
  component: lazyRouteComponent(() => import("@/routes/module-job-detail"), "ModuleJobDetailPage"),
});

const settingsSetupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings-setup",
  component: lazyRouteComponent(() => import("@/routes/settings-setup"), "SettingsSetupPage"),
});

const seedboxRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/seedbox",
  component: lazyRouteComponent(() => import("@/routes/seedbox"), "SeedboxPage"),
});

const uploadRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/upload",
  component: lazyRouteComponent(() => import("@/routes/upload"), "UploadPage"),
});

const pipelineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/pipeline",
  component: lazyRouteComponent(() => import("@/routes/pipeline"), "PipelinePage"),
});

const batchRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/batch",
  component: lazyRouteComponent(() => import("@/routes/batch"), "BatchPage"),
});

const moduleStudioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/studio/$module",
  component: lazyRouteComponent(() => import("@/routes/module-studio"), "ModuleStudioPage"),
});

const routeTree = rootRoute.addChildren([
  homeRoute,
  doctorRoute,
  modulesRoute,
  moduleJobDetailRoute,
  settingsSetupRoute,
  seedboxRoute,
  uploadRoute,
  pipelineRoute,
  batchRoute,
  moduleStudioRoute,
]);

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
