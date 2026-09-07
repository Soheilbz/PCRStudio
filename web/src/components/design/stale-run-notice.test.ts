import { describe, expect, it } from "vitest";

import junctionFixture from "@/lib/api/__fixtures__/historical/gibson-assembly__pre-e5510-orderability-contract.json";
import historicalProbeFixture from "@/lib/api/__fixtures__/historical/qpcr-probe__unbound-pre-chemistry.json";
import { junctionResultSchema, probeResultSchema, type RunResult } from "@/lib/api/types";

import { staleRun } from "./stale-run-notice";

/**
 * The marker for a run computed before its assay was applied.
 *
 * What makes this checkable rather than a guess: the preparation those runs
 * skipped is the same code that writes `assay.id`, so an empty one is a run
 * that skipped it. Fourteen of the fifteen runs in the development database
 * carried the empty marker; the one that did not was made after the fix.
 *
 * The case worth protecting is the false positive. One engine never emits an
 * assay block for any run, and reading that absence as evidence would put a
 * warning on every consensus design that nobody could act on.
 */
describe("the marker", () => {
  it("clears a run that carries its assay", () => {
    const good = probeResultSchema.parse(historicalProbeFixture) as RunResult;
    expect(staleRun(good)).toBe(false);
  });

  it("flags a run whose assay id is empty", () => {
    // What the broken path stored: the engine ran, the profile did not reach it.
    const parsed = probeResultSchema.parse(historicalProbeFixture);
    const broken = {
      ...parsed,
      assay: { ...parsed.assay, id: "", name: "" },
    } as RunResult;
    expect(staleRun(broken)).toBe(true);
  });

  it("flags a run with no assay key at all", () => {
    const parsed = junctionResultSchema.parse(junctionFixture);
    const { assay: _dropped, ...without } = parsed;
    expect(staleRun({ ...without, assay: undefined } as RunResult)).toBe(true);
  });

  it("does not flag an engine that never emits an assay", () => {
    // A field that is always absent is not evidence of anything. Warning on
    // every one of these runs would be a warning nobody could act on, on
    // designs that were never broken.
    const consensus = {
      engine: "consensus-pair",
      alignment: {
        sequences: 3,
        columns: 900,
        names: [],
        gapped_columns: 0,
        conserved_columns: 900,
      },
    } as unknown as RunResult;
    expect(staleRun(consensus)).toBe(false);
  });
});
