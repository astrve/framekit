import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "@/routes/home";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to }: { children: ReactNode; to: string }) => (
    <a href={to}>{children}</a>
  ),
}));

const mockUseQuery = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}));

// Default: all queries return undefined (loading state) — no warnings, no jobs.
beforeEach(() => {
  mockUseQuery.mockReturnValue({ data: undefined, isLoading: true, isError: false });
});

describe("HomePage dashboard", () => {
  it("renders Active Operations section heading", () => {
    render(<HomePage />);
    expect(screen.getByText("Active Operations")).toBeInTheDocument();
  });

  it("renders Recent Results section heading", () => {
    render(<HomePage />);
    expect(screen.getByText("Recent Results")).toBeInTheDocument();
  });

  it("renders Quick Actions section heading", () => {
    render(<HomePage />);
    expect(screen.getByText("Quick Actions")).toBeInTheDocument();
  });

  it("does not show warnings banner when no data is loaded", () => {
    render(<HomePage />);
    expect(screen.queryByText("Attention required")).not.toBeInTheDocument();
  });

  it("shows warning banner when doctor returns error checks", () => {
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === "dashboard-doctor") {
        return {
          data: {
            checks: [{ section: "sys", name: "ffmpeg", status: "err", detail: "not found" }],
            tools: [],
          },
          isLoading: false,
          isError: false,
        };
      }
      return { data: undefined, isLoading: true, isError: false };
    });
    render(<HomePage />);
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText(/1 diagnostic error/)).toBeInTheDocument();
  });

  it("shows vault-offline warning when vault query errors", () => {
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === "dashboard-vault") {
        return { data: undefined, isLoading: false, isError: true };
      }
      return { data: undefined, isLoading: true, isError: false };
    });
    render(<HomePage />);
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText(/Vault offline/)).toBeInTheDocument();
  });

  it("shows upload-no-trackers warning when upload enabled with zero enabled trackers", () => {
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === "dashboard-upload-state") {
        return { data: { enabled: true, auto_upload: false }, isLoading: false, isError: false };
      }
      if (queryKey[0] === "dashboard-trackers") {
        return { data: { trackers: [] }, isLoading: false, isError: false };
      }
      return { data: undefined, isLoading: true, isError: false };
    });
    render(<HomePage />);
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText(/Upload active but no trackers configured/)).toBeInTheDocument();
  });

  it("suppresses upload-no-trackers warning when upload is disabled", () => {
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: string[] }) => {
      if (queryKey[0] === "dashboard-upload-state") {
        return { data: { enabled: false, auto_upload: false }, isLoading: false, isError: false };
      }
      if (queryKey[0] === "dashboard-trackers") {
        return { data: { trackers: [] }, isLoading: false, isError: false };
      }
      return { data: undefined, isLoading: true, isError: false };
    });
    render(<HomePage />);
    expect(screen.queryByText(/Upload active but no trackers/)).not.toBeInTheDocument();
  });
});
