import { z } from "zod";

export const HealthSchema = z.object({
  status: z.literal("ok"),
});

export const SystemInfoSchema = z.object({
  name: z.string(),
  version: z.string(),
  python_version: z.string(),
});

export const DoctorCheckSchema = z.object({
  section: z.string(),
  name: z.string(),
  status: z.enum(["ok", "warn", "err"]),
  detail: z.string(),
});

export const DoctorToolSchema = z.record(z.string(), z.unknown());

export const DoctorPayloadSchema = z.object({
  tools: z.array(DoctorToolSchema),
  checks: z.array(DoctorCheckSchema),
});

export const ModuleSpecSchema = z.object({
  name: z.string(),
  description: z.string(),
  destructive: z.boolean(),
  supports_dry_run: z.boolean(),
});

export const ModulesCatalogSchema = z.object({
  modules: z.array(ModuleSpecSchema),
});

export const ModulePresetSchema = z.object({
  id: z.string(),
  label: z.string(),
  module: z.string(),
  args_text: z.string(),
  dry_run: z.boolean(),
  auto_yes: z.boolean(),
  confirm_destructive: z.boolean(),
});

export const ModulesPresetsSchema = z.object({
  presets: z.array(ModulePresetSchema),
});

export const RunModuleResultSchema = z.object({
  ok: z.boolean(),
  argv: z.array(z.string()),
  returncode: z.number(),
  stdout: z.string(),
  stderr: z.string(),
  parsed_kind: z.string().nullable().optional(),
  parsed_payload: z.union([z.record(z.string(), z.unknown()), z.array(z.unknown())]).nullable().optional(),
});

export const ModuleJobSchema = z.object({
  id: z.string(),
  status: z.enum(["pending", "running", "completed", "failed", "cancelled"]),
  created_at: z.string(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  request: z.record(z.string(), z.unknown()),
  result: RunModuleResultSchema.nullable().optional(),
  error: z.string().nullable().optional(),
});

export const ModuleJobsListSchema = z.object({
  jobs: z.array(ModuleJobSchema),
});

export type HealthPayload = z.infer<typeof HealthSchema>;
export type SystemInfoPayload = z.infer<typeof SystemInfoSchema>;
export type DoctorCheck = z.infer<typeof DoctorCheckSchema>;
export type DoctorPayload = z.infer<typeof DoctorPayloadSchema>;
export type ModuleSpec = z.infer<typeof ModuleSpecSchema>;
export type ModulesCatalog = z.infer<typeof ModulesCatalogSchema>;
export type ModulesPresets = z.infer<typeof ModulesPresetsSchema>;
export type RunModuleResult = z.infer<typeof RunModuleResultSchema>;
export type ModuleJob = z.infer<typeof ModuleJobSchema>;
