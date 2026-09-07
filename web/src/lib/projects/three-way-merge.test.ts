import { describe, expect, it } from "vitest";
import { threeWayMerge } from "./three-way-merge";

describe("threeWayMerge", () => {
  it("combines independent field edits", () => {
    expect(
      threeWayMerge(
        { template: "AAA", polymerase: "q5" },
        { template: "CCC", polymerase: "q5" },
        { template: "AAA", polymerase: "taq" },
      ),
    ).toEqual({ merged: { polymerase: "taq", template: "CCC" }, conflicts: [] });
  });

  it("accepts the same edit made on both sides", () => {
    expect(threeWayMerge({ x: "a" }, { x: "b" }, { x: "b" })).toEqual({
      merged: { x: "b" },
      conflicts: [],
    });
  });

  it("reports divergent edits of the same field", () => {
    expect(threeWayMerge({ x: "a" }, { x: "b" }, { x: "c" })).toEqual({
      merged: { x: "c" },
      conflicts: ["x"],
    });
  });
});
