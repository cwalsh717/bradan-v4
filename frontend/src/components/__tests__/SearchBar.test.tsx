import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(),
}));

import { SearchBar } from "../SearchBar";
import { apiGet } from "@/lib/api";

const mockApiGet = vi.mocked(apiGet);

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

describe("SearchBar", () => {
  it("renders search input", () => {
    render(<SearchBar />);
    expect(screen.getByPlaceholderText("Search stocks...")).toBeInTheDocument();
  });

  it("shows dropdown with results on typing", async () => {
    mockApiGet.mockResolvedValueOnce([
      { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", cached: true },
    ]);

    render(<SearchBar />);
    const input = screen.getByPlaceholderText("Search stocks...");

    fireEvent.change(input, { target: { value: "AA" } });

    // Advance past debounce
    vi.advanceTimersByTime(350);

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    });
  });

  it("shows 'No results' for empty results", async () => {
    mockApiGet.mockResolvedValueOnce([]);

    render(<SearchBar />);
    const input = screen.getByPlaceholderText("Search stocks...");

    fireEvent.change(input, { target: { value: "ZZZZ" } });

    vi.advanceTimersByTime(350);

    await waitFor(() => {
      expect(screen.getByText("No results")).toBeInTheDocument();
    });
  });

  it("navigates on selection", async () => {
    mockApiGet.mockResolvedValueOnce([
      { symbol: "AAPL", name: "Apple Inc.", exchange: "NASDAQ", cached: false },
    ]);

    render(<SearchBar />);
    const input = screen.getByPlaceholderText("Search stocks...");

    fireEvent.change(input, { target: { value: "AA" } });

    vi.advanceTimersByTime(350);

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });

    fireEvent.mouseDown(screen.getByText("AAPL"));

    expect(mockPush).toHaveBeenCalledWith("/stocks/AAPL");
  });

  it("does not search with fewer than 2 characters", () => {
    render(<SearchBar />);
    const input = screen.getByPlaceholderText("Search stocks...");

    fireEvent.change(input, { target: { value: "A" } });

    vi.advanceTimersByTime(350);

    expect(mockApiGet).not.toHaveBeenCalled();
  });
});
