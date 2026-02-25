import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const mockApiGet = vi.fn();
const mockUseWebSocket = vi.fn();

vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => mockApiGet(...args),
}));

vi.mock("@/lib/ws", () => ({
  useWebSocket: (...args: unknown[]) => mockUseWebSocket(...args),
}));

import DashboardPage from "@/app/page";
import { TickerCard } from "@/components/dashboard/TickerCard";
import type { DashboardTicker, PriceUpdate } from "@/lib/types";

const makeTicker = (overrides: Partial<DashboardTicker> = {}): DashboardTicker => ({
  id: 1,
  category: "equities",
  display_name: "S&P 500 (SPY)",
  symbol: "SPY",
  data_source: "twelvedata_ws",
  display_format: "price",
  display_order: 1,
  is_active: true,
  ...overrides,
});

const makePriceUpdate = (overrides: Partial<PriceUpdate> = {}): PriceUpdate => ({
  symbol: "SPY",
  price: 450.25,
  timestamp: "2026-02-25T10:00:00Z",
  change: 3.5,
  change_percent: 0.78,
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockUseWebSocket.mockReturnValue({ data: null, isConnected: false });
});

describe("DashboardPage", () => {
  it("renders loading state initially", () => {
    // apiGet never resolves — stays in loading
    mockApiGet.mockReturnValue(new Promise(() => {}));

    render(<DashboardPage />);

    expect(screen.getByText("Market Dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-loading")).toBeInTheDocument();
  });

  it("renders category sections after config loads", async () => {
    mockApiGet.mockResolvedValue({
      categories: [
        {
          name: "equities",
          tickers: [makeTicker()],
        },
        {
          name: "crypto",
          tickers: [
            makeTicker({
              id: 2,
              category: "crypto",
              display_name: "Bitcoin (BTC/USD)",
              symbol: "BTC/USD",
            }),
          ],
        },
      ],
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("category-equities")).toBeInTheDocument();
      expect(screen.getByTestId("category-crypto")).toBeInTheDocument();
    });

    expect(screen.getByText("Equities")).toBeInTheDocument();
    expect(screen.getByText("Crypto")).toBeInTheDocument();
    expect(screen.queryByTestId("dashboard-loading")).not.toBeInTheDocument();
  });
});

describe("TickerCard", () => {
  it("renders with price data", () => {
    const ticker = makeTicker();
    const price = makePriceUpdate();

    render(<TickerCard ticker={ticker} price={price} />);

    expect(screen.getByText("S&P 500 (SPY)")).toBeInTheDocument();
    expect(screen.getByText("$450.25")).toBeInTheDocument();
    expect(screen.getByText("+0.78%")).toBeInTheDocument();
  });

  it("renders with no price data (shows dash)", () => {
    const ticker = makeTicker();

    render(<TickerCard ticker={ticker} price={null} />);

    expect(screen.getByText("S&P 500 (SPY)")).toBeInTheDocument();
    // The em dash character rendered via &mdash;
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it('handles "percentage" display format', () => {
    const ticker = makeTicker({
      display_name: "10Y Treasury (DGS10)",
      symbol: "DGS10",
      display_format: "percentage",
    });
    const price = makePriceUpdate({
      symbol: "DGS10",
      price: 4.35,
      change_percent: -0.02,
    });

    render(<TickerCard ticker={ticker} price={price} />);

    expect(screen.getByText("10Y Treasury (DGS10)")).toBeInTheDocument();
    // percentage format: "4.35%"
    expect(screen.getByText("4.35%")).toBeInTheDocument();
    // change: "-0.02%"
    expect(screen.getByText("-0.02%")).toBeInTheDocument();
  });
});
