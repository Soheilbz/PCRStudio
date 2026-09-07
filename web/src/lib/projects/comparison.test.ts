/**
 * The comparison arithmetic, against real API responses.
 *
 * The fixtures are captured from a running API, so what is being checked is
 * that the extraction agrees with captured result shapes — not with a
 * hand-written object written while looking at the extractor. The one thing a
 * comparison must not do is quietly compare the wrong fields and flag nothing:
 * a table where every row reads "equal" is worse than no table at all.
 */

import { describe, expect, it } from "vitest";

import historicalLoopSetFixture from "@/lib/api/__fixtures__/historical/lamp__pre-diagnostic-temperature-contract.json";
import historicalProbeFixture from "@/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
import { loopSetResultSchema, probeResultSchema } from "@/lib/api/types";

import {
  buildComparisonRows,
  COMPARISON_EPSILON,
  firstPair,
  isFlagged,
  parseCompareIds,
} from "./comparison";

const base = () => firstPair(probeResultSchema.parse(historicalProbeFixture));
if (!base()) throw new Error("the captured probe response has no comparable pair in it");

describe("flagging", () => {
  it("flags nothing when both runs agree on everything", () => {
    const metrics = base()!;
    for (const row of buildComparisonRows(metrics, metrics)) {
      expect(isFlagged(row, "a")).toBe(false);
      expect(isFlagged(row, "b")).toBe(false);
    }
  });

  it("flags a 0.6 °C gap in a melting temperature", () => {
    const a = base()!;
    const b = { ...a, leftTm: a.leftTm + 0.6 };
    // Both sides are shaded: the difference belongs to neither cell alone.
    const row = buildComparisonRows(a, b).find((entry) => entry.label === "Left primer Tm");
    expect(row && isFlagged(row, "a")).toBe(true);
    expect(row && isFlagged(row, "b")).toBe(true);
  });

  it("leaves a drift inside the threshold quiet", () => {
    const a = base()!;
    const b = { ...a, rightTm: a.rightTm + (COMPARISON_EPSILON - 0.1) };
    const row = buildComparisonRows(a, b).find((entry) => entry.label === "Right primer Tm");
    expect(row && isFlagged(row, "a")).toBe(false);
  });

  it("treats a missing figure on either side as no difference at all", () => {
    const a = base()!;
    const b = { ...a, productSize: null };
    const row = buildComparisonRows(a, b).find((entry) => entry.label === "Product size");
    expect(row && isFlagged(row, "a")).toBe(false);
  });
});

describe("missing fields", () => {
  it("renders an unavailable metric as absent, with a reason rather than a zero", () => {
    // A probe run measures three oligos but reports no cross-dimer figure;
    // that has to arrive as "—" plus why, never as some other row's number.
    const a = base()!;
    const rows = buildComparisonRows(a, a);
    const crossDimer = rows.find((entry) => entry.label === "Cross-dimer ΔG");
    expect(crossDimer?.a.text).toBeNull();
    expect(crossDimer?.a.numeric).toBeNull();
    expect(crossDimer?.missingBecause).toBeTruthy();
  });

  it("blames the whole column when one side has no comparable pair", () => {
    const a = base()!;
    const rows = buildComparisonRows(a, null);
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row.b.text).toBeNull();
      expect(row.missingBecause).toMatch(/does not produce a comparable primer pair/i);
    }
  });

  it("produces no rows at all when neither side has one", () => {
    expect(buildComparisonRows(null, null)).toEqual([]);
  });
});

describe("engines without a comparable pair", () => {
  it("says so for a loop set rather than reading the wrong fields", () => {
    // A LAMP result carries six regions of two-to-five oligos; there is no
    // left/right pair in it anywhere, and inventing one would be comparing
    // things that are not the same kind of thing.
    expect(firstPair(loopSetResultSchema.parse(historicalLoopSetFixture))).toBeNull();
  });
});

describe("parseCompareIds", () => {
  const runs = [{ id: "a" }, { id: "b" }, { id: "c" }];

  it("keeps only ids this project actually has", () => {
    // The same rule opening a single run applies: an unknown id is not looked
    // up, which is what stops `?compare=` probing for other people's runs.
    expect(parseCompareIds("a,not-here,c", runs)).toEqual(["a", "c"]);
  });

  it("takes at most two", () => {
    expect(parseCompareIds("c,b,a", runs)).toEqual(["c", "b"]);
  });

  it("ignores repeats and empty segments", () => {
    expect(parseCompareIds("a,,a,", runs)).toEqual(["a"]);
  });

  it("reads nothing from a missing parameter", () => {
    expect(parseCompareIds(undefined, runs)).toEqual([]);
  });
});
