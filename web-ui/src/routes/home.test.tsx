import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { HomePage } from "@/routes/home";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="/">{children}</a>,
}));

describe("HomePage", () => {
  it("renders web-ui heading", () => {
    render(<HomePage />);

    expect(screen.getByText("Framekit stack must")).toBeInTheDocument();
    expect(screen.getByText(/Interface web locale moderne/i)).toBeInTheDocument();
  });
});
