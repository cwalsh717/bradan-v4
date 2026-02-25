import { describe, it, expect } from "vitest";
import type {
  DashboardTicker,
  PriceUpdate,
  StockProfile,
  SearchResult,
} from "../types";

describe("types", () => {
  it("DashboardTicker has expected shape", () => {
    const ticker: DashboardTicker = {
      id: 1,
      category: "equities",
      display_name: "S&P 500",
      symbol: "SPY",
      data_source: "twelvedata_ws",
      display_format: "price",
      display_order: 1,
      is_active: true,
    };
    expect(ticker.symbol).toBe("SPY");
    expect(ticker.id).toBe(1);
    expect(ticker.category).toBe("equities");
    expect(ticker.is_active).toBe(true);
  });

  it("PriceUpdate has expected shape", () => {
    const update: PriceUpdate = {
      symbol: "AAPL",
      price: 178.5,
      timestamp: "2024-01-15T10:30:00Z",
      change: 2.3,
      change_percent: 1.3,
    };
    expect(update.symbol).toBe("AAPL");
    expect(update.price).toBe(178.5);
    expect(update.timestamp).toBe("2024-01-15T10:30:00Z");
    expect(update.change).toBe(2.3);
    expect(update.change_percent).toBe(1.3);
  });

  it("PriceUpdate works without optional fields", () => {
    const update: PriceUpdate = {
      symbol: "MSFT",
      price: 400.0,
      timestamp: "2024-01-15T10:30:00Z",
    };
    expect(update.change).toBeUndefined();
    expect(update.change_percent).toBeUndefined();
  });

  it("StockProfile has expected shape", () => {
    const profile: StockProfile = {
      symbol: "AAPL",
      name: "Apple Inc.",
      exchange: "NASDAQ",
      sector: "Technology",
      industry: "Consumer Electronics",
      currency: "USD",
    };
    expect(profile.symbol).toBe("AAPL");
    expect(profile.name).toBe("Apple Inc.");
    expect(profile.exchange).toBe("NASDAQ");
    expect(profile.sector).toBe("Technology");
    expect(profile.industry).toBe("Consumer Electronics");
    expect(profile.currency).toBe("USD");
  });

  it("SearchResult has expected shape", () => {
    const result: SearchResult = {
      symbol: "AAPL",
      name: "Apple Inc.",
      exchange: "NASDAQ",
      cached: true,
    };
    expect(result.symbol).toBe("AAPL");
    expect(result.name).toBe("Apple Inc.");
    expect(result.exchange).toBe("NASDAQ");
    expect(result.cached).toBe(true);
  });
});
