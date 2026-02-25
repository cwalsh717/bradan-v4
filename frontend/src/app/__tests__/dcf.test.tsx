import { Suspense } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockDCFResult = {
  symbol: "AAPL",
  company_name: "Apple Inc.",
  value_per_share: 200,
  current_price: 175,
  implied_upside: 0.1429,
  verdict: "Undervalued",
  computed_inputs: {
    wacc: 0.09,
    levered_beta: 1.15,
    expected_growth: 0.1,
    effective_tax_rate: 0.21,
    computed_tax_rate: 0.21,
    ebit_after_tax: 100000000000,
    reinvestment: 25000000000,
    reinvestment_rate: 0.25,
    return_on_capital: 0.4,
    cost_of_equity: 0.1,
    synthetic_rating: "AAA",
    default_spread: 0.006,
    cost_of_debt_pretax: 0.045,
    cost_of_debt_aftertax: 0.036,
    debt_ratio: 0.2,
    market_cap: 2800000000000,
  },
  projections: [
    {
      year: 1,
      growth_rate: 0.1,
      revenue: 400000000000,
      ebit: 120000000000,
      ebit_after_tax: 95000000000,
      reinvestment_rate: 0.25,
      reinvestment: 24000000000,
      fcff: 71000000000,
      beta: 1.15,
      cost_of_equity: 0.1,
      debt_ratio: 0.2,
      wacc: 0.09,
      roc: 0.4,
      pv_factor: 0.917,
      pv_fcff: 65100000000,
    },
    {
      year: 2,
      growth_rate: 0.09,
      revenue: 436000000000,
      ebit: 130800000000,
      ebit_after_tax: 103332000000,
      reinvestment_rate: 0.24,
      reinvestment: 24800000000,
      fcff: 78532000000,
      beta: 1.12,
      cost_of_equity: 0.098,
      debt_ratio: 0.2,
      wacc: 0.088,
      roc: 0.38,
      pv_factor: 0.843,
      pv_fcff: 66200000000,
    },
  ],
  terminal: {
    terminal_growth: 0.03,
    terminal_roc: 0.09,
    terminal_wacc: 0.085,
    terminal_reinvestment_rate: 0.33,
    terminal_fcff: 90000000000,
    terminal_value: 1636000000000,
    pv_terminal: 750000000000,
  },
  equity_bridge: {
    enterprise_value: 2900000000000,
    plus_cash: 60000000000,
    minus_debt: 120000000000,
    minus_minority_interests: 0,
    minus_preferred_stock: 0,
    equity_value: 2840000000000,
    shares_outstanding: 15000000000,
    value_per_share: 200,
  },
  scenario: "moderate",
  forecast_years: 10,
  source_fiscal_date: "2025-06-30",
  computed_at: "2026-02-25T12:00:00Z",
  pv_operating_cashflows: 600000000000,
  terminal_value_pct: 0.55,
};

const mockOvervalued = {
  ...mockDCFResult,
  value_per_share: 150,
  current_price: 200,
  implied_upside: -0.25,
  verdict: "Overvalued",
};

const mockSensitivity = {
  wacc_values: [0.07, 0.08, 0.09, 0.1, 0.11],
  growth_values: [0.02, 0.025, 0.03, 0.035, 0.04],
  matrix: [
    [250, 230, 210, 195, 180],
    [260, 240, 220, 200, 185],
    [275, 250, 200, 210, 190],
    [290, 265, 240, 220, 200],
    [310, 280, 255, 230, 210],
  ],
  base_wacc: 0.09,
  base_growth: 0.03,
  base_value: 200,
};

const mockConstraints = {
  forecast_years: { min: 5, max: 15, step: 1 },
  stable_growth_rate: { min: 0.01, max: 0.05, step: 0.005 },
  stable_beta: { min: 0.5, max: 2.0, step: 0.1 },
  stable_roc: { min: 0.05, max: 0.5, step: 0.01 },
  stable_debt_to_equity: { min: 0, max: 1.0, step: 0.05 },
  marginal_tax_rate: { min: 0.1, max: 0.4, step: 0.01 },
};

const mockApiFetch = vi.fn();

vi.mock("@/lib/api", () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  apiGet: vi.fn(),
  API_BASE: "http://localhost:8000",
}));

// ---------------------------------------------------------------------------
// Component imports (after mock)
// ---------------------------------------------------------------------------

import { Headline } from "@/components/dcf/Headline";
import { AssumptionCards } from "@/components/dcf/AssumptionCards";
import { ScenarioSelector } from "@/components/dcf/ScenarioSelector";
import { EquityBridge } from "@/components/dcf/EquityBridge";
import { ProjectionTable } from "@/components/dcf/ProjectionTable";
import { SensitivityTable } from "@/components/dcf/SensitivityTable";
import DCFPage from "@/app/dcf/[symbol]/page";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Headline", () => {
  it("renders headline with verdict badge", () => {
    render(<Headline result={mockDCFResult} />);
    expect(screen.getByText("Undervalued")).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
    expect(screen.getByText("(AAPL)")).toBeInTheDocument();
  });

  it("shows correct upside color for positive upside", () => {
    render(<Headline result={mockDCFResult} />);
    const upsideEl = screen.getByTestId("implied-upside");
    expect(upsideEl.className).toContain("text-green-500");
  });

  it("shows correct upside color for negative upside (overvalued)", () => {
    render(<Headline result={mockOvervalued} />);
    const upsideEl = screen.getByTestId("implied-upside");
    expect(upsideEl.className).toContain("text-red-500");
  });

  it("shows overvalued verdict badge in red", () => {
    render(<Headline result={mockOvervalued} />);
    const badge = screen.getByText("Overvalued");
    expect(badge.className).toContain("bg-red-100");
  });

  it("shows fairly valued verdict badge in gray", () => {
    const fairlyValued = {
      ...mockDCFResult,
      implied_upside: 0,
      verdict: "Fairly Valued",
    };
    render(<Headline result={fairlyValued} />);
    const badge = screen.getByText("Fairly Valued");
    expect(badge.className).toContain("bg-gray-100");
  });
});

describe("AssumptionCards", () => {
  it("renders key metrics with tooltip labels", () => {
    render(<AssumptionCards result={mockDCFResult} />);
    expect(screen.getByTestId("assumption-cards")).toBeInTheDocument();
    expect(screen.getByText("Cost of Running the Business")).toBeInTheDocument();
    expect(screen.getByText("Risk Level")).toBeInTheDocument();
    expect(screen.getByText("Long-Term Growth")).toBeInTheDocument();
    expect(screen.getByText("Expected Growth")).toBeInTheDocument();
    expect(screen.getByText("Effective Tax Rate")).toBeInTheDocument();
  });

  it("renders WACC value correctly", () => {
    render(<AssumptionCards result={mockDCFResult} />);
    // WACC is 0.09 * 100 = 9.00%
    expect(screen.getByText("9.00%")).toBeInTheDocument();
  });
});

describe("ScenarioSelector", () => {
  it("renders 3 scenario buttons", () => {
    const onSelect = vi.fn();
    render(
      <ScenarioSelector activeScenario="moderate" onSelect={onSelect} />,
    );
    expect(screen.getByText("Conservative")).toBeInTheDocument();
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(screen.getByText("Optimistic")).toBeInTheDocument();
  });

  it("highlights active scenario", () => {
    const onSelect = vi.fn();
    render(
      <ScenarioSelector activeScenario="moderate" onSelect={onSelect} />,
    );
    const moderateBtn = screen.getByText("Moderate");
    expect(moderateBtn.className).toContain("bg-blue-600");
  });

  it("calls onSelect when a button is clicked", () => {
    const onSelect = vi.fn();
    render(
      <ScenarioSelector activeScenario="moderate" onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByText("Conservative"));
    expect(onSelect).toHaveBeenCalledWith("conservative");
  });
});

describe("EquityBridge", () => {
  it("renders all bridge steps", () => {
    render(<EquityBridge bridge={mockDCFResult.equity_bridge} />);
    expect(screen.getByTestId("equity-bridge")).toBeInTheDocument();
    expect(screen.getByText("Enterprise Value")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByText("Debt")).toBeInTheDocument();
    expect(screen.getByText("Minority Interests")).toBeInTheDocument();
    expect(screen.getByText("Preferred Stock")).toBeInTheDocument();
    expect(screen.getByText("Equity Value")).toBeInTheDocument();
    expect(screen.getByText("Shares")).toBeInTheDocument();
    expect(screen.getByText("Value/Share")).toBeInTheDocument();
  });
});

describe("ProjectionTable", () => {
  it("renders year columns", () => {
    render(
      <ProjectionTable
        projections={mockDCFResult.projections}
        terminal={mockDCFResult.terminal}
      />,
    );
    expect(screen.getByTestId("projection-table")).toBeInTheDocument();
    // Header columns
    expect(screen.getByText("Year")).toBeInTheDocument();
    expect(screen.getByText("Growth")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("EBIT")).toBeInTheDocument();
    expect(screen.getByText("FCFF")).toBeInTheDocument();
    // Year rows
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    // Terminal row
    expect(screen.getByText("Terminal")).toBeInTheDocument();
  });
});

describe("SensitivityTable", () => {
  it("renders matrix with highlighted base case", () => {
    render(
      <SensitivityTable
        matrix={mockSensitivity}
        currentPrice={175}
      />,
    );
    expect(screen.getByTestId("sensitivity-table")).toBeInTheDocument();
    // Base case cell should have ring-2
    const baseCell = screen.getByTestId("base-case-cell");
    expect(baseCell).toBeInTheDocument();
    expect(baseCell.className).toContain("ring-2");
    expect(baseCell.className).toContain("ring-blue-500");
  });

  it("colors cells green when above current price", () => {
    render(
      <SensitivityTable
        matrix={mockSensitivity}
        currentPrice={175}
      />,
    );
    // Most values in the matrix are above 175, so most cells should be green
    const baseCell = screen.getByTestId("base-case-cell");
    expect(baseCell.className).toContain("bg-green-50");
  });
});

describe("DCF Page integration", () => {
  beforeEach(() => {
    mockApiFetch.mockReset();
  });

  it("renders headline with verdict after data loads", async () => {
    mockApiFetch.mockResolvedValue({
      data: mockDCFResult,
      data_as_of: "2026-02-25",
      next_refresh: null,
    });

    await act(async () => {
      render(
        <Suspense fallback={<div>Loading...</div>}>
          <DCFPage params={Promise.resolve({ symbol: "AAPL" })} />
        </Suspense>,
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Undervalued")).toBeInTheDocument();
      expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
    });
  });

  it("shows error state when API fails", async () => {
    mockApiFetch.mockRejectedValue(new Error("Network error"));

    await act(async () => {
      render(
        <Suspense fallback={<div>Loading...</div>}>
          <DCFPage params={Promise.resolve({ symbol: "AAPL" })} />
        </Suspense>,
      );
    });

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
