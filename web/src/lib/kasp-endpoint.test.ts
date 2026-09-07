import { describe, expect, it } from "vitest";

import { parseKaspEndpoint } from "./kasp-endpoint";

describe("KASP endpoint evidence parser", () => {
  it("preserves provider/software calls without inventing genotype calls", () => {
    const parsed = parseKaspEndpoint(
      "sample,FAM,HEX,provider,software\nA1,1200,340,LGC,Hydrocycler\n",
    );

    expect(parsed.rows).toHaveLength(1);
    expect(parsed.rows[0]).toMatchObject({
      sampleId: "A1",
      fam: 1200,
      hex: 340,
      provider: "LGC",
      software: "Hydrocycler",
    });
    expect(parsed.rows[0]?.call).toBeUndefined();
    expect(parsed.callSummary).toEqual({ unreviewed: 1 });
  });
});
