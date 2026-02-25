import { Suspense } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";

import type {
  StockProfile,
  FinancialRatios,
  FinancialStatement,
  Dividend,
  PeerStock,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockApiGet = vi.fn();

vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => mockApiGet(...args),
  API_BASE: "http://localhost:8000",
}));

vi.mock("@/lib/ws", () => ({
  useWebSocket: () => ({ data: null, isConnected: false }),
}));

// Recharts ResponsiveContainer doesn't render children in jsdom because it
// measures the parent element's size (which is 0 in jsdom). We replace it
// with a simple pass-through so the chart internals can render.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({
      children,
    }: {
      children: React.ReactNode;
    }) => <div data-testid="responsive-container">{children}</div>,
  };
});

import StockProfilePage from "@/app/stocks/[symbol]/page";
import { PriceChart } from "@/components/stocks/PriceChart";
import { RatiosGrid } from "@/components/stocks/RatiosGrid";
import { PeerList } from "@/components/stocks/PeerList";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PROFILE: StockProfile = {
  symbol: "AAPL",
  name: "Apple Inc.",
  exchange: "NASDAQ",
  sector: "Technology",
  industry: "Consumer Electronics",
  currency: "USD",
};

const RATIOS: FinancialRatios = {
  gross_margin: 43.31,
  operating_margin: 30.74,
  net_margin: 25.31,
  roe: 160.58,
  roa: 28.29,
  roic: 56.42,
  current_ratio: 0.99,
  quick_ratio: 0.84,
  debt_to_equity: 1.87,
  debt_to_assets: 0.32,
  interest_coverage: 29.15,
  pe_ratio: 28.64,
  pb_ratio: 46.19,
  ps_ratio: 7.25,
  ev_to_ebitda: 22.17,
  asset_turnover: 1.12,
  inventory_turnover: 33.21,
};

const NULL_RATIOS: FinancialRatios = {
  gross_margin: null,
  operating_margin: null,
  net_margin: null,
  roe: null,
  roa: null,
  roic: null,
  current_ratio: null,
  quick_ratio: null,
  debt_to_equity: null,
  debt_to_assets: null,
  interest_coverage: null,
  pe_ratio: null,
  pb_ratio: null,
  ps_ratio: null,
  ev_to_ebitda: null,
  asset_turnover: null,
  inventory_turnover: null,
};

const FINANCIALS: FinancialStatement[] = [
  {
    id: 1,
    statement_type: "income_statement",
    period: "annual",
    fiscal_date: "2024-09-30",
    data: {
      revenue: 391035000000,
      gross_profit: 180683000000,
      operating_income: 123216000000,
      net_income: 93736000000,
    },
    fetched_at: "2025-01-01T00:00:00Z",
  },
  {
    id: 2,
    statement_type: "income_statement",
    period: "annual",
    fiscal_date: "2023-09-30",
    data: {
      revenue: 383285000000,
      gross_profit: 169148000000,
      operating_income: 114301000000,
      net_income: 96995000000,
    },
    fetched_at: "2025-01-01T00:00:00Z",
  },
];

const DIVIDENDS: Dividend[] = [
  { id: 1, ex_date: "2025-02-07", amount: 0.25, fetched_at: "2025-02-01T00:00:00Z" },
  { id: 2, ex_date: "2024-11-08", amount: 0.25, fetched_at: "2024-11-01T00:00:00Z" },
];

const PEERS: PeerStock[] = [
  { symbol: "MSFT", name: "Microsoft Corporation", sector: "Technology", industry: "Software" },
  { symbol: "GOOG", name: "Alphabet Inc.", sector: "Technology", industry: "Internet Content" },
];

const PRICE_HISTORY = [
  { date: "2025-01-02", close: 185.5 },
  { date: "2025-01-03", close: 187.2 },
  { date: "2025-01-06", close: 188.1 },
];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function renderPage(symbol = "AAPL") {
  return render(
    <Suspense fallback={<div>Loading...</div>}>
      <StockProfilePage params={Promise.resolve({ symbol })} />
    </Suspense>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StockProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", async () => {
    // Make apiGet hang so we stay in loading
    mockApiGet.mockReturnValue(new Promise(() => {}));

    await act(async () => {
      renderPage();
    });

    // During loading, the skeleton placeholders are present (animate-pulse divs)
    // The suspense fallback may show first, then the loading skeleton
    // Either "Loading..." (Suspense) or the skeleton is acceptable
    const body = document.body.innerHTML;
    expect(
      body.includes("animate-pulse") || body.includes("Loading..."),
    ).toBe(true);
  });

  it("renders stock profile header after data loads", async () => {
    mockApiGet.mockImplementation((path: string) => {
      if (path.includes("/profile")) return Promise.resolve(PROFILE);
      if (path.includes("/price-history")) return Promise.resolve(PRICE_HISTORY);
      if (path.includes("/financials")) return Promise.resolve(FINANCIALS);
      if (path.includes("/ratios")) return Promise.resolve(RATIOS);
      if (path.includes("/dividends")) return Promise.resolve(DIVIDENDS);
      if (path.includes("/peers")) return Promise.resolve(PEERS);
      return Promise.resolve(null);
    });

    await act(async () => {
      renderPage();
    });

    await waitFor(() => {
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });

    // Symbol
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    // Exchange
    expect(screen.getByText("NASDAQ")).toBeInTheDocument();
    // Sector badge
    expect(screen.getByText("Technology")).toBeInTheDocument();
    // Industry badge
    expect(screen.getByText("Consumer Electronics")).toBeInTheDocument();
  });

  it("renders error state when profile fails to load", async () => {
    mockApiGet.mockRejectedValue(new Error("Not found"));

    await act(async () => {
      renderPage("INVALID");
    });

    await waitFor(() => {
      expect(screen.getByText("Stock not found")).toBeInTheDocument();
    });
  });
});

describe("PriceChart", () => {
  it("renders with data", () => {
    render(<PriceChart data={PRICE_HISTORY} />);
    // The chart renders inside the mocked ResponsiveContainer
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("shows empty message when no data", () => {
    render(<PriceChart data={[]} />);
    expect(screen.getByText("No price data available")).toBeInTheDocument();
  });
});

describe("RatiosGrid", () => {
  it("renders ratio values", () => {
    render(<RatiosGrid ratios={RATIOS} />);

    // Check group headings
    expect(screen.getByText("Profitability")).toBeInTheDocument();
    expect(screen.getByText("Liquidity")).toBeInTheDocument();
    expect(screen.getByText("Leverage")).toBeInTheDocument();
    expect(screen.getByText("Valuation")).toBeInTheDocument();

    // Check specific ratio values
    expect(screen.getByTestId("ratio-pe_ratio")).toHaveTextContent("28.64");
    expect(screen.getByTestId("ratio-current_ratio")).toHaveTextContent("0.99");
    expect(screen.getByTestId("ratio-debt_to_equity")).toHaveTextContent("1.87");
  });

  it("shows N/A for null ratios", () => {
    render(<RatiosGrid ratios={NULL_RATIOS} />);

    // All ratio values should show N/A (non-percent) or em-dash (percent)
    const peRatio = screen.getByTestId("ratio-pe_ratio");
    expect(peRatio).toHaveTextContent("N/A");

    const currentRatio = screen.getByTestId("ratio-current_ratio");
    expect(currentRatio).toHaveTextContent("N/A");
  });
});

describe("PeerList", () => {
  it("renders peer links", () => {
    render(<PeerList peers={PEERS} />);

    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("Microsoft Corporation")).toBeInTheDocument();
    expect(screen.getByText("GOOG")).toBeInTheDocument();
    expect(screen.getByText("Alphabet Inc.")).toBeInTheDocument();

    // Check that links point to correct URLs
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/stocks/MSFT");
    expect(links[1]).toHaveAttribute("href", "/stocks/GOOG");
  });

  it("shows empty state when no peers", () => {
    render(<PeerList peers={[]} />);
    expect(screen.getByText("No peers found")).toBeInTheDocument();
  });
});
