import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn().mockReturnValue("/"),
}));

import { Navigation } from "../Navigation";

describe("Navigation", () => {
  it("renders Dashboard and Portfolio links", () => {
    render(<Navigation />);

    const dashboardLink = screen.getByText("Dashboard");
    const portfolioLink = screen.getByText("Portfolio");

    expect(dashboardLink).toBeInTheDocument();
    expect(portfolioLink).toBeInTheDocument();
  });

  it("Dashboard link points to /", () => {
    render(<Navigation />);

    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).toHaveAttribute("href", "/");
  });

  it("Portfolio link points to /portfolio", () => {
    render(<Navigation />);

    const portfolioLink = screen.getByText("Portfolio").closest("a");
    expect(portfolioLink).toHaveAttribute("href", "/portfolio");
  });
});
