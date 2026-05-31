import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronRight,
  Copy,
  Disc3,
  ExternalLink,
  Layers,
  Loader2,
  Lock,
  Music,
  Play,
  Plus,
  Settings,
  Subtitles,
  X,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Toggle } from "@/components/ui/toggle";
import {
  createModuleJob,
  getModulesResources,
  getPipelineInspect,
  getPipelinePlan,
} from "@/lib/api/endpoints";
import type {
  InspectFileScan,
  InspectTrack,
  ModuleJob,
  PipelineInspect,
  PipelinePlan,
} from "@/lib/api/schemas";
import { cn } from "@/lib/utils";

// ── constants ─────────────────────────────────────────────────────────────────

const ALL_MODULES = [
  "renamer", "cleanmkv", "metadata", "nfo", "torrent",
  "prez", "encode", "screenshot", "seedbox", "upload", "rename-parent",
] as const;

const DEFAULT_MODULES = ["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"];

const STEP_LABELS: Record<string, string> = {
  path: "Path",
  modules: "Modules",
  renamer: "Renamer",
  cleanmkv: "CleanMKV",
  metadata: "Metadata",
  nfo: "NFO",
  prez: "Prez",
  torrent: "Torrent",
  execute: "Execute",
};

const PIECE_LENGTHS = ["auto", "512K", "1M", "2M"] as const;

// ── types ─────────────────────────────────────────────────────────────────────

type StepId = "path" | "modules" | "renamer" | "cleanmkv" | "metadata" | "nfo" | "prez" | "torrent" | "execute";
type StepStatus = "active" | "done" | "locked";
type NfoDetail = "default" | "detailed";

interface InsertAfterPair { after: string; insert: string }

interface Config {
  path: string;
  modules: string[];
  dryRun: boolean;
  interactive: boolean;

  // Renamer
  removeTerms: string[];
  lang: string;
  forceLang: boolean;
  renamerProfile: string;
  insertAfterPairs: InsertAfterPair[];

  // CleanMKV
  cleanmkvPreset: string;

  // Metadata
  metadataAutoAccept: boolean;

  // NFO
  nfoLocale: "auto" | "en" | "fr" | "es";
  nfoDetail: NfoDetail;
  nfoTemplate: string;
  nfoMode: "global" | "per_file" | "both";
  nfoWithMetadata: boolean;

  // Prez
  prezPreset: string;
  prezFormat: "both" | "bbcode" | "html";
  prezHtmlTemplate: string;
  prezBbcodeTemplate: string;
  prezMediainfoMode: "none" | "spoiler" | "only";

  // Torrent
  announce: string;
  torrentPrivate: boolean;
  torrentPieceLength: string;
}

const INITIAL: Config = {
  path: "",
  modules: [...DEFAULT_MODULES],
  dryRun: true,
  interactive: false,

  removeTerms: [],
  lang: "",
  forceLang: false,
  renamerProfile: "",
  insertAfterPairs: [],

  cleanmkvPreset: "",

  metadataAutoAccept: true,

  nfoLocale: "auto",
  nfoDetail: "default",
  nfoTemplate: "",
  nfoMode: "global",
  nfoWithMetadata: false,

  prezPreset: "",
  prezFormat: "both",
  prezHtmlTemplate: "",
  prezBbcodeTemplate: "",
  prezMediainfoMode: "none",

  announce: "",
  torrentPrivate: true,
  torrentPieceLength: "auto",
};

// ── arg builders ──────────────────────────────────────────────────────────────

function quoteArg(v: string): string {
  const t = v.trim();
  if (!t) return "";
  return /[\s"]/.test(t) ? `"${t.replaceAll('"', '\\"')}"` : t;
}

function buildRenamerArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (cfg.dryRun) { a.push("--dry-run"); } else { a.push("--apply"); }
  if (cfg.renamerProfile) a.push("--profile", quoteArg(cfg.renamerProfile));
  if (cfg.lang) a.push("--lang", quoteArg(cfg.lang));
  if (cfg.forceLang) a.push("--force-lang");
  for (const t of cfg.removeTerms) a.push("--remove-term", quoteArg(t));
  for (const pair of cfg.insertAfterPairs) {
    if (pair.after.trim() && pair.insert.trim()) {
      a.push("--insert-after", quoteArg(pair.after.trim()), quoteArg(pair.insert.trim()));
    }
  }
  a.push("--auto");
  return a.join(" ").trim();
}

function buildCleanmkvArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (!cfg.dryRun) a.push("--apply");
  if (cfg.dryRun) a.push("--dry-run");
  if (cfg.cleanmkvPreset) a.push("--preset", quoteArg(cfg.cleanmkvPreset));
  a.push("--auto");
  return a.join(" ").trim();
}

function buildMetadataArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (cfg.metadataAutoAccept) a.push("--auto-accept");
  return a.join(" ").trim();
}

function buildNfoArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (!cfg.dryRun) a.push("--write");
  if (cfg.nfoTemplate) a.push("--template", quoteArg(cfg.nfoTemplate));
  if (cfg.nfoLocale !== "auto") a.push("--locale", cfg.nfoLocale);
  if (cfg.nfoMode !== "global") a.push("--mode", cfg.nfoMode);
  if (cfg.nfoWithMetadata) { a.push("--with-metadata"); } else { a.push("--no-metadata"); }
  return a.join(" ").trim();
}

function buildPrezArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (cfg.dryRun) a.push("--dry-run");
  if (cfg.prezPreset) a.push("--preset", quoteArg(cfg.prezPreset));
  if (cfg.prezFormat !== "both") a.push("--format", cfg.prezFormat);
  const showHtml = cfg.prezFormat === "html" || cfg.prezFormat === "both";
  const showBb = cfg.prezFormat === "bbcode" || cfg.prezFormat === "both";
  if (cfg.prezHtmlTemplate && showHtml) a.push("--html-template", quoteArg(cfg.prezHtmlTemplate));
  if (cfg.prezBbcodeTemplate && showBb) a.push("--bbcode-template", quoteArg(cfg.prezBbcodeTemplate));
  if (cfg.prezMediainfoMode !== "none") a.push("--mediainfo-mode", cfg.prezMediainfoMode);
  return a.join(" ").trim();
}

function buildTorrentArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (cfg.dryRun) a.push("--dry-run");
  if (cfg.announce) a.push("--announce", quoteArg(cfg.announce));
  a.push(cfg.torrentPrivate ? "--private" : "--public");
  if (cfg.torrentPieceLength && cfg.torrentPieceLength !== "auto") {
    a.push("--piece-length", cfg.torrentPieceLength);
  }
  return a.join(" ").trim();
}

function buildPipelineArgs(cfg: Config): string {
  const a: string[] = [];
  const p = quoteArg(cfg.path);
  if (p) a.push(p);
  if (cfg.nfoLocale !== "auto") a.push("--nfo-locale", cfg.nfoLocale);
  if (cfg.announce) a.push("--announce", quoteArg(cfg.announce));
  if (cfg.prezPreset) a.push("--preset", quoteArg(cfg.prezPreset));
  if (cfg.dryRun) a.push("--dry-run");
  if (!cfg.interactive) a.push("--auto");
  for (const t of cfg.removeTerms) a.push("--remove-term", quoteArg(t));
  for (const m of cfg.modules) a.push("--modules", m);
  return a.join(" ").trim();
}

// maps StepId → { module name, args builder }
const STEP_MODULE_MAP: Partial<Record<StepId, { mod: string; buildArgs: (c: Config) => string }>> = {
  renamer: { mod: "renamer", buildArgs: buildRenamerArgs },
  cleanmkv: { mod: "cleanmkv", buildArgs: buildCleanmkvArgs },
  metadata: { mod: "metadata", buildArgs: buildMetadataArgs },
  nfo: { mod: "nfo", buildArgs: buildNfoArgs },
  prez: { mod: "prez", buildArgs: buildPrezArgs },
  torrent: { mod: "torrent", buildArgs: buildTorrentArgs },
};

// ── helpers ───────────────────────────────────────────────────────────────────

function activeSteps(modules: string[]): StepId[] {
  const s: StepId[] = ["path", "modules"];
  if (modules.includes("renamer")) s.push("renamer");
  if (modules.includes("cleanmkv")) s.push("cleanmkv");
  if (modules.includes("metadata")) s.push("metadata");
  if (modules.includes("nfo")) s.push("nfo");
  if (modules.includes("prez")) s.push("prez");
  if (modules.includes("torrent") || modules.includes("upload")) s.push("torrent");
  s.push("execute");
  return s;
}

function formatBitrate(b: number | null | undefined): string {
  if (!b) return "";
  if (b >= 1_000_000) return `${(b / 1_000_000).toFixed(1)} Mbps`;
  if (b >= 1_000) return `${Math.round(b / 1_000)} kbps`;
  return `${b} bps`;
}

// ── sub-components ────────────────────────────────────────────────────────────

// Modules that have a dedicated wizard step card
const WIZARD_MODULES = new Set(["renamer", "cleanmkv", "metadata", "nfo", "prez", "torrent", "upload"]);

function ReleaseDashboard({ inspection, steps, currentStep, doneSteps, selectedModules }: {
  inspection: PipelineInspect;
  steps: StepId[];
  currentStep: StepId;
  doneSteps: Set<StepId>;
  selectedModules: string[];
}) {
  const kind = (inspection as unknown as { kind?: string }).kind ?? null;
  const mkvCount = inspection.tracks.length;
  const fileCount = inspection.renamer.total;
  // Modules with no wizard step — they run automatically in pipeline
  const autoModules = selectedModules.filter((m) => !WIZARD_MODULES.has(m));

  return (
    <div className="rounded-2xl border border-primary/30 bg-card p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-base font-semibold tracking-tight">{inspection.folder_name}</p>
          <div className="flex flex-wrap gap-2 mt-1">
            {kind ? (
              <Badge variant="secondary" className="capitalize text-xs">
                {kind.replace("_", " ")}
              </Badge>
            ) : null}
            <span className="text-xs text-muted-foreground">{fileCount} file{fileCount !== 1 ? "s" : ""}</span>
            {mkvCount > 0 && (
              <span className="text-xs text-muted-foreground">{mkvCount} MKV</span>
            )}
            {inspection.effective_locale && (
              <span className="text-xs text-muted-foreground">{inspection.effective_locale}</span>
            )}
          </div>
        </div>
        {inspection.renamer.changed > 0 && (
          <Badge variant="secondary" className="text-[10px]">
            {inspection.renamer.changed} rename{inspection.renamer.changed !== 1 ? "s" : ""}
          </Badge>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1">
        {steps.map((stepId, idx) => {
          const isDone = doneSteps.has(stepId);
          const isActive = stepId === currentStep;
          const label = STEP_LABELS[stepId] ?? stepId;
          return (
            <div key={stepId} className="flex items-center gap-1">
              <span className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold shrink-0",
                isDone && "bg-emerald-500/20 text-emerald-500",
                isActive && !isDone && "bg-primary text-primary-foreground",
                !isDone && !isActive && "bg-muted text-muted-foreground",
              )}>
                {isDone ? <CheckCircle2 className="h-3 w-3" /> : idx + 1}
              </span>
              <span className={cn(
                "text-[11px] font-medium",
                isActive && !isDone ? "text-foreground" : isDone ? "text-emerald-500/80" : "text-muted-foreground",
              )}>{label}</span>
              {idx < steps.length - 1 && (
                <span className="text-muted-foreground/30 text-xs mx-0.5">›</span>
              )}
            </div>
          );
        })}
      </div>

      {autoModules.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Auto:</span>
          {autoModules.map((m) => (
            <Badge key={m} variant="secondary" className="text-[10px] font-mono">{m}</Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function StepCard({ title, stepNum, status, summary, onClickDone, children }: {
  title: string; stepNum: number; status: StepStatus;
  summary?: string | undefined; onClickDone?: (() => void) | undefined;
  children?: React.ReactNode | undefined;
}) {
  return (
    <div
      onClick={status === "done" ? onClickDone : undefined}
      className={cn(
        "rounded-xl border transition-all duration-200",
        status === "active" && "border-primary/50 bg-card shadow-lg shadow-primary/8",
        status === "done" && "border-emerald-500/30 bg-card/60 cursor-pointer hover:border-emerald-500/50",
        status === "locked" && "border-border/50 bg-card/30 opacity-50",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <span className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
          status === "active" && "bg-primary text-primary-foreground",
          status === "done" && "bg-emerald-500/20 text-emerald-500",
          status === "locked" && "bg-muted text-muted-foreground",
        )}>
          {status === "done" ? <CheckCircle2 className="h-3.5 w-3.5" /> : stepNum}
        </span>
        <span className={cn("text-sm font-semibold", status === "locked" && "text-muted-foreground")}>{title}</span>
        {status === "done" && summary && <span className="ml-1 truncate text-xs text-muted-foreground">{summary}</span>}
        {status === "locked" && <Lock className="ml-auto h-3.5 w-3.5 text-muted-foreground/50" />}
      </div>
      {status === "active" && children ? <div className="border-t border-border/40 px-4 py-4">{children}</div> : null}
    </div>
  );
}

function OptionPills<T extends string>({ options, value, onChange }: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onChange(opt.id)}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            value === opt.id
              ? "border-primary/50 bg-primary/15 text-foreground"
              : "border-border/60 bg-secondary/30 text-muted-foreground hover:border-primary/25 hover:bg-secondary/60",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function TemplateList({ options, value, onChange, placeholder = "Default" }: {
  options: string[]; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  if (!options.length) return <p className="text-xs text-muted-foreground">No presets available.</p>;
  return (
    <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
      {[{ id: "", label: placeholder }, ...options.map((o) => ({ id: o, label: o }))].map((opt) => (
        <button key={opt.id} type="button" onClick={() => onChange(opt.id)} className={cn(
          "w-full rounded-md border px-3 py-2 text-left text-sm transition-colors",
          value === opt.id
            ? "border-primary/50 bg-primary/10 text-foreground"
            : "border-border/50 bg-secondary/30 text-muted-foreground hover:border-primary/25 hover:bg-secondary/60 hover:text-foreground",
        )}>{opt.label}</button>
      ))}
    </div>
  );
}

function TermPicker({ terms, suggested, onChange }: {
  terms: string[]; suggested: string[]; onChange: (t: string[]) => void;
}) {
  const [input, setInput] = useState("");
  const add = (t: string) => { const v = t.trim(); if (v && !terms.includes(v)) onChange([...terms, v]); };
  const unused = suggested.filter((s) => !terms.includes(s));

  return (
    <div className="space-y-3">
      {unused.length > 0 && (
        <div>
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Detected in filenames</p>
          <div className="flex flex-wrap gap-1.5">
            {unused.map((s) => (
              <button key={s} type="button" onClick={() => add(s)} className="flex items-center gap-1 rounded-full border border-border/60 bg-secondary/60 px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:bg-primary/8 hover:text-foreground">
                <Plus className="h-2.5 w-2.5" />{s}
              </button>
            ))}
          </div>
        </div>
      )}
      {terms.length > 0 && (
        <div>
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Will be removed</p>
          <div className="flex flex-wrap gap-1.5">
            {terms.map((t) => (
              <span key={t} className="flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-medium text-foreground">
                {t}
                <button type="button" onClick={() => onChange(terms.filter((x) => x !== t))} className="hover:text-destructive">
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="flex gap-2">
        <Input
          value={input}
          placeholder="Add term"
          className="h-8 text-xs"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { add(input); setInput(""); } }}
        />
        <Button type="button" variant="outline" size="sm" onClick={() => { add(input); setInput(""); }}>Add</Button>
      </div>
    </div>
  );
}

function InsertAfterEditor({ pairs, onChange }: {
  pairs: InsertAfterPair[];
  onChange: (pairs: InsertAfterPair[]) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Insert after</p>
      {pairs.map((pair, idx) => (
        <div key={idx} className="flex gap-2 items-center">
          <Input
            value={pair.after}
            placeholder="After term"
            className="h-8 text-xs"
            onChange={(e) => {
              const next = [...pairs];
              next[idx] = { ...pair, after: e.target.value };
              onChange(next);
            }}
          />
          <span className="text-muted-foreground text-xs shrink-0">→</span>
          <Input
            value={pair.insert}
            placeholder="Insert"
            className="h-8 text-xs"
            onChange={(e) => {
              const next = [...pairs];
              next[idx] = { ...pair, insert: e.target.value };
              onChange(next);
            }}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 shrink-0 text-muted-foreground hover:text-destructive"
            onClick={() => onChange(pairs.filter((_, i) => i !== idx))}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 text-xs"
        onClick={() => onChange([...pairs, { after: "", insert: "" }])}
      >
        <Plus className="h-3 w-3 mr-1" />Add pair
      </Button>
    </div>
  );
}

function TrackRow({ track, kind }: { track: InspectTrack; kind: "audio" | "subtitle" }) {
  const Icon = kind === "audio" ? Music : Subtitles;
  const lang = track.language ?? "und";
  const variant = kind === "subtitle" ? track.subtitle_variant : track.language_variant;
  const detail = [
    track.codec,
    track.channels,
    track.format_name,
    track.bitrate ? formatBitrate(track.bitrate) : null,
    variant,
    track.title,
  ].filter(Boolean).join(" · ");

  return (
    <div className={cn(
      "flex items-center gap-2 rounded-md border px-3 py-2 text-xs",
      track.is_default ? "border-primary/30 bg-primary/5" : "border-border/40 bg-secondary/20",
    )}>
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <span className="font-mono font-semibold w-8 shrink-0">{lang}</span>
      <span className="truncate text-muted-foreground">{detail}</span>
      <div className="ml-auto flex shrink-0 gap-1">
        {track.is_default && <Badge variant="secondary" className="text-[9px] px-1.5">default</Badge>}
        {track.is_forced && <Badge variant="secondary" className="text-[9px] px-1.5">forced</Badge>}
      </div>
    </div>
  );
}

function FileTracks({ scan }: { scan: InspectFileScan }) {
  return (
    <div className="rounded-lg border border-border/60 overflow-hidden">
      <div className="bg-secondary/30 px-3 py-2 text-xs font-medium flex items-center gap-2">
        <Disc3 className="h-3.5 w-3.5 text-muted-foreground" />
        {scan.filename}
        <span className="ml-auto text-muted-foreground">{scan.audio.length}A · {scan.subtitles.length}S</span>
      </div>
      <div className="p-2 space-y-1">
        {scan.audio.map((t) => <TrackRow key={`a-${t.track_id}`} track={t} kind="audio" />)}
        {scan.subtitles.map((t) => <TrackRow key={`s-${t.track_id}`} track={t} kind="subtitle" />)}
        {scan.audio.length === 0 && scan.subtitles.length === 0 && (
          <p className="px-2 py-1 text-xs text-muted-foreground">No audio/subtitle tracks found.</p>
        )}
      </div>
    </div>
  );
}

// ── step footer helpers ───────────────────────────────────────────────────────

function StepFooter({ stepId, stepJobs, cfg, onApply, onSkip, onComplete, onRerun }: {
  stepId: StepId;
  stepJobs: Record<string, string>;
  cfg: Config;
  onApply: () => void;
  onSkip: () => void;
  onComplete: () => void;
  onRerun: (job: ModuleJob) => void;
}) {
  const spec = STEP_MODULE_MAP[stepId];
  const jobId = stepJobs[stepId] ?? null;
  const isPending = false; // managed by parent mutation

  return (
    <div className="space-y-3 mt-3">
      {cfg.dryRun && (
        <p className="text-[11px] text-amber-600 dark:text-amber-400 flex items-center gap-1">
          <Layers className="h-3 w-3" />Simulation mode — no files will be written.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {spec && (
          <Button
            type="button"
            disabled={isPending || !!jobId}
            onClick={onApply}
          >
            <Play className="mr-1.5 h-3.5 w-3.5" />
            {jobId ? "Running…" : "Apply step"}
          </Button>
        )}
        <Button type="button" variant="ghost" size="sm" className="text-muted-foreground" onClick={onSkip}>
          Skip <ChevronRight className="ml-1 h-3.5 w-3.5" />
        </Button>
      </div>
      {jobId && spec && (
        <InlineJobPanel
          jobId={jobId}
          moduleName={spec.mod}
          onComplete={onComplete}
          onRerun={onRerun}
        />
      )}
    </div>
  );
}

// ── main ──────────────────────────────────────────────────────────────────────

export function PipelinePage() {
  const resourcesQuery = useQuery({ queryKey: ["modules-resources"], queryFn: getModulesResources });
  const [cfg, setCfg] = useState<Config>(INITIAL);
  const [currentStep, setCurrentStep] = useState<StepId>("path");
  const [doneSteps, setDoneSteps] = useState<Set<StepId>>(new Set());
  const [inspection, setInspection] = useState<PipelineInspect | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [stepJobs, setStepJobs] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);
  const [plan, setPlan] = useState<PipelinePlan | null>(null);

  const steps = useMemo(() => activeSteps(cfg.modules), [cfg.modules]);
  const res = resourcesQuery.data;

  const patch = useCallback((u: Partial<Config>) => setCfg((prev) => ({ ...prev, ...u })), []);

  const status = useCallback((step: StepId): StepStatus => {
    if (step === currentStep) return "active";
    if (doneSteps.has(step)) return "done";
    return "locked";
  }, [currentStep, doneSteps]);

  function advance(from: StepId) {
    setDoneSteps((prev) => new Set([...prev, from]));
    const idx = steps.indexOf(from);
    const next = steps[idx + 1];
    if (next !== undefined) setCurrentStep(next);
  }

  function goTo(step: StepId) {
    setCurrentStep(step);
    setDoneSteps((prev) => {
      const next = new Set(prev);
      const idx = steps.indexOf(step);
      for (let i = idx; i < steps.length; i++) { const s = steps[i]; if (s !== undefined) next.delete(s); }
      return next;
    });
  }

  const inspectMutation = useMutation({
    mutationFn: getPipelineInspect,
    onSuccess: (data) => setInspection(data),
  });

  const createJobMutation = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job: ModuleJob) => setJobId(job.id),
  });

  const applyStepMutation = useMutation({
    mutationFn: (args: { stepId: string; module: string; args_text: string }) =>
      createModuleJob({
        module: args.module,
        args_text: args.args_text,
        dry_run: cfg.dryRun,
        auto_yes: true,
        confirm_destructive: true,
        checkpoint_enabled: false,
      }).then((job) => ({ job, stepId: args.stepId })),
    onSuccess: ({ job, stepId }) => {
      setStepJobs((prev) => ({ ...prev, [stepId]: job.id }));
    },
  });

  const planMutation = useMutation({
    mutationFn: getPipelinePlan,
    onSuccess: (data) => setPlan(data),
  });

  function handleApplyStep(stepId: StepId) {
    const spec = STEP_MODULE_MAP[stepId];
    if (!spec) return;
    applyStepMutation.mutate({
      stepId,
      module: spec.mod,
      args_text: spec.buildArgs(cfg),
    });
  }

  function handleStepJobRerun(stepId: StepId, newJob: ModuleJob) {
    setStepJobs((prev) => ({ ...prev, [stepId]: newJob.id }));
  }

  async function confirmPath() {
    if (!cfg.path.trim()) return;
    try {
      const data = await inspectMutation.mutateAsync({
        path: cfg.path.trim(),
        remove_terms: cfg.removeTerms,
        nfo_locale: cfg.nfoLocale,
      });
      setInspection(data);
      advance("path");
    } catch { /* error shown via inspectMutation.isError */ }
  }

  async function reinspect() {
    if (!cfg.path.trim()) return;
    try {
      const data = await inspectMutation.mutateAsync({
        path: cfg.path.trim(),
        remove_terms: cfg.removeTerms,
        nfo_locale: cfg.nfoLocale,
      });
      setInspection(data);
    } catch { /* error shown via inspectMutation.isError */ }
  }

  const suggestedTerms = useMemo(() => {
    if (!inspection?.renamer?.files) return [];
    const terms = new Set<string>();
    for (const f of inspection.renamer.files) {
      for (const tag of [f.inferred_source, f.inferred_resolution, f.inferred_video_tag, f.inferred_audio_tag, f.hdr_display_label, f.existing_language_tag]) {
        if (tag) terms.add(tag);
      }
    }
    return [...terms].sort();
  }, [inspection]);

  const detectedKind = (inspection as unknown as { kind?: string } | null)?.kind ?? null;

  const previewCommand = `swirrl pipeline ${buildPipelineArgs(cfg)}`.trim();
  let stepNum = 0;

  // compute which module steps were skipped (no job applied) for "run remaining"
  const moduleStepsWithSpec = steps.filter((s) => STEP_MODULE_MAP[s]);
  const appliedSteps = moduleStepsWithSpec.filter((s) => stepJobs[s]);
  const skippedModules = moduleStepsWithSpec
    .filter((s) => !stepJobs[s])
    .map((s) => STEP_MODULE_MAP[s]?.mod)
    .filter(Boolean) as string[];

  return (
    <div className="space-y-3 ops-reveal">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Pipeline</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">Configure each step with real release data, then apply.</p>
      </div>

      {/* ── Release dashboard (P1) ─────────────────────────────────────────── */}
      {inspection && (
        <ReleaseDashboard
          inspection={inspection}
          steps={steps}
          currentStep={currentStep}
          doneSteps={doneSteps}
          selectedModules={cfg.modules}
        />
      )}

      {/* ── Path ───────────────────────────────────────────────────────────── */}
      {(() => { stepNum++; return null; })()}
      <StepCard title="Release path" stepNum={stepNum} status={status("path")}
        summary={inspection?.folder_name} onClickDone={() => goTo("path")}>
        <div className="space-y-3">
          <Input
            autoFocus
            value={cfg.path}
            placeholder="C:\Releases\Movie.Title.2023.1080p.BluRay"
            onChange={(e) => patch({ path: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && cfg.path.trim() && confirmPath()}
          />
          <Toggle checked={cfg.dryRun} onChange={(v) => patch({ dryRun: v })} label="Simulation (dry run)" />
          <Button type="button" disabled={!cfg.path.trim() || inspectMutation.isPending} onClick={confirmPath}>
            {inspectMutation.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <ChevronRight className="mr-1.5 h-4 w-4" />}
            {inspectMutation.isPending ? "Scanning…" : "Scan & Continue"}
          </Button>
          {inspectMutation.isError && (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
              {(inspectMutation.error as Error).message}
            </p>
          )}
        </div>
      </StepCard>

      {/* ── Modules ────────────────────────────────────────────────────────── */}
      {steps.includes("modules") && (() => { stepNum++; return null; })()}
      {steps.includes("modules") && status("modules") !== "locked" && (
        <StepCard title="Pipeline steps" stepNum={stepNum} status={status("modules")}
          summary={cfg.modules.join(", ")} onClickDone={() => goTo("modules")}>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {ALL_MODULES.map((mod) => {
                const on = cfg.modules.includes(mod);
                return (
                  <button key={mod} type="button"
                    onClick={() => patch({ modules: on ? cfg.modules.filter((m) => m !== mod) : [...cfg.modules, mod] })}
                    className={cn("rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                      on ? "border-primary/50 bg-primary/15 text-foreground" : "border-border/60 bg-secondary/30 text-muted-foreground hover:border-primary/25 hover:bg-secondary/60"
                    )}>{mod}</button>
                );
              })}
            </div>
            <Button type="button" onClick={() => advance("modules")}><ChevronRight className="mr-1.5 h-4 w-4" />Continue</Button>
          </div>
        </StepCard>
      )}

      {/* ── Renamer (P2) ───────────────────────────────────────────────────── */}
      {steps.includes("renamer") && (() => { stepNum++; return null; })()}
      {steps.includes("renamer") && status("renamer") !== "locked" && (
        <StepCard title="Renamer" stepNum={stepNum} status={status("renamer")}
          summary={inspection ? `${inspection.renamer.changed}/${inspection.renamer.total} files to rename` : undefined}
          onClickDone={() => goTo("renamer")}>
          <div className="space-y-4">
            {/* Terms */}
            <TermPicker terms={cfg.removeTerms} suggested={suggestedTerms} onChange={(t) => patch({ removeTerms: t })} />

            {/* Insert-after */}
            <InsertAfterEditor pairs={cfg.insertAfterPairs} onChange={(p) => patch({ insertAfterPairs: p })} />

            {/* Profile + lang */}
            {(res?.renamer_profiles ?? []).length > 0 && (
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Renamer profile</p>
                <TemplateList
                  options={res?.renamer_profiles ?? []}
                  value={cfg.renamerProfile}
                  onChange={(v) => patch({ renamerProfile: v })}
                  placeholder="Default"
                />
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Language tag</label>
                <Input
                  value={cfg.lang}
                  placeholder="e.g. FRENCH"
                  className="h-8 text-xs"
                  onChange={(e) => patch({ lang: e.target.value })}
                />
              </div>
              <div className="flex items-end pb-0.5">
                <Toggle
                  checked={cfg.forceLang}
                  onChange={(v) => patch({ forceLang: v })}
                  label="Force (overwrite existing tag)"
                />
              </div>
            </div>

            {/* Rename preview */}
            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" size="sm" disabled={inspectMutation.isPending} onClick={reinspect}>
                {inspectMutation.isPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : null}
                Refresh preview
              </Button>
              {(cfg.lang || cfg.insertAfterPairs.some((p) => p.after.trim())) && (
                <p className="text-[11px] text-muted-foreground">
                  Language tag and insert-after take effect on Apply, not shown in preview.
                </p>
              )}
            </div>
            {inspection && inspection.renamer.files.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Rename preview ({inspection.renamer.changed} changed, {inspection.renamer.collisions} collisions)
                </p>
                <div className="max-h-56 overflow-auto rounded-md border border-border divide-y divide-border/40">
                  {inspection.renamer.files.map((f, i) => (
                    <div key={i} className={cn("grid grid-cols-[1fr_auto_1fr] gap-2 px-3 py-1.5 text-[11px]", !f.changed && "opacity-40")}>
                      <span className="truncate font-mono text-muted-foreground">{f.original}</span>
                      <span className="text-muted-foreground">{f.changed ? "→" : "="}</span>
                      <span className={cn("truncate font-mono", f.collision ? "text-destructive" : f.changed ? "text-foreground" : "text-muted-foreground")}>
                        {f.renamed}{f.collision ? " ⚠" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <StepFooter
              stepId="renamer"
              stepJobs={stepJobs}
              cfg={cfg}
              onApply={() => handleApplyStep("renamer")}
              onSkip={() => advance("renamer")}
              onComplete={() => advance("renamer")}
              onRerun={(j) => handleStepJobRerun("renamer", j)}
            />
          </div>
        </StepCard>
      )}

      {/* ── CleanMKV (P3) ──────────────────────────────────────────────────── */}
      {steps.includes("cleanmkv") && (() => { stepNum++; return null; })()}
      {steps.includes("cleanmkv") && status("cleanmkv") !== "locked" && (
        <StepCard title="CleanMKV" stepNum={stepNum} status={status("cleanmkv")}
          summary={inspection?.tracks ? `${inspection.tracks.length} file${inspection.tracks.length !== 1 ? "s" : ""} scanned` : undefined}
          onClickDone={() => goTo("cleanmkv")}>
          <div className="space-y-4">
            {/* Preset selector */}
            {(res?.cleanmkv_presets ?? []).length > 0 && (
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Preset</p>
                <TemplateList
                  options={res?.cleanmkv_presets ?? []}
                  value={cfg.cleanmkvPreset}
                  onChange={(v) => patch({ cleanmkvPreset: v })}
                  placeholder="Default (from settings)"
                />
              </div>
            )}

            {/* Track display */}
            {inspectMutation.isPending ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />Scanning tracks…
              </div>
            ) : inspection?.tracks && inspection.tracks.length > 0 ? (
              <div className="space-y-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Tracks in release</p>
                {inspection.tracks.map((scan, i) => <FileTracks key={i} scan={scan} />)}
              </div>
            ) : inspection ? (
              <p className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                No MKV tracks found. Is mkvmerge installed and in PATH?
              </p>
            ) : null}

            <p className="text-xs text-muted-foreground">
              Manual track selection:{" "}
              <Link to="/module/$moduleSlug" params={{ moduleSlug: "cleanmkv" }} className="text-primary hover:underline inline-flex items-center gap-0.5">
                CleanMKV module <ExternalLink className="h-3 w-3" />
              </Link>
            </p>

            <StepFooter
              stepId="cleanmkv"
              stepJobs={stepJobs}
              cfg={cfg}
              onApply={() => handleApplyStep("cleanmkv")}
              onSkip={() => advance("cleanmkv")}
              onComplete={() => advance("cleanmkv")}
              onRerun={(j) => handleStepJobRerun("cleanmkv", j)}
            />
          </div>
        </StepCard>
      )}

      {/* ── Metadata (P4) ──────────────────────────────────────────────────── */}
      {steps.includes("metadata") && (() => { stepNum++; return null; })()}
      {steps.includes("metadata") && status("metadata") !== "locked" && (
        <StepCard title="Metadata" stepNum={stepNum} status={status("metadata")}
          summary={detectedKind ? `Detected: ${detectedKind.replace("_", " ")}` : "TMDB lookup"}
          onClickDone={() => goTo("metadata")}>
          <div className="space-y-4">
            {inspection && (
              <div className="rounded-md border border-border/50 bg-secondary/20 px-3 py-2 space-y-1 text-xs">
                <div className="flex gap-2">
                  <span className="w-20 shrink-0 text-muted-foreground">Release</span>
                  <span className="font-medium">{inspection.folder_name}</span>
                </div>
                {detectedKind && (
                  <div className="flex gap-2">
                    <span className="w-20 shrink-0 text-muted-foreground">Kind</span>
                    <span className="capitalize">{detectedKind.replace("_", " ")}</span>
                  </div>
                )}
              </div>
            )}

            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Options</p>
              <Toggle
                checked={cfg.metadataAutoAccept}
                onChange={(v) => patch({ metadataAutoAccept: v })}
                label="Auto-accept TMDB match (skip confirmation prompt)"
              />
            </div>

            <p className="text-xs text-muted-foreground">
              Requires a TMDB API token in{" "}
              <Link to="/settings-setup" className="text-primary hover:underline inline-flex items-center gap-0.5">
                Settings <ExternalLink className="h-3 w-3" />
              </Link>.
            </p>

            <StepFooter
              stepId="metadata"
              stepJobs={stepJobs}
              cfg={cfg}
              onApply={() => handleApplyStep("metadata")}
              onSkip={() => advance("metadata")}
              onComplete={() => advance("metadata")}
              onRerun={(j) => handleStepJobRerun("metadata", j)}
            />
          </div>
        </StepCard>
      )}

      {/* ── NFO (P5) ───────────────────────────────────────────────────────── */}
      {steps.includes("nfo") && (() => { stepNum++; return null; })()}
      {steps.includes("nfo") && status("nfo") !== "locked" && (
        <StepCard title="NFO" stepNum={stepNum} status={status("nfo")}
          summary={[cfg.nfoDetail !== "default" ? cfg.nfoDetail : null, cfg.nfoMode !== "global" ? cfg.nfoMode : null, cfg.nfoLocale !== "auto" ? cfg.nfoLocale.toUpperCase() : null].filter(Boolean).join(" · ") || "Default"}
          onClickDone={() => goTo("nfo")}>
          <div className="space-y-4">
            {detectedKind && (
              <p className="text-xs text-muted-foreground">
                Detected kind: <span className="font-medium text-foreground capitalize">{detectedKind.replace("_", " ")}</span>
              </p>
            )}

            {/* Detail level — primary option */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Detail level</p>
              <OptionPills<NfoDetail>
                options={[
                  { id: "default", label: "Default" },
                  { id: "detailed", label: "Detailed" },
                ]}
                value={cfg.nfoDetail}
                onChange={(v) => patch({ nfoDetail: v })}
              />
            </div>

            {/* Mode */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Output mode</p>
              <OptionPills<Config["nfoMode"]>
                options={[
                  { id: "global", label: "Global (one NFO)" },
                  { id: "per_file", label: "Per file" },
                  { id: "both", label: "Both" },
                ]}
                value={cfg.nfoMode}
                onChange={(v) => patch({ nfoMode: v })}
              />
            </div>

            {/* Locale */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Language</p>
              <OptionPills<Config["nfoLocale"]>
                options={[
                  { id: "auto", label: "Auto" },
                  { id: "en", label: "EN" },
                  { id: "fr", label: "FR" },
                  { id: "es", label: "ES" },
                ]}
                value={cfg.nfoLocale}
                onChange={(v) => patch({ nfoLocale: v })}
              />
            </div>

            {/* With metadata */}
            <Toggle
              checked={cfg.nfoWithMetadata}
              onChange={(v) => patch({ nfoWithMetadata: v })}
              label="Fetch fresh TMDB metadata during NFO generation"
            />

            {/* Advanced: template selector */}
            {(res?.nfo_templates ?? []).length > 0 && (
              <details className="rounded-md border border-border">
                <summary className="cursor-pointer px-3 py-2 text-xs text-muted-foreground hover:text-foreground">
                  Advanced: choose template ({res?.nfo_templates?.length ?? 0} available)
                </summary>
                <div className="border-t border-border p-3">
                  <TemplateList
                    options={res?.nfo_templates ?? []}
                    value={cfg.nfoTemplate}
                    onChange={(v) => patch({ nfoTemplate: v })}
                    placeholder="Auto (based on detail level)"
                  />
                </div>
              </details>
            )}

            <StepFooter
              stepId="nfo"
              stepJobs={stepJobs}
              cfg={cfg}
              onApply={() => handleApplyStep("nfo")}
              onSkip={() => advance("nfo")}
              onComplete={() => advance("nfo")}
              onRerun={(j) => handleStepJobRerun("nfo", j)}
            />
          </div>
        </StepCard>
      )}

      {/* ── Prez (P6) ──────────────────────────────────────────────────────── */}
      {steps.includes("prez") && (() => { stepNum++; return null; })()}
      {steps.includes("prez") && status("prez") !== "locked" && (
        <StepCard title="Presentation" stepNum={stepNum} status={status("prez")}
          summary={[cfg.prezPreset || null, cfg.prezFormat !== "both" ? cfg.prezFormat : null].filter(Boolean).join(" · ") || "Default"}
          onClickDone={() => goTo("prez")}>
          <div className="space-y-4">
            {/* Preset */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Prez preset</p>
              <TemplateList
                options={(res?.prez_presets ?? []).map((p) => p.name)}
                value={cfg.prezPreset}
                onChange={(v) => patch({ prezPreset: v })}
                placeholder="Default (from settings)"
              />
            </div>

            {/* Format */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Output format</p>
              <OptionPills<Config["prezFormat"]>
                options={[
                  { id: "both", label: "BBCode + HTML" },
                  { id: "bbcode", label: "BBCode only" },
                  { id: "html", label: "HTML only" },
                ]}
                value={cfg.prezFormat}
                onChange={(v) => patch({ prezFormat: v })}
              />
            </div>

            {/* BBCode template */}
            {(cfg.prezFormat === "bbcode" || cfg.prezFormat === "both") && (res?.prez_templates?.bbcode ?? []).length > 0 && (
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">BBCode template</p>
                <TemplateList
                  options={res?.prez_templates?.bbcode ?? []}
                  value={cfg.prezBbcodeTemplate}
                  onChange={(v) => patch({ prezBbcodeTemplate: v })}
                  placeholder="Default"
                />
              </div>
            )}

            {/* HTML template */}
            {(cfg.prezFormat === "html" || cfg.prezFormat === "both") && (res?.prez_templates?.html ?? []).length > 0 && (
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">HTML template</p>
                <TemplateList
                  options={res?.prez_templates?.html ?? []}
                  value={cfg.prezHtmlTemplate}
                  onChange={(v) => patch({ prezHtmlTemplate: v })}
                  placeholder="Default"
                />
              </div>
            )}

            {/* Mediainfo mode */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Mediainfo block</p>
              <OptionPills<Config["prezMediainfoMode"]>
                options={[
                  { id: "none", label: "None" },
                  { id: "spoiler", label: "Spoiler" },
                  { id: "only", label: "Only" },
                ]}
                value={cfg.prezMediainfoMode}
                onChange={(v) => patch({ prezMediainfoMode: v })}
              />
            </div>

            <StepFooter
              stepId="prez"
              stepJobs={stepJobs}
              cfg={cfg}
              onApply={() => handleApplyStep("prez")}
              onSkip={() => advance("prez")}
              onComplete={() => advance("prez")}
              onRerun={(j) => handleStepJobRerun("prez", j)}
            />
          </div>
        </StepCard>
      )}

      {/* ── Torrent (P7) ───────────────────────────────────────────────────── */}
      {steps.includes("torrent") && (() => { stepNum++; return null; })()}
      {steps.includes("torrent") && status("torrent") !== "locked" && (
        <StepCard title="Torrent & Upload" stepNum={stepNum} status={status("torrent")}
          summary={cfg.announce || "No tracker"} onClickDone={() => goTo("torrent")}>
          <div className="space-y-4">
            {/* Announce */}
            {(res?.announces ?? []).length > 0 ? (
              <TemplateList
                options={(res?.announces ?? []).map((a) => a.value)}
                value={cfg.announce}
                onChange={(v) => patch({ announce: v })}
                placeholder="— No tracker —"
              />
            ) : (
              <div className="rounded-md border border-border/50 bg-secondary/20 px-3 py-3 space-y-2">
                <p className="text-sm text-muted-foreground">No announce URLs configured.</p>
                <Link to="/settings-setup" className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline">
                  <Settings className="h-3.5 w-3.5" />Configure trackers in Settings → Upload<ExternalLink className="h-3 w-3" />
                </Link>
              </div>
            )}

            {/* Private + piece length */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Toggle
                  checked={cfg.torrentPrivate}
                  onChange={(v) => patch({ torrentPrivate: v })}
                  label="Private torrent"
                />
              </div>
              <div className="space-y-1.5">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Piece length</p>
                <OptionPills<string>
                  options={PIECE_LENGTHS.map((l) => ({ id: l, label: l }))}
                  value={cfg.torrentPieceLength}
                  onChange={(v) => patch({ torrentPieceLength: v })}
                />
              </div>
            </div>

            <StepFooter
              stepId="torrent"
              stepJobs={stepJobs}
              cfg={cfg}
              onApply={() => handleApplyStep("torrent")}
              onSkip={() => advance("torrent")}
              onComplete={() => advance("torrent")}
              onRerun={(j) => handleStepJobRerun("torrent", j)}
            />
          </div>
        </StepCard>
      )}

      {/* ── Execute (P8) ───────────────────────────────────────────────────── */}
      {steps.includes("execute") && (() => { stepNum++; return null; })()}
      {steps.includes("execute") && status("execute") !== "locked" && (
        <StepCard title="Execute" stepNum={stepNum} status={status("execute")}>
          <div className="space-y-4">
            {/* Summary */}
            <div className="rounded-lg border border-border/60 bg-secondary/20 p-3 space-y-1 text-xs">
              <div className="flex gap-2"><span className="w-20 shrink-0 text-muted-foreground">Path</span><span className="truncate font-mono">{cfg.path || "—"}</span></div>
              <div className="flex gap-2"><span className="w-20 shrink-0 text-muted-foreground">Steps</span><span>{cfg.modules.join(", ")}</span></div>
              {cfg.removeTerms.length > 0 && <div className="flex gap-2"><span className="w-20 shrink-0 text-muted-foreground">Remove</span><span>{cfg.removeTerms.join(", ")}</span></div>}
              <div className="flex gap-2"><span className="w-20 shrink-0 text-muted-foreground">Mode</span><span>{cfg.dryRun ? "Simulation" : "Apply"}</span></div>
              {appliedSteps.length > 0 && (
                <div className="flex gap-2">
                  <span className="w-20 shrink-0 text-muted-foreground">Applied</span>
                  <span className="text-emerald-600 dark:text-emerald-400">{appliedSteps.join(", ")}</span>
                </div>
              )}
              {skippedModules.length > 0 && (
                <div className="flex gap-2">
                  <span className="w-20 shrink-0 text-muted-foreground">Skipped</span>
                  <span className="text-muted-foreground">{skippedModules.join(", ")}</span>
                </div>
              )}
              {inspection && <div className="flex gap-2"><span className="w-20 shrink-0 text-muted-foreground">Files</span><span>{inspection.renamer.total} · {inspection.tracks.length} scanned</span></div>}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Run remaining (skipped steps) as a single pipeline job */}
              {skippedModules.length > 0 && (
                <Button
                  type="button"
                  disabled={!cfg.path.trim() || createJobMutation.isPending}
                  onClick={() => createJobMutation.mutate({
                    module: "pipeline",
                    args_text: (() => {
                      const a: string[] = [];
                      const p = quoteArg(cfg.path);
                      if (p) a.push(p);
                      if (cfg.dryRun) a.push("--dry-run");
                      a.push("--auto");
                      for (const m of skippedModules) a.push("--modules", m);
                      return a.join(" ").trim();
                    })(),
                    dry_run: cfg.dryRun,
                    auto_yes: false,
                    confirm_destructive: true,
                    checkpoint_enabled: false,
                  })}
                >
                  <Play className="mr-2 h-4 w-4" />
                  {createJobMutation.isPending ? "Starting…" : `Run remaining (${skippedModules.join(", ")})`}
                </Button>
              )}
              {skippedModules.length === 0 && appliedSteps.length > 0 && (
                <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-4 w-4" />All selected steps applied individually.
                </div>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={!cfg.path.trim() || planMutation.isPending}
                onClick={() => planMutation.mutate({
                  path: cfg.path.trim(),
                  modules: cfg.modules,
                  remove_terms: cfg.removeTerms,
                  nfo_locale: cfg.nfoLocale,
                })}
              >
                {planMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Layers className="mr-2 h-4 w-4" />}
                Preview plan
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={async () => { await navigator.clipboard.writeText(previewCommand); setCopied(true); setTimeout(() => setCopied(false), 1400); }}
              >
                <Copy className="mr-2 h-4 w-4" />Copy Command
              </Button>
              {copied && <Badge variant="success">Copied</Badge>}
              {cfg.dryRun && <Badge variant="secondary" className="text-[10px]"><Layers className="mr-1 h-2.5 w-2.5" />Simulation</Badge>}
            </div>

            {planMutation.isError && (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
                {(planMutation.error as Error).message}
              </p>
            )}
            {plan && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2 text-xs">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Plan summary</p>
                <div className="flex flex-wrap gap-1.5">
                  {plan.enabled_modules.map((m) => (
                    <span key={m} className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-medium text-foreground">{m}</span>
                  ))}
                </div>
                <div className="grid gap-1 sm:grid-cols-2">
                  <div className="flex gap-2"><span className="w-24 shrink-0 text-muted-foreground">Rename</span><span>{plan.renamer.changed}/{plan.renamer.total} files{plan.renamer.collisions > 0 ? ` · ${plan.renamer.collisions} collision(s)` : ""}</span></div>
                  <div className="flex gap-2"><span className="w-24 shrink-0 text-muted-foreground">CleanMKV</span><span>{plan.cleanmkv.total} file(s){plan.cleanmkv.preset ? ` · ${plan.cleanmkv.preset}` : ""}</span></div>
                  <div className="flex gap-2"><span className="w-24 shrink-0 text-muted-foreground">NFO</span><span>{plan.nfo.template || "default"}{plan.nfo.locale ? ` · ${plan.nfo.locale}` : ""}</span></div>
                  <div className="flex gap-2"><span className="w-24 shrink-0 text-muted-foreground">Prez</span><span>{plan.prez.preset || "default"}</span></div>
                </div>
              </div>
            )}
            <details className="rounded-md border border-border">
              <summary className="cursor-pointer px-3 py-2 text-xs text-muted-foreground hover:text-foreground">Show pipeline command</summary>
              <pre className="max-h-32 overflow-auto border-t border-border bg-muted p-3 text-[11px]">{previewCommand}</pre>
            </details>
          </div>
        </StepCard>
      )}

      {/* ── Pipeline job (run-remaining) ───────────────────────────────────── */}
      {jobId !== null && (
        <section className="surface-enter">
          <h2 className="mb-2 text-sm font-semibold">Pipeline execution</h2>
          <InlineJobPanel jobId={jobId} moduleName="pipeline" onRerun={(j: ModuleJob) => setJobId(j.id)} />
        </section>
      )}
    </div>
  );
}
