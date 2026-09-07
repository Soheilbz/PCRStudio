import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModuleStatusBadge } from "./module-status-badge";

describe("ModuleStatusBadge", () => {
  it("says which status it is showing", () => {
    render(<ModuleStatusBadge status="planned" />);
    expect(screen.getByText("Planned")).toBeInTheDocument();
  });

  it("distinguishes an unvalidated implementation from a validated one", () => {
    const { rerender } = render(<ModuleStatusBadge status="experimental" />);
    expect(screen.getByText("Needs review")).toBeInTheDocument();
    rerender(<ModuleStatusBadge status="stable" />);
    expect(screen.getByText("Stable")).toBeInTheDocument();
    expect(screen.queryByText("Needs review")).not.toBeInTheDocument();
  });
});
