import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import DashboardPage from "@/app/page";
import PortfolioPage from "@/app/portfolio/page";
import StockProfilePage from "@/app/stocks/[symbol]/page";
import DCFPage from "@/app/dcf/[symbol]/page";

describe("DashboardPage", () => {
  it("renders heading", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });
});

describe("PortfolioPage", () => {
  it("renders heading", () => {
    render(<PortfolioPage />);
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
  });
});

describe("StockProfilePage", () => {
  it("renders with symbol", async () => {
    const result = await StockProfilePage({
      params: Promise.resolve({ symbol: "AAPL" }),
    });
    render(result);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });
});

describe("DCFPage", () => {
  it("renders with symbol", async () => {
    const result = await DCFPage({
      params: Promise.resolve({ symbol: "MSFT" }),
    });
    render(result);
    expect(screen.getByText(/DCF/)).toBeInTheDocument();
    expect(screen.getByText(/MSFT/)).toBeInTheDocument();
  });
});
