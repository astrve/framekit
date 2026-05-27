import { useMutation, useQuery } from "@tanstack/react-query";
import { Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  cancelModuleJob,
  clearModuleJobs,
  createModuleJob,
  getModuleJob,
  getModulesCatalog,
  listModuleJobs,
} from "@/lib/api/endpoints";
import type { ModuleJob } from "@/lib/api/schemas";

const POLL_INTERVAL = 2000;
const LIVE_FEED_LIMIT = 10;

const CREAM_BG = "#fdf8f0";
const CREAM_TITLEBAR = "#ede8df";
const CREAM_BORDER = "#d6cfc4";
const CREAM_PROMPT = "#b07040";
const CREAM_MUTED = "#a09080";
const CREAM_TEXT = "#3a2c1e";
const CREAM_INPUT_BG = "#f5efe6";

function StatusPill({ status }: { status: ModuleJob["status"] }) {
  const colors: Record<string, string> = {
    completed: "#4a8c5c",
    failed: "#b04040",
    cancelled: "#806040",
    running: "#3a6ea8",
    pending: "#7060a0",
  };
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        color: colors[status] ?? CREAM_MUTED,
        border: `1px solid ${colors[status] ?? CREAM_BORDER}`,
        borderRadius: 4,
        padding: "1px 6px",
        whiteSpace: "nowrap",
      }}
    >
      {status}
    </span>
  );
}

function JobEntry({ job }: { job: ModuleJob }) {
  const req = job.request as { module?: string; args_text?: string } | undefined;
  const cmd = `$ framekit ${req?.module ?? ""}${req?.args_text ? " " + req.args_text : ""}`.trim();
  const stdout = job.live_stdout ?? job.result?.stdout ?? "";
  const stderr = job.live_stderr ?? job.result?.stderr ?? "";

  return (
    <div style={{ borderBottom: `1px solid ${CREAM_BORDER}`, paddingBottom: 12, marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ fontFamily: "monospace", fontSize: 13, color: CREAM_PROMPT, fontWeight: 600 }}>
          {cmd}
        </span>
        <StatusPill status={job.status} />
        {job.status === "running" && (
          <span
            style={{
              display: "inline-block",
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#4a8c5c",
              animation: "pulse 1s ease-in-out infinite",
            }}
          />
        )}
      </div>
      {stdout && (
        <pre
          style={{
            margin: 0,
            fontFamily: "monospace",
            fontSize: 12,
            color: CREAM_TEXT,
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            opacity: 0.85,
          }}
        >
          {stdout}
        </pre>
      )}
      {stderr && (
        <pre
          style={{
            margin: "4px 0 0",
            fontFamily: "monospace",
            fontSize: 12,
            color: "#b04040",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
          }}
        >
          {stderr}
        </pre>
      )}
      {job.error && (
        <span style={{ fontSize: 11, color: "#b04040" }}>{job.error}</span>
      )}
    </div>
  );
}

export function CliPage() {
  const catalogQuery = useQuery({ queryKey: ["modules-catalog"], queryFn: getModulesCatalog });
  const modules = (catalogQuery.data?.modules ?? []).map((m) => m.name).sort();

  const [selectedModule, setSelectedModule] = useState("doctor");
  const [argsText, setArgsText] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [allowDestructive, setAllowDestructive] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [inputFocused, setInputFocused] = useState(false);

  const feedRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Live feed — recent jobs
  const feedQuery = useQuery({
    queryKey: ["cli-feed"],
    queryFn: () => listModuleJobs(LIVE_FEED_LIMIT),
    refetchInterval: POLL_INTERVAL,
  });
  const feedJobs = feedQuery.data?.jobs ?? [];

  const clearJobs = useMutation({
    mutationFn: clearModuleJobs,
    onSuccess: () => { void feedQuery.refetch(); },
  });

  // Active job polling
  const { data: liveJob } = useQuery({
    queryKey: ["cli-job", activeJobId],
    queryFn: ({ queryKey }) => getModuleJob(queryKey[1] as string),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status || status === "completed" || status === "failed" || status === "cancelled") return false;
      return POLL_INTERVAL;
    },
  });

  const createJob = useMutation({
    mutationFn: createModuleJob,
    onSuccess: (job: ModuleJob) => {
      setActiveJobId(job.id);
    },
  });

  const cancelJob = useMutation({
    mutationFn: (id: string) => cancelModuleJob(id),
    onSuccess: () => setActiveJobId(null),
  });

  const isRunning = liveJob?.status === "running" || liveJob?.status === "pending" || createJob.isPending;

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [feedJobs.length]);

  function run() {
    if (isRunning) return;
    const spec = (catalogQuery.data?.modules ?? []).find((m) => m.name === selectedModule);
    createJob.mutate({
      module: selectedModule,
      args_text: argsText,
      dry_run: dryRun,
      auto_yes: true,
      confirm_destructive: allowDestructive || spec?.destructive === false,
    });
    setArgsText("");
  }

  function cancel() {
    if (activeJobId) cancelJob.mutate(activeJobId);
  }

  return (
    <>
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        .cli-cursor::after {
          content: '▋';
          animation: blink 1s step-end infinite;
          color: ${CREAM_PROMPT};
          margin-left: 1px;
        }
      `}</style>

      <div
        style={{
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 4px 24px rgba(80,50,20,0.13)",
          border: `1px solid ${CREAM_BORDER}`,
          fontFamily: "monospace",
          display: "flex",
          flexDirection: "column",
          minHeight: "70vh",
        }}
      >
        {/* Title bar */}
        <div
          style={{
            background: CREAM_TITLEBAR,
            borderBottom: `1px solid ${CREAM_BORDER}`,
            display: "flex",
            alignItems: "center",
            padding: "9px 14px",
            gap: 8,
            userSelect: "none",
          }}
        >
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57", display: "inline-block" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#ffbd2e", display: "inline-block" }} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840", display: "inline-block" }} />
          <span
            style={{
              flex: 1,
              textAlign: "center",
              fontSize: 12,
              color: CREAM_MUTED,
              letterSpacing: "0.06em",
            }}
          >
            framekit — cli
          </span>
          {feedJobs.length > 0 && !isRunning ? (
            <button
              type="button"
              onClick={() => clearJobs.mutate()}
              disabled={clearJobs.isPending}
              style={{
                background: "transparent",
                border: "none",
                fontSize: 11,
                color: CREAM_MUTED,
                cursor: "pointer",
                fontFamily: "monospace",
                padding: "0 4px",
                opacity: clearJobs.isPending ? 0.5 : 1,
              }}
            >
              clear
            </button>
          ) : (
            <span style={{ width: 56 }} />
          )}
        </div>

        {/* Feed area */}
        <div
          ref={feedRef}
          style={{
            flex: 1,
            background: CREAM_BG,
            overflowY: "auto",
            padding: "20px 24px",
            minHeight: 320,
            maxHeight: "60vh",
          }}
        >
          {feedJobs.length === 0 && (
            <span style={{ color: CREAM_MUTED, fontSize: 13 }}>
              No recent jobs. Run a command below.{" "}
              <span style={{ opacity: 0.6 }}>(Async jobs only — sync runs are not tracked here.)</span>
            </span>
          )}
          {[...feedJobs].reverse().map((job) => (
            <JobEntry key={job.id} job={job} />
          ))}
        </div>

        {/* Input bar */}
        <div
          style={{
            background: CREAM_TITLEBAR,
            borderTop: `1px solid ${CREAM_BORDER}`,
            padding: "10px 14px",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          {/* Module + args row */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <select
              value={selectedModule}
              onChange={(e) => setSelectedModule(e.target.value)}
              disabled={isRunning}
              style={{
                background: CREAM_INPUT_BG,
                border: `1px solid ${CREAM_BORDER}`,
                borderRadius: 6,
                padding: "4px 8px",
                fontSize: 12,
                color: CREAM_TEXT,
                fontFamily: "monospace",
                outline: "none",
              }}
            >
              {modules.length === 0 && <option value="doctor">doctor</option>}
              {modules.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>

            <span style={{ color: CREAM_PROMPT, fontWeight: 700, fontSize: 14, userSelect: "none" }}>$</span>

            <div style={{ flex: 1, position: "relative", display: "flex", alignItems: "center" }}>
              <input
                ref={inputRef}
                value={argsText}
                onChange={(e) => setArgsText(e.target.value)}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                onKeyDown={(e) => { if (e.key === "Enter" && !isRunning) run(); }}
                placeholder='"/path/to/release" --flag'
                disabled={isRunning}
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  fontFamily: "monospace",
                  fontSize: 13,
                  color: CREAM_TEXT,
                  caretColor: CREAM_PROMPT,
                }}
                className={inputFocused && !argsText && !isRunning ? "cli-cursor" : ""}
              />
            </div>

            {isRunning ? (
              <button
                type="button"
                onClick={cancel}
                disabled={cancelJob.isPending}
                style={{
                  background: "transparent",
                  border: `1px solid #b04040`,
                  borderRadius: 6,
                  padding: "4px 10px",
                  fontSize: 12,
                  color: "#b04040",
                  cursor: "pointer",
                  fontFamily: "monospace",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <Square size={10} /> Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={run}
                style={{
                  background: CREAM_PROMPT,
                  border: "none",
                  borderRadius: 6,
                  padding: "4px 12px",
                  fontSize: 12,
                  color: "#fff",
                  cursor: "pointer",
                  fontFamily: "monospace",
                  fontWeight: 600,
                }}
              >
                Run ↵
              </button>
            )}
          </div>

          {/* Toggles row */}
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: CREAM_MUTED, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                style={{ accentColor: CREAM_PROMPT }}
              />
              Dry-run
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: CREAM_MUTED, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={allowDestructive}
                onChange={(e) => setAllowDestructive(e.target.checked)}
                style={{ accentColor: CREAM_PROMPT }}
              />
              Allow file changes
            </label>
            {createJob.isError && (
              <span style={{ fontSize: 11, color: "#b04040" }}>
                Error: {String(createJob.error)}
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
