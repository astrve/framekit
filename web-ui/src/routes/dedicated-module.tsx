import { Link, useParams } from "@tanstack/react-router";

import { DedicatedModuleLauncher } from "@/components/modules/dedicated-module-launcher";
import { configBySlug } from "@/routes/dedicated-modules-config";

export function DedicatedModulePage() {
  const { moduleSlug } = useParams({ from: "/module/$moduleSlug" });
  const config = configBySlug(moduleSlug);

  if (!config) {
    return (
      <div className="space-y-4">
        <p>Unknown dedicated module: {moduleSlug}</p>
        <Link to="/jobs">Back to jobs</Link>
      </div>
    );
  }

  return (
    <DedicatedModuleLauncher
      moduleName={config.moduleName}
      title={config.title}
      description={config.description}
      presets={config.presets}
      {...(config.requiredFlags ? { requiredFlags: config.requiredFlags } : {})}
    />
  );
}
