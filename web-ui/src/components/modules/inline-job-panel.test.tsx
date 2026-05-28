import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InlineJobPanel } from "@/components/modules/inline-job-panel";
import type { ModuleJob, RunModuleResult } from "@/lib/api/schemas";

// ── mocks ─────────────────────────────────────────────────────────────────────

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    to,
    params,
  }: {
    children: ReactNode;
    to: string;
    params?: Record<string, string>;
  }) => {
    let href = to;
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        href = href.replace(`$${key}`, value);
      }
    }
    return <a href={href}>{children}</a>;
  },
}));

const mockUseQuery = vi.fn();
const mockUseMutation = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useMutation: (...args: unknown[]) => mockUseMutation(...args),
}));

vi.mock("@/lib/api/endpoints", () => ({
  getModuleJob: vi.fn(),
  cancelModuleJob: vi.fn(),
  rerunModuleJob: vi.fn(),
}));

// RunTimeline uses cn / Tailwind classes — stub to keep tests lightweight
vi.mock("@/components/modules/run-timeline", () => ({
  RunTimeline: ({ items }: { items: { label: string }[] }) => (
    <div data-testid="run-timeline">
      {items.map((item) => <span key={item.label}>{item.label}</span>)}
    </div>
  ),
}));

// ── fixtures ──────────────────────────────────────────────────────────────────

function makeJob(overrides: Partial<ModuleJob> = {}): ModuleJob {
  return {
    id: "job-001",
    status: "pending",
    created_at: "2024-01-01T00:00:00Z",
    started_at: null,
    finished_at: null,
    request: {},
    live_stdout: "",
    live_stderr: "",
    result: null,
    error: null,
    priority: 0,
    ...overrides,
  };
}

function makeResult(overrides: Partial<RunModuleResult> = {}): RunModuleResult {
  return {
    ok: true,
    argv: ["framekit"],
    returncode: 0,
    stdout: "",
    stderr: "",
    parsed_kind: null,
    parsed_payload: null,
    ...overrides,
  };
}

const INSPECT_PAYLOAD = {
  media_kind: "movie",
  release_title: "Movie Title 2024",
  series_title: null,
  year: "2024",
  episode_count: 1,
  completeness_label: "complete",
  missing_codes: [],
  size_bytes: 10737418240, // 10.00 GB
  duration_ms: 6720000,   // 1h 52m 0s
  source: "BluRay",
  resolution: "1080p",
  video_tag: "HEVC",
  audio_tag: "DTS-HD",
  language_tag: "MULTi",
};

const VALIDATE_PAYLOAD = {
  release_name: "Movie.2024.BluRay",
  is_valid: false,
  checks_passed: 3,
  checks_warned: 1,
  checks_failed: 1,
  issues: [
    {
      severity: "error",
      category: "container",
      message: "Unsupported container: .avi",
      suggestion: "Convert to MKV",
    },
    {
      severity: "warning",
      category: "nfo",
      message: "No NFO file found",
      suggestion: "Run fk nfo",
    },
  ],
};

// ── setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  mockUseQuery.mockReturnValue({ data: undefined, isError: false });
  mockUseMutation.mockReturnValue({ mutate: vi.fn(), isPending: false });
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe("InlineJobPanel", () => {
  it("renders nothing when jobId is null", () => {
    const { container } = render(
      <InlineJobPanel jobId={null} moduleName="renamer" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows 'pending' badge and timeline for pending job", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({ status: "pending" }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByTestId("run-timeline")).toBeInTheDocument();
  });

  it("shows 'running' badge and live output label for running job", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "running",
        started_at: "2024-01-01T00:00:00Z",
        live_stdout: "[INFO] Processing MKV files in folder",
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="cleanmkv" />);
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getAllByText(/Processing MKV files/)[0]).toBeInTheDocument();
    expect(screen.getByText("Live output")).toBeInTheDocument();
  });

  it("shows 'completed' badge and stdout for completed job without parsed_payload", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "completed",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:00:05Z",
        result: makeResult({ stdout: "[OK]   Rename operation completed." }),
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText(/Rename operation completed/)).toBeInTheDocument();
    expect(screen.queryByText("Release inspection")).not.toBeInTheDocument();
  });

  it("shows 'failed' badge and stderr section for failed job", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "failed",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:00:01Z",
        result: makeResult({ ok: false, returncode: 1, stderr: "Error: folder not found" }),
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText(/folder not found/)).toBeInTheDocument();
  });

  it("shows non-zero exit code for failed job", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "failed",
        finished_at: "2024-01-01T00:00:01Z",
        result: makeResult({ ok: false, returncode: 2, stderr: "fatal" }),
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    expect(screen.getByText("exit 2")).toBeInTheDocument();
  });

  it("shows job-level error string when result is absent", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "failed",
        error: "Subprocess crashed before producing output",
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    expect(screen.getByText(/Subprocess crashed/)).toBeInTheDocument();
  });

  it("shows 'Failed to load job status' on query error with no data", () => {
    mockUseQuery.mockReturnValue({ data: undefined, isError: true });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    expect(screen.getByText(/Failed to load job status/)).toBeInTheDocument();
  });

  it("always shows Debug link pointing to job detail page", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({ status: "pending" }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="renamer" />);
    const link = screen.getByRole("link", { name: /Debug/ });
    expect(link).toHaveAttribute("href", "/modules/job-001");
  });

  // ── structured result cards ─────────────────────────────────────────────────

  it("renders InspectResult card for inspect module with parsed_payload", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "completed",
        finished_at: "2024-01-01T00:01:00Z",
        result: makeResult({ parsed_kind: "json", parsed_payload: INSPECT_PAYLOAD, stdout: '{"parsed":true}' }),
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="inspect" />);
    expect(screen.getByText("Release inspection")).toBeInTheDocument();
    expect(screen.getByText("Movie Title 2024")).toBeInTheDocument();
    expect(screen.getByText("10.00 GB")).toBeInTheDocument();
    expect(screen.getByText("HEVC")).toBeInTheDocument();
    expect(screen.getByText("BluRay")).toBeInTheDocument();
    expect(screen.getByText("MULTi")).toBeInTheDocument();
    // Raw output available as collapsible
    expect(screen.getByText("Raw output")).toBeInTheDocument();
    // No validate section shown
    expect(screen.queryByText(/\d+ passed/)).not.toBeInTheDocument();
  });

  it("renders ValidateResult counts and issues for validate module", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "completed",
        finished_at: "2024-01-01T00:01:00Z",
        result: makeResult({ parsed_kind: "json", parsed_payload: VALIDATE_PAYLOAD, stdout: '{"parsed":true}' }),
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="validate" />);
    expect(screen.getByText(/3 passed/)).toBeInTheDocument();
    expect(screen.getByText(/1 warning/)).toBeInTheDocument();
    expect(screen.getByText(/1 error/)).toBeInTheDocument();
    expect(screen.getByText(/Unsupported container: \.avi/)).toBeInTheDocument();
    expect(screen.getByText(/No NFO file found/)).toBeInTheDocument();
    expect(screen.getByText("Convert to MKV")).toBeInTheDocument();
    // Raw output available as collapsible
    expect(screen.getByText("Raw output")).toBeInTheDocument();
    // No inspect card
    expect(screen.queryByText("Release inspection")).not.toBeInTheDocument();
  });

  it("falls back to raw <pre> output for other modules even with parsed_payload", () => {
    mockUseQuery.mockReturnValue({
      data: makeJob({
        status: "completed",
        result: makeResult({
          parsed_kind: "json",
          parsed_payload: { some: "data" },
          stdout: "raw output line for cleanmkv",
        }),
      }),
      isError: false,
    });
    render(<InlineJobPanel jobId="job-001" moduleName="cleanmkv" />);
    expect(screen.queryByText("Release inspection")).not.toBeInTheDocument();
    expect(screen.getByText("raw output line for cleanmkv")).toBeInTheDocument();
  });
});
