import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatCurrency,
  formatPercent,
  formatLargeNumber,
  formatChange,
  changeColor,
  formatDate,
  formatRatio,
  formatRelativeTime,
} from "../format";

describe("formatCurrency", () => {
  it("formats positive value", () => {
    expect(formatCurrency(1234.56)).toBe("$1,234.56");
  });

  it("formats negative value", () => {
    expect(formatCurrency(-1234.56)).toBe("-$1,234.56");
  });

  it("returns em dash for null", () => {
    expect(formatCurrency(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatCurrency(undefined)).toBe("\u2014");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0.00");
  });

  it("formats with custom currency", () => {
    expect(formatCurrency(100, "EUR")).toContain("100");
  });
});

describe("formatPercent", () => {
  it("formats positive value", () => {
    expect(formatPercent(12.345)).toBe("12.35%");
  });

  it("formats negative value", () => {
    expect(formatPercent(-5.678)).toBe("-5.68%");
  });

  it("returns em dash for null", () => {
    expect(formatPercent(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatPercent(undefined)).toBe("\u2014");
  });

  it("respects custom decimals", () => {
    expect(formatPercent(12.3456, 3)).toBe("12.346%");
  });
});

describe("formatLargeNumber", () => {
  it("formats billions", () => {
    expect(formatLargeNumber(1_200_000_000)).toBe("1.2B");
  });

  it("formats millions", () => {
    expect(formatLargeNumber(345_600_000)).toBe("345.6M");
  });

  it("formats thousands", () => {
    expect(formatLargeNumber(12_300)).toBe("12.3K");
  });

  it("formats small numbers", () => {
    expect(formatLargeNumber(42)).toBe("42.00");
  });

  it("returns em dash for null", () => {
    expect(formatLargeNumber(null)).toBe("\u2014");
  });

  it("handles negative billions", () => {
    expect(formatLargeNumber(-2_500_000_000)).toBe("-2.5B");
  });
});

describe("formatChange", () => {
  it("formats positive with plus sign", () => {
    expect(formatChange(5.23)).toBe("+5.23%");
  });

  it("formats negative with minus sign", () => {
    expect(formatChange(-2.14)).toBe("-2.14%");
  });

  it("returns em dash for null", () => {
    expect(formatChange(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatChange(undefined)).toBe("\u2014");
  });

  it("formats zero without sign", () => {
    expect(formatChange(0)).toBe("0.00%");
  });
});

describe("changeColor", () => {
  it("returns green for positive", () => {
    expect(changeColor(5)).toBe("text-green-500");
  });

  it("returns red for negative", () => {
    expect(changeColor(-3)).toBe("text-red-500");
  });

  it("returns gray for zero", () => {
    expect(changeColor(0)).toBe("text-gray-500");
  });

  it("returns gray for null", () => {
    expect(changeColor(null)).toBe("text-gray-500");
  });

  it("returns gray for undefined", () => {
    expect(changeColor(undefined)).toBe("text-gray-500");
  });
});

describe("formatDate", () => {
  it("formats valid date string", () => {
    // Use a fixed UTC time to avoid timezone issues
    expect(formatDate("2026-01-15T12:00:00Z")).toBe("Jan 15, 2026");
  });

  it("returns em dash for null", () => {
    expect(formatDate(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatDate(undefined)).toBe("\u2014");
  });

  it("returns em dash for empty string", () => {
    expect(formatDate("")).toBe("\u2014");
  });
});

describe("formatRatio", () => {
  it("formats valid number", () => {
    expect(formatRatio(15.678)).toBe("15.68");
  });

  it("returns N/A for null", () => {
    expect(formatRatio(null)).toBe("N/A");
  });

  it("returns N/A for undefined", () => {
    expect(formatRatio(undefined)).toBe("N/A");
  });

  it("formats zero", () => {
    expect(formatRatio(0)).toBe("0.00");
  });
});

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-02-25T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'Just now' for < 60 seconds", () => {
    expect(formatRelativeTime("2026-02-25T11:59:30Z")).toBe("Just now");
  });

  it("returns minutes for < 1 hour", () => {
    expect(formatRelativeTime("2026-02-25T11:55:00Z")).toBe("5 min ago");
  });

  it("returns hours for < 24 hours", () => {
    expect(formatRelativeTime("2026-02-25T09:00:00Z")).toBe("3 hours ago");
  });

  it("returns singular hour", () => {
    expect(formatRelativeTime("2026-02-25T11:00:00Z")).toBe("1 hour ago");
  });

  it("returns 'Yesterday' for 1 day", () => {
    expect(formatRelativeTime("2026-02-24T12:00:00Z")).toBe("Yesterday");
  });

  it("returns days for > 1 day", () => {
    expect(formatRelativeTime("2026-02-22T12:00:00Z")).toBe("3 days ago");
  });

  it("returns em dash for null", () => {
    expect(formatRelativeTime(null)).toBe("\u2014");
  });

  it("returns em dash for undefined", () => {
    expect(formatRelativeTime(undefined)).toBe("\u2014");
  });

  it("returns em dash for invalid date", () => {
    expect(formatRelativeTime("not-a-date")).toBe("\u2014");
  });

  it("accepts Date objects", () => {
    const fiveMinAgo = new Date("2026-02-25T11:55:00Z");
    expect(formatRelativeTime(fiveMinAgo)).toBe("5 min ago");
  });
});
