import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingSkeleton } from "../LoadingSkeleton";

describe("LoadingSkeleton", () => {
  it("renders card variant by default", () => {
    render(<LoadingSkeleton />);
    expect(screen.getByTestId("skeleton-card")).toBeInTheDocument();
  });

  it("renders table variant", () => {
    render(<LoadingSkeleton variant="table" />);
    expect(screen.getByTestId("skeleton-table")).toBeInTheDocument();
  });

  it("renders chart variant", () => {
    render(<LoadingSkeleton variant="chart" />);
    expect(screen.getByTestId("skeleton-chart")).toBeInTheDocument();
  });

  it("renders text variant", () => {
    render(<LoadingSkeleton variant="text" />);
    expect(screen.getByTestId("skeleton-text")).toBeInTheDocument();
  });

  it("renders multiple skeletons with count", () => {
    const { container } = render(<LoadingSkeleton variant="card" count={3} />);
    const cards = container.querySelectorAll(".animate-pulse");
    expect(cards.length).toBe(3);
  });
});
