import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorState } from "../ErrorState";

describe("ErrorState", () => {
  it("renders error message", () => {
    render(<ErrorState message="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders without retry button when no onRetry", () => {
    render(<ErrorState message="Error" />);
    expect(screen.queryByTestId("retry-button")).not.toBeInTheDocument();
  });

  it("renders retry button when onRetry is provided", () => {
    render(<ErrorState message="Error" onRetry={() => {}} />);
    expect(screen.getByTestId("retry-button")).toBeInTheDocument();
  });

  it("calls onRetry when retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Error" onRetry={onRetry} />);
    fireEvent.click(screen.getByTestId("retry-button"));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
