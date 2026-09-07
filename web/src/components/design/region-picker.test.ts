/**
 * The packed string is the only state the avoided-region rows have, so the
 * round trip has to survive rows that are not finished yet.
 */
import { describe, expect, it } from "vitest";

import { packAvoided, parseAvoided } from "./region-picker";

describe("avoided regions", () => {
  it("keeps a row that has just been added and holds no numbers yet", () => {
    // Filtering incomplete rows out here deleted the row on the click that
    // created it, which made the control impossible to use at all.
    const packed = packAvoided([{ from: "", to: "" }]);
    expect(parseAvoided(packed)).toHaveLength(1);
  });

  it("keeps a row with only its first number typed", () => {
    expect(parseAvoided(packAvoided([{ from: "400", to: "" }]))).toEqual([{ from: "400", to: "" }]);
  });

  it("round-trips several finished rows in order", () => {
    const regions = [
      { from: "10", to: "40" },
      { from: "600", to: "700" },
    ];
    expect(parseAvoided(packAvoided(regions))).toEqual(regions);
  });

  it("reads no rows from an empty string rather than one blank row", () => {
    expect(parseAvoided("")).toEqual([]);
  });
});
