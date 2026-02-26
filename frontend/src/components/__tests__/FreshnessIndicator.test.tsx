import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { FreshnessIndicator } from "../FreshnessIndicator";

describe("FreshnessIndicator", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-02-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null for null timestamp", () => {
    const { container } = render(<FreshnessIndicator timestamp={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for undefined timestamp", () => {
    const { container } = render(<FreshnessIndicator timestamp={undefined} />);
    expect(container.innerHTML).toBe("");
  });

  it("returns null for invalid date string", () => {
    const { container } = render(<FreshnessIndicator timestamp="not-a-date" />);
    expect(container.innerHTML).toBe("");
  });

  it("shows green dot for fresh data (< 1 hour)", () => {
    const fiveMinAgo = new Date("2026-02-25T11:55:00Z").toISOString();
    render(<FreshnessIndicator timestamp={fiveMinAgo} />);
    const indicator = screen.getByTestId("freshness-indicator");
    expect(indicator).toBeInTheDocument();
    const dot = indicator.querySelector("span.rounded-full");
    expect(dot?.className).toContain("bg-green-500");
  });

  it("shows yellow dot for aging data (1-24 hours)", () => {
    const threeHoursAgo = new Date("2026-02-25T09:00:00Z").toISOString();
    render(<FreshnessIndicator timestamp={threeHoursAgo} />);
    const indicator = screen.getByTestId("freshness-indicator");
    const dot = indicator.querySelector("span.rounded-full");
    expect(dot?.className).toContain("bg-yellow-500");
  });

  it("shows red dot for stale data (> 24 hours)", () => {
    const twoDaysAgo = new Date("2026-02-23T12:00:00Z").toISOString();
    render(<FreshnessIndicator timestamp={twoDaysAgo} />);
    const indicator = screen.getByTestId("freshness-indicator");
    const dot = indicator.querySelector("span.rounded-full");
    expect(dot?.className).toContain("bg-red-500");
  });

  it("accepts Date objects", () => {
    const recent = new Date("2026-02-25T11:50:00Z");
    render(<FreshnessIndicator timestamp={recent} />);
    expect(screen.getByTestId("freshness-indicator")).toBeInTheDocument();
  });
});
