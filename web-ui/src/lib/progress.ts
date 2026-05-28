import type { ModuleJob } from "@/lib/api/schemas";

export type ParsedStep = {
  label: string;
  status: "running" | "done" | "failed";
};

const MODULE_PATTERNS: Record<string, RegExp[]> = {
  // "[INFO] Renamer in progress..." — pipeline.step.running key is absent from all locale
  // files so the default English string is always used regardless of the UI locale setting.
  pipeline: [/^\[INFO\]\s+(?<module>.+?)\s+in\s+progress/i],
  // EN: "Processing N of M: name" | FR: "Traitement N sur M : name" | ES: "Procesando N de M: name"
  // Rich console.rule() may surround the text with dashes; match anywhere in the line.
  batch: [/(?:Processing|Traitement|Procesando)\s+\d+\s+(?:of|sur|de)\s+\d+\s*[: ]\s*(?<module>.+)/i],
  // EN: "Processing MKV files" | FR: "Traitement des fichiers MKV" | ES: "Procesando archivos MKV"
  cleanmkv: [/(?:Processing\s+MKV\s+files?|Traitement\s+des\s+fichiers\s+MKV|Procesando\s+archivos\s+MKV)/i],
  // EN: "Hashing torrent payload" | FR: "Hachage de la charge utile du torrent" | ES: "Hashing del payload del torrent"
  torrent: [/(?:Hashing\s+torrent|Hachage\s+de\s+la\s+charge|Hashing\s+del\s+payload)/i],
  upload: [/^upload/i, /^tracker/i],
  // EN: "Extracting 6 screenshots per video" | "Extracting 3 screenshots at specific timestamps"
  screenshot: [/Extracting\s+\d+\s+screenshots?/i],
  // EN: "Processing N file(s)..." — emitted by all extract sub-commands (subtitle/audio/video)
  extract: [/Processing\s+\d+\s+file/i],
  // EN: "Modified: N" | "Planned changes: N" (dry-run count) | "Rename operation completed."
  renamer: [
    /(?:Modified|Planned\s+changes)\s*:\s*(?<module>\d+)/i,
    /Rename\s+operation\s+completed/i,
    /(?:Dry-run\s+completed|Dry\s+run\s+completed)/i,
  ],
  // EN: "NFO written: /path/to/file.nfo" — emitted once per output file
  nfo: [/NFO\s+written\s*:\s*(?<module>.+)/i],
  // EN: "Output: /path/to/output.html" | "Presentation generated." | "Presentation dry-run completed."
  prez: [
    /(?:\[INFO\]\s+)?Output\s*:\s*(?<module>.+)/i,
    /Presentation\s+(?:generated|dry-run\s+completed|dry\s+run\s+completed)/i,
  ],
};

export function parseSubSteps(moduleName: string, stdout: string, stderr: string): ParsedStep[] {
  const lines = `${stdout}\n${stderr}`.split("\n").map((line) => line.trim()).filter(Boolean);
  const patterns = MODULE_PATTERNS[moduleName] ?? [];
  const steps: ParsedStep[] = [];
  for (const line of lines.slice(-300)) {
    for (const pattern of patterns) {
      const match = line.match(pattern);
      if (!match) {
        continue;
      }
      const groups = (match.groups ?? {}) as { module?: string; state?: string };
      const label = (groups.module ?? line).slice(0, 120);
      const state = (groups.state ?? "").toLowerCase();
      let status: ParsedStep["status"] = "running";
      if (state.includes("ok") || state.includes("done")) {
        status = "done";
      } else if (state.includes("échec") || state.includes("failed")) {
        status = "failed";
      }
      steps.push({ label, status });
      break;
    }
  }
  return steps.slice(-10);
}

export function runTimeline(job: ModuleJob | null | undefined): [
  { label: string; active: boolean; done: boolean; failed: boolean },
  { label: string; active: boolean; done: boolean; failed: boolean },
  { label: string; active: boolean; done: boolean; failed: boolean },
] {
  const status = job?.status ?? "pending";
  const queueDone = status !== "pending";
  const runningDone = status === "completed" || status === "failed" || status === "cancelled";
  return [
    { label: "Queued", active: status === "pending", done: queueDone, failed: false },
    { label: "Running", active: status === "running", done: runningDone, failed: status === "failed" || status === "cancelled" },
    { label: status === "completed" ? "Completed" : status === "failed" ? "Failed" : status === "cancelled" ? "Cancelled" : "Result", active: status === "completed" || status === "failed" || status === "cancelled", done: status === "completed", failed: status === "failed" || status === "cancelled" },
  ];
}
