import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GlossaryTooltip } from "../GlossaryTooltip";

describe("GlossaryTooltip", () => {
  it("renders the technical label for a known term", () => {
    render(<GlossaryTooltip term="wacc" />);
    expect(screen.getByText("WACC")).toBeInTheDocument();
  });

  it("renders children when provided", () => {
    render(
      <GlossaryTooltip term="wacc">
        <span>Custom Label</span>
      </GlossaryTooltip>,
    );
    expect(screen.getByText("Custom Label")).toBeInTheDocument();
  });

  it("shows tooltip content on hover", () => {
    render(<GlossaryTooltip term="pe_ratio" />);

    const trigger = screen.getByText("P/E");
    fireEvent.mouseEnter(trigger);

    expect(screen.getByText("Price-to-Earnings")).toBeInTheDocument();
    expect(
      screen.getByText(/Share price divided by earnings per share/),
    ).toBeInTheDocument();
  });

  it("hides tooltip on mouse leave", () => {
    render(<GlossaryTooltip term="pe_ratio" />);

    const trigger = screen.getByText("P/E");
    fireEvent.mouseEnter(trigger);
    expect(screen.getByText("Price-to-Earnings")).toBeInTheDocument();

    fireEvent.mouseLeave(trigger);
    expect(screen.queryByText("Price-to-Earnings")).not.toBeInTheDocument();
  });

  it("handles unknown term gracefully", () => {
    render(<GlossaryTooltip term="unknown_term_xyz" />);
    expect(screen.getByText("unknown_term_xyz")).toBeInTheDocument();
  });

  it("handles unknown term with children gracefully", () => {
    render(
      <GlossaryTooltip term="unknown_term_xyz">
        <span>Child content</span>
      </GlossaryTooltip>,
    );
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  it("tooltip has the correct display label and description for beta", () => {
    render(<GlossaryTooltip term="beta" />);

    const trigger = screen.getByText("Beta");
    fireEvent.mouseEnter(trigger);

    expect(screen.getByText("Risk (Beta)")).toBeInTheDocument();
    expect(
      screen.getByText(/measure of a stock's volatility/),
    ).toBeInTheDocument();
  });
});
