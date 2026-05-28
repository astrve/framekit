import { z } from "zod";

import { ApiError, fetchValidated, resolveApiBaseUrl } from "@/lib/api/client";
import {
  AliasListSchema,
  AuthLoginResponseSchema,
  AuthStatusSchema,
  AuthUsersListSchema,
  AuthUserSchema,
  WebhookListSchema,
  ToolsCheckSchema,
  DoctorPayloadSchema,
  HealthSchema,
  LogsReadSchema,
  ModulesCatalogSchema,
  ModulesCliSpecSchema,
  ModuleJobSchema,
  ModuleJobsListSchema,
  ModulesPresetsSchema,
  ModulesResourcesSchema,
  PresetDeleteAllResultSchema,
  ProviderTokenSchema,
  RunModuleResultSchema,
  SeedboxListSchema,
  SeedboxHistorySchema,
  SettingsSummarySchema,
  SystemInfoSchema,
  ImageHostKeySchema,
  TorrentClientPasswordSchema,
  PresetResultSchema,
  TmdbTokenSchema,
  TorrentAnnouncesSchema,
  UploadHistorySchema,
  UploadTrackerInfoSchema,
  UploadStateSchema,
  UploadTrackersSchema,
  VaultStatusSchema,
  WatchFoldersSchema,
  WatchServiceStatusSchema,
  WatchServiceStopSchema,
  ServiceStatusSchema,
  SettingsProfilesSchema,
  RunsListSchema,
  type RunsList,
  type AliasList,
  type AuthLoginResponse,
  type AuthStatus,
  type AuthUser,
  type AuthUsersList,
  type WebhookList,
  type ToolsCheck,
  type DoctorPayload,
  type HealthPayload,
  type LogsRead,
  type ModuleJob,
  type ModulesCatalog,
  type ModulesCliSpec,
  type ModulesPresets,
  type ModulesResources,
  type PresetDeleteAllResult,
  type ProviderToken,
  type SeedboxList,
  type SeedboxHistory,
  type SettingsSummary,
  type ImageHostKey,
  type TorrentClientPassword,
  type PresetResult,
  type TmdbToken,
  type TorrentAnnounces,
  type UploadHistory,
  type UploadTrackerInfo,
  type UploadState,
  type RunModuleResult,
  type SystemInfoPayload,
  type UploadTrackers,
  type VaultStatus,
  type WatchFolders,
  type WatchServiceStatus,
  type WatchServiceStop,
  type ServiceStatus,
  type SettingsProfiles,
  IntakeSourceListSchema,
  IntakeReleaseResponseSchema,
  ServiceEventSchema,
  ServiceEventsListSchema,
  type IntakeSource,
  type IntakeSourceList,
  type IntakeReleaseResponse,
  type ServiceEvent,
  type ServiceEventsList,
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

export async function getModulesCliSpec(): Promise<ModulesCliSpec> {
  return fetchValidated("/api/v1/modules/spec", ModulesCliSpecSchema);
}

export async function getModulesPresets(): Promise<ModulesPresets> {
  return fetchValidated("/api/v1/modules/presets", ModulesPresetsSchema);
}

export async function getModulesResources(): Promise<ModulesResources> {
  return fetchValidated("/api/v1/modules/resources", ModulesResourcesSchema);
}

export async function getSettingsSummary(): Promise<SettingsSummary> {
  return fetchValidated("/api/v1/settings/summary", SettingsSummarySchema);
}

export async function patchSettings(changes: Record<string, unknown>): Promise<SettingsSummary> {
  return fetchValidated("/api/v1/settings/patch", SettingsSummarySchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ changes }),
  });
}

export async function getSeedboxList(): Promise<SeedboxList> {
  return fetchValidated("/api/v1/seedbox/list", SeedboxListSchema);
}

export async function addSeedbox(payload: {
  name: string;
  rclone_remote: string;
  remote_base_path: string;
  max_concurrent_uploads?: number;
  bandwidth_limit?: string;
  set_default?: boolean;
}): Promise<SeedboxList> {
  return fetchValidated("/api/v1/seedbox/add", SeedboxListSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function useSeedbox(name: string, profileName?: string): Promise<SeedboxList> {
  return fetchValidated("/api/v1/seedbox/use", SeedboxListSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, profile_name: profileName ?? null }),
  });
}

export async function removeSeedbox(name: string): Promise<SeedboxList> {
  return fetchValidated("/api/v1/seedbox/remove", SeedboxListSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function getUploadTrackers(): Promise<UploadTrackers> {
  return fetchValidated("/api/v1/upload/trackers", UploadTrackersSchema);
}

export async function getUploadTrackerInfo(name: string): Promise<UploadTrackerInfo> {
  return fetchValidated(`/api/v1/upload/tracker/${encodeURIComponent(name)}`, UploadTrackerInfoSchema);
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

export async function clearModuleJobs(): Promise<{ deleted: number }> {
  return fetchValidated("/api/v1/modules/jobs", z.object({ deleted: z.number() }), { method: "DELETE" });
}

export async function getLogsRead(lines = 200, level?: string): Promise<LogsRead> {
  const lvlParam = level ? `&level=${encodeURIComponent(level)}` : "";
  return fetchValidated(`/api/v1/logs/read?lines=${lines}${lvlParam}`, LogsReadSchema);
}

export async function getVaultStatus(): Promise<VaultStatus> {
  return fetchValidated("/api/v1/security/vault", VaultStatusSchema);
}

export async function getTmdbToken(): Promise<TmdbToken> {
  return fetchValidated("/api/v1/settings/tmdb-token", TmdbTokenSchema);
}

export async function setTmdbToken(token: string): Promise<TmdbToken> {
  return fetchValidated("/api/v1/settings/tmdb-token", TmdbTokenSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export async function getTorrentAnnounces(): Promise<TorrentAnnounces> {
  return fetchValidated("/api/v1/torrent/announces", TorrentAnnouncesSchema);
}

export async function addTorrentAnnounce(url: string): Promise<TorrentAnnounces> {
  return fetchValidated("/api/v1/torrent/announces", TorrentAnnouncesSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function removeTorrentAnnounce(index: number): Promise<TorrentAnnounces> {
  return fetchValidated(`/api/v1/torrent/announces/${index}`, TorrentAnnouncesSchema, {
    method: "DELETE",
  });
}

export async function selectTorrentAnnounce(url: string): Promise<TorrentAnnounces> {
  return fetchValidated("/api/v1/torrent/announces/select", TorrentAnnouncesSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function getImageHostKey(host: string): Promise<ImageHostKey> {
  return fetchValidated(`/api/v1/upload/image-host-key/${encodeURIComponent(host)}`, ImageHostKeySchema);
}

export async function setImageHostKey(host: string, key: string): Promise<ImageHostKey> {
  return fetchValidated(`/api/v1/upload/image-host-key/${encodeURIComponent(host)}`, ImageHostKeySchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
}

export async function getTorrentClientPassword(): Promise<TorrentClientPassword> {
  return fetchValidated("/api/v1/upload/torrent-client-password", TorrentClientPasswordSchema);
}

export async function setTorrentClientPassword(password: string): Promise<TorrentClientPassword> {
  return fetchValidated("/api/v1/upload/torrent-client-password", TorrentClientPasswordSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
}

export async function createPreset(kind: string, name: string, content: string): Promise<PresetResult> {
  return fetchValidated(`/api/v1/presets/${encodeURIComponent(kind)}`, PresetResultSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, content }),
  });
}

export async function deletePreset(kind: string, name: string): Promise<PresetResult> {
  return fetchValidated(`/api/v1/presets/${encodeURIComponent(kind)}/${encodeURIComponent(name)}`, PresetResultSchema, {
    method: "DELETE",
  });
}

export async function getWatchFolders(): Promise<WatchFolders> {
  return fetchValidated("/api/v1/watch/folders", WatchFoldersSchema);
}

export async function addWatchFolder(path: string, preset = "default"): Promise<WatchFolders> {
  return fetchValidated("/api/v1/watch/folders", WatchFoldersSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, preset }),
  });
}

export async function removeWatchFolder(index: number): Promise<WatchFolders> {
  return fetchValidated(`/api/v1/watch/folders/${index}`, WatchFoldersSchema, {
    method: "DELETE",
  });
}

export async function getProviderToken(provider: string): Promise<ProviderToken> {
  return fetchValidated(`/api/v1/settings/provider-token/${encodeURIComponent(provider)}`, ProviderTokenSchema);
}

export async function setProviderToken(provider: string, token: string): Promise<ProviderToken> {
  return fetchValidated(`/api/v1/settings/provider-token/${encodeURIComponent(provider)}`, ProviderTokenSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
}

export async function renameAnnounce(index: number, label: string): Promise<TorrentAnnounces> {
  return fetchValidated(`/api/v1/torrent/announces/${index}`, TorrentAnnouncesSchema, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
}

export async function deleteAllPresets(kind: string): Promise<PresetDeleteAllResult> {
  return fetchValidated(`/api/v1/presets/${encodeURIComponent(kind)}/all`, PresetDeleteAllResultSchema, {
    method: "DELETE",
  });
}

export async function getSettingsProfiles(): Promise<SettingsProfiles> {
  return fetchValidated("/api/v1/profiles", SettingsProfilesSchema);
}

export async function activateSettingsProfile(name: string): Promise<SettingsProfiles> {
  return fetchValidated("/api/v1/profiles/activate", SettingsProfilesSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function deactivateSettingsProfile(): Promise<SettingsProfiles> {
  return fetchValidated("/api/v1/profiles/deactivate", SettingsProfilesSchema, {
    method: "POST",
  });
}

export async function createSettingsProfile(
  name: string,
  description = "",
  overrides: Record<string, unknown> = {},
): Promise<SettingsProfiles> {
  return fetchValidated("/api/v1/profiles", SettingsProfilesSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, overrides }),
  });
}

export async function deleteSettingsProfile(name: string): Promise<SettingsProfiles> {
  return fetchValidated(`/api/v1/profiles/${encodeURIComponent(name)}`, SettingsProfilesSchema, {
    method: "DELETE",
  });
}

export async function checkToolsStatus(): Promise<ToolsCheck> {
  return fetchValidated("/api/v1/tools/check", ToolsCheckSchema);
}

export async function getAliases(): Promise<AliasList> {
  return fetchValidated("/api/v1/aliases", AliasListSchema);
}

export async function addAlias(payload: {
  name: string;
  command: string;
  description?: string;
  enabled?: boolean;
}): Promise<AliasList> {
  return fetchValidated("/api/v1/aliases", AliasListSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function removeAlias(name: string): Promise<AliasList> {
  return fetchValidated(`/api/v1/aliases/${encodeURIComponent(name)}`, AliasListSchema, {
    method: "DELETE",
  });
}

export async function enableAlias(name: string): Promise<AliasList> {
  return fetchValidated(`/api/v1/aliases/${encodeURIComponent(name)}/enable`, AliasListSchema, {
    method: "POST",
  });
}

export async function disableAlias(name: string): Promise<AliasList> {
  return fetchValidated(`/api/v1/aliases/${encodeURIComponent(name)}/disable`, AliasListSchema, {
    method: "POST",
  });
}

// Webhooks
export async function getWebhooks(): Promise<WebhookList> {
  return fetchValidated("/api/v1/webhooks", WebhookListSchema);
}

export async function addWebhook(payload: {
  name: string;
  url: string;
  discord?: boolean;
  events?: string[];
  title_template?: string;
  body_template?: string;
}): Promise<WebhookList> {
  return fetchValidated("/api/v1/webhooks", WebhookListSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateWebhook(
  id: string,
  patch: { enabled?: boolean; name?: string; url?: string; discord?: boolean; events?: string[]; title_template?: string; body_template?: string },
): Promise<WebhookList> {
  return fetchValidated(`/api/v1/webhooks/${encodeURIComponent(id)}`, WebhookListSchema, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function removeWebhook(id: string): Promise<WebhookList> {
  return fetchValidated(`/api/v1/webhooks/${encodeURIComponent(id)}`, WebhookListSchema, {
    method: "DELETE",
  });
}

function _extractApiDetail(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      return (JSON.parse(err.body) as { detail?: string }).detail || err.message;
    } catch {
      return err.message;
    }
  }
  return err instanceof Error ? err.message : String(err);
}

export async function testWebhook(id: string): Promise<void> {
  let result: { ok: boolean };
  try {
    result = await fetchValidated(
      `/api/v1/webhooks/${encodeURIComponent(id)}/test`,
      z.object({ ok: z.boolean() }),
      { method: "POST" },
    );
  } catch (err) {
    throw new Error(_extractApiDetail(err) || "Test failed");
  }
  if (!result.ok) throw new Error("Test failed");
}

export async function testWebhookPayload(payload: {
  url: string;
  discord?: boolean;
  events?: string[];
  title_template?: string;
  body_template?: string;
}): Promise<void> {
  let result: { ok: boolean };
  try {
    result = await fetchValidated("/api/v1/webhooks/test", z.object({ ok: z.boolean() }), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    throw new Error(_extractApiDetail(err) || "Test failed");
  }
  if (!result.ok) throw new Error("Test failed");
}

// Auth
export async function getAuthStatus(): Promise<AuthStatus> {
  return fetchValidated("/api/v1/auth/status", AuthStatusSchema);
}

export async function authLogin(username: string, password: string): Promise<AuthLoginResponse> {
  return fetchValidated("/api/v1/auth/login", AuthLoginResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function authSetup(username: string, password: string): Promise<AuthLoginResponse> {
  return fetchValidated("/api/v1/auth/setup", AuthLoginResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function getAuthMe(token: string): Promise<AuthUser> {
  return fetchValidated("/api/v1/auth/me", AuthUserSchema, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getAuthUsers(token: string): Promise<AuthUsersList> {
  return fetchValidated("/api/v1/auth/users", AuthUsersListSchema, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function createAuthUser(token: string, payload: {
  username: string;
  password: string;
  role?: string;
}): Promise<AuthUser> {
  return fetchValidated("/api/v1/auth/users", AuthUserSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

function _parseRawDetail(body: string): string {
  try {
    return (JSON.parse(body) as { detail?: string }).detail || body;
  } catch {
    return body;
  }
}

export async function deleteAuthUser(token: string, userId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${resolveApiBaseUrl()}/api/v1/auth/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(_parseRawDetail(await res.text()));
  return { ok: true };
}

export async function enableAuthUser(token: string, userId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${resolveApiBaseUrl()}/api/v1/auth/users/${encodeURIComponent(userId)}/enable`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(_parseRawDetail(await res.text()));
  return { ok: true };
}

export async function disableAuthUser(token: string, userId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${resolveApiBaseUrl()}/api/v1/auth/users/${encodeURIComponent(userId)}/disable`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(_parseRawDetail(await res.text()));
  return { ok: true };
}

export async function changeAuthUserPassword(token: string, userId: string, newPassword: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${resolveApiBaseUrl()}/api/v1/auth/users/${encodeURIComponent(userId)}/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ new_password: newPassword }),
  });
  if (!res.ok) throw new Error(_parseRawDetail(await res.text()));
  return { ok: true };
}

export async function getRuns(limit = 50): Promise<RunsList> {
  return fetchValidated(`/api/v1/runs?limit=${limit}`, RunsListSchema);
}

export async function getServiceStatus(): Promise<ServiceStatus> {
  return fetchValidated("/api/v1/service/status", ServiceStatusSchema);
}

export async function reloadService(): Promise<{ ok: boolean }> {
  return fetchValidated(
    "/api/v1/service/reload",
    ServiceStatusSchema.pick({ status: true }).extend({ ok: z.boolean(), watcher: ServiceStatusSchema.shape.watcher }),
    { method: "POST" },
  );
}

export async function getWatchServiceStatus(): Promise<WatchServiceStatus> {
  return fetchValidated("/api/v1/watch/service", WatchServiceStatusSchema);
}

export async function startWatchService(): Promise<ModuleJob> {
  return fetchValidated("/api/v1/watch/service/start", ModuleJobSchema, { method: "POST" });
}

export async function stopWatchService(): Promise<WatchServiceStop> {
  return fetchValidated("/api/v1/watch/service/stop", WatchServiceStopSchema, { method: "POST" });
}

// ── Intake API ────────────────────────────────────────────────────────────────

export async function listIntakeSources(): Promise<IntakeSourceList> {
  return fetchValidated("/api/v1/intake/sources", IntakeSourceListSchema);
}

export async function createIntakeSource(payload: {
  name: string;
  source_id: string;
  default_preset?: string | null;
}): Promise<IntakeSource> {
  // Response includes token field (shown once).
  return fetchValidated("/api/v1/intake/sources", IntakeSourceListSchema.shape.sources.element, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteIntakeSource(sourceId: string): Promise<{ deleted: boolean; source_id: string }> {
  return fetchValidated(
    `/api/v1/intake/sources/${encodeURIComponent(sourceId)}`,
    z.object({ deleted: z.boolean(), source_id: z.string() }),
    { method: "DELETE" },
  );
}

export async function submitIntakeRelease(payload: {
  source: string;
  path: string;
  preset?: string | null;
  dedup_key?: string | null;
}): Promise<IntakeReleaseResponse> {
  return fetchValidated("/api/v1/intake/release", IntakeReleaseResponseSchema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getRecentServiceEvents(limit = 100): Promise<ServiceEventsList> {
  return fetchValidated(`/api/v1/events/recent?limit=${limit}`, ServiceEventsListSchema);
}

function _parseSseChunk(rawChunk: string): { id: string | null; event: string; data: string | null } | null {
  const lines = rawChunk.replace(/\r/g, "").split("\n");
  let eventName = "message";
  let eventId: string | null = null;
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim() || "message";
      continue;
    }
    if (line.startsWith("id:")) {
      eventId = line.slice(3).trim() || null;
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }
  return {
    id: eventId,
    event: eventName,
    data: dataLines.join("\n"),
  };
}

export async function streamServiceEvents(params: {
  signal: AbortSignal;
  onEvent: (event: ServiceEvent) => void;
  lastEventId?: string | null;
}): Promise<void> {
  const token = localStorage.getItem("framekit_token");
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(params.lastEventId ? { "Last-Event-ID": params.lastEventId } : {}),
  };

  const response = await fetch(`${resolveApiBaseUrl()}/api/v1/events/stream`, {
    method: "GET",
    headers,
    signal: params.signal,
  });

  if (!response.ok) {
    const body = await response.text();
    if (response.status === 401) {
      localStorage.removeItem("framekit_token");
      window.dispatchEvent(new CustomEvent("framekit:unauthorized"));
    }
    throw new ApiError("API request failed for /api/v1/events/stream", response.status, body);
  }
  if (!response.body) {
    throw new Error("Event stream body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    while (true) {
      const separatorIndex = buffer.indexOf("\n\n");
      if (separatorIndex < 0) break;
      const chunk = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const parsed = _parseSseChunk(chunk);
      if (!parsed?.data) continue;
      try {
        const event = ServiceEventSchema.parse(JSON.parse(parsed.data));
        params.onEvent(event);
      } catch {
        // Ignore malformed event payloads; keep stream alive.
      }
    }
  }
}
