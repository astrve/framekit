import type { ModuleJob } from "@/lib/api/schemas";

export type ParsedStep = {
  label: string;
  status: "running" | "done" | "failed";
};

const MODULE_PATTERNS: Record<string, RegExp[]> = {
  pipeline: [/^\[(?<module>[a-z-]+)\]\s+(?<state>en cours|ok|failed|en échec|done)/i, /^Step\s+\d+\/\d+:\s+(?<module>.+)$/i],
  batch: [/^Traitement\s+\d+\s+sur\s+\d+\s*:\s*(?<module>.+)$/i],
  cleanmkv: [/^Traitement des fichiers MKV/i],
  torrent: [/^Hachage de la charge utile du torrent/i],
  upload: [/^upload/i, /^tracker/i],
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

export function runTimeline(job: ModuleJob | null | undefined): Array<{ label: string; active: boolean; done: boolean; failed: boolean }> {
  const status = job?.status ?? "pending";
  const queueDone = status !== "pending";
  const runningDone = status === "completed" || status === "failed" || status === "cancelled";
  return [
    { label: "Queued", active: status === "pending", done: queueDone, failed: false },
    { label: "Running", active: status === "running", done: runningDone, failed: status === "failed" || status === "cancelled" },
    { label: status === "completed" ? "Completed" : status === "failed" ? "Failed" : status === "cancelled" ? "Cancelled" : "Result", active: status === "completed" || status === "failed" || status === "cancelled", done: status === "completed", failed: status === "failed" || status === "cancelled" },
  ];
}
