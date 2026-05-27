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

export const CliParameterSpecSchema = z.object({
  kind: z.enum(["option", "argument"]),
  name: z.string(),
  label: z.string(),
  help: z.string().optional().default(""),
  required: z.boolean(),
  repeatable: z.boolean(),
  nargs: z.number(),
  type: z.enum(["bool", "int", "float", "choice", "multi-choice", "multi-value", "path", "string"]),
  choices: z.array(z.string()),
  default: z.unknown().nullable().optional(),
  aliases: z.array(z.string()),
  secondary_aliases: z.array(z.string()),
  flag_value: z.unknown().nullable().optional(),
  is_flag: z.boolean(),
  is_bool_flag: z.boolean(),
  metavar: z.string().optional().default(""),
});

export const CliCommandSpecSchema = z.object({
  name: z.string(),
  label: z.string(),
  help: z.string().optional().default(""),
  is_group: z.boolean(),
  destructive: z.boolean().optional(),
  supports_dry_run: z.boolean().optional(),
  group: z.string().optional(),
  parameters: z.array(CliParameterSpecSchema),
  subcommands: z.array(z.any()).optional(),
});

export const ModulesCliSpecSchema = z.object({
  modules: z.array(CliCommandSpecSchema),
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

export const PresetResourceSchema = z.object({
  name: z.string(),
  path: z.string(),
  source: z.string(),
});

export const AnnounceResourceSchema = z.object({
  value: z.string(),
  label: z.string().optional().default(""),
  is_selected: z.boolean(),
});

export const ModulesResourcesSchema = z.object({
  pipeline_presets: z.array(PresetResourceSchema),
  prez_presets: z.array(PresetResourceSchema),
  announces: z.array(AnnounceResourceSchema),
  selected_announce: z.string().nullable(),
  nfo_templates: z.array(z.string()),
  prez_templates: z.object({
    bbcode: z.array(z.string()),
    html: z.array(z.string()),
  }),
  banner_previews: z.array(
    z.object({
      name: z.string(),
      preview_url: z.string(),
    }),
  ),
  cleanmkv_presets: z.array(z.string()).optional().default([]),
  renamer_profiles: z.array(z.string()).optional().default([]),
  encoder_presets: z.array(z.string()).optional().default([]),
});

export const VaultStatusSchema = z.object({
  enabled: z.boolean().optional(),
  vault_exists: z.boolean().optional(),
  key_exists: z.boolean().optional(),
  entry_count: z.number().optional(),
  keys: z.array(z.string()).optional(),
  error: z.string().optional(),
}).catchall(z.unknown());

export const TmdbTokenSchema = z.object({
  token: z.string(),
  is_set: z.boolean(),
  error: z.string().optional(),
});

export const TorrentAnnouncesSchema = z.object({
  announces: z.array(AnnounceResourceSchema),
  selected_announce: z.string().nullable(),
});

export const SettingsSummarySchema = z.object({
  settings_path: z.string(),
  config_dir: z.string(),
  cache_dir: z.string(),
  settings: z.record(z.string(), z.unknown()),
});

export const SeedboxSummarySchema = z.object({
  name: z.string(),
  rclone_remote: z.string(),
  remote_base_path: z.string(),
  max_concurrent_uploads: z.number().nullable().optional(),
  bandwidth_limit: z.string(),
  is_default: z.boolean(),
});

export const SeedboxListSchema = z.object({
  seedboxes: z.array(SeedboxSummarySchema),
  default_by_profile: z.record(z.string()).optional(),
});

export const UploadTrackerSummarySchema = z.object({
  name: z.string(),
  type: z.string(),
  url: z.string(),
  enabled: z.boolean(),
});

export const UploadTrackersSchema = z.object({
  trackers: z.array(UploadTrackerSummarySchema),
});

export const UploadTrackerInfoSchema = z.object({
  tracker: z.record(z.string(), z.unknown()),
});

export const UploadStateSchema = z.object({
  enabled: z.boolean(),
  auto_upload: z.boolean(),
});

export const UploadHistorySchema = z.object({
  entries: z.array(z.record(z.string(), z.unknown())),
});

export const SeedboxHistorySchema = z.object({
  entries: z.array(z.record(z.string(), z.unknown())),
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
  live_stdout: z.string().optional(),
  live_stderr: z.string().optional(),
  result: RunModuleResultSchema.nullable().optional(),
  error: z.string().nullable().optional(),
});

export const ModuleJobsListSchema = z.object({
  jobs: z.array(ModuleJobSchema),
});

export const LogEntrySchema = z.object({
  time: z.string().optional().default(""),
  level: z.string().optional().default("INFO"),
  message: z.string().optional().default(""),
}).catchall(z.unknown());

export const LogsReadSchema = z.object({
  entries: z.array(LogEntrySchema),
});

export const ImageHostKeySchema = z.object({
  host: z.string(),
  key: z.string(),
  is_set: z.boolean(),
  encrypted: z.boolean(),
});

export const TorrentClientPasswordSchema = z.object({
  is_set: z.boolean(),
  encrypted: z.boolean(),
});

export const PresetResultSchema = z.object({
  name: z.string(),
  kind: z.string(),
  path: z.string().optional(),
  source: z.string().optional(),
  deleted: z.boolean().optional(),
});

export const PresetDeleteAllResultSchema = z.object({
  kind: z.string(),
  deleted: z.array(z.string()),
  count: z.number(),
});

export const ProviderTokenSchema = z.object({
  provider: z.string(),
  token: z.string(),
  is_set: z.boolean(),
  encrypted: z.boolean(),
  error: z.string().optional(),
});

export const SettingsProfileSchema = z.object({
  name: z.string(),
  description: z.string().default(""),
  active: z.boolean(),
  overrides: z.record(z.string(), z.unknown()).optional().default({}),
});

export const SettingsProfilesSchema = z.object({
  profiles: z.array(SettingsProfileSchema),
  active: z.string().nullable(),
});

export type SettingsProfile = z.infer<typeof SettingsProfileSchema>;
export type SettingsProfiles = z.infer<typeof SettingsProfilesSchema>;

export const WatchFolderSchema = z.object({
  path: z.string(),
  preset: z.string().default("default"),
  enabled: z.boolean().default(true),
});

export const WatchFoldersSchema = z.object({
  folders: z.array(WatchFolderSchema),
});

export type WatchFolder = z.infer<typeof WatchFolderSchema>;
export type WatchFolders = z.infer<typeof WatchFoldersSchema>;

export type VaultStatus = z.infer<typeof VaultStatusSchema>;
export type TmdbToken = z.infer<typeof TmdbTokenSchema>;
export type TorrentAnnounces = z.infer<typeof TorrentAnnouncesSchema>;
export type ImageHostKey = z.infer<typeof ImageHostKeySchema>;
export type TorrentClientPassword = z.infer<typeof TorrentClientPasswordSchema>;
export type PresetResult = z.infer<typeof PresetResultSchema>;
export type PresetDeleteAllResult = z.infer<typeof PresetDeleteAllResultSchema>;
export type ProviderToken = z.infer<typeof ProviderTokenSchema>;

export type HealthPayload = z.infer<typeof HealthSchema>;
export type SystemInfoPayload = z.infer<typeof SystemInfoSchema>;
export type DoctorCheck = z.infer<typeof DoctorCheckSchema>;
export type DoctorPayload = z.infer<typeof DoctorPayloadSchema>;
export type ModuleSpec = z.infer<typeof ModuleSpecSchema>;
export type CliParameterSpec = z.infer<typeof CliParameterSpecSchema>;
export type CliCommandSpec = z.infer<typeof CliCommandSpecSchema>;
export type ModulesCliSpec = z.infer<typeof ModulesCliSpecSchema>;
export type ModulesCatalog = z.infer<typeof ModulesCatalogSchema>;
export type ModulesPresets = z.infer<typeof ModulesPresetsSchema>;
export type ModulesResources = z.infer<typeof ModulesResourcesSchema>;
export type SettingsSummary = z.infer<typeof SettingsSummarySchema>;
export type SeedboxList = z.infer<typeof SeedboxListSchema>;
export type UploadTrackers = z.infer<typeof UploadTrackersSchema>;
export type UploadTrackerInfo = z.infer<typeof UploadTrackerInfoSchema>;
export type UploadState = z.infer<typeof UploadStateSchema>;
export type UploadHistory = z.infer<typeof UploadHistorySchema>;
export type SeedboxHistory = z.infer<typeof SeedboxHistorySchema>;
export type RunModuleResult = z.infer<typeof RunModuleResultSchema>;
export type ModuleJob = z.infer<typeof ModuleJobSchema>;
export type LogEntry = z.infer<typeof LogEntrySchema>;
export type LogsRead = z.infer<typeof LogsReadSchema>;

export const ToolCheckItemSchema = z.object({
  name: z.string(),
  binary: z.string(),
  ok: z.boolean(),
  path: z.string(),
});

export const ToolsCheckSchema = z.object({
  tools: z.array(ToolCheckItemSchema),
});

export type ToolCheckItem = z.infer<typeof ToolCheckItemSchema>;
export type ToolsCheck = z.infer<typeof ToolsCheckSchema>;

export const WebhookConfigSchema = z.object({
  id: z.string(),
  name: z.string(),
  url: z.string(),
  enabled: z.boolean(),
  discord: z.boolean(),
  events: z.array(z.string()),
  title_template: z.string().nullable(),
  body_template: z.string().nullable(),
});

export const WebhookListSchema = z.object({
  webhooks: z.array(WebhookConfigSchema),
});

export type WebhookConfig = z.infer<typeof WebhookConfigSchema>;
export type WebhookList = z.infer<typeof WebhookListSchema>;

export const AuthUserSchema = z.object({
  id: z.string(),
  username: z.string(),
  role: z.enum(["admin", "viewer"]),
  created_at: z.string(),
  enabled: z.boolean(),
});

export const AuthLoginResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  user: AuthUserSchema,
});

export const AuthStatusSchema = z.object({
  enabled: z.boolean(),
  has_users: z.boolean(),
  user_count: z.number(),
});

export const AuthUsersListSchema = z.object({
  users: z.array(AuthUserSchema),
});

export type AuthUser = z.infer<typeof AuthUserSchema>;
export type AuthLoginResponse = z.infer<typeof AuthLoginResponseSchema>;
export type AuthStatus = z.infer<typeof AuthStatusSchema>;
export type AuthUsersList = z.infer<typeof AuthUsersListSchema>;

export const AliasItemSchema = z.object({
  name: z.string(),
  command: z.string(),
  description: z.string(),
  enabled: z.boolean(),
  kind: z.enum(["user", "builtin"]),
});

export const AliasListSchema = z.object({
  aliases: z.array(AliasItemSchema),
});

export type AliasItem = z.infer<typeof AliasItemSchema>;
export type AliasList = z.infer<typeof AliasListSchema>;
