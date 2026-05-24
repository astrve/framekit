import { fetchValidated } from "@/lib/api/client";
import {
  DoctorPayloadSchema,
  HealthSchema,
  ModulesCatalogSchema,
  ModuleJobSchema,
  ModuleJobsListSchema,
  ModulesPresetsSchema,
  RunModuleResultSchema,
  SeedboxListSchema,
  SeedboxHistorySchema,
  SettingsSummarySchema,
  SystemInfoSchema,
  UploadHistorySchema,
  UploadStateSchema,
  UploadTrackersSchema,
  type DoctorPayload,
  type HealthPayload,
  type ModuleJob,
  type ModulesCatalog,
  type ModulesPresets,
  type SeedboxList,
  type SeedboxHistory,
  type SettingsSummary,
  type UploadHistory,
  type UploadState,
  type RunModuleResult,
  type SystemInfoPayload,
  type UploadTrackers,
} from "@/lib/api/schemas";

export async function getHealth(): Promise<HealthPayload> {
  return fetchValidated("/healthz", HealthSchema);
}

export async function getSystemInfo(): Promise<SystemInfoPayload> {
  return fetchValidated("/api/v1/system/info", SystemInfoSchema);
}

export async function getDoctorPayload(): Promise<DoctorPayload> {
  return fetchValidated("/api/v1/doctor", DoctorPayloadSchema);
}

export async function getModulesCatalog(): Promise<ModulesCatalog> {
  return fetchValidated("/api/v1/modules/catalog", ModulesCatalogSchema);
}

export async function getModulesPresets(): Promise<ModulesPresets> {
  return fetchValidated("/api/v1/modules/presets", ModulesPresetsSchema);
}

export async function getSettingsSummary(): Promise<SettingsSummary> {
  return fetchValidated("/api/v1/settings/summary", SettingsSummarySchema);
}

export async function getSeedboxList(): Promise<SeedboxList> {
  return fetchValidated("/api/v1/seedbox/list", SeedboxListSchema);
}

export async function getUploadTrackers(): Promise<UploadTrackers> {
  return fetchValidated("/api/v1/upload/trackers", UploadTrackersSchema);
}

export async function getUploadState(): Promise<UploadState> {
  return fetchValidated("/api/v1/upload/state", UploadStateSchema);
}

export async function setUploadState(payload: {
  enabled: boolean;
  auto_upload?: boolean;
}): Promise<UploadState> {
  return fetchValidated("/api/v1/upload/state", UploadStateSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getUploadHistory(limit = 20): Promise<UploadHistory> {
  return fetchValidated(`/api/v1/upload/history?limit=${limit}`, UploadHistorySchema);
}

export async function getSeedboxHistory(limit = 50, seedboxName = ""): Promise<SeedboxHistory> {
  const seedboxQuery = seedboxName.trim() ? `&seedbox_name=${encodeURIComponent(seedboxName.trim())}` : "";
  return fetchValidated(`/api/v1/seedbox/history?limit=${limit}${seedboxQuery}`, SeedboxHistorySchema);
}

export async function runModule(payload: {
  module: string;
  args_text: string;
  dry_run: boolean;
  auto_yes: boolean;
  confirm_destructive: boolean;
}): Promise<RunModuleResult> {
  return fetchValidated(
    "/api/v1/modules/run",
    RunModuleResultSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
}

export async function createModuleJob(payload: {
  module: string;
  args_text: string;
  dry_run: boolean;
  auto_yes: boolean;
  confirm_destructive: boolean;
}): Promise<ModuleJob> {
  return fetchValidated(
    "/api/v1/modules/jobs",
    ModuleJobSchema,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
  );
}

export async function getModuleJob(jobId: string): Promise<ModuleJob> {
  return fetchValidated(`/api/v1/modules/jobs/${jobId}`, ModuleJobSchema);
}

export async function cancelModuleJob(jobId: string): Promise<ModuleJob> {
  return fetchValidated(
    `/api/v1/modules/jobs/${jobId}`,
    ModuleJobSchema,
    {
      method: "DELETE",
    },
  );
}

export async function rerunModuleJob(jobId: string): Promise<ModuleJob> {
  return fetchValidated(
    `/api/v1/modules/jobs/${jobId}/rerun`,
    ModuleJobSchema,
    {
      method: "POST",
    },
  );
}

export async function listModuleJobs(limit = 20): Promise<{ jobs: ModuleJob[] }> {
  return fetchValidated(`/api/v1/modules/jobs?limit=${limit}`, ModuleJobsListSchema);
}
