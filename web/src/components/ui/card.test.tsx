import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card } from "./card";

describe("card surface intent", () => {
  it("marks a default card so the workbench tint can reach it", () => {
    render(<Card className="workbench-card">Default</Card>);
    expect(screen.getByText("Default")).toHaveAttribute("data-surface", "default");
  });

  it("preserves an explicitly chosen background surface", () => {
    render(
      <Card className="workbench-card bg-warning/5" data-testid="custom-card">
        Warning
      </Card>,
    );
    expect(screen.getByTestId("custom-card")).toHaveAttribute("data-surface", "custom");
  });
});
