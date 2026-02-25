import { Suspense } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor, fireEvent } from "@testing-library/react";

import type { Portfolio, PerformanceSummary } from "@/lib/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockAuthFetch = vi.fn();

vi.mock("@/lib/api", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: vi.fn().mockResolvedValue("test-token"), isSignedIn: true }),
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  SignedIn: ({ children }: { children: React.ReactNode }) => children,
  SignedOut: () => null,
  SignInButton: () => null,
  UserButton: () => null,
}));

vi.mock("@/lib/useAuthSync", () => ({
  useAuthSync: vi.fn(),
}));

import PortfolioPage from "@/app/portfolio/page";
import PortfolioDetailPage from "@/app/portfolio/[id]/page";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PORTFOLIOS: Portfolio[] = [
  {
    id: 1,
    name: "Tech Stocks",
    mode: "full",
    created_at: "2025-06-01T00:00:00Z",
    updated_at: null,
    holdings_count: 3,
  },
  {
    id: 2,
    name: "Watchlist",
    mode: "watchlist",
    created_at: "2025-07-15T00:00:00Z",
    updated_at: null,
    holdings_count: 5,
  },
];

const FULL_PERFORMANCE: PerformanceSummary = {
  total_value: 15000,
  total_cost_basis: 12000,
  total_gain_loss: 3000,
  total_gain_loss_pct: 25.0,
  holdings: [
    {
      id: 1,
      stock_id: 1,
      symbol: "AAPL",
      name: "Apple Inc",
      shares: 10,
      cost_basis_per_share: 150,
      added_at: "2025-06-01T00:00:00Z",
      current_price: 175,
      market_value: 1750,
      gain_loss: 250,
      gain_loss_pct: 16.67,
    },
    {
      id: 2,
      stock_id: 2,
      symbol: "MSFT",
      name: "Microsoft Corp",
      shares: 5,
      cost_basis_per_share: 300,
      added_at: "2025-06-15T00:00:00Z",
      current_price: 350,
      market_value: 1750,
      gain_loss: 250,
      gain_loss_pct: 16.67,
    },
  ],
};

const WATCHLIST_PERFORMANCE: PerformanceSummary = {
  total_value: 0,
  total_cost_basis: 0,
  total_gain_loss: 0,
  total_gain_loss_pct: null,
  holdings: [
    {
      id: 10,
      stock_id: 3,
      symbol: "GOOG",
      name: "Alphabet Inc",
      shares: null,
      cost_basis_per_share: null,
      added_at: "2025-07-15T00:00:00Z",
      current_price: 140,
      market_value: null,
      gain_loss: null,
      gain_loss_pct: null,
    },
  ],
};

const EMPTY_PERFORMANCE: PerformanceSummary = {
  total_value: 0,
  total_cost_basis: 0,
  total_gain_loss: 0,
  total_gain_loss_pct: null,
  holdings: [],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDetailPage(id = "1") {
  return render(
    <Suspense fallback={<div>Loading...</div>}>
      <PortfolioDetailPage params={Promise.resolve({ id })} />
    </Suspense>,
  );
}

// ---------------------------------------------------------------------------
// Tests — Portfolio List Page
// ---------------------------------------------------------------------------

describe("PortfolioPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders portfolio heading", () => {
    mockAuthFetch.mockReturnValue(new Promise(() => {}));

    render(<PortfolioPage />);

    expect(screen.getByText("Portfolio")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockAuthFetch.mockReturnValue(new Promise(() => {}));

    render(<PortfolioPage />);

    expect(screen.getByTestId("portfolio-loading")).toBeInTheDocument();
  });

  it("displays portfolios after loading", async () => {
    mockAuthFetch.mockResolvedValue(PORTFOLIOS);

    render(<PortfolioPage />);

    await waitFor(() => {
      expect(screen.getByTestId("portfolio-1")).toBeInTheDocument();
      expect(screen.getByTestId("portfolio-2")).toBeInTheDocument();
    });

    expect(screen.getByText("Tech Stocks")).toBeInTheDocument();
    expect(screen.getByText("Watchlist")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-loading")).not.toBeInTheDocument();
  });

  it("shows empty state when no portfolios", async () => {
    mockAuthFetch.mockResolvedValue([]);

    render(<PortfolioPage />);

    await waitFor(() => {
      expect(
        screen.getByText("No portfolios yet. Create one to get started."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByTestId("portfolio-loading")).not.toBeInTheDocument();
  });

  it("shows create form on button click", async () => {
    mockAuthFetch.mockResolvedValue([]);
    render(<PortfolioPage />);

    await waitFor(() => {
      expect(screen.getByText("New Portfolio")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("create-form")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("New Portfolio"));

    expect(screen.getByTestId("create-form")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-name-input")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-mode-select")).toBeInTheDocument();
    expect(screen.getByTestId("create-submit")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — Portfolio Detail Page
// ---------------------------------------------------------------------------

describe("PortfolioDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders detail page with portfolio name", async () => {
    mockAuthFetch.mockImplementation(async (path: string) => {
      if (path === "/api/portfolios") return PORTFOLIOS;
      if (path.includes("/performance")) return FULL_PERFORMANCE;
      return [];
    });

    await act(async () => {
      renderDetailPage("1");
    });

    await waitFor(() => {
      expect(screen.getByText("Tech Stocks")).toBeInTheDocument();
    });

    expect(screen.getByText("full")).toBeInTheDocument();
  });

  it("shows performance summary in full mode", async () => {
    mockAuthFetch.mockImplementation(async (path: string) => {
      if (path === "/api/portfolios") return PORTFOLIOS;
      if (path.includes("/performance")) return FULL_PERFORMANCE;
      return [];
    });

    await act(async () => {
      renderDetailPage("1");
    });

    await waitFor(() => {
      expect(screen.getByTestId("performance-summary")).toBeInTheDocument();
    });

    expect(screen.getByText("Total Value")).toBeInTheDocument();
    // "Cost Basis" appears in both the performance summary and the table header
    expect(screen.getAllByText("Cost Basis").length).toBeGreaterThanOrEqual(1);
    // "Gain/Loss" appears in both the performance summary and the table header
    expect(screen.getAllByText("Gain/Loss").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Return")).toBeInTheDocument();
  });

  it("shows holdings table with symbol links", async () => {
    mockAuthFetch.mockImplementation(async (path: string) => {
      if (path === "/api/portfolios") return PORTFOLIOS;
      if (path.includes("/performance")) return FULL_PERFORMANCE;
      return [];
    });

    await act(async () => {
      renderDetailPage("1");
    });

    await waitFor(() => {
      expect(screen.getByTestId("holdings-table")).toBeInTheDocument();
    });

    expect(screen.getByTestId("holding-1")).toBeInTheDocument();
    expect(screen.getByTestId("holding-2")).toBeInTheDocument();

    // Symbol links
    const aaplLink = screen.getByRole("link", { name: "AAPL" });
    expect(aaplLink).toHaveAttribute("href", "/stocks/AAPL");

    const msftLink = screen.getByRole("link", { name: "MSFT" });
    expect(msftLink).toHaveAttribute("href", "/stocks/MSFT");

    // Names rendered
    expect(screen.getByText("Apple Inc")).toBeInTheDocument();
    expect(screen.getByText("Microsoft Corp")).toBeInTheDocument();
  });

  it("hides P&L columns in watchlist mode", async () => {
    mockAuthFetch.mockImplementation(async (path: string) => {
      if (path === "/api/portfolios") return PORTFOLIOS;
      if (path.includes("/performance")) return WATCHLIST_PERFORMANCE;
      return [];
    });

    await act(async () => {
      renderDetailPage("2");
    });

    await waitFor(() => {
      expect(screen.getByTestId("holding-10")).toBeInTheDocument();
    });

    // Performance summary should NOT be visible in watchlist mode
    expect(screen.queryByTestId("performance-summary")).not.toBeInTheDocument();

    // P&L column headers should not be present
    expect(screen.queryByText("Shares")).not.toBeInTheDocument();
    expect(screen.queryByText("Cost Basis")).not.toBeInTheDocument();
    expect(screen.queryByText("Market Value")).not.toBeInTheDocument();

    // Symbol and Name columns should still be present
    expect(screen.getByText("GOOG")).toBeInTheDocument();
    expect(screen.getByText("Alphabet Inc")).toBeInTheDocument();
  });

  it("shows empty holdings state", async () => {
    mockAuthFetch.mockImplementation(async (path: string) => {
      if (path === "/api/portfolios") return PORTFOLIOS;
      if (path.includes("/performance")) return EMPTY_PERFORMANCE;
      return [];
    });

    await act(async () => {
      renderDetailPage("1");
    });

    await waitFor(() => {
      expect(
        screen.getByText("No holdings yet. Add stocks to your portfolio."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByTestId("holdings-table")).not.toBeInTheDocument();
  });
});
