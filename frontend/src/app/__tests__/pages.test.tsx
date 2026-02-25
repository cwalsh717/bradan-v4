import { Suspense } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn().mockResolvedValue({ categories: [] }),
  apiFetch: vi.fn().mockResolvedValue({ data: null, data_as_of: "", next_refresh: null }),
}));

vi.mock("@/lib/ws", () => ({
  useWebSocket: () => ({ data: null, isConnected: false }),
}));

import DashboardPage from "@/app/page";
import PortfolioPage from "@/app/portfolio/page";
import StockProfilePage from "@/app/stocks/[symbol]/page";
import DCFPage from "@/app/dcf/[symbol]/page";

describe("DashboardPage", () => {
  it("renders heading", () => {
    render(<DashboardPage />);
    expect(screen.getByText("Market Dashboard")).toBeInTheDocument();
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
    await act(async () => {
      render(
        <Suspense fallback={<div>Loading...</div>}>
          <StockProfilePage params={Promise.resolve({ symbol: "AAPL" })} />
        </Suspense>,
      );
    });
    await waitFor(() => {
      expect(screen.getAllByText("AAPL").length).toBeGreaterThanOrEqual(1);
    });
  });
});

describe("DCFPage", () => {
  it("renders with symbol", async () => {
    await act(async () => {
      render(
        <Suspense fallback={<div>Loading...</div>}>
          <DCFPage params={Promise.resolve({ symbol: "MSFT" })} />
        </Suspense>,
      );
    });
    await waitFor(() => {
      expect(screen.getByText(/DCF/)).toBeInTheDocument();
      expect(screen.getByText(/MSFT/)).toBeInTheDocument();
    });
  });
});
