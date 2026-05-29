import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { BookOpen, Check, ChevronDown, ChevronRight, Eye, EyeOff, FileText, Key, Layers, Pencil, Plus, Shield, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { Input } from "@/components/ui/input";
import { addTorrentAnnounce, createPreset, deleteAllPresets, deletePreset, getModulesResources, getProviderToken, getTmdbToken, removeTorrentAnnounce, renameAnnounce, selectTorrentAnnounce } from "@/lib/api/endpoints";

function Section({
  id,
  title,
  icon: Icon,
  tooltip,
  children,
  defaultOpen = true,
}: {
  id?: string;
  title: string;
  icon: React.ElementType;
  tooltip?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card id={id}>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={() => setOpen((v) => !v)}
      >
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Icon className="h-4 w-4 text-primary" />
          {title}
          {tooltip ? <InfoTooltip text={tooltip} /> : null}
          <span className="ml-auto text-muted-foreground">
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </span>
        </CardTitle>
      </CardHeader>
      {open ? <CardContent>{children}</CardContent> : null}
    </Card>
  );
}

export function PresetsPage() {
  const resourcesQuery = useQuery({ queryKey: ["modules-resources"], queryFn: getModulesResources });

  const resources = resourcesQuery.data;
  const isLoading = resourcesQuery.isLoading;
  const isError = resourcesQuery.isError;

  const placeholder = isLoading ? "Loading…" : "—";

  const [newPresetKind, setNewPresetKind] = useState<"pipeline" | "cleanmkv" | "prez">("pipeline");
  const [newPresetName, setNewPresetName] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [showYamlPreview, setShowYamlPreview] = useState(false);

  const [pipelineCfg, setPipelineCfg] = useState({
    displayName: "",
    description: "",
    modules: ["renamer", "cleanmkv", "nfo", "torrent", "prez"] as string[],
    cleanmkvPreset: "",
    nfoTemplate: "detailed",
    nfoLocale: "fr",
    nfoMode: "global" as "global" | "per_file" | "both",
    nfoAutoMeta: true,
    torrentPrivate: true,
    prezFormat: "both",
    prezBbcode: "detailed",
    prezHtml: "magazine_dark",
  });

  const [cleanmkvCfg, setCleanmkvCfg] = useState({
    displayName: "",
    keepAudioLangs: "french",
    keepSubLangs: "french",
    audioLang: "french",
    subLang: "french",
    audioExplicit: true,
    subExplicit: true,
  });

  const [prezCfg, setPrezCfg] = useState({
    displayName: "",
    format: "both",
    bbcode: "detailed",
    html: "magazine_dark",
    mediainfoMode: "none" as "none" | "spoiler" | "only",
    detailLevel: "detailed",
    showTmdb: true,
    showMediainfo: true,
  });

  function generatePresetYaml(): string {
    const slug = newPresetName.trim().replace(/[^\w-]/g, "_").toLowerCase();
    if (!slug) return "";

    if (newPresetKind === "pipeline") {
      const lines: string[] = [
        `${slug}:`,
        `  name: "${pipelineCfg.displayName || slug}"`,
      ];
      if (pipelineCfg.description) lines.push(`  description: "${pipelineCfg.description}"`);
      lines.push(`  modules:`);
      for (const m of pipelineCfg.modules) lines.push(`    - "${m}"`);
      if (pipelineCfg.modules.includes("renamer")) {
        lines.push(`  renamer:`, `    auto_detect: true`);
      }
      if (pipelineCfg.modules.includes("cleanmkv")) {
        lines.push(`  cleanmkv:`);
        if (pipelineCfg.cleanmkvPreset) lines.push(`    external_preset: "${pipelineCfg.cleanmkvPreset}"`);
        lines.push(`    apply_changes: true`);
      }
      if (pipelineCfg.modules.includes("nfo")) {
        lines.push(`  nfo:`, `    template: "${pipelineCfg.nfoTemplate}"`, `    locale: "${pipelineCfg.nfoLocale}"`, `    mode: "${pipelineCfg.nfoMode}"`, `    auto_metadata: ${pipelineCfg.nfoAutoMeta}`);
      }
      if (pipelineCfg.modules.includes("torrent")) {
        lines.push(`  torrent:`, `    private: ${pipelineCfg.torrentPrivate}`);
      }
      if (pipelineCfg.modules.includes("prez")) {
        lines.push(`  prez:`, `    format: "${pipelineCfg.prezFormat}"`, `    bbcode_template: "${pipelineCfg.prezBbcode}"`, `    html_template: "${pipelineCfg.prezHtml}"`);
      }
      return lines.join("\n");
    }

    if (newPresetKind === "cleanmkv") {
      const audioList = cleanmkvCfg.keepAudioLangs.split(",").map((s) => s.trim()).filter(Boolean);
      const subList = cleanmkvCfg.keepSubLangs.split(",").map((s) => s.trim()).filter(Boolean);
      const fmtList = (items: string[]) => items.length ? `[${items.map((l) => `"${l}"`).join(", ")}]` : "[]";
      return [
        `${slug}:`,
        `  name: "${cleanmkvCfg.displayName || slug}"`,
        `  keep_audio_filters: ${fmtList(audioList)}`,
        `  default_audio_filter: "${cleanmkvCfg.audioLang}"`,
        `  keep_subtitle_filters: ${fmtList(subList)}`,
        `  keep_subtitle_variants: []`,
        `  default_subtitle_filter: "${cleanmkvCfg.subLang}"`,
        `  default_subtitle_variant: null`,
        `  audio_default_explicit: ${cleanmkvCfg.audioExplicit}`,
        `  subtitle_default_explicit: ${cleanmkvCfg.subExplicit}`,
      ].join("\n");
    }

    if (newPresetKind === "prez") {
      return [
        `${slug}:`,
        `  name: "${prezCfg.displayName || slug}"`,
        `  format: "${prezCfg.format}"`,
        `  bbcode_template: "${prezCfg.bbcode}"`,
        `  html_template: "${prezCfg.html}"`,
        `  mediainfo_mode: "${prezCfg.mediainfoMode}"`,
        `  detail_level: "${prezCfg.detailLevel}"`,
        `  show_tmdb: "${prezCfg.showTmdb}"`,
        `  show_mediainfo: "${prezCfg.showMediainfo}"`,
      ].join("\n");
    }

    return "";
  }

  const deleteMutation = useMutation({
    mutationFn: ({ kind, name }: { kind: string; name: string }) => deletePreset(kind, name),
    onSuccess: () => void resourcesQuery.refetch(),
  });
  const createMutation = useMutation({
    mutationFn: () => createPreset(newPresetKind, newPresetName, generatePresetYaml()),
    onSuccess: () => {
      void resourcesQuery.refetch();
      setNewPresetName("");
      setCreateOpen(false);
    },
  });

  const deleteAllPipelineMutation = useMutation({
    mutationFn: () => deleteAllPresets("pipeline"),
    onSuccess: () => void resourcesQuery.refetch(),
  });
  const deleteAllPrezMutation = useMutation({
    mutationFn: () => deleteAllPresets("prez"),
    onSuccess: () => void resourcesQuery.refetch(),
  });

  const [confirmDeleteAll, setConfirmDeleteAll] = useState<"pipeline" | "prez" | null>(null);

  const [announceReveal, setAnnounceReveal] = useState<Record<string, boolean>>({});
  const [announceEditIdx, setAnnounceEditIdx] = useState<string | null>(null);
  const [announceEditLabel, setAnnounceEditLabel] = useState("");
  const [newAnnounceUrl, setNewAnnounceUrl] = useState("");
  const renameAnnounceMutation = useMutation({
    mutationFn: ({ index, label }: { index: number; label: string }) => renameAnnounce(index, label),
    onSuccess: () => { void resourcesQuery.refetch(); setAnnounceEditIdx(null); setAnnounceEditLabel(""); },
  });
  const addAnnounceMutation = useMutation({
    mutationFn: (url: string) => addTorrentAnnounce(url),
    onSuccess: () => { void resourcesQuery.refetch(); setNewAnnounceUrl(""); },
  });
  const removeAnnounceMutation = useMutation({
    mutationFn: (index: number) => removeTorrentAnnounce(index),
    onSuccess: () => void resourcesQuery.refetch(),
  });
  const selectAnnounceMutation = useMutation({
    mutationFn: (url: string) => selectTorrentAnnounce(url),
    onSuccess: () => void resourcesQuery.refetch(),
  });

  const tmdbTokenQuery = useQuery({ queryKey: ["tmdb-token"], queryFn: getTmdbToken });
  const tvdbTokenQuery = useQuery({ queryKey: ["provider-token-tvdb"], queryFn: () => getProviderToken("tvdb") });
  const anilistTokenQuery = useQuery({ queryKey: ["provider-token-anilist"], queryFn: () => getProviderToken("anilist") });
  const traktTokenQuery = useQuery({ queryKey: ["provider-token-trakt"], queryFn: () => getProviderToken("trakt") });
  const configuredTokenCount = [
    tmdbTokenQuery.data?.is_set,
    tvdbTokenQuery.data?.is_set,
    anilistTokenQuery.data?.is_set,
    traktTokenQuery.data?.is_set,
  ].filter(Boolean).length;
  const totalPresetCount =
    (resources?.pipeline_presets.length ?? 0) +
    (resources?.prez_presets.length ?? 0) +
    (resources?.cleanmkv_presets?.length ?? 0) +
    (resources?.renamer_profiles?.length ?? 0);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Presets &amp; Profiles</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Browse available presets, templates, and profiles for all modules.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/settings-setup"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Open Settings
            </Link>
            <Link
              to="/pipeline"
              className="inline-flex items-center rounded-md border border-border bg-transparent px-3 py-1.5 text-xs font-medium hover:border-primary/40 hover:bg-secondary/55"
            >
              Run Pipeline
            </Link>
          </div>
        </div>
      </section>

      {isError ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          Failed to load resources — is the API running?
        </p>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Preset Inventory</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{totalPresetCount}</p>
            <p className="text-xs text-muted-foreground">Pipeline + Prez + CleanMKV + Renamer</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Tracker Announces</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{resources?.announces.length ?? 0}</p>
            <p className="text-xs text-muted-foreground">
              Active: {resources?.announces.filter((item) => item.is_selected).length ?? 0}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Token Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{configuredTokenCount}/4</p>
            <p className="text-xs text-muted-foreground">TMDB, TVDB, AniList, Trakt</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Template Catalog</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">
              {(resources?.nfo_templates.length ?? 0) + (resources?.prez_templates.bbcode.length ?? 0) + (resources?.prez_templates.html.length ?? 0)}
            </p>
            <p className="text-xs text-muted-foreground">NFO + BBCode + HTML templates</p>
          </CardContent>
        </Card>
      </section>

      {/* Pipeline Presets */}
      <Section
        id="p-pipeline"
        title="Pipeline Presets"
        icon={Layers}
        tooltip="YAML preset files that define which modules run and their options. Stored in config/pipeline/"
        defaultOpen={false}
      >
        {!resources ? (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        ) : resources.pipeline_presets.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No pipeline presets found. Create YAML files in your config/pipeline/ folder.
          </p>
        ) : (
          <>
            <div className="divide-y divide-border">
              {resources.pipeline_presets.map((p) => (
                <div key={p.name} className="flex items-center justify-between py-2 gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.source}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="secondary" className="font-mono text-xs hidden sm:flex">{p.path}</Badge>
                    <Button type="button" variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      onClick={() => deleteMutation.mutate({ kind: "pipeline", name: p.name })}
                      disabled={deleteMutation.isPending && deleteMutation.variables?.name === p.name}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-border pt-3 flex items-center gap-3 flex-wrap">
              {confirmDeleteAll === "pipeline" ? (
                <>
                  <span className="text-sm text-destructive font-medium">Delete all pipeline presets?</span>
                  <Button type="button" size="sm" variant="destructive"
                    onClick={() => { deleteAllPipelineMutation.mutate(); setConfirmDeleteAll(null); }}
                    disabled={deleteAllPipelineMutation.isPending}>
                    Yes, delete all
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => setConfirmDeleteAll(null)}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button type="button" variant="outline" size="sm" className="text-destructive border-destructive/40 hover:bg-destructive/10"
                  onClick={() => setConfirmDeleteAll("pipeline")}
                  disabled={resources.pipeline_presets.length === 0}>
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" />Reset to factory
                </Button>
              )}
              {deleteAllPipelineMutation.isSuccess ? <span className="text-xs text-muted-foreground">Deleted {deleteAllPipelineMutation.data.count} preset{deleteAllPipelineMutation.data.count !== 1 ? "s" : ""}.</span> : null}
            </div>
          </>
        )}
      </Section>

      {/* Prez Presets */}
      <Section
        id="p-prez"
        title="Prez Presets"
        icon={FileText}
        tooltip="YAML preset files for presentation generation, stored in config/prez/"
        defaultOpen={false}
      >
        {!resources ? (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        ) : resources.prez_presets.length === 0 ? (
          <p className="text-sm text-muted-foreground">No prez presets found.</p>
        ) : (
          <>
            <div className="divide-y divide-border">
              {resources.prez_presets.map((p) => (
                <div key={p.name} className="flex items-center justify-between py-2 gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.source}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="secondary" className="font-mono text-xs hidden sm:flex">{p.path}</Badge>
                    <Button type="button" variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                      onClick={() => deleteMutation.mutate({ kind: "prez", name: p.name })}
                      disabled={deleteMutation.isPending && deleteMutation.variables?.name === p.name}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 border-t border-border pt-3 flex items-center gap-3 flex-wrap">
              {confirmDeleteAll === "prez" ? (
                <>
                  <span className="text-sm text-destructive font-medium">Delete all prez presets?</span>
                  <Button type="button" size="sm" variant="destructive"
                    onClick={() => { deleteAllPrezMutation.mutate(); setConfirmDeleteAll(null); }}
                    disabled={deleteAllPrezMutation.isPending}>
                    Yes, delete all
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => setConfirmDeleteAll(null)}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button type="button" variant="outline" size="sm" className="text-destructive border-destructive/40 hover:bg-destructive/10"
                  onClick={() => setConfirmDeleteAll("prez")}
                  disabled={resources.prez_presets.length === 0}>
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" />Reset to factory
                </Button>
              )}
              {deleteAllPrezMutation.isSuccess ? <span className="text-xs text-muted-foreground">Deleted {deleteAllPrezMutation.data.count} preset{deleteAllPrezMutation.data.count !== 1 ? "s" : ""}.</span> : null}
            </div>
          </>
        )}
      </Section>

      {/* NFO Templates */}
      <Section
        id="p-nfo"
        title="NFO Templates"
        icon={FileText}
        tooltip="Available NFO template files. Set the active template in Settings → NFO."
        defaultOpen={false}
      >
        {!resources ? (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        ) : resources.nfo_templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No NFO templates found.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {resources.nfo_templates.map((t) => (
              <Badge key={t} variant="secondary">{t}</Badge>
            ))}
          </div>
        )}
      </Section>

      {/* Prez Templates */}
      <Section
        id="p-prez-templates"
        title="Prez Templates"
        icon={FileText}
        tooltip="HTML and BBCode presentation templates. Set the active ones in Settings → Prez."
        defaultOpen={false}
      >
        {!resources ? (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">HTML</p>
              {(resources.prez_templates.html ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">No HTML templates.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {(resources.prez_templates.html ?? []).map((t) => (
                    <Badge key={t} variant="secondary">{t}</Badge>
                  ))}
                </div>
              )}
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">BBCode</p>
              {(resources.prez_templates.bbcode ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">No BBCode templates.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {(resources.prez_templates.bbcode ?? []).map((t) => (
                    <Badge key={t} variant="secondary">{t}</Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Section>

      {/* Banner Previews */}
      {resources && resources.banner_previews.length > 0 ? (
        <Section title="Banner Previews" icon={BookOpen} tooltip="Available banner image templates for release presentations" defaultOpen={false}>
          <div className="flex flex-wrap gap-2">
            {resources.banner_previews.map((b) => (
              <a
                key={b.name}
                href={b.preview_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium transition-colors hover:border-primary/40 hover:bg-secondary"
              >
                {b.name}
              </a>
            ))}
          </div>
        </Section>
      ) : null}

      {/* CleanMKV Presets */}
      <Section
        id="p-cleanmkv"
        title="CleanMKV Presets"
        icon={Layers}
        tooltip="Available built-in and user-defined CleanMKV track-selection presets."
        defaultOpen={false}
      >
        {!resources ? (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        ) : (resources.cleanmkv_presets ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No presets found.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {(resources.cleanmkv_presets ?? []).map((name) => (
              <Badge key={name} variant="secondary">{name}</Badge>
            ))}
          </div>
        )}
      </Section>

      {/* Renamer Profiles */}
      <Section
        id="p-renamer"
        title="Renamer Profiles"
        icon={FileText}
        tooltip="Available built-in and user-defined renamer behavior profiles."
        defaultOpen={false}
      >
        {!resources ? (
          <p className="text-sm text-muted-foreground">{placeholder}</p>
        ) : (resources.renamer_profiles ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No profiles found.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {(resources.renamer_profiles ?? []).map((name) => (
              <Badge key={name} variant="secondary">{name}</Badge>
            ))}
          </div>
        )}
      </Section>

      {/* Saved Announce URLs */}
      <Section
        id="p-announces"
        title="Saved Announce URLs"
        icon={FileText}
        tooltip="Tracker announce URLs stored in your vault. Encrypted at rest."
        defaultOpen={false}
      >
        {resources && resources.announces.length > 0 && (
          <div className="divide-y divide-border rounded-md border border-border mb-3">
            {resources.announces.map((a, i) => (
              <div key={a.value} className="flex flex-col gap-0.5 px-3 py-2">
                <div className="flex items-center gap-2">
                  {announceEditIdx === a.value ? (
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
                      {a.label || a.value.replace(/\/[^/]+$/, "/…")}
                    </span>
                  )}
                  <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0"
                    onClick={() => setAnnounceReveal((prev) => ({ ...prev, [a.value]: !prev[a.value] }))}>
                    {announceReveal[a.value] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </Button>
                  {announceEditIdx === a.value ? (
                    <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0"
                      onClick={() => renameAnnounceMutation.mutate({ index: i, label: announceEditLabel })}
                      disabled={renameAnnounceMutation.isPending}>
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                    </Button>
                  ) : (
                    <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0"
                      onClick={() => { setAnnounceEditIdx(a.value); setAnnounceEditLabel(a.label ?? ""); }}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {a.is_selected ? (
                    <Badge variant="default" className="text-xs shrink-0">Active</Badge>
                  ) : (
                    <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 px-2 text-xs"
                      onClick={() => selectAnnounceMutation.mutate(a.value)}
                      disabled={selectAnnounceMutation.isPending}>
                      Use
                    </Button>
                  )}
                  <Button type="button" variant="ghost" size="sm" className="shrink-0 h-7 w-7 p-0 text-destructive hover:text-destructive"
                    onClick={() => removeAnnounceMutation.mutate(i)}
                    disabled={removeAnnounceMutation.isPending}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
                {announceReveal[a.value] ? (
                  <span className="font-mono text-xs text-muted-foreground break-all">{a.value}</span>
                ) : null}
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-center">
          <Input
            className="flex-1 font-mono text-xs h-8"
            value={newAnnounceUrl}
            onChange={(e) => setNewAnnounceUrl(e.target.value)}
            placeholder="https://tracker.example.com/announce/…"
            onKeyDown={(e) => { if (e.key === "Enter" && newAnnounceUrl.trim()) addAnnounceMutation.mutate(newAnnounceUrl.trim()); }}
          />
          <Button type="button" size="sm" onClick={() => addAnnounceMutation.mutate(newAnnounceUrl.trim())}
            disabled={!newAnnounceUrl.trim() || addAnnounceMutation.isPending}>
            <Plus className="mr-1 h-3.5 w-3.5" />Add
          </Button>
        </div>
        {addAnnounceMutation.isError && (
          <p className="mt-1 text-xs text-destructive">{String((addAnnounceMutation.error as Error)?.message ?? "Failed")}</p>
        )}
      </Section>
      {/* API Tokens */}
      <Section
        id="p-tokens"
        title="API Tokens"
        icon={Key}
        tooltip="Status of metadata provider API tokens. Set values in Settings → Metadata."
        defaultOpen={false}
      >
        <div className="divide-y divide-border rounded-md border border-border">
          {([
            ["TMDB", tmdbTokenQuery.data?.is_set, tmdbTokenQuery.data?.encrypted],
            ["TVDB", tvdbTokenQuery.data?.is_set, tvdbTokenQuery.data?.encrypted],
            ["AniList", anilistTokenQuery.data?.is_set, anilistTokenQuery.data?.encrypted],
            ["Trakt", traktTokenQuery.data?.is_set, traktTokenQuery.data?.encrypted],
          ] as const).map(([label, isSet, encrypted]) => (
            <div key={label} className="flex items-center gap-3 px-3 py-2">
              <span className="w-16 text-sm font-medium shrink-0">{label}</span>
              {isSet ? (
                <Badge variant="success" className="text-xs">{encrypted ? "Set (encrypted)" : "Set"}</Badge>
              ) : (
                <Badge variant="secondary" className="text-xs">Not set</Badge>
              )}
            </div>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Manage tokens in <a href="/settings#s-metadata" className="text-primary underline">Settings → Metadata</a>.</p>
      </Section>

      {/* Renamer Rules */}
      <Section
        id="p-renamer-rules"
        title="Renamer Rules"
        icon={Shield}
        tooltip="Custom renaming rules and regex patterns. Edit rule files directly in your config/renamer/ directory."
        defaultOpen={false}
      >
        <p className="text-sm text-muted-foreground">Renamer rule files are managed via the CLI or by editing YAML files in <code className="font-mono text-xs bg-muted px-1 rounded">config/renamer/</code> directly.</p>
      </Section>

      {/* Preset Creator */}
      <Card>
        <CardHeader
          className="cursor-pointer select-none"
          onClick={() => setCreateOpen((v) => !v)}
        >
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <Plus className="h-4 w-4 text-primary" />
            Preset Creator
            <span className="ml-auto text-muted-foreground">
              {createOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </span>
          </CardTitle>
        </CardHeader>
        {createOpen && (
          <CardContent className="space-y-4">
            {/* type + name row */}
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="font-medium">Module type</span>
                <select
                  className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                  value={newPresetKind}
                  onChange={(e) => setNewPresetKind(e.target.value as "pipeline" | "cleanmkv" | "prez")}
                >
                  <option value="pipeline">Pipeline</option>
                  <option value="cleanmkv">CleanMKV</option>
                  <option value="prez">Prez</option>
                </select>
              </label>
              <label className="space-y-1 text-sm">
                <span className="font-medium">Preset name (slug)</span>
                <Input value={newPresetName} onChange={(e) => setNewPresetName(e.target.value)} placeholder="my_preset" />
              </label>
            </div>

            {/* ── Pipeline form ── */}
            {newPresetKind === "pipeline" && (
              <div className="space-y-4 rounded-md border border-border p-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Display name</span>
                    <Input value={pipelineCfg.displayName} onChange={(e) => setPipelineCfg(c => ({ ...c, displayName: e.target.value }))} placeholder="My Preset" />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Description</span>
                    <Input value={pipelineCfg.description} onChange={(e) => setPipelineCfg(c => ({ ...c, description: e.target.value }))} placeholder="Optional description" />
                  </label>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Enabled steps</p>
                  <div className="flex flex-wrap gap-4">
                    {["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"].map((m) => (
                      <label key={m} className="flex items-center gap-1.5 text-sm cursor-pointer">
                        <input
                          type="checkbox"
                          className="accent-primary"
                          checked={pipelineCfg.modules.includes(m)}
                          onChange={(e) => setPipelineCfg(c => ({
                            ...c,
                            modules: e.target.checked ? [...c.modules, m] : c.modules.filter(x => x !== m),
                          }))}
                        />
                        <span className="capitalize">{m}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {pipelineCfg.modules.includes("cleanmkv") && (
                  <div className="space-y-1">
                    <p className="text-sm font-medium">CleanMKV</p>
                    <label className="space-y-1 text-sm block w-64">
                      <span className="text-xs text-muted-foreground">External preset name</span>
                      <Input value={pipelineCfg.cleanmkvPreset} onChange={(e) => setPipelineCfg(c => ({ ...c, cleanmkvPreset: e.target.value }))} placeholder="multi_fr" />
                    </label>
                  </div>
                )}

                {pipelineCfg.modules.includes("nfo") && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">NFO</p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <label className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">Template</span>
                        <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={pipelineCfg.nfoTemplate} onChange={(e) => setPipelineCfg(c => ({ ...c, nfoTemplate: e.target.value }))}>
                          <option value="detailed">detailed</option>
                          <option value="compact">compact</option>
                        </select>
                      </label>
                      <label className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">Locale</span>
                        <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={pipelineCfg.nfoLocale} onChange={(e) => setPipelineCfg(c => ({ ...c, nfoLocale: e.target.value }))}>
                          <option value="auto">auto</option>
                          <option value="fr">fr</option>
                          <option value="en">en</option>
                          <option value="es">es</option>
                        </select>
                      </label>
                      <label className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">Output mode</span>
                        <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={pipelineCfg.nfoMode} onChange={(e) => setPipelineCfg(c => ({ ...c, nfoMode: e.target.value as "global" | "per_file" | "both" }))}>
                          <option value="global">global</option>
                          <option value="per_file">per_file</option>
                          <option value="both">both</option>
                        </select>
                      </label>
                      <label className="flex items-center gap-2 text-sm cursor-pointer pt-5">
                        <input type="checkbox" className="accent-primary" checked={pipelineCfg.nfoAutoMeta} onChange={(e) => setPipelineCfg(c => ({ ...c, nfoAutoMeta: e.target.checked }))} />
                        Auto metadata
                      </label>
                    </div>
                  </div>
                )}

                {pipelineCfg.modules.includes("torrent") && (
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Torrent</p>
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" className="accent-primary" checked={pipelineCfg.torrentPrivate} onChange={(e) => setPipelineCfg(c => ({ ...c, torrentPrivate: e.target.checked }))} />
                      Private torrent
                    </label>
                  </div>
                )}

                {pipelineCfg.modules.includes("prez") && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Prez</p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <label className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">Format</span>
                        <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={pipelineCfg.prezFormat} onChange={(e) => setPipelineCfg(c => ({ ...c, prezFormat: e.target.value }))}>
                          <option value="both">both</option>
                          <option value="bbcode">bbcode</option>
                          <option value="html">html</option>
                        </select>
                      </label>
                      <label className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">BBCode template</span>
                        <Input value={pipelineCfg.prezBbcode} onChange={(e) => setPipelineCfg(c => ({ ...c, prezBbcode: e.target.value }))} placeholder="detailed" />
                      </label>
                      <label className="space-y-1 text-sm">
                        <span className="text-xs text-muted-foreground">HTML template</span>
                        <Input value={pipelineCfg.prezHtml} onChange={(e) => setPipelineCfg(c => ({ ...c, prezHtml: e.target.value }))} placeholder="magazine_dark" />
                      </label>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── CleanMKV form ── */}
            {newPresetKind === "cleanmkv" && (
              <div className="space-y-3 rounded-md border border-border p-3">
                <label className="space-y-1 text-sm block">
                  <span className="font-medium">Display name</span>
                  <Input value={cleanmkvCfg.displayName} onChange={(e) => setCleanmkvCfg(c => ({ ...c, displayName: e.target.value }))} placeholder="My CleanMKV Preset" />
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Audio languages to keep</span>
                    <Input value={cleanmkvCfg.keepAudioLangs} onChange={(e) => setCleanmkvCfg(c => ({ ...c, keepAudioLangs: e.target.value }))} placeholder="french, english" />
                    <span className="text-xs text-muted-foreground">Comma-separated</span>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Subtitle languages to keep</span>
                    <Input value={cleanmkvCfg.keepSubLangs} onChange={(e) => setCleanmkvCfg(c => ({ ...c, keepSubLangs: e.target.value }))} placeholder="french" />
                    <span className="text-xs text-muted-foreground">Comma-separated</span>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Default audio language</span>
                    <Input value={cleanmkvCfg.audioLang} onChange={(e) => setCleanmkvCfg(c => ({ ...c, audioLang: e.target.value }))} placeholder="french" />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Default subtitle language</span>
                    <Input value={cleanmkvCfg.subLang} onChange={(e) => setCleanmkvCfg(c => ({ ...c, subLang: e.target.value }))} placeholder="french" />
                  </label>
                </div>
                <div className="flex gap-6 flex-wrap">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" className="accent-primary" checked={cleanmkvCfg.audioExplicit} onChange={(e) => setCleanmkvCfg(c => ({ ...c, audioExplicit: e.target.checked }))} />
                    Audio default explicit
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" className="accent-primary" checked={cleanmkvCfg.subExplicit} onChange={(e) => setCleanmkvCfg(c => ({ ...c, subExplicit: e.target.checked }))} />
                    Subtitle default explicit
                  </label>
                </div>
              </div>
            )}

            {/* ── Prez form ── */}
            {newPresetKind === "prez" && (
              <div className="space-y-3 rounded-md border border-border p-3">
                <label className="space-y-1 text-sm block">
                  <span className="font-medium">Display name</span>
                  <Input value={prezCfg.displayName} onChange={(e) => setPrezCfg(c => ({ ...c, displayName: e.target.value }))} placeholder="My Prez Preset" />
                </label>
                <div className="grid gap-3 sm:grid-cols-3">
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Format</span>
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={prezCfg.format} onChange={(e) => setPrezCfg(c => ({ ...c, format: e.target.value }))}>
                      <option value="both">both</option>
                      <option value="bbcode">bbcode</option>
                      <option value="html">html</option>
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">BBCode template</span>
                    <Input value={prezCfg.bbcode} onChange={(e) => setPrezCfg(c => ({ ...c, bbcode: e.target.value }))} placeholder="detailed" />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">HTML template</span>
                    <Input value={prezCfg.html} onChange={(e) => setPrezCfg(c => ({ ...c, html: e.target.value }))} placeholder="magazine_dark" />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">Detail level</span>
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={prezCfg.detailLevel} onChange={(e) => setPrezCfg(c => ({ ...c, detailLevel: e.target.value }))}>
                      <option value="detailed">detailed</option>
                      <option value="standard">standard</option>
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="font-medium">MediaInfo mode</span>
                    <select className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm" value={prezCfg.mediainfoMode} onChange={(e) => setPrezCfg(c => ({ ...c, mediainfoMode: e.target.value as "none" | "spoiler" | "only" }))}>
                      <option value="none">none</option>
                      <option value="spoiler">spoiler</option>
                      <option value="only">only</option>
                    </select>
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer pt-5">
                    <input type="checkbox" className="accent-primary" checked={prezCfg.showTmdb} onChange={(e) => setPrezCfg(c => ({ ...c, showTmdb: e.target.checked }))} />
                    Show TMDB
                  </label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer pt-5">
                    <input type="checkbox" className="accent-primary" checked={prezCfg.showMediainfo} onChange={(e) => setPrezCfg(c => ({ ...c, showMediainfo: e.target.checked }))} />
                    Show MediaInfo
                  </label>
                </div>
              </div>
            )}

            {/* YAML preview */}
            {newPresetName.trim() && (
              <div className="space-y-1">
                <button
                  type="button"
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setShowYamlPreview(v => !v)}
                >
                  {showYamlPreview ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  {showYamlPreview ? "Hide" : "Preview"} YAML
                </button>
                {showYamlPreview && (
                  <pre className="overflow-x-auto whitespace-pre rounded-md border border-border bg-muted/50 p-3 font-mono text-xs">
                    {generatePresetYaml()}
                  </pre>
                )}
              </div>
            )}

            {createMutation.isError && (
              <p className="text-xs text-destructive">{String((createMutation.error as Error)?.message ?? "Failed")}</p>
            )}
            <Button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={!newPresetName.trim() || createMutation.isPending}
            >
              <Plus className="mr-2 h-4 w-4" />
              Save preset
            </Button>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
