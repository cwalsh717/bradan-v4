import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiFetch, apiGet, ApiError, API_BASE } from "../api";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

describe("apiFetch", () => {
  it("prepends API_BASE to path", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ data: {}, data_as_of: "2024-01-01", next_refresh: null }),
    });

    await apiFetch("/api/v1/tickers");

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/api/v1/tickers`,
      expect.objectContaining({
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
  });

  it("returns parsed ApiResponse on success", async () => {
    const mockBody = {
      data: { symbol: "AAPL" },
      data_as_of: "2024-01-01T00:00:00Z",
      next_refresh: "2024-01-02T00:00:00Z",
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockBody,
    });

    const result = await apiFetch("/api/v1/stock/AAPL");

    expect(result).toEqual(mockBody);
    expect(result.data).toEqual({ symbol: "AAPL" });
    expect(result.data_as_of).toBe("2024-01-01T00:00:00Z");
    expect(result.next_refresh).toBe("2024-01-02T00:00:00Z");
  });

  it("throws ApiError with status and detail on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "Stock not found" }),
    });

    try {
      await apiFetch("/api/v1/stock/INVALID");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(404);
      expect(apiErr.detail).toBe("Stock not found");
      expect(apiErr.name).toBe("ApiError");
    }
  });

  it("handles non-JSON error responses gracefully", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not JSON");
      },
    });

    try {
      await apiFetch("/api/v1/broken");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(500);
      expect(apiErr.detail).toBe("Internal Server Error");
    }
  });
});

describe("apiGet", () => {
  it("returns just the data field from the envelope", async () => {
    const stockData = { symbol: "AAPL", name: "Apple Inc." };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: stockData,
        data_as_of: "2024-01-01T00:00:00Z",
        next_refresh: null,
      }),
    });

    const result = await apiGet("/api/v1/stock/AAPL");

    expect(result).toEqual(stockData);
  });
});
