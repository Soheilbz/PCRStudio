import { describe, expect, it } from "vitest";

import { countAssayDesigns } from "./result-count";

describe("assay-level result counting", () => {
  it("counts nested alternatives rather than missing the nests array", () => {
    expect(countAssayDesigns({ engine: "nested", nests: [{}, {}] } as never)).toBe(2);
  });

  it("counts a tiling scheme as one design, not one result per tile", () => {
    expect(countAssayDesigns({ engine: "tiling-scheme", tiles: [{}, {}, {}] } as never)).toBe(1);
    expect(countAssayDesigns({ engine: "tiling-scheme", tiles: [] } as never)).toBe(0);
  });

  it("counts a Gibson assembly as one plan, not one result per junction", () => {
    expect(
      countAssayDesigns({
        engine: "junction-primers",
        junctions: [{}, {}, {}],
        primers: [],
      } as never),
    ).toBe(1);
  });
});
