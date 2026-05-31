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

export const JobCheckpointOptionSchema = z.object({
  index: z.number(),
  label: z.string(),
  hint: z.string().optional().default(""),
});

export const JobCheckpointSchema = z.object({
  pending: z.boolean(),
  type: z.enum(["select_one", "step_confirm"]).optional(),
  title: z.string().optional(),
  options: z.array(JobCheckpointOptionSchema).optional().default([]),
  default_index: z.number().optional().default(0),
  // step_confirm fields
  step: z.string().optional(),
  step_index: z.number().optional(),
  step_total: z.number().optional(),
  summary: z.string().optional(),
});

export type JobCheckpoint = z.infer<typeof JobCheckpointSchema>;

export const InspectTrackSchema = z.object({
  track_id: z.number(),
  codec: z.string(),
  language: z.string().nullable().optional(),
  language_variant: z.string().nullable().optional(),
  subtitle_variant: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  channels: z.string().nullable().optional(),
  bitrate: z.number().nullable().optional(),
  is_default: z.boolean(),
  is_forced: z.boolean(),
  format_name: z.string().nullable().optional(),
});

export const InspectFileScanSchema = z.object({
  filename: z.string(),
  audio: z.array(InspectTrackSchema).default([]),
  subtitles: z.array(InspectTrackSchema).default([]),
});

export const InspectRenamerFileSchema = z.object({
  original: z.string(),
  renamed: z.string(),
  changed: z.boolean(),
  collision: z.boolean(),
  inferred_video_tag: z.string().nullable().optional(),
  inferred_audio_tag: z.string().nullable().optional(),
  inferred_source: z.string().nullable().optional(),
  inferred_resolution: z.string().nullable().optional(),
  hdr_display_label: z.string().nullable().optional(),
  existing_language_tag: z.string().nullable().optional(),
  resulting_language_tag: z.string().nullable().optional(),
  parsed_episode_code: z.string().nullable().optional(),
});

export const PipelineInspectSchema = z.object({
  path: z.string(),
  folder_name: z.string(),
  effective_locale: z.string(),
  renamer: z.object({
    files: z.array(InspectRenamerFileSchema).default([]),
    total: z.number(),
    changed: z.number(),
    collisions: z.number(),
    error: z.string().optional(),
  }),
  tracks: z.array(InspectFileScanSchema).default([]),
  nfo: z.object({
    template: z.string().optional(),
    locale: z.string().optional(),
  }),
  prez: z.object({
    preset: z.string().optional(),
    html_template: z.string().optional(),
    bbcode_template: z.string().optional(),
  }),
});

export type PipelineInspect = z.infer<typeof PipelineInspectSchema>;
export type InspectFileScan = z.infer<typeof InspectFileScanSchema>;
export type InspectTrack = z.infer<typeof InspectTrackSchema>;
export type InspectRenamerFile = z.infer<typeof InspectRenamerFileSchema>;

export const CleanmkvSelectionPresetSchema = z.object({
  preset_file: z.string(),
});
export type CleanmkvSelectionPreset = z.infer<typeof CleanmkvSelectionPresetSchema>;

export const PipelineRenamerFileSchema = z.object({
  original: z.string(),
  renamed: z.string(),
  changed: z.boolean(),
  collision: z.boolean(),
  language_tag_conflict: z.boolean().optional(),
});

export const PipelinePlanSchema = z.object({
  enabled_modules: z.array(z.string()),
  effective_locale: z.string(),
  renamer: z.object({
    files: z.array(PipelineRenamerFileSchema).default([]),
    total: z.number(),
    changed: z.number(),
    collisions: z.number(),
  }),
  cleanmkv: z.object({
    preset: z.string().optional(),
    files: z.array(z.object({ filename: z.string() })).default([]),
    total: z.number(),
  }),
  nfo: z.object({
    template: z.string().optional(),
    locale: z.string().optional(),
  }),
  prez: z.object({
    preset: z.string().optional(),
    html_template: z.string().optional(),
    bbcode_template: z.string().optional(),
  }),
});

export type PipelinePlan = z.infer<typeof PipelinePlanSchema>;

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
  encrypted: z.boolean().optional(),
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
  default_by_profile: z.record(z.string(), z.string()).optional(),
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

export const UploadHistoryEntrySchema = z.object({
  success: z.boolean(),
  tracker: z.string(),
  torrent_id: z.number().nullable().optional(),
  url: z.string().nullable().optional(),
  message: z.string().default(""),
  errors: z.array(z.string()).default([]),
  upload_time: z.number().default(0),
  timestamp: z.string(),
  torrent: z.string().optional(),
});

export const UploadHistorySchema = z.object({
  entries: z.array(UploadHistoryEntrySchema),
});

export const SeedboxHistoryEntrySchema = z
  .object({
    timestamp: z.string().optional(),
    action: z.string().optional(),
    seedbox: z.string().optional(),
    local_path: z.string().optional(),
    remote_path: z.string().optional(),
    success: z.boolean().optional(),
  })
  .passthrough();

export const SeedboxHistorySchema = z.object({
  entries: z.array(SeedboxHistoryEntrySchema),
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
  origin: z.string().nullable().optional(),
  category: z.string().nullable().optional(),
  priority: z.number().optional().default(0),
  attempts: z.number().optional().default(0),
  max_attempts: z.number().optional().default(1),
  next_retry_at: z.string().nullable().optional(),
  last_failure_kind: z.string().nullable().optional(),
  retryable: z.boolean().optional().default(false),
  paused: z.boolean().optional(),
});

export const QueueCategorySnapshotSchema = z.object({
  pending: z.number(),
  paused: z.number(),
  running: z.number(),
});

export const QueueSnapshotSchema = z.object({
  draining: z.boolean(),
  pending: z.number(),
  paused: z.number(),
  running: z.number(),
  by_category: z.record(z.string(), QueueCategorySnapshotSchema),
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

export const WatchRulePostActionsSchema = z.object({
  seedbox_push: z.boolean().default(false),
  seedbox_profile: z.string().nullable().default(null),
  tracker_upload: z.boolean().default(false),
  tracker: z.string().nullable().default(null),
});

export const WatchRulePresetsByKindSchema = z.object({
  movie: z.string().nullable().default(null),
  series: z.string().nullable().default(null),
  single_episode: z.string().nullable().default(null),
});

export const WatchRuleSchema = z.object({
  id: z.string(),
  path: z.string(),
  preset: z.string().default("default"),
  enabled: z.boolean().default(true),
  pattern: z.string().default(""),
  kind_routing: z.enum(["fixed", "auto"]).default("fixed"),
  presets_by_kind: WatchRulePresetsByKindSchema.default(() => ({ movie: null, series: null, single_episode: null })),
  post_actions: WatchRulePostActionsSchema.default(() => ({ seedbox_push: false, seedbox_profile: null, tracker_upload: false, tracker: null })),
});

export const WatchRulesListSchema = z.object({
  rules: z.array(WatchRuleSchema),
});

export type WatchRule = z.infer<typeof WatchRuleSchema>;
export type WatchRulePostActions = z.infer<typeof WatchRulePostActionsSchema>;
export type WatchRulePresetsByKind = z.infer<typeof WatchRulePresetsByKindSchema>;
export type WatchRulesList = z.infer<typeof WatchRulesListSchema>;

export const WatchServiceStatusSchema = z.object({
  status: z.enum(["running", "stopped"]),
  pid: z.number().nullable(),
});

export const WatchServiceStopSchema = z.object({
  stopped: z.boolean(),
});

export type WatchServiceStatus = z.infer<typeof WatchServiceStatusSchema>;
export type WatchServiceStop = z.infer<typeof WatchServiceStopSchema>;

// ── Service status (swirrl serve) ──────────────────────────────────────────

export const ServiceWatcherStateSchema = z.object({
  status: z.enum(["running", "stopped", "error"]),
  folders_active: z.number(),
  last_error: z.string().nullable(),
});

export const ServiceStatusSchema = z.object({
  status: z.enum(["running", "stopped", "starting"]),
  pid: z.number().nullable(),
  started_at: z.number().nullable(),
  heartbeat_at: z.number().nullable(),
  uptime_seconds: z.number().nullable(),
  watcher: ServiceWatcherStateSchema.optional(),
  draining: z.boolean().optional(),
  queue: QueueSnapshotSchema.optional(),
  metrics: z.object({
    queued: z.number(),
    running: z.number(),
    completed: z.number(),
    failed: z.number(),
    retried: z.number(),
  }).optional(),
});

export type ServiceWatcherState = z.infer<typeof ServiceWatcherStateSchema>;
export type ServiceStatus = z.infer<typeof ServiceStatusSchema>;

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
export type UploadHistoryEntry = z.infer<typeof UploadHistoryEntrySchema>;
export type UploadHistory = z.infer<typeof UploadHistorySchema>;
export type SeedboxHistory = z.infer<typeof SeedboxHistorySchema>;
export type RunModuleResult = z.infer<typeof RunModuleResultSchema>;
export type ModuleJob = z.infer<typeof ModuleJobSchema>;
export type QueueSnapshot = z.infer<typeof QueueSnapshotSchema>;
export type LogEntry = z.infer<typeof LogEntrySchema>;

export const LedgerEntrySchema = z.object({
  run_id: z.string(),
  action: z.string(),
  src: z.string(),
  dst: z.string(),
  module: z.string(),
  timestamp: z.string(),
});

export const RunSummarySchema = z.object({
  run_id: z.string(),
  module: z.string(),
  file_count: z.number(),
  timestamp: z.string(),
  actions: z.array(LedgerEntrySchema),
});

export const RunsListSchema = z.object({
  runs: z.array(RunSummarySchema),
});

export type LedgerEntry = z.infer<typeof LedgerEntrySchema>;
export type RunSummary = z.infer<typeof RunSummarySchema>;
export type RunsList = z.infer<typeof RunsListSchema>;
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

export const IntakeSourceSchema = z.object({
  id: z.string(),
  name: z.string(),
  source_id: z.string(),
  enabled: z.boolean(),
  default_preset: z.string().nullable().optional(),
  created_at: z.string(),
  // token only present in create response (shown once)
  token: z.string().optional(),
});

export const IntakeSourceListSchema = z.object({
  sources: z.array(IntakeSourceSchema),
});

export const IntakeReleaseResponseSchema = z.object({
  job_id: z.string(),
  accepted: z.boolean(),
  dedup_hit: z.boolean(),
});

export const ServiceEventSchema = z.object({
  id: z.string(),
  ts: z.string(),
  type: z.string(),
  level: z.string(),
  message: z.string(),
  data: z.record(z.string(), z.unknown()).optional(),
});

export const ServiceEventsListSchema = z.object({
  events: z.array(ServiceEventSchema),
});

export type IntakeSource = z.infer<typeof IntakeSourceSchema>;
export type IntakeSourceList = z.infer<typeof IntakeSourceListSchema>;
export type IntakeReleaseResponse = z.infer<typeof IntakeReleaseResponseSchema>;
export type ServiceEvent = z.infer<typeof ServiceEventSchema>;
export type ServiceEventsList = z.infer<typeof ServiceEventsListSchema>;

export const ReleaseStatusSchema = z.enum(["local", "processing", "done", "failed", "on_seedbox", "uploaded"]);

export const ReleaseSchema = z.object({
  id: z.string(),
  path: z.string(),
  folder_name: z.string(),
  detected_kind: z.string(),
  status: ReleaseStatusSchema,
  created_at: z.string(),
  updated_at: z.string(),
});

export const ReleasesListSchema = z.object({
  releases: z.array(ReleaseSchema),
});

export const ReleaseOperationSchema = z.object({
  id: z.string(),
  release_id: z.string(),
  job_id: z.string(),
  module: z.string(),
  timestamp: z.string(),
  result_ok: z.number(),
});

export const ReleaseOperationsListSchema = z.object({
  operations: z.array(ReleaseOperationSchema),
});

export type Release = z.infer<typeof ReleaseSchema>;
export type ReleasesList = z.infer<typeof ReleasesListSchema>;
export type ReleaseOperation = z.infer<typeof ReleaseOperationSchema>;
export type ReleaseOperationsList = z.infer<typeof ReleaseOperationsListSchema>;

export const WorkflowSessionStatusSchema = z.enum([
  "draft",
  "running",
  "paused",
  "blocked",
  "completed",
  "failed",
  "cancelled",
]);

export const WorkflowStepStateSchema = z.enum([
  "locked",
  "ready",
  "in_progress",
  "blocked_decision",
  "done",
  "skipped",
  "failed",
  "cancelled",
]);

export const WorkflowExecutionStatusSchema = z.enum([
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
]);

export const WorkflowModeSchema = z.enum([
  "interactive",
  "auto",
  "batch_interactive",
  "batch_auto",
]);

export const WorkflowSessionSchema = z.object({
  id: z.string(),
  release_id: z.string(),
  status: WorkflowSessionStatusSchema,
  mode: WorkflowModeSchema,
  stop_on_error: z.boolean(),
  current_step_key: z.string().nullable(),
  source: z.string(),
  created_by: z.string().nullable(),
  context: z.record(z.string(), z.unknown()),
  last_error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});

export const WorkflowStepSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  step_key: z.string(),
  step_label: z.string(),
  module_name: z.string(),
  position: z.number(),
  state: WorkflowStepStateSchema,
  required: z.boolean(),
  continue_on_prev_failure: z.boolean(),
  latest_execution_id: z.string().nullable(),
  last_error: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});

export const WorkflowDecisionSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  step_id: z.string(),
  decision_key: z.string(),
  value: z.unknown(),
  source: z.string(),
  revision: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const WorkflowExecutionSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  step_id: z.string(),
  attempt: z.number(),
  status: WorkflowExecutionStatusSchema,
  job_id: z.string().nullable(),
  module_name: z.string(),
  input: z.record(z.string(), z.unknown()),
  args_text: z.string(),
  command_preview: z.string().nullable(),
  dry_run: z.boolean(),
  returncode: z.number().nullable(),
  stdout_tail: z.string(),
  stderr_tail: z.string(),
  failure_kind: z.string().nullable(),
  error: z.string().nullable(),
  queued_at: z.string(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  updated_at: z.string(),
});

export const WorkflowArtifactSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  step_id: z.string().nullable(),
  execution_id: z.string().nullable(),
  kind: z.string(),
  path: z.string(),
  exists: z.boolean(),
  metadata: z.record(z.string(), z.unknown()),
  created_at: z.string(),
});

export const WorkflowSessionsListSchema = z.object({
  sessions: z.array(WorkflowSessionSchema),
});

export const WorkflowSessionDetailSchema = z.object({
  session: WorkflowSessionSchema,
  steps: z.array(WorkflowStepSchema),
  decisions: z.array(WorkflowDecisionSchema),
  executions: z.array(WorkflowExecutionSchema),
  artifacts: z.array(WorkflowArtifactSchema),
});

export const WorkflowArtifactsListSchema = z.object({
  artifacts: z.array(WorkflowArtifactSchema),
});

export type WorkflowSessionStatus = z.infer<typeof WorkflowSessionStatusSchema>;
export type WorkflowStepState = z.infer<typeof WorkflowStepStateSchema>;
export type WorkflowExecutionStatus = z.infer<typeof WorkflowExecutionStatusSchema>;
export type WorkflowMode = z.infer<typeof WorkflowModeSchema>;
export type WorkflowSession = z.infer<typeof WorkflowSessionSchema>;
export type WorkflowStep = z.infer<typeof WorkflowStepSchema>;
export type WorkflowDecision = z.infer<typeof WorkflowDecisionSchema>;
export type WorkflowExecution = z.infer<typeof WorkflowExecutionSchema>;
export type WorkflowArtifact = z.infer<typeof WorkflowArtifactSchema>;
export type WorkflowSessionsList = z.infer<typeof WorkflowSessionsListSchema>;
export type WorkflowSessionDetail = z.infer<typeof WorkflowSessionDetailSchema>;
export type WorkflowArtifactsList = z.infer<typeof WorkflowArtifactsListSchema>;
