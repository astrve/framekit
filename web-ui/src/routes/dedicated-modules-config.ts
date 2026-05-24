import type { ModulePreset } from "@/components/modules/dedicated-module-launcher";

export type DedicatedModuleConfig = {
  slug: string;
  moduleName: string;
  title: string;
  description: string;
  presets: ModulePreset[];
  requiredFlags?: string[];
};

export const DEDICATED_MODULE_CONFIGS: DedicatedModuleConfig[] = [
  { slug: "watch", moduleName: "watch", title: "Watch", description: "Surveillance locale et polling.", presets: [{ id: "list", label: "List", args: "list" }, { id: "doctor", label: "Doctor", args: "doctor" }] },
  { slug: "inspect", moduleName: "inspect", title: "Inspect", description: "Inspection média rapide.", presets: [{ id: "basic", label: "Inspect basic", args: "\"\"" }] },
  { slug: "renamer", moduleName: "renamer", title: "Renamer", description: "Rename non destructif par défaut.", presets: [{ id: "dry", label: "Dry run", args: "\"\" --dry-run" }], requiredFlags: ["--dry-run"] },
  { slug: "cleanmkv", moduleName: "cleanmkv", title: "CleanMKV", description: "Nettoyage piste/conteneur en dry-run.", presets: [{ id: "dry", label: "Dry run", args: "\"\" --dry-run" }], requiredFlags: ["--dry-run"] },
  { slug: "torrent", moduleName: "torrent", title: "Torrent", description: "Génération/contrôle torrent.", presets: [{ id: "build", label: "Build dry", args: "build \"\" --dry-run" }] },
  { slug: "nfo", moduleName: "nfo", title: "NFO", description: "NFO generation locale.", presets: [{ id: "gen", label: "Generate", args: "generate \"\" --locale fr" }] },
  { slug: "prez", moduleName: "prez", title: "Prez", description: "Génération présentation release.", presets: [{ id: "gen", label: "Generate", args: "generate \"\"" }] },
  { slug: "screenshot", moduleName: "screenshot", title: "Screenshot", description: "Captures media.", presets: [{ id: "grab", label: "Grab", args: "grab \"\" --count 6" }] },
  { slug: "encode", moduleName: "encode", title: "Encode", description: "Encodage local.", presets: [{ id: "run", label: "Run", args: "run \"\"" }] },
  { slug: "extract", moduleName: "extract", title: "Extract", description: "Extraction sous-titres/tracks.", presets: [{ id: "subs", label: "Subtitle", args: "subtitle \"\"" }] },
  { slug: "sort", moduleName: "sort", title: "Sort", description: "Tri et organisation fichiers.", presets: [{ id: "run", label: "Run", args: "\"\" --dry-run" }], requiredFlags: ["--dry-run"] },
  { slug: "browse", moduleName: "browse", title: "Browse", description: "Parcours catalogue local.", presets: [{ id: "list", label: "List", args: "list" }] },
  { slug: "metadata", moduleName: "metadata", title: "Metadata", description: "Validation et doctor metadata.", presets: [{ id: "doctor", label: "Doctor", args: "doctor" }] },
  { slug: "validate", moduleName: "validate", title: "Validate", description: "Validation structure/inputs.", presets: [{ id: "run", label: "Run", args: "\"\"" }] },
  { slug: "logs", moduleName: "logs", title: "Logs", description: "Lecture logs framekit.", presets: [{ id: "tail", label: "Tail", args: "tail --lines 120" }] },
];

export function configBySlug(slug: string): DedicatedModuleConfig | null {
  return DEDICATED_MODULE_CONFIGS.find((item) => item.slug === slug) ?? null;
}
