import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Activity,
  AlertCircle,
  Check,
  Cog,
  Database,
  Eye,
  EyeOff,
  Folder,
  FolderOpen,
  FolderTree,
  Loader2,
  Pencil,
  Play,
  Plus,
  ScrollText,
  Server,
  ServerCog,
  Settings,
  Shield,
  SlidersHorizontal,
  Square,
  Trash2,
  Upload,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import {
  activateSettingsProfile,
  addTorrentAnnounce,
  addWatchFolder,
  getWatchServiceStatus,
  startWatchService,
  stopWatchService,
  createSettingsProfile,
  deactivateSettingsProfile,
  deleteSettingsProfile,
  getDoctorPayload,
  getImageHostKey,
  getModulesResources,
  getSeedboxList,
  getSettingsSummary,
  getSettingsProfiles,
  getTmdbToken,
  getTorrentAnnounces,
  getUploadTrackers,
  getVaultStatus,
  getWatchFolders,
  patchSettings,
  removeTorrentAnnounce,
  removeWatchFolder,
  renameAnnounce,
  selectTorrentAnnounce,
  getProviderToken,
  getTorrentClientPassword,
  setImageHostKey,
  setProviderToken,
  setTmdbToken,
  setTorrentClientPassword,
  checkToolsStatus,
  addSeedbox,
  useSeedbox,
  removeSeedbox,
} from "@/lib/api/endpoints";
import type { DoctorPayload, ModuleJob, ProviderToken, SettingsProfiles, TmdbToken, TorrentAnnounces, TorrentClientPassword, VaultStatus, WatchFolders, WatchServiceStatus, ToolsCheck, ToolCheckItem } from "@/lib/api/schemas";

// ────────────────────────────────────────────────────────────────────────────
// helpers
// ────────────────────────────────────────────────────────────────────────────

function getS(settings: Record<string, unknown>, path: string, fallback: unknown = ""): unknown {
  const parts = path.split(".");
  let current: unknown = settings;
  for (const part of parts) {
    if (current && typeof current === "object" && !Array.isArray(current)) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return fallback;
    }
  }
  return current ?? fallback;
}

function str(v: unknown, fallback = ""): string {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return fallback;
  return String(v);
}
function bool(v: unknown, fallback = false): boolean {
  if (typeof v === "boolean") return v;
  return fallback;
}
function num(v: unknown, fallback = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

// ────────────────────────────────────────────────────────────────────────────
// field helpers
// ────────────────────────────────────────────────────────────────────────────

function FieldLabel({ label, tooltip }: { label: string; tooltip?: string | undefined }) {
  return (
    <span className="flex items-center gap-0 text-sm font-medium leading-none">
      {label}
      {tooltip ? <InfoTooltip text={tooltip} /> : null}
    </span>
  );
}

function TextField({
  label,
  value,
  onChange,
  tooltip,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  tooltip?: string | undefined;
  placeholder?: string | undefined;
  type?: string | undefined;
}) {
  return (
    <label className="space-y-1">
      <FieldLabel label={label} tooltip={tooltip} />
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  tooltip,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
  tooltip?: string;
}) {
  return (
    <label className="space-y-1">
      <FieldLabel label={label} tooltip={tooltip} />
      <select
        className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function BoolField({
  label,
  checked,
  onChange,
  tooltip,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  tooltip?: string;
}) {
  return (
    <Toggle
      checked={checked}
      onChange={onChange}
      label={label}
      tooltip={tooltip ? <InfoTooltip text={tooltip} /> : undefined}
    />
  );
}

function SaveRow({
  onSave,
  isPending,
  isSuccess,
  error,
}: {
  onSave: () => void;
  isPending: boolean;
  isSuccess: boolean;
  error?: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
      <Button type="button" size="sm" onClick={onSave} disabled={isPending}>
        Save
      </Button>
      {isSuccess ? <Badge variant="success">Saved</Badge> : null}
      {error ? <span className="text-xs text-destructive">{error}</span> : null}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// main component
// ────────────────────────────────────────────────────────────────────────────

type Draft = Record<string, unknown>;

function initDraft(settings: Record<string, unknown>): Draft {
  return {
    // General
    "general.locale": str(getS(settings, "general.locale"), "en"),
    "general.log_level": str(getS(settings, "general.log_level"), "INFO"),
    "general.default_folder": str(getS(settings, "general.default_folder"), ""),
    "general.report_output_folder": str(getS(settings, "general.report_output_folder"), ""),
    // Logging
    "logging.max_size_mb": num(getS(settings, "logging.max_size_mb"), 100),
    "logging.max_backups": num(getS(settings, "logging.max_backups"), 30),
    "logging.compress_old_logs": bool(getS(settings, "logging.compress_old_logs"), true),
    "logging.retention_days": num(getS(settings, "logging.retention_days"), 5),
    "logging.cleanup_on_startup": bool(getS(settings, "logging.cleanup_on_startup"), true),
    // Tools
    "tools.mkvmerge": str(getS(settings, "tools.mkvmerge"), ""),
    "tools.ffmpeg": str(getS(settings, "tools.ffmpeg"), ""),
    "tools.ffprobe": str(getS(settings, "tools.ffprobe"), ""),
    "tools.mediainfo": str(getS(settings, "tools.mediainfo"), ""),
    // Metadata
    "metadata.provider": str(getS(settings, "metadata.provider"), "tmdb"),
    "metadata.language": str(getS(settings, "metadata.language"), "en-US"),
    "metadata.cache_ttl_hours": num(getS(settings, "metadata.cache_ttl_hours"), 168),
    "metadata.interactive_confirmation": bool(getS(settings, "metadata.interactive_confirmation"), true),
    "metadata.enabled_by_default": bool(getS(settings, "metadata.enabled_by_default"), true),
    "metadata.prompt_missing_token_in_pipeline": bool(getS(settings, "metadata.prompt_missing_token_in_pipeline"), true),
    "metadata.anilist_enabled": bool(getS(settings, "metadata.anilist_enabled"), true),
    "metadata.anilist_language": str(getS(settings, "metadata.anilist_language"), "en"),
    "metadata.tvdb_language": str(getS(settings, "metadata.tvdb_language"), "eng"),
    // Upload
    "upload.enabled": bool(getS(settings, "upload.enabled"), false),
    "upload.auto_upload": bool(getS(settings, "upload.auto_upload"), false),
    "upload.max_parallel_uploads": num(getS(settings, "upload.max_parallel_uploads"), 3),
    "upload.image_host": str(getS(settings, "upload.image_host"), ""),
    "upload.torrent_client": str(getS(settings, "upload.torrent_client"), ""),
    "upload.torrent_client_host": str(getS(settings, "upload.torrent_client_host"), "localhost"),
    "upload.torrent_client_port": num(getS(settings, "upload.torrent_client_port"), 8080),
    "upload.torrent_client_category": str(getS(settings, "upload.torrent_client_category"), "framekit"),
    "upload.torrent_client_username": str(getS(settings, "upload.torrent_client_username"), ""),
    "upload.torrent_client_tag": str(getS(settings, "upload.torrent_client_tag"), ""),
    // Seedbox
    "seedbox.max_concurrent_uploads": num(getS(settings, "seedbox.max_concurrent_uploads"), 3),
    "seedbox.history_enabled": bool(getS(settings, "seedbox.history_enabled"), true),
    // Watch
    "watch.enabled": bool(getS(settings, "watch.enabled"), false),
    "watch.notifications.enabled": bool(getS(settings, "watch.notifications.enabled"), true),
    "watch.notifications.on_start": bool(getS(settings, "watch.notifications.on_start"), false),
    "watch.notifications.on_success": bool(getS(settings, "watch.notifications.on_success"), false),
    "watch.notifications.on_error": bool(getS(settings, "watch.notifications.on_error"), true),
    "watch.notifications.on_watch_started": bool(getS(settings, "watch.notifications.on_watch_started"), true),
    // Setup
    "setup.completed": bool(getS(settings, "setup.completed"), false),
    "setup.prompt_on_start": bool(getS(settings, "setup.prompt_on_start"), true),
    // Pipeline
    "modules.pipeline.stop_on_error": bool(getS(settings, "modules.pipeline.stop_on_error"), false),
    "modules.pipeline.with_metadata": bool(getS(settings, "modules.pipeline.with_metadata"), true),
    "modules.pipeline.auto_mode": bool(getS(settings, "modules.pipeline.auto_mode"), false),
    "modules.pipeline.upload_on_failure": bool(getS(settings, "modules.pipeline.upload_on_failure"), false),
    "modules.pipeline.upload_timeout": num(getS(settings, "modules.pipeline.upload_timeout"), 300),
    "modules.pipeline.enabled_modules": (() => { const raw = getS(settings, "modules.pipeline.enabled_modules"); return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : ["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"]; })(),
    // NFO
    "modules.nfo.locale": str(getS(settings, "modules.nfo.locale"), "auto"),
    "modules.nfo.active_template": str(getS(settings, "modules.nfo.active_template"), "default"),
    "modules.nfo.with_metadata": bool(getS(settings, "modules.nfo.with_metadata"), true),
    "modules.nfo.mode": str(getS(settings, "modules.nfo.mode"), "global"),
    // Torrent
    "modules.torrent.private": bool(getS(settings, "modules.torrent.private"), true),
    "modules.torrent.piece_length": str(getS(settings, "modules.torrent.piece_length"), "auto"),
    "modules.torrent.prompt_save_announce": bool(getS(settings, "modules.torrent.prompt_save_announce"), true),
    // Prez
    "modules.prez.locale": str(getS(settings, "modules.prez.locale"), "auto"),
    "modules.prez.format": str(getS(settings, "modules.prez.format"), "both"),
    "modules.prez.html_template": str(getS(settings, "modules.prez.html_template"), "aurora"),
    "modules.prez.bbcode_template": str(getS(settings, "modules.prez.bbcode_template"), "classic"),
    "modules.prez.mediainfo_mode": str(getS(settings, "modules.prez.mediainfo_mode"), "none"),
    "modules.prez.include_mediainfo": bool(getS(settings, "modules.prez.include_mediainfo"), false),
    "modules.prez.with_metadata": bool(getS(settings, "modules.prez.with_metadata"), true),
    // CleanMKV
    "modules.cleanmkv.default_preset": str(getS(settings, "modules.cleanmkv.default_preset"), "multi"),
    "modules.cleanmkv.output_dir_name": str(getS(settings, "modules.cleanmkv.output_dir_name"), "Release/{release}"),
    "modules.cleanmkv.copy_unchanged_files": bool(getS(settings, "modules.cleanmkv.copy_unchanged_files"), true),
    // Renamer
    "modules.renamer.default_language_tag": str(getS(settings, "modules.renamer.default_language_tag"), "MULTI.VFF"),
    "modules.renamer.profile": str(getS(settings, "modules.renamer.profile"), ""),
    // Screenshot
    "modules.screenshot.target": str(getS(settings, "modules.screenshot.target"), "prez"),
    // Encoder
    "modules.encoder.preset": str(getS(settings, "modules.encoder.preset"), ""),
    "modules.encoder.output_dir_name": str(getS(settings, "modules.encoder.output_dir_name"), "encoded"),
  };
}

export function SettingsSetupPage() {
  const [draft, setDraft] = useState<Draft>({});
  const [patchError, setPatchError] = useState<string | null>(null);
  const [lastSavedSection, setLastSavedSection] = useState<string | null>(null);

  const settingsQuery = useQuery({ queryKey: ["settings-summary"], queryFn: getSettingsSummary });
  const seedboxesQuery = useQuery({ queryKey: ["seedbox-list"], queryFn: getSeedboxList });
  const trackersQuery = useQuery({ queryKey: ["upload-trackers"], queryFn: getUploadTrackers });
  const resourcesQuery = useQuery({ queryKey: ["modules-resources"], queryFn: getModulesResources });
  const vaultQuery = useQuery({ queryKey: ["vault-status"], queryFn: getVaultStatus });
  const tmdbTokenQuery = useQuery({ queryKey: ["tmdb-token"], queryFn: getTmdbToken });
  const announcesQuery = useQuery({ queryKey: ["torrent-announces"], queryFn: getTorrentAnnounces });

  const addSeedboxMutation = useMutation({
    mutationFn: addSeedbox,
    onSuccess: () => void seedboxesQuery.refetch(),
  });
  const useSeedboxMutation = useMutation({
    mutationFn: useSeedbox,
    onSuccess: () => void seedboxesQuery.refetch(),
  });
  const removeSeedboxMutation = useMutation({
    mutationFn: removeSeedbox,
    onSuccess: () => void seedboxesQuery.refetch(),
  });

  const [newSeedboxName, setNewSeedboxName] = useState("");
  const [newSeedboxRemote, setNewSeedboxRemote] = useState("");
  const [newSeedboxPath, setNewSeedboxPath] = useState("");
  const [newSeedboxBandwidth, setNewSeedboxBandwidth] = useState("");
  const [newSeedboxAddOpen, setNewSeedboxAddOpen] = useState(false);

  const [tmdbInput, setTmdbInput] = useState("");
  const [tvdbInput, setTvdbInput] = useState("");
  const [anilistInput, setAnilistInput] = useState("");
  const [traktInput, setTraktInput] = useState("");
  const [newAnnounceUrl, setNewAnnounceUrl] = useState("");
  const [announceReveal, setAnnounceReveal] = useState<Record<number, boolean>>({});
  const [announceEditIdx, setAnnounceEditIdx] = useState<number | null>(null);
  const [announceEditLabel, setAnnounceEditLabel] = useState("");
  const [tokenReveal, setTokenReveal] = useState<Record<string, boolean>>({});

  const setTmdbMutation = useMutation({
    mutationFn: (token: string) => setTmdbToken(token),
    onSuccess: () => {
      void tmdbTokenQuery.refetch();
      setTmdbInput("");
    },
  });

  const tvdbTokenQuery = useQuery({ queryKey: ["provider-token-tvdb"], queryFn: () => getProviderToken("tvdb") });
  const anilistTokenQuery = useQuery({ queryKey: ["provider-token-anilist"], queryFn: () => getProviderToken("anilist") });
  const traktTokenQuery = useQuery({ queryKey: ["provider-token-trakt"], queryFn: () => getProviderToken("trakt") });

  const saveTvdbTokenMutation = useMutation({
    mutationFn: (token: string) => setProviderToken("tvdb", token),
    onSuccess: () => { void tvdbTokenQuery.refetch(); setTvdbInput(""); },
  });
  const saveAnilistTokenMutation = useMutation({
    mutationFn: (token: string) => setProviderToken("anilist", token),
    onSuccess: () => { void anilistTokenQuery.refetch(); setAnilistInput(""); },
  });
  const saveTraktTokenMutation = useMutation({
    mutationFn: (token: string) => setProviderToken("trakt", token),
    onSuccess: () => { void traktTokenQuery.refetch(); setTraktInput(""); },
  });

  const renameAnnounceMutation = useMutation({
    mutationFn: ({ index, label }: { index: number; label: string }) => renameAnnounce(index, label),
    onSuccess: () => { void announcesQuery.refetch(); setAnnounceEditIdx(null); setAnnounceEditLabel(""); },
  });

  const addAnnounceMutation = useMutation({
    mutationFn: (url: string) => addTorrentAnnounce(url),
    onSuccess: () => { void announcesQuery.refetch(); setNewAnnounceUrl(""); },
  });
  const removeAnnounceMutation = useMutation({
    mutationFn: (index: number) => removeTorrentAnnounce(index),
    onSuccess: () => void announcesQuery.refetch(),
  });
  const selectAnnounceMutation = useMutation({
    mutationFn: (url: string) => selectTorrentAnnounce(url),
    onSuccess: () => void announcesQuery.refetch(),
  });

  const imgbbKeyQuery = useQuery({ queryKey: ["imghost-key-imgbb"], queryFn: () => getImageHostKey("imgbb") });
  const ptpimgKeyQuery = useQuery({ queryKey: ["imghost-key-ptpimg"], queryFn: () => getImageHostKey("ptpimg") });
  const freeimageKeyQuery = useQuery({ queryKey: ["imghost-key-freeimage"], queryFn: () => getImageHostKey("freeimage") });
  const imgboxKeyQuery = useQuery({ queryKey: ["imghost-key-imgbox"], queryFn: () => getImageHostKey("imgbox") });

  const watchFoldersQuery = useQuery({ queryKey: ["watch-folders"], queryFn: getWatchFolders });
  const [newWatchPath, setNewWatchPath] = useState("");
  const [newWatchPreset, setNewWatchPreset] = useState("default");
  const addWatchFolderMutation = useMutation({
    mutationFn: ({ path, preset }: { path: string; preset: string }) => addWatchFolder(path, preset),
    onSuccess: () => { void watchFoldersQuery.refetch(); setNewWatchPath(""); setNewWatchPreset("default"); },
  });
  const removeWatchFolderMutation = useMutation({
    mutationFn: (index: number) => removeWatchFolder(index),
    onSuccess: () => void watchFoldersQuery.refetch(),
  });

  const [watchJobId, setWatchJobId] = useState<string | null>(null);
  const watchServiceQuery = useQuery({
    queryKey: ["watch-service-status"],
    queryFn: getWatchServiceStatus,
    refetchInterval: 5000,
  });
  const startWatchMutation = useMutation({
    mutationFn: startWatchService,
    onSuccess: (job: ModuleJob) => {
      setWatchJobId(job.id);
      void watchServiceQuery.refetch();
    },
  });
  const stopWatchMutation = useMutation({
    mutationFn: stopWatchService,
    onSuccess: () => { void watchServiceQuery.refetch(); },
  });

  const [toolsCheckResult, setToolsCheckResult] = useState<ToolsCheck | null>(null);
  const toolsCheckMutation = useMutation({
    mutationFn: checkToolsStatus,
    onSuccess: (data) => setToolsCheckResult(data),
  });

  const profilesQuery = useQuery({ queryKey: ["settings-profiles"], queryFn: getSettingsProfiles });
  const activateProfileMutation = useMutation({
    mutationFn: (name: string) => activateSettingsProfile(name),
    onSuccess: () => { void profilesQuery.refetch(); void settingsQuery.refetch(); },
  });
  const deactivateProfileMutation = useMutation({
    mutationFn: () => deactivateSettingsProfile(),
    onSuccess: () => void profilesQuery.refetch(),
  });
  const [newProfileName, setNewProfileName] = useState("");
  const [newProfileDesc, setNewProfileDesc] = useState("");
  const [newProfileOverrides, setNewProfileOverrides] = useState("");
  const [newProfileOpen, setNewProfileOpen] = useState(false);
  const [expandedProfile, setExpandedProfile] = useState<string | null>(null);
  const createProfileMutation = useMutation({
    mutationFn: () => {
      let overrides: Record<string, unknown> = {};
      if (newProfileOverrides.trim()) {
        try { overrides = JSON.parse(newProfileOverrides) as Record<string, unknown>; }
        catch { throw new Error("Overrides must be valid JSON"); }
      }
      return createSettingsProfile(newProfileName.trim(), newProfileDesc.trim(), overrides);
    },
    onSuccess: () => {
      void profilesQuery.refetch();
      setNewProfileName("");
      setNewProfileDesc("");
      setNewProfileOverrides("");
      setNewProfileOpen(false);
    },
  });
  const deleteProfileMutation = useMutation({
    mutationFn: (name: string) => deleteSettingsProfile(name),
    onSuccess: () => void profilesQuery.refetch(),
  });
  const [imgbbKeyInput, setImgbbKeyInput] = useState("");
  const [ptpimgKeyInput, setPtpimgKeyInput] = useState("");
  const [freeimageKeyInput, setFreeimageKeyInput] = useState("");
  const [imgboxKeyInput, setImgboxKeyInput] = useState("");
  const saveImgbbKey = useMutation({ mutationFn: (k: string) => setImageHostKey("imgbb", k), onSuccess: () => { void imgbbKeyQuery.refetch(); setImgbbKeyInput(""); } });
  const savePtpimgKey = useMutation({ mutationFn: (k: string) => setImageHostKey("ptpimg", k), onSuccess: () => { void ptpimgKeyQuery.refetch(); setPtpimgKeyInput(""); } });
  const saveFreeimageKey = useMutation({ mutationFn: (k: string) => setImageHostKey("freeimage", k), onSuccess: () => { void freeimageKeyQuery.refetch(); setFreeimageKeyInput(""); } });
  const saveImgboxKey = useMutation({ mutationFn: (k: string) => setImageHostKey("imgbox", k), onSuccess: () => { void imgboxKeyQuery.refetch(); setImgboxKeyInput(""); } });

  const torrentPwdQuery = useQuery({ queryKey: ["torrent-client-password"], queryFn: getTorrentClientPassword });
  const [torrentPwdInput, setTorrentPwdInput] = useState("");
  const saveTorrentPwdMutation = useMutation({
    mutationFn: (pwd: string) => setTorrentClientPassword(pwd),
    onSuccess: () => { void torrentPwdQuery.refetch(); setTorrentPwdInput(""); },
  });

  const NFO_TEMPLATE_OPTIONS = [{ value: "default", label: "Default" }, { value: "detailed", label: "Detailed" }];
  const htmlTemplates = (resourcesQuery.data?.prez_templates.html ?? []).map((t) => ({ value: t, label: t }));
  const bbcodeTemplates = (resourcesQuery.data?.prez_templates.bbcode ?? []).map((t) => ({ value: t, label: t }));
  const cleanmkvPresets = (resourcesQuery.data?.cleanmkv_presets ?? []).map((t) => ({ value: t, label: t }));
  const renamerProfiles = (resourcesQuery.data?.renamer_profiles ?? []).map((t) => ({ value: t, label: t }));

  const patchMutation = useMutation({
    mutationFn: patchSettings,
    onSuccess: (payload) => {
      setPatchError(null);
      const s = payload.settings as Record<string, unknown>;
      setDraft((prev) => ({ ...prev, ...initDraft(s) }));
      void settingsQuery.refetch();
    },
    onError: (err) => setPatchError(err instanceof Error ? err.message : "Save failed"),
  });

  useEffect(() => {
    if (!settingsQuery.data?.settings) return;
    setDraft(initDraft(settingsQuery.data.settings as Record<string, unknown>));
  }, [settingsQuery.data]);

  function set(key: string, value: unknown) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  function save(section: string, keys: string[]) {
    const changes: Record<string, unknown> = {};
    for (const k of keys) changes[k] = draft[k];
    setLastSavedSection(section);
    patchMutation.mutate(changes);
  }

  const isSaved = (section: string) => lastSavedSection === section && patchMutation.isSuccess;

  function SaveBtn({ section, keys }: { section: string; keys: string[] }) {
    return (
      <SaveRow
        onSave={() => save(section, keys)}
        isPending={patchMutation.isPending && lastSavedSection === section}
        isSuccess={isSaved(section)}
        error={lastSavedSection === section ? patchError : null}
      />
    );
  }

  const defaultSeedbox = useMemo(
    () => (seedboxesQuery.data?.seedboxes ?? []).find((item) => item.is_default)?.name ?? "-",
    [seedboxesQuery.data?.seedboxes],
  );

  const [cleanmkvOverride, setCleanmkvOverride] = useState(false);

  const d = draft;

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border border-border bg-card p-5">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">All configurable settings, grouped by module and domain.</p>
      </section>

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader><CardTitle className="text-sm">Locale</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-semibold">{str(d["general.locale"], "–").toUpperCase()}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Default Seedbox</CardTitle></CardHeader>
          <CardContent><p className="text-sm font-semibold">{defaultSeedbox}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Seedbox Profiles</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-semibold">{(seedboxesQuery.data?.seedboxes ?? []).length}</p></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Upload Trackers</CardTitle></CardHeader>
          <CardContent><p className="text-xl font-semibold">{(trackersQuery.data?.trackers ?? []).length}</p></CardContent>
        </Card>
      </div>

      {/* ── PROFILES ────────────────────────────────────────────── */}
      <Card id="s-profiles">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Folder className="h-4 w-4 text-primary" />Configuration Profiles</CardTitle>
          <CardDescription>Named setting snapshots — activate one to apply its overrides instantly.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(profilesQuery.data?.profiles ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">No profiles yet. Create one below.</p>
          ) : (
            <div className="divide-y divide-border rounded-md border border-border">
              {(profilesQuery.data?.profiles ?? []).map((p) => (
                <div key={p.name} className="flex flex-col gap-0.5 px-3 py-2">
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      className="flex-1 min-w-0 text-left"
                      onClick={() => setExpandedProfile(expandedProfile === p.name ? null : p.name)}
                    >
                      <p className="text-sm font-medium flex items-center gap-2">
                        {p.name}
                        {p.active ? <Badge variant="success" className="text-xs">Active</Badge> : null}
                      </p>
                      {p.description ? <p className="text-xs text-muted-foreground">{p.description}</p> : null}
                    </button>
                    <div className="flex gap-2 shrink-0">
                      {p.active ? (
                        <Button type="button" variant="outline" size="sm"
                          onClick={() => deactivateProfileMutation.mutate()}
                          disabled={deactivateProfileMutation.isPending}>
                          Deactivate
                        </Button>
                      ) : (
                        <Button type="button" size="sm"
                          onClick={() => activateProfileMutation.mutate(p.name)}
                          disabled={activateProfileMutation.isPending}>
                          Activate
                        </Button>
                      )}
                      <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0 text-destructive hover:text-destructive shrink-0"
                        onClick={() => deleteProfileMutation.mutate(p.name)}
                        disabled={deleteProfileMutation.isPending}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                  {expandedProfile === p.name && Object.keys(p.overrides ?? {}).length > 0 ? (
                    <pre className="mt-1 rounded-md border border-border bg-muted p-2 text-xs font-mono overflow-auto max-h-40">
                      {JSON.stringify(p.overrides, null, 2)}
                    </pre>
                  ) : expandedProfile === p.name ? (
                    <p className="text-xs text-muted-foreground mt-1">No overrides defined.</p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
          {activateProfileMutation.isError ? (
            <p className="text-xs text-destructive">{String((activateProfileMutation.error as Error)?.message ?? "Failed")}</p>
          ) : null}
          {deleteProfileMutation.isError ? (
            <p className="text-xs text-destructive">{String((deleteProfileMutation.error as Error)?.message ?? "Failed")}</p>
          ) : null}
          {/* Create profile */}
          <div className="border-t border-border pt-3">
            <button
              type="button"
              className="flex items-center gap-1.5 text-sm text-primary hover:underline mb-2"
              onClick={() => setNewProfileOpen((v) => !v)}
            >
              <Plus className="h-3.5 w-3.5" />{newProfileOpen ? "Cancel" : "Create profile"}
            </button>
            {newProfileOpen ? (
              <div className="space-y-2">
                <div className="grid gap-2 sm:grid-cols-2">
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Name</span>
                    <Input value={newProfileName} onChange={(e) => setNewProfileName(e.target.value)} placeholder="my-profile" />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Description</span>
                    <Input value={newProfileDesc} onChange={(e) => setNewProfileDesc(e.target.value)} placeholder="Optional description" />
                  </label>
                </div>
                <label className="space-y-1 text-sm block">
                  <span className="font-medium flex items-center gap-1">
                    Overrides (JSON)
                    <InfoTooltip text="Settings key/value pairs this profile will apply when activated — e.g. {&quot;metadata.provider&quot;: &quot;tvdb&quot;}" />
                  </span>
                  <textarea
                    className="h-24 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                    value={newProfileOverrides}
                    onChange={(e) => setNewProfileOverrides(e.target.value)}
                    placeholder={'{\n  "metadata.provider": "tvdb"\n}'}
                  />
                </label>
                {createProfileMutation.isError ? (
                  <p className="text-xs text-destructive">{String((createProfileMutation.error as Error)?.message ?? "Failed")}</p>
                ) : null}
                <Button type="button" size="sm"
                  onClick={() => createProfileMutation.mutate()}
                  disabled={!newProfileName.trim() || createProfileMutation.isPending}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />Create
                </Button>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* ── GENERAL ─────────────────────────────────────────────── */}
      <Card id="s-general">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-primary" />General</CardTitle>
          <CardDescription>Core preferences applied across all modules.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="Language" value={str(d["general.locale"], "en")} onChange={(v) => set("general.locale", v)}
              tooltip="Interface language for Framekit CLI output"
              options={[{ value: "en", label: "English" }, { value: "fr", label: "French" }, { value: "es", label: "Spanish" }]} />
            <SelectField label="Log level" value={str(d["general.log_level"], "INFO")} onChange={(v) => set("general.log_level", v)}
              tooltip="Verbosity of process logs — DEBUG shows everything, ERROR shows only failures"
              options={[
                { value: "DEBUG", label: "Debug (verbose)" },
                { value: "INFO", label: "Info (normal)" },
                { value: "WARNING", label: "Warnings only" },
                { value: "ERROR", label: "Errors only" },
              ]} />
            <TextField label="Default folder" value={str(d["general.default_folder"])} onChange={(v) => set("general.default_folder", v)}
              tooltip="Default release folder when no path argument is provided" placeholder="/path/to/releases" />
            <TextField label="Report output folder" value={str(d["general.report_output_folder"])} onChange={(v) => set("general.report_output_folder", v)}
              tooltip="Folder where generated reports are saved (empty = next to release)" placeholder="/path/to/reports" />
          </div>
          <SaveBtn section="general" keys={["general.locale", "general.log_level", "general.default_folder", "general.report_output_folder"]} />
        </CardContent>
      </Card>

      {/* ── FILE LOCATIONS ──────────────────────────────────────── */}
      <Card id="s-file-locations">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><FolderTree className="h-4 w-4 text-primary" />File Locations</CardTitle>
          <CardDescription>Runtime files and directories (read-only).</CardDescription>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-border">
              <tr className="py-2">
                <td className="py-2 pr-4 font-medium text-muted-foreground w-36">Settings file</td>
                <td className="py-2 font-mono text-xs break-all">{settingsQuery.data?.settings_path ?? "–"}</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 font-medium text-muted-foreground">Config folder</td>
                <td className="py-2 font-mono text-xs break-all">{settingsQuery.data?.config_dir ?? "–"}</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 font-medium text-muted-foreground">Cache folder</td>
                <td className="py-2 font-mono text-xs break-all">{settingsQuery.data?.cache_dir ?? "–"}</td>
              </tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* ── LOGGING ─────────────────────────────────────────────── */}
      <Card id="s-logging">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ScrollText className="h-4 w-4 text-primary" />Logging</CardTitle>
          <CardDescription>Log file rotation and retention settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <TextField label="Max size (MB)" value={str(d["logging.max_size_mb"])} onChange={(v) => set("logging.max_size_mb", Number(v))}
              tooltip="Maximum log file size in MB before rotation triggers" type="number" />
            <TextField label="Max backups" value={str(d["logging.max_backups"])} onChange={(v) => set("logging.max_backups", Number(v))}
              tooltip="Number of rotated log files kept on disk" type="number" />
            <TextField label="Retention (days)" value={str(d["logging.retention_days"])} onChange={(v) => set("logging.retention_days", Number(v))}
              tooltip="Days to keep old log files before automatic deletion" type="number" />
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="Compress old logs" checked={bool(d["logging.compress_old_logs"], true)} onChange={(v) => set("logging.compress_old_logs", v)}
              tooltip="Gzip-compress rotated log files to save disk space" />
            <BoolField label="Cleanup on startup" checked={bool(d["logging.cleanup_on_startup"], true)} onChange={(v) => set("logging.cleanup_on_startup", v)}
              tooltip="Run log rotation/cleanup automatically when Framekit starts" />
          </div>
          <SaveBtn section="logging" keys={["logging.max_size_mb", "logging.max_backups", "logging.compress_old_logs", "logging.retention_days", "logging.cleanup_on_startup"]} />
        </CardContent>
      </Card>

      {/* ── TOOLS ───────────────────────────────────────────────── */}
      <Card id="s-tools">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Wrench className="h-4 w-4 text-primary" />External Tools</CardTitle>
          <CardDescription>Paths to required binaries. Leave empty to use system PATH.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="mkvmerge" value={str(d["tools.mkvmerge"])} onChange={(v) => set("tools.mkvmerge", v)}
              tooltip="Path to the mkvmerge binary used by cleanmkv and extract modules" placeholder="mkvmerge" />
            <TextField label="ffmpeg" value={str(d["tools.ffmpeg"])} onChange={(v) => set("tools.ffmpeg", v)}
              tooltip="Path to the ffmpeg binary used by encode and screenshot modules" placeholder="ffmpeg" />
            <TextField label="ffprobe" value={str(d["tools.ffprobe"])} onChange={(v) => set("tools.ffprobe", v)}
              tooltip="Path to ffprobe — used for media stream analysis" placeholder="ffprobe" />
            <TextField label="mediainfo" value={str(d["tools.mediainfo"])} onChange={(v) => set("tools.mediainfo", v)}
              tooltip="Path to the mediainfo binary — used for detailed track inspection" placeholder="mediainfo" />
          </div>
          <SaveBtn section="tools" keys={["tools.mkvmerge", "tools.ffmpeg", "tools.ffprobe", "tools.mediainfo"]} />
          <div className="border-t border-border pt-3 space-y-2">
            <Button type="button" variant="outline" size="sm" onClick={() => { setToolsCheckResult(null); toolsCheckMutation.mutate(); }} disabled={toolsCheckMutation.isPending}>
              {toolsCheckMutation.isPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Play className="mr-1.5 h-3.5 w-3.5" />}
              {toolsCheckMutation.isPending ? "Checking…" : "Check dependencies"}
            </Button>
            {toolsCheckResult ? (
              <div className="divide-y divide-border rounded-md border border-border text-xs">
                {toolsCheckResult.tools.map((t) => (
                  <div key={t.name} className="flex items-center gap-2 px-3 py-1.5">
                    {t.ok ? (
                      <Check className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    ) : (
                      <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0" />
                    )}
                    <span className="font-mono font-semibold w-20 shrink-0">{t.name}</span>
                    <span className="text-muted-foreground truncate">{t.ok ? t.path : "Not found"}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* ── METADATA ────────────────────────────────────────────── */}
      <Card id="s-metadata">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Database className="h-4 w-4 text-primary" />Metadata</CardTitle>
          <CardDescription>Providers and language configuration for title lookups.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="Primary provider" value={str(d["metadata.provider"], "tmdb")} onChange={(v) => set("metadata.provider", v)}
              tooltip="First metadata source queried when resolving titles (TMDB recommended)"
              options={[{ value: "tmdb", label: "TMDB" }, { value: "tvdb", label: "TVDB" }, { value: "anilist", label: "AniList" }, { value: "trakt", label: "Trakt" }]} />
            <TextField label="Metadata language" value={str(d["metadata.language"], "en-US")} onChange={(v) => set("metadata.language", v)}
              tooltip="BCP-47 language tag sent to metadata APIs (e.g. en-US, fr-FR)" placeholder="en-US" />
            <TextField label="Cache TTL (hours)" value={str(d["metadata.cache_ttl_hours"])} onChange={(v) => set("metadata.cache_ttl_hours", Number(v))}
              tooltip="How long metadata responses are cached locally before re-fetching" type="number" />
            {str(d["metadata.provider"]) === "anilist" ? (
              <SelectField label="AniList language" value={str(d["metadata.anilist_language"], "en")} onChange={(v) => set("metadata.anilist_language", v)}
                tooltip="Preferred title language when fetching from AniList"
                options={[{ value: "en", label: "English" }, { value: "romaji", label: "Romaji" }, { value: "native", label: "Native" }]} />
            ) : null}
            {str(d["metadata.provider"]) === "tvdb" ? (
              <SelectField label="TVDB language" value={str(d["metadata.tvdb_language"], "eng")} onChange={(v) => set("metadata.tvdb_language", v)}
                tooltip="3-letter ISO-639-2 language code for TVDB responses"
                options={[
                  { value: "eng", label: "English" }, { value: "fra", label: "French" }, { value: "deu", label: "German" },
                  { value: "spa", label: "Spanish" }, { value: "ita", label: "Italian" }, { value: "jpn", label: "Japanese" },
                  { value: "kor", label: "Korean" }, { value: "por", label: "Portuguese" }, { value: "zho", label: "Chinese" },
                  { value: "rus", label: "Russian" }, { value: "pol", label: "Polish" }, { value: "nld", label: "Dutch" },
                ]} />
            ) : null}
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="Interactive confirmation" checked={bool(d["metadata.interactive_confirmation"], true)} onChange={(v) => set("metadata.interactive_confirmation", v)}
              tooltip="Prompt before writing resolved metadata to files" />
            <BoolField label="Enabled by default" checked={bool(d["metadata.enabled_by_default"], true)} onChange={(v) => set("metadata.enabled_by_default", v)}
              tooltip="Enable metadata resolution in pipeline by default" />
            <BoolField label="Prompt for missing token" checked={bool(d["metadata.prompt_missing_token_in_pipeline"], true)} onChange={(v) => set("metadata.prompt_missing_token_in_pipeline", v)}
              tooltip="Ask for API credentials interactively when a required token is absent during pipeline run" />
            {str(d["metadata.provider"]) !== "anilist" ? (
              <BoolField label="AniList fallback" checked={bool(d["metadata.anilist_enabled"], true)} onChange={(v) => set("metadata.anilist_enabled", v)}
                tooltip="Allow AniList as a fallback provider for anime titles when the primary provider finds no result" />
            ) : null}
          </div>
          <SaveBtn section="metadata" keys={["metadata.provider", "metadata.language", "metadata.cache_ttl_hours", "metadata.interactive_confirmation", "metadata.enabled_by_default", "metadata.prompt_missing_token_in_pipeline", "metadata.anilist_enabled", "metadata.anilist_language", "metadata.tvdb_language"]} />
          {/* Provider API tokens */}
          <div className="border-t border-border pt-3 space-y-3">
            <p className="text-sm font-medium">API Tokens</p>
            {([
              ["TMDB", "eyJhbGciOi…", tmdbTokenQuery.data as ProviderToken | undefined, tmdbInput, setTmdbInput, setTmdbMutation, "Read access token from TMDB. Stored encrypted in the vault when security is enabled."],
              ["TVDB", "your-tvdb-api-key", tvdbTokenQuery.data as ProviderToken | undefined, tvdbInput, setTvdbInput, saveTvdbTokenMutation, "TVDB API key. Required when TVDB is selected as primary provider."],
              ["AniList", "your-anilist-token", anilistTokenQuery.data as ProviderToken | undefined, anilistInput, setAnilistInput, saveAnilistTokenMutation, "AniList client token. Required for AniList provider or fallback lookups."],
              ["Trakt", "your-trakt-token", traktTokenQuery.data as ProviderToken | undefined, traktInput, setTraktInput, saveTraktTokenMutation, "Trakt API access token. Required when Trakt is selected as primary provider."],
            ] as const).map(([label, placeholder, qdata, inputVal, setInput, mutation, tooltip]) => (
              <div key={label} className="space-y-1.5">
                <p className="text-sm flex items-center gap-1.5">
                  <span className="font-medium w-16 shrink-0">{label}</span>
                  <InfoTooltip text={tooltip} />
                  {qdata?.is_set ? <Badge variant="success" className="text-xs">Set{qdata.encrypted ? " (encrypted)" : ""}</Badge> : <Badge variant="secondary" className="text-xs">Not set</Badge>}
                </p>
                {qdata?.error ? <p className="text-xs text-destructive">{qdata.error}</p> : null}
                {qdata?.is_set && qdata.token ? (
                  <div className="flex items-center gap-2 font-mono text-xs bg-muted rounded px-2 py-1.5 break-all">
                    <span className="flex-1 text-muted-foreground break-all">
                      {tokenReveal[label] ? qdata.token : "•".repeat(Math.min(qdata.token.length, 24))}
                    </span>
                    <button
                      type="button"
                      onClick={() => setTokenReveal((prev) => ({ ...prev, [label]: !prev[label] }))}
                      className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {tokenReveal[label] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                ) : null}
                <div className="flex gap-2">
                  <Input type="password" value={inputVal} onChange={(e) => setInput(e.target.value)} placeholder={placeholder} className="flex-1" />
                  <Button type="button" size="sm" onClick={() => mutation.mutate(inputVal)} disabled={!inputVal.trim() || mutation.isPending}>Save</Button>
                </div>
                {mutation.isSuccess ? <p className="text-xs text-emerald-600 dark:text-emerald-400">Token saved.</p> : null}
                {mutation.isError ? <p className="text-xs text-destructive">{String((mutation.error as Error)?.message ?? "Failed")}</p> : null}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── UPLOAD ──────────────────────────────────────────────── */}
      <Card id="s-upload">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Upload className="h-4 w-4 text-primary" />Upload</CardTitle>
          <CardDescription>Tracker upload and torrent client settings. <Link to="/upload" className="text-primary underline">Open Upload →</Link></CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="Max parallel uploads" value={str(d["upload.max_parallel_uploads"])} onChange={(v) => set("upload.max_parallel_uploads", Number(v))}
              tooltip="Maximum number of simultaneous tracker upload connections" type="number" />
            <SelectField label="Image host" value={str(d["upload.image_host"])} onChange={(v) => set("upload.image_host", v)}
              tooltip="Screenshot hosting service used when generating upload presentations"
              options={[{ value: "", label: "None" }, { value: "imgbb", label: "ImgBB" }, { value: "imgbox", label: "Imgbox" }, { value: "ptpimg", label: "PTPImg" }, { value: "freeimage", label: "Freeimage" }]} />
            <SelectField label="Torrent client" value={str(d["upload.torrent_client"])} onChange={(v) => set("upload.torrent_client", v)}
              tooltip="Torrent client integration for automatic seeding after upload"
              options={[{ value: "", label: "Disabled" }, { value: "qbittorrent", label: "qBittorrent" }]} />
            <TextField label="Host" value={str(d["upload.torrent_client_host"], "localhost")} onChange={(v) => set("upload.torrent_client_host", v)}
              tooltip="Hostname or IP of the torrent client Web UI" placeholder="localhost" />
            <TextField label="Port" value={str(d["upload.torrent_client_port"])} onChange={(v) => set("upload.torrent_client_port", Number(v))}
              tooltip="Port of the torrent client Web UI" type="number" />
            <TextField label="Category" value={str(d["upload.torrent_client_category"], "framekit")} onChange={(v) => set("upload.torrent_client_category", v)}
              tooltip="Category/label applied to torrents added by Framekit (comma-separated for multiple)" placeholder="framekit, movies" />
            <TextField label="Tag" value={str(d["upload.torrent_client_tag"])} onChange={(v) => set("upload.torrent_client_tag", v)}
              tooltip="Tag added to torrents in the client (e.g. 'framekit')" placeholder="framekit" />
            <TextField label="Username" value={str(d["upload.torrent_client_username"])} onChange={(v) => set("upload.torrent_client_username", v)}
              tooltip="Username for the torrent client Web UI" placeholder="admin" />
            <div className="space-y-1">
              <FieldLabel label="Password" tooltip="Password for the torrent client Web UI" />
              <div className="flex items-center gap-2 mb-1">
                {torrentPwdQuery.data?.is_set
                  ? <Badge variant="success" className="text-xs">{torrentPwdQuery.data.encrypted ? "Set (encrypted)" : "Set"}</Badge>
                  : <Badge variant="secondary" className="text-xs">Not set</Badge>}
              </div>
              <div className="flex gap-2">
                <Input type="password" value={torrentPwdInput} onChange={(e) => setTorrentPwdInput(e.target.value)}
                  placeholder="Enter new password…" className="flex-1" />
                <Button type="button" size="sm"
                  onClick={() => saveTorrentPwdMutation.mutate(torrentPwdInput)}
                  disabled={!torrentPwdInput.trim() || saveTorrentPwdMutation.isPending}>Save</Button>
              </div>
              {saveTorrentPwdMutation.isError
                ? <p className="text-xs text-destructive">{String((saveTorrentPwdMutation.error as Error)?.message ?? "Failed")}</p>
                : null}
            </div>
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="Upload enabled" checked={bool(d["upload.enabled"])} onChange={(v) => set("upload.enabled", v)}
              tooltip="Enable the upload module globally — must be true to push releases to trackers" />
            <BoolField label="Auto-upload" checked={bool(d["upload.auto_upload"])} onChange={(v) => set("upload.auto_upload", v)}
              tooltip="Automatically trigger upload after a successful pipeline run" />
          </div>
          <SaveBtn section="upload" keys={["upload.enabled", "upload.auto_upload", "upload.max_parallel_uploads", "upload.image_host", "upload.torrent_client", "upload.torrent_client_host", "upload.torrent_client_port", "upload.torrent_client_category", "upload.torrent_client_tag", "upload.torrent_client_username"]} />
          {/* Image host API keys */}
          <div className="border-t border-border pt-3 space-y-3">
            <p className="text-sm font-medium">Image Host API Keys</p>
            {([
              ["ImgBB", imgbbKeyQuery.data, imgbbKeyInput, setImgbbKeyInput, saveImgbbKey],
              ["Imgbox", imgboxKeyQuery.data, imgboxKeyInput, setImgboxKeyInput, saveImgboxKey],
              ["PTPImg", ptpimgKeyQuery.data, ptpimgKeyInput, setPtpimgKeyInput, savePtpimgKey],
              ["FreeImage", freeimageKeyQuery.data, freeimageKeyInput, setFreeimageKeyInput, saveFreeimageKey],
            ] as const).map(([label, queryData, inputVal, setInput, mutation]) => (
              <div key={label} className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="w-24 text-sm text-muted-foreground shrink-0">{label}</span>
                  {queryData?.is_set ? <Badge variant="success" className="text-xs">Set</Badge> : <Badge variant="secondary" className="text-xs">Not set</Badge>}
                </div>
                <div className="flex gap-2">
                  <Input type="password" value={inputVal} onChange={(e) => setInput(e.target.value)} placeholder="Paste API key…" className="flex-1" />
                  <Button type="button" size="sm" onClick={() => mutation.mutate(inputVal)} disabled={!inputVal.trim() || mutation.isPending}>Save</Button>
                </div>
                {mutation.isError ? <p className="text-xs text-destructive">{String((mutation.error as Error)?.message ?? "Failed")}</p> : null}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── SEEDBOX ─────────────────────────────────────────────── */}
      <Card id="s-seedbox">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Server className="h-4 w-4 text-primary" />Seedbox</CardTitle>
          <CardDescription>Rclone-based remote transfer settings. <Link to="/seedbox" className="text-primary underline">Manage profiles →</Link></CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="Max concurrent transfers" value={str(d["seedbox.max_concurrent_uploads"])} onChange={(v) => set("seedbox.max_concurrent_uploads", Number(v))}
              tooltip="Maximum simultaneous file transfers when pushing to seedbox" type="number" />
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="History enabled" checked={bool(d["seedbox.history_enabled"], true)} onChange={(v) => set("seedbox.history_enabled", v)}
              tooltip="Record all seedbox transfers to the local history database" />
          </div>
          <SaveBtn section="seedbox" keys={["seedbox.max_concurrent_uploads", "seedbox.history_enabled"]} />
          {/* Seedbox profiles */}
          <div className="border-t border-border pt-3 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Profiles</p>
              <Button type="button" variant="outline" size="sm" onClick={() => setNewSeedboxAddOpen((v) => !v)}>
                {newSeedboxAddOpen ? <X className="h-3.5 w-3.5 mr-1" /> : <Plus className="h-3.5 w-3.5 mr-1" />}
                {newSeedboxAddOpen ? "Cancel" : "Add profile"}
              </Button>
            </div>
            {newSeedboxAddOpen && (
              <div className="rounded-md border border-border p-3 space-y-2">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1">
                    <FieldLabel label="Name" />
                    <Input className="h-8 text-sm" placeholder="my-seedbox" value={newSeedboxName} onChange={(e) => setNewSeedboxName(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <FieldLabel label="Rclone remote" tooltip="Rclone remote name configured in rclone.conf (e.g. myseedbox:)" />
                    <Input className="h-8 text-sm font-mono" placeholder="remote:" value={newSeedboxRemote} onChange={(e) => setNewSeedboxRemote(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <FieldLabel label="Remote base path" tooltip="Destination folder on the remote (e.g. /data/torrents)" />
                    <Input className="h-8 text-sm font-mono" placeholder="/path/on/remote" value={newSeedboxPath} onChange={(e) => setNewSeedboxPath(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <FieldLabel label="Bandwidth limit" tooltip="Optional rclone bandwidth cap (e.g. 10M, 0 = unlimited)" />
                    <Input className="h-8 text-sm font-mono" placeholder="0" value={newSeedboxBandwidth} onChange={(e) => setNewSeedboxBandwidth(e.target.value)} />
                  </div>
                </div>
                <Button type="button" size="sm"
                  disabled={!newSeedboxName.trim() || !newSeedboxRemote.trim() || !newSeedboxPath.trim() || addSeedboxMutation.isPending}
                  onClick={() => addSeedboxMutation.mutate({ name: newSeedboxName.trim(), rclone_remote: newSeedboxRemote.trim(), remote_base_path: newSeedboxPath.trim(), bandwidth_limit: newSeedboxBandwidth.trim() || "0", set_default: (seedboxesQuery.data?.seedboxes ?? []).length === 0 })}>
                  <Check className="mr-1.5 h-3.5 w-3.5" />Save profile
                </Button>
                {addSeedboxMutation.isError ? <p className="text-xs text-destructive">{String((addSeedboxMutation.error as Error)?.message ?? "Failed")}</p> : null}
              </div>
            )}
            {(seedboxesQuery.data?.seedboxes ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No profiles configured.</p>
            ) : (
              <div className="divide-y divide-border rounded-md border border-border">
                {(seedboxesQuery.data?.seedboxes ?? []).map((sb) => (
                  <div key={sb.name} className="flex items-center gap-2 px-3 py-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{sb.name}</p>
                      <p className="text-xs text-muted-foreground font-mono truncate">{sb.rclone_remote}</p>
                    </div>
                    {sb.is_default ? (
                      <Badge variant="success" className="shrink-0 text-xs">Default</Badge>
                    ) : (
                      <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 px-2 text-xs"
                        onClick={() => useSeedboxMutation.mutate(sb.name)}
                        disabled={useSeedboxMutation.isPending}>
                        Set default
                      </Button>
                    )}
                    <Button type="button" variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive hover:text-destructive shrink-0"
                      onClick={() => removeSeedboxMutation.mutate(sb.name)}
                      disabled={removeSeedboxMutation.isPending}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            {useSeedboxMutation.isError ? <p className="text-xs text-destructive mt-1">{String((useSeedboxMutation.error as Error)?.message ?? "Failed")}</p> : null}
            {removeSeedboxMutation.isError ? <p className="text-xs text-destructive mt-1">{String((removeSeedboxMutation.error as Error)?.message ?? "Failed")}</p> : null}
          </div>
        </CardContent>
      </Card>

      {/* ── WATCH ───────────────────────────────────────────────── */}
      <Card id="s-watch">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Settings className="h-4 w-4 text-primary" />Watch</CardTitle>
          <CardDescription>Filesystem watcher that auto-triggers workflows on new files.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* ── Watch session ─────────────────────────────────────── */}
          <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <Activity className="h-4 w-4 text-primary shrink-0" />
              <span className="text-sm font-medium">Watch session</span>
              {watchServiceQuery.data ? (
                <Badge variant={watchServiceQuery.data.status === "running" ? "success" : "secondary"}>
                  {watchServiceQuery.data.status === "running"
                    ? `Active (PID ${watchServiceQuery.data.pid ?? "?"})`
                    : "Inactive"}
                </Badge>
              ) : (
                <Badge variant="secondary">Unknown</Badge>
              )}
              <div className="flex gap-2 ml-auto">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={startWatchMutation.isPending || watchServiceQuery.data?.status === "running"}
                  onClick={() => startWatchMutation.mutate()}
                >
                  <Play className="mr-1.5 h-3.5 w-3.5" />
                  Start session
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={stopWatchMutation.isPending || watchServiceQuery.data?.status === "stopped"}
                  onClick={() => stopWatchMutation.mutate()}
                >
                  <Square className="mr-1.5 h-3.5 w-3.5" />
                  Stop session
                </Button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Web UI watch sessions are temporary — managed by the web server process, max 2 hours. For 24/7 watching use <code className="font-mono">framekit watch start</code> from the CLI.
            </p>
            {startWatchMutation.error ? (
              <p className="text-xs text-destructive">
                {startWatchMutation.error instanceof Error ? startWatchMutation.error.message : "Failed to start watch session."}
              </p>
            ) : null}
            {stopWatchMutation.isSuccess && !stopWatchMutation.data?.stopped ? (
              <p className="text-xs text-muted-foreground">
                No active session found — may have already stopped, or was started from a different directory.
              </p>
            ) : null}
            {stopWatchMutation.error ? (
              <p className="text-xs text-destructive">
                {stopWatchMutation.error instanceof Error ? stopWatchMutation.error.message : "Failed to stop watch session."}
              </p>
            ) : null}
          </div>
          {watchJobId !== null ? (
            <InlineJobPanel
              jobId={watchJobId}
              moduleName="watch"
              onRerun={(newJob: ModuleJob) => setWatchJobId(newJob.id)}
            />
          ) : null}

          <BoolField label="Watcher enabled" checked={bool(d["watch.enabled"])} onChange={(v) => set("watch.enabled", v)}
            tooltip="Enable the background filesystem watcher — monitors configured folders and triggers pipeline on new releases" />
          <div className="grid gap-3 sm:grid-cols-2">
            <BoolField label="Notifications enabled" checked={bool(d["watch.notifications.enabled"], true)} onChange={(v) => set("watch.notifications.enabled", v)}
              tooltip="Send OS desktop notifications for watch mode events" />
            <BoolField label="Notify on start" checked={bool(d["watch.notifications.on_start"])} onChange={(v) => set("watch.notifications.on_start", v)}
              tooltip="Send notification when a new release starts processing" />
            <BoolField label="Notify on success" checked={bool(d["watch.notifications.on_success"])} onChange={(v) => set("watch.notifications.on_success", v)}
              tooltip="Send notification when a release finishes successfully" />
            <BoolField label="Notify on error" checked={bool(d["watch.notifications.on_error"], true)} onChange={(v) => set("watch.notifications.on_error", v)}
              tooltip="Send notification when a release fails" />
            <BoolField label="Notify watch started" checked={bool(d["watch.notifications.on_watch_started"], true)} onChange={(v) => set("watch.notifications.on_watch_started", v)}
              tooltip="Send notification when watch mode starts or stops" />
          </div>
          <SaveBtn section="watch" keys={["watch.enabled", "watch.notifications.enabled", "watch.notifications.on_start", "watch.notifications.on_success", "watch.notifications.on_error", "watch.notifications.on_watch_started"]} />

          <div className="border-t border-border pt-3 space-y-3">
            <p className="text-sm font-medium flex items-center gap-2"><FolderOpen className="h-4 w-4 text-primary" />Watch Folders</p>
            {(watchFoldersQuery.data?.folders ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No folders configured. Add one below.</p>
            ) : (
              <div className="divide-y divide-border rounded-md border border-border">
                {(watchFoldersQuery.data?.folders ?? []).map((folder, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2">
                    <span className="flex-1 min-w-0 font-mono text-xs break-all">{folder.path}</span>
                    <Badge variant="secondary" className="shrink-0 text-xs">{folder.preset}</Badge>
                    {folder.enabled ? null : <Badge variant="secondary" className="shrink-0 text-xs text-amber-600">disabled</Badge>}
                    <Button type="button" variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive hover:text-destructive shrink-0"
                      onClick={() => removeWatchFolderMutation.mutate(i)}
                      disabled={removeWatchFolderMutation.isPending}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Input
                className="flex-1 min-w-48 font-mono text-sm"
                placeholder="/path/to/watch/folder"
                value={newWatchPath}
                onChange={(e) => setNewWatchPath(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && newWatchPath.trim()) addWatchFolderMutation.mutate({ path: newWatchPath.trim(), preset: newWatchPreset }); }}
              />
              <Input
                className="w-32 text-sm"
                placeholder="preset"
                value={newWatchPreset}
                onChange={(e) => setNewWatchPreset(e.target.value)}
              />
              <Button type="button" size="sm"
                onClick={() => addWatchFolderMutation.mutate({ path: newWatchPath.trim(), preset: newWatchPreset })}
                disabled={!newWatchPath.trim() || addWatchFolderMutation.isPending}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />Add
              </Button>
            </div>
            {addWatchFolderMutation.isError ? (
              <p className="text-xs text-destructive">{String((addWatchFolderMutation.error as Error)?.message ?? "Failed")}</p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* ── PIPELINE ────────────────────────────────────────────── */}
      <Card id="s-pipeline">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ServerCog className="h-4 w-4 text-primary" />Pipeline</CardTitle>
          <CardDescription>Full workflow execution settings for the pipeline module.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="Upload timeout (s)" value={str(d["modules.pipeline.upload_timeout"])} onChange={(v) => set("modules.pipeline.upload_timeout", Number(v))}
              tooltip="Seconds to wait for upload completion before the pipeline aborts" type="number" />
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="Stop on error" checked={bool(d["modules.pipeline.stop_on_error"])} onChange={(v) => set("modules.pipeline.stop_on_error", v)}
              tooltip="Abort the entire pipeline if any module step fails" />
            <BoolField label="With metadata" checked={bool(d["modules.pipeline.with_metadata"], true)} onChange={(v) => set("modules.pipeline.with_metadata", v)}
              tooltip="Run metadata resolution as part of pipeline by default" />
            <BoolField label="Auto mode" checked={bool(d["modules.pipeline.auto_mode"])} onChange={(v) => set("modules.pipeline.auto_mode", v)}
              tooltip="Run pipeline without interactive prompts — requires all modules to support non-interactive mode" />
            <BoolField label="Upload on failure" checked={bool(d["modules.pipeline.upload_on_failure"])} onChange={(v) => set("modules.pipeline.upload_on_failure", v)}
              tooltip="Attempt upload even if some pipeline steps failed" />
          </div>
          <SaveBtn section="pipeline" keys={["modules.pipeline.stop_on_error", "modules.pipeline.with_metadata", "modules.pipeline.auto_mode", "modules.pipeline.upload_on_failure", "modules.pipeline.upload_timeout"]} />
          {/* Default modules */}
          <div className="border-t border-border pt-3 space-y-2">
            <p className="text-sm font-medium flex items-center gap-1.5">
              Default modules
              <InfoTooltip text="Modules enabled by default in every pipeline run. You can override per-run from the Pipeline page." />
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {(["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez", "encode", "screenshot", "seedbox", "upload", "rename-parent"] as const).map((mod) => {
                const enabledMods: string[] = Array.isArray(d["modules.pipeline.enabled_modules"])
                  ? (d["modules.pipeline.enabled_modules"] as string[])
                  : ["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"];
                const isOn = enabledMods.includes(mod);
                const toggle = () => {
                  const next = isOn ? enabledMods.filter((m) => m !== mod) : [...enabledMods, mod];
                  set("modules.pipeline.enabled_modules", next);
                };
                const tooltips: Record<string, string> = {
                  renamer: "Normalize release folder and file names",
                  cleanmkv: "Strip unwanted MKV tracks (audio/subtitle)",
                  metadata: "Resolve title metadata from external APIs",
                  nfo: "Generate NFO description file",
                  torrent: "Create .torrent file for the release",
                  prez: "Generate release presentation (BBCode/HTML)",
                  encode: "Encode video with optimized h264/h265 presets",
                  screenshot: "Capture screenshots from video files",
                  seedbox: "Transfer release to configured seedbox remote",
                  upload: "Upload release to tracker APIs",
                  "rename-parent": "Rename parent release folder from metadata",
                };
                return (
                  <BoolField key={mod} label={mod} checked={isOn} onChange={toggle} tooltip={tooltips[mod] ?? mod} />
                );
              })}
            </div>
            <SaveBtn section="pipeline-modules" keys={["modules.pipeline.enabled_modules"]} />
          </div>
          <div className="pt-1 flex items-center gap-4">
            <Link to="/presets" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
              <Plus className="h-3.5 w-3.5" />
              Manage pipeline presets
            </Link>
            <Link to="/presets" hash="p-pipeline" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
              <Plus className="h-3.5 w-3.5" />
              Create pipeline preset
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* ── NFO ─────────────────────────────────────────────────── */}
      <Card id="s-nfo">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />NFO</CardTitle>
          <CardDescription>NFO file generation settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="NFO locale" value={str(d["modules.nfo.locale"], "auto")} onChange={(v) => set("modules.nfo.locale", v)}
              tooltip="Language for NFO file content — 'auto' uses the general UI locale"
              options={[{ value: "auto", label: "Auto (follow UI locale)" }, { value: "en", label: "English" }, { value: "fr", label: "French" }, { value: "es", label: "Spanish" }]} />
            <SelectField label="Active template" value={str(d["modules.nfo.active_template"], "default")} onChange={(v) => set("modules.nfo.active_template", v)}
              tooltip="NFO template style — 'Default' is concise, 'Detailed' includes full track and metadata breakdown"
              options={NFO_TEMPLATE_OPTIONS} />
            <SelectField label="Generation mode" value={str(d["modules.nfo.mode"], "global")} onChange={(v) => set("modules.nfo.mode", v)}
              tooltip="'global' generates one NFO per release folder; 'per-file' generates one per media file; 'both' generates both"
              options={[{ value: "global", label: "Global (one per folder)" }, { value: "per-file", label: "Per-file" }, { value: "both", label: "Both" }]} />
          </div>
          <BoolField label="With metadata" checked={bool(d["modules.nfo.with_metadata"], true)} onChange={(v) => set("modules.nfo.with_metadata", v)}
            tooltip="Embed API-resolved metadata (title, year, overview) in the NFO file" />
          <SaveBtn section="nfo" keys={["modules.nfo.locale", "modules.nfo.active_template", "modules.nfo.with_metadata", "modules.nfo.mode"]} />
        </CardContent>
      </Card>

      {/* ── TORRENT ─────────────────────────────────────────────── */}
      <Card id="s-torrent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />Torrent</CardTitle>
          <CardDescription>Torrent file creation settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="Piece length" value={str(d["modules.torrent.piece_length"], "auto")} onChange={(v) => set("modules.torrent.piece_length", v)}
              tooltip="Torrent piece size — 'auto' picks optimal size based on total release size"
              options={[{ value: "auto", label: "Auto" }, { value: "512KB", label: "512 KB" }, { value: "1MB", label: "1 MB" }, { value: "2MB", label: "2 MB" }, { value: "4MB", label: "4 MB" }, { value: "8MB", label: "8 MB" }]} />
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="Private torrent" checked={bool(d["modules.torrent.private"], true)} onChange={(v) => set("modules.torrent.private", v)}
              tooltip="Set the private flag in the torrent — disables DHT and PEX, required by most private trackers" />
            <BoolField label="Prompt save announce" checked={bool(d["modules.torrent.prompt_save_announce"], true)} onChange={(v) => set("modules.torrent.prompt_save_announce", v)}
              tooltip="Ask before saving a new announce URL to the settings file" />
          </div>
          <SaveBtn section="torrent" keys={["modules.torrent.private", "modules.torrent.piece_length", "modules.torrent.prompt_save_announce"]} />
          {/* Announce URL management */}
          <div className="border-t border-border pt-3 space-y-2">
            <p className="text-sm font-medium">Announce URLs</p>
            {(announcesQuery.data?.announces ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No announce URLs saved. Add one below.</p>
            ) : (
              <div className="divide-y divide-border rounded-md border border-border">
                {(announcesQuery.data?.announces ?? []).map((item, i) => (
                  <div key={i} className="flex flex-col gap-0.5 px-3 py-2">
                    <div className="flex items-center gap-2">
                      {/* label or truncated URL */}
                      {announceEditIdx === i ? (
                        <input
                          autoFocus
                          className="flex-1 h-7 rounded border border-input bg-background px-2 font-mono text-xs"
                          value={announceEditLabel}
                          onChange={(e) => setAnnounceEditLabel(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") renameAnnounceMutation.mutate({ index: i, label: announceEditLabel });
                            if (e.key === "Escape") { setAnnounceEditIdx(null); setAnnounceEditLabel(""); }
                          }}
                          placeholder="Display label…"
                        />
                      ) : (
                        <span className="flex-1 text-xs font-medium truncate">
                          {item.label || item.value.replace(/\/[^/]+$/, "/…")}
                        </span>
                      )}
                      {/* eye toggle */}
                      <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0"
                        onClick={() => setAnnounceReveal((prev) => ({ ...prev, [i]: !prev[i] }))}>
                        {announceReveal[i] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      </Button>
                      {/* rename edit */}
                      {announceEditIdx === i ? (
                        <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0"
                          onClick={() => renameAnnounceMutation.mutate({ index: i, label: announceEditLabel })}
                          disabled={renameAnnounceMutation.isPending}>
                          <Check className="h-3.5 w-3.5 text-emerald-600" />
                        </Button>
                      ) : (
                        <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0"
                          onClick={() => { setAnnounceEditIdx(i); setAnnounceEditLabel(item.label ?? ""); }}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      {item.is_selected ? <Badge variant="default" className="shrink-0 text-xs">Active</Badge> : (
                        <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 px-2 text-xs"
                          onClick={() => selectAnnounceMutation.mutate(item.value)}
                          disabled={selectAnnounceMutation.isPending}>
                          <Check className="h-3 w-3 mr-1" />Use
                        </Button>
                      )}
                      <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0 text-destructive hover:text-destructive"
                        onClick={() => removeAnnounceMutation.mutate(i)}
                        disabled={removeAnnounceMutation.isPending}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    {/* revealed URL */}
                    {announceReveal[i] ? (
                      <span className="font-mono text-xs text-muted-foreground break-all">{item.value}</span>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
            {removeAnnounceMutation.isError ? <p className="text-xs text-destructive">{String((removeAnnounceMutation.error as Error)?.message ?? "Failed")}</p> : null}
            {selectAnnounceMutation.isError ? <p className="text-xs text-destructive">{String((selectAnnounceMutation.error as Error)?.message ?? "Failed")}</p> : null}
            {renameAnnounceMutation.isError ? <p className="text-xs text-destructive">{String((renameAnnounceMutation.error as Error)?.message ?? "Failed")}</p> : null}
            <div className="flex gap-2">
              <Input value={newAnnounceUrl} onChange={(e) => setNewAnnounceUrl(e.target.value)}
                placeholder="https://tracker.example.com/…/announce" className="flex-1 font-mono text-xs" />
              <Button type="button" size="sm" onClick={() => addAnnounceMutation.mutate(newAnnounceUrl)}
                disabled={!newAnnounceUrl.trim() || addAnnounceMutation.isPending}>
                <Plus className="h-3.5 w-3.5 mr-1" />Add
              </Button>
            </div>
            {addAnnounceMutation.isError ? <p className="text-xs text-destructive">{String((addAnnounceMutation.error as Error)?.message ?? "Failed")}</p> : null}
          </div>
        </CardContent>
      </Card>

      {/* ── PREZ ────────────────────────────────────────────────── */}
      <Card id="s-prez">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />Presentation (Prez)</CardTitle>
          <CardDescription>Release presentation generation settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="Output format" value={str(d["modules.prez.format"], "both")} onChange={(v) => set("modules.prez.format", v)}
              tooltip="Which output formats to generate — BBCode for forums, HTML for web, or both"
              options={[{ value: "both", label: "Both (BBCode + HTML)" }, { value: "bbcode", label: "BBCode only" }, { value: "html", label: "HTML only" }, { value: "mediainfo", label: "MediaInfo only" }]} />
            <SelectField label="Prez locale" value={str(d["modules.prez.locale"], "auto")} onChange={(v) => set("modules.prez.locale", v)}
              tooltip="Language for presentation content — 'auto' uses the general UI locale"
              options={[{ value: "auto", label: "Auto" }, { value: "en", label: "English" }, { value: "fr", label: "French" }, { value: "es", label: "Spanish" }]} />
            <SelectField label="HTML template" value={str(d["modules.prez.html_template"], "")} onChange={(v) => set("modules.prez.html_template", v)}
              tooltip="HTML presentation template — loaded from your config/prez/html/ directory"
              options={htmlTemplates.length > 0 ? htmlTemplates : [{ value: str(d["modules.prez.html_template"], "aurora"), label: str(d["modules.prez.html_template"], "aurora") }]} />
            <SelectField label="BBCode template" value={str(d["modules.prez.bbcode_template"], "")} onChange={(v) => set("modules.prez.bbcode_template", v)}
              tooltip="BBCode presentation template — loaded from your config/prez/bbcode/ directory"
              options={bbcodeTemplates.length > 0 ? bbcodeTemplates : [{ value: str(d["modules.prez.bbcode_template"], "classic"), label: str(d["modules.prez.bbcode_template"], "classic") }]} />
            <SelectField label="Mediainfo mode" value={str(d["modules.prez.mediainfo_mode"], "none")} onChange={(v) => set("modules.prez.mediainfo_mode", v)}
              tooltip="Controls how raw mediainfo output is embedded in the presentation"
              options={[{ value: "none", label: "None" }, { value: "spoiler", label: "Spoiler" }, { value: "only", label: "Only (mediainfo alone)" }]} />
          </div>
          <div className="flex flex-wrap gap-4">
            <BoolField label="Include mediainfo" checked={bool(d["modules.prez.include_mediainfo"])} onChange={(v) => set("modules.prez.include_mediainfo", v)}
              tooltip="Append full mediainfo block to the presentation output" />
            <BoolField label="With metadata" checked={bool(d["modules.prez.with_metadata"], true)} onChange={(v) => set("modules.prez.with_metadata", v)}
              tooltip="Use API-resolved metadata (title, year, synopsis) in presentation" />
          </div>
          <SaveBtn section="prez" keys={["modules.prez.locale", "modules.prez.format", "modules.prez.html_template", "modules.prez.bbcode_template", "modules.prez.mediainfo_mode", "modules.prez.include_mediainfo", "modules.prez.with_metadata"]} />
        </CardContent>
      </Card>

      {/* ── CLEANMKV ────────────────────────────────────────────── */}
      <Card id="s-cleanmkv">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />CleanMKV</CardTitle>
          <CardDescription>MKV track cleaning and remux settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="Default preset" value={str(d["modules.cleanmkv.default_preset"], "multi")} onChange={(v) => set("modules.cleanmkv.default_preset", v)}
              tooltip="CleanMKV track-selection preset applied when no --preset flag is given"
              options={cleanmkvPresets.length > 0 ? cleanmkvPresets : [{ value: str(d["modules.cleanmkv.default_preset"], "multi"), label: str(d["modules.cleanmkv.default_preset"], "multi") }]} />
            <div className="space-y-1">
              <FieldLabel label="Output dir name" tooltip="Subdirectory name for cleaned output — supports {release} placeholder" />
              <div className="h-9 flex items-center rounded-md border border-border bg-muted px-3 font-mono text-xs text-muted-foreground">
                {str(d["modules.cleanmkv.output_dir_name"]) || "Release/{release}"}
              </div>
              <details open={cleanmkvOverride} onToggle={(e) => setCleanmkvOverride((e.currentTarget as HTMLDetailsElement).open)} className="text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground py-1 select-none">Override…</summary>
                <input
                  className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 font-mono text-xs"
                  value={str(d["modules.cleanmkv.output_dir_name"])}
                  onChange={(e) => set("modules.cleanmkv.output_dir_name", e.target.value)}
                  placeholder="Release/{release}"
                />
              </details>
            </div>
          </div>
          <BoolField label="Copy unchanged files" checked={bool(d["modules.cleanmkv.copy_unchanged_files"], true)} onChange={(v) => set("modules.cleanmkv.copy_unchanged_files", v)}
            tooltip="Copy files that don't require any cleaning instead of skipping them" />
          <SaveBtn section="cleanmkv" keys={["modules.cleanmkv.default_preset", "modules.cleanmkv.output_dir_name", "modules.cleanmkv.copy_unchanged_files"]} />
          <div className="pt-1">
            <Link to="/presets" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
              <Plus className="h-3.5 w-3.5" />Create CleanMKV preset
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* ── RENAMER ─────────────────────────────────────────────── */}
      <Card id="s-renamer">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />Renamer</CardTitle>
          <CardDescription>File and folder naming normalization settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <TextField label="Default language tag" value={str(d["modules.renamer.default_language_tag"], "MULTI.VFF")} onChange={(v) => set("modules.renamer.default_language_tag", v)}
              tooltip="Audio language tag appended to renamed outputs when language cannot be auto-detected" placeholder="MULTI.VFF" />
            <SelectField label="Active profile" value={str(d["modules.renamer.profile"])} onChange={(v) => set("modules.renamer.profile", v)}
              tooltip="Renamer behavior profile to apply"
              options={[{ value: "", label: "— Default —" }, ...(renamerProfiles.length > 0 ? renamerProfiles : [])]} />
          </div>
          <SaveBtn section="renamer" keys={["modules.renamer.default_language_tag", "modules.renamer.profile"]} />
          <div className="pt-1">
            <Link to="/presets" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
              <SlidersHorizontal className="h-3.5 w-3.5" />Renamer rules
            </Link>
          </div>
        </CardContent>
      </Card>

      {/* ── SCREENSHOT ──────────────────────────────────────────── */}
      <Card id="s-screenshot">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />Screenshot</CardTitle>
          <CardDescription>Screenshot capture settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <SelectField label="Screenshot target" value={str(d["modules.screenshot.target"], "prez")} onChange={(v) => set("modules.screenshot.target", v)}
            tooltip="Where captured screenshots are written — 'prez' puts them alongside presentation files"
            options={[{ value: "prez", label: "Prez folder" }, { value: "release", label: "Release folder" }]} />
          <SaveBtn section="screenshot" keys={["modules.screenshot.target"]} />
        </CardContent>
      </Card>

      {/* ── ENCODER ─────────────────────────────────────────────── */}
      <Card id="s-encoder">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />Encoder</CardTitle>
          <CardDescription>Local video encoding settings.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            <SelectField label="Active preset" value={str(d["modules.encoder.preset"])} onChange={(v) => set("modules.encoder.preset", v)}
              tooltip="Encode preset to use — must exist in config/encode/"
              options={[
  { value: "", label: "None" },
  ...(resourcesQuery.data?.encoder_presets ?? []).map((p) => ({
    value: p,
    label: p.replace(/_/g, " "),
  })),
]} />
            <TextField label="Output dir name" value={str(d["modules.encoder.output_dir_name"], "encoded")} onChange={(v) => set("modules.encoder.output_dir_name", v)}
              tooltip="Subdirectory name for encoded output files" placeholder="encoded" />
          </div>
          <SaveBtn section="encoder" keys={["modules.encoder.preset", "modules.encoder.output_dir_name"]} />
        </CardContent>
      </Card>

      {/* ── CONNECTED SERVICES ──────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ServerCog className="h-4 w-4 text-primary" />Connected Services</CardTitle>
          <CardDescription>Overview of seedbox and tracker configuration.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-md border border-border p-3 text-sm">
            <p className="font-medium">Seedbox</p>
            <p className="text-muted-foreground">Profiles: {(seedboxesQuery.data?.seedboxes ?? []).length}</p>
            <p className="text-muted-foreground">Default: {defaultSeedbox}</p>
            <Link to="/seedbox" className="mt-2 inline-block text-primary underline">Open Seedbox</Link>
          </div>
          <div className="rounded-md border border-border p-3 text-sm">
            <p className="font-medium">Upload</p>
            <p className="text-muted-foreground">Trackers: {(trackersQuery.data?.trackers ?? []).length}</p>
            <p className="text-muted-foreground">Active: {(trackersQuery.data?.trackers ?? []).filter((t) => t.enabled).length}</p>
            <Link to="/upload" className="mt-2 inline-block text-primary underline">Open Upload</Link>
          </div>
        </CardContent>
      </Card>

      {/* ── SECURITY ────────────────────────────────────────────── */}
      <Card id="s-security">
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Shield className="h-4 w-4 text-primary" />Security &amp; Vault</CardTitle>
          <CardDescription>Encrypted storage status for sensitive settings (TMDB token, announce URLs).</CardDescription>
        </CardHeader>
        <CardContent>
          {vaultQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Loading vault status…</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-4 text-sm">
              <div className="rounded-md border border-border p-3">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Vault enabled</p>
                <Badge variant={vaultQuery.data?.enabled ? "success" : "secondary"}>{vaultQuery.data?.enabled ? "Yes" : "No"}</Badge>
              </div>
              <div className="rounded-md border border-border p-3">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Vault file</p>
                <Badge variant={vaultQuery.data?.vault_exists ? "success" : "secondary"}>{vaultQuery.data?.vault_exists ? "Exists" : "Missing"}</Badge>
              </div>
              <div className="rounded-md border border-border p-3">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Master key</p>
                <Badge variant={vaultQuery.data?.key_exists ? "success" : "secondary"}>{vaultQuery.data?.key_exists ? "Found" : "Missing"}</Badge>
              </div>
              <div className="rounded-md border border-border p-3">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">Stored entries</p>
                <p className="font-semibold">{vaultQuery.data?.entry_count ?? 0}</p>
              </div>
            </div>
          )}
          {vaultQuery.data?.error ? (
            <p className="mt-2 text-xs text-destructive">{vaultQuery.data.error}</p>
          ) : null}
        </CardContent>
      </Card>

      {/* ── RAW CONFIG ──────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Cog className="h-4 w-4 text-primary" />Raw Configuration</CardTitle>
          <CardDescription>Read-only view of the full settings file.</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted p-3 text-xs">
            {settingsQuery.data ? JSON.stringify(settingsQuery.data.settings, null, 2) : "Loading…"}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}
