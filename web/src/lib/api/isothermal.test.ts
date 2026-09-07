/**
 * RPA is isothermal, but Scientific-Strict does not manufacture pair-level
 * cycling/hold instructions from a generic calculation preset.  The named
 * TwistAmp protocol record owns the isothermal bench handoff.
 */
import { describe, expect, it } from "vitest";

import rpa from "./__fixtures__/historical/rpa__pre-specificity-v5-source-mirrored.json";
import { runResultSchema } from "./types";

describe("an isothermal RPA result reaches the page without a synthetic PCR programme", () => {
  it("parses the historical source-mirrored RPA fixture without making it current authority", () => {
    const parsed = runResultSchema.safeParse(rpa);
    expect(
      parsed.success,
      parsed.success ? "" : JSON.stringify(parsed.error.issues.slice(0, 3)),
    ).toBe(true);
  });

  it("does not put a generic cycling record on the selected primer pair", () => {
    expect((rpa as { pairs: Record<string, unknown>[] }).pairs[0]).not.toHaveProperty("cycling");
  });

  it("keeps the named isothermal conditions in the protocol handoff", () => {
    const protocol = (
      rpa as {
        protocol: {
          selection: string;
          temperature_c: number;
          incubation_minutes: number;
          agitation: { after_minutes: number };
        };
      }
    ).protocol;
    expect(protocol.selection).toMatch(/TwistAmp Basic/);
    expect(protocol.temperature_c).toBe(39);
    expect(protocol.incubation_minutes).toBe(20);
    expect(protocol.agitation.after_minutes).toBe(4);
  });

  it("does not label RPA with a PCR annealing temperature", () => {
    expect(
      (rpa as { pairs: { annealing_temperature: number | null }[] }).pairs[0]!
        .annealing_temperature,
    ).toBeNull();
  });
});
