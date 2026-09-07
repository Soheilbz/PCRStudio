import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OrderActions } from "./order-actions";

describe("OrderActions", () => {
  it("keeps its hook order when an order sheet appears after an empty result", () => {
    const view = render(<OrderActions lines={[]} />);

    view.rerender(
      <OrderActions
        lines={[{ name: "primer", sequence: "ACGT", length: 4, gc_percent: 50, tm: 10 }]}
      />,
    );

    expect(screen.getByRole("button", { name: /copy 1 oligo/i })).toBeInTheDocument();
  });
});
