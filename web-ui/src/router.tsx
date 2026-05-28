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

const configurationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/configuration",
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

const studiosRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/studios",
  component: lazyRouteComponent(() => import("@/routes/studios"), "StudiosPage"),
});

const dedicatedModuleRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/module/$moduleSlug",
  component: lazyRouteComponent(() => import("@/routes/dedicated-module"), "DedicatedModulePage"),
});

const logsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/logs",
  component: lazyRouteComponent(() => import("@/routes/logs"), "LogsPage"),
});

const cliRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cli",
  component: lazyRouteComponent(() => import("@/routes/cli"), "CliPage"),
});

const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/about",
  component: lazyRouteComponent(() => import("@/routes/about"), "AboutPage"),
});

const presetsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/presets",
  component: lazyRouteComponent(() => import("@/routes/presets"), "PresetsPage"),
});

const aliasesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/aliases",
  component: lazyRouteComponent(() => import("@/routes/aliases"), "AliasesPage"),
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: lazyRouteComponent(() => import("@/routes/login"), "LoginPage"),
});

const usersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/users",
  component: lazyRouteComponent(() => import("@/routes/users"), "UsersPage"),
});

const webhooksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/webhooks",
  component: lazyRouteComponent(() => import("@/routes/webhooks"), "WebhooksPage"),
});

const intakeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/intake",
  component: lazyRouteComponent(() => import("@/routes/intake"), "IntakePage"),
});

const rollbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/rollback",
  component: lazyRouteComponent(() => import("@/routes/rollback"), "RollbackPage"),
});

const routeTree = rootRoute.addChildren([
  homeRoute,
  doctorRoute,
  modulesRoute,
  configurationRoute,
  moduleJobDetailRoute,
  settingsSetupRoute,
  seedboxRoute,
  uploadRoute,
  pipelineRoute,
  batchRoute,
  moduleStudioRoute,
  studiosRoute,
  dedicatedModuleRoute,
  logsRoute,
  presetsRoute,
  aliasesRoute,
  cliRoute,
  aboutRoute,
  loginRoute,
  usersRoute,
  webhooksRoute,
  intakeRoute,
  rollbackRoute,
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
