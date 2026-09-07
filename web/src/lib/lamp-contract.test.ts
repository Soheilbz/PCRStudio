import { describe, expect, it } from "vitest";

import {
  diffLampNumericPreview,
  LAMP_BENCH_FIELD_MAP,
  LAMP_DNA_ONLY_PROTOCOLS,
  LAMP_RNA_ONLY_PROTOCOLS,
  lampBenchOptimizationRange,
  lampProtocolDirectMatrix,
  lampProtocolForbidsChemistry,
  lampProtocolForbidsReadout,
  lampProtocolFormulationAllowed,
  lampProtocolSupportsSubstrate,
  lampReadoutChemistryBranch,
  lampScenarioIssueOwner,
  lampScenarioIssues,
  resolveLampNumericPreview,
} from "./lamp-contract";

describe("LAMP browser compatibility contract", () => {
  it("retains the reviewed substrate partition", () => {
    expect(LAMP_DNA_ONLY_PROTOCOLS.size).toBe(35);
    expect(LAMP_RNA_ONLY_PROTOCOLS).toEqual(
      new Set(["eiken-lmp244", "jena-pcr540", "jena-pcr541", "nippon-dr0701"]),
    );
    for (const id of [
      "optigene-iso004",
      "optigene-dr004",
      "optigene-iso004-lyo",
      "meridian-mdx118",
    ]) {
      expect(LAMP_DNA_ONLY_PROTOCOLS.has(id)).toBe(true);
      expect(lampProtocolSupportsSubstrate(id, true)).toBe(false);
    }
    expect(lampProtocolSupportsSubstrate("takara-rr385", true)).toBe(true);
    expect(lampProtocolSupportsSubstrate("eiken-lmp244", false)).toBe(false);
  });

  it("models special formulation authority without making every protocol air-dryable", () => {
    expect(lampProtocolFormulationAllowed("meridian-mdx126", "air-dryable")).toBe(true);
    expect(lampProtocolFormulationAllowed("meridian-mdx126", "liquid")).toBe(true);
    expect(lampProtocolFormulationAllowed("meridian-mdx126", "lyophilized")).toBe(false);
    expect(lampProtocolFormulationAllowed("meridian-mdx118", "lyophilized")).toBe(true);
    expect(lampProtocolFormulationAllowed("neb-m0275", "assembled-enzyme")).toBe(true);
    expect(lampProtocolFormulationAllowed("neb-e1700", "liquid")).toBe(true);
    expect(lampProtocolFormulationAllowed("", "liquid")).toBe(false);
  });

  it("keeps direct specimen authority matrix-specific", () => {
    expect(lampProtocolDirectMatrix("meridian-mdx126")).toBe("blood-plasma-serum");
    expect(lampProtocolDirectMatrix("meridian-mdx134")).toBe("saliva-sputum");
    expect(lampProtocolDirectMatrix("optigene-iso001-lnl")).toBe("koh-lysate");
    expect(lampProtocolDirectMatrix("neb-e1700")).toBeUndefined();
  });

  it("mirrors hard readout chemistry incompatibilities", () => {
    expect(lampProtocolForbidsReadout("takara-rr385", "turbidity")).toBe(true);
    expect(lampProtocolForbidsChemistry("takara-rr385", "turbidity-pyrophosphate")).toBe(true);
    expect(lampProtocolForbidsChemistry("neb-m1712", "hydroxynaphthol-blue")).toBe(true);
    expect(lampReadoutChemistryBranch("tb-green")).toBe("fluorescence");
    expect(lampReadoutChemistryBranch("calcein")).toBe("colorimetric");
  });

  it("exposes only source-bounded bench overrides", () => {
    expect(LAMP_BENCH_FIELD_MAP).toHaveLength(12);
    expect(lampBenchOptimizationRange("meridian-mdx126", "magnesium_mM")).toBeUndefined();
    expect(lampBenchOptimizationRange("meridian-mdx126", "fip_bip_uM")).toBeUndefined();
    expect(lampBenchOptimizationRange("takara-rr385", "hold_temperature_c")).toBeUndefined();
    expect(lampBenchOptimizationRange("neb-m9204", "magnesium_mM")).toEqual([6, 8]);
    expect(lampBenchOptimizationRange("neb-e1700", "magnesium_mM")).toBeUndefined();
  });

  it("turns backend-guaranteed failures into Run-readiness issues", () => {
    const issues = lampScenarioIssues({
      protocol: "meridian-mdx126",
      fromRna: true,
      matrix: "saliva-sputum",
      preparation: "direct-addition",
      formulation: "lyophilized",
      readout: "turbidity",
      chemistry: "tb-green",
      designIntent: "panel-conservation-aware",
      inclusivity: "",
      benchValues: { lampOptMagnesium: "20", lampOptBetaine: "0.5" },
    });
    expect(new Set(issues.map((issue) => issue.field))).toEqual(
      new Set([
        "lampProtocol",
        "lampSampleMatrix",
        "lampFormulation",
        "lampReadoutChemistry",
        "inclusivity",
        "lampOptMagnesium",
        "lampOptBetaine",
      ]),
    );
  });
  it("assigns dynamic conflicts to the page that owns the corrective control", () => {
    const issues = lampScenarioIssues({
      protocol: "meridian-mdx126",
      fromRna: false,
      matrix: "saliva-sputum",
      preparation: "direct-addition",
      formulation: "liquid",
      readout: "fluorescence",
      chemistry: "syto82",
      designIntent: "panel-conservation-aware",
      inclusivity: "",
    });
    expect(
      issues.some(
        (issue) =>
          issue.field === "lampSampleMatrix" && lampScenarioIssueOwner(issue) === "reaction",
      ),
    ).toBe(true);
    expect(
      issues.some(
        (issue) => issue.field === "inclusivity" && lampScenarioIssueOwner(issue) === "specificity",
      ),
    ).toBe(true);
  });

  it("resolves instrument- and substrate-conditioned numeric overlays", () => {
    const slan = resolveLampNumericPreview({
      protocol: "vazyme-rp711",
      fromRna: false,
      matrix: "purified-nucleic-acid",
      preparation: "purified",
      formulation: "liquid",
      readout: "fluorescence",
      chemistry: "supplied-intercalating-dye",
      instrumentProfile: "vazyme-slan96p",
    });
    expect(slan.values.fluorescent_dye_x).toBe(0.1);
    expect(slan.values.fluorescent_dye_uL_per_25uL).toBeCloseTo(0.05);
    expect(slan.origins.fluorescent_dye_uL_per_25uL).toBe("derived-stoichiometry");

    const other = resolveLampNumericPreview({
      protocol: "vazyme-rp711",
      fromRna: false,
      matrix: "purified-nucleic-acid",
      preparation: "purified",
      formulation: "liquid",
      readout: "fluorescence",
      chemistry: "supplied-intercalating-dye",
      instrumentProfile: "other-qpcr",
    });
    expect(other.values.fluorescent_dye_x).toBeUndefined();
    expect(other.ranges.fluorescent_dye_x).toEqual([0.1, 1]);
    expect(other.ranges.fluorescent_dye_uL_per_25uL).toEqual([0.05, 0.5]);

    const agdia = resolveLampNumericPreview({
      protocol: "agdia-lmx54700",
      fromRna: true,
      matrix: "purified-nucleic-acid",
      preparation: "purified",
      formulation: "liquid",
      readout: "fluorescence",
      chemistry: "supplied-intercalating-dye",
      instrumentProfile: "agdia-amplifire",
    });
    expect(agdia.values.external_rt_units).toBe(50);
    expect(agdia.values.external_rt_uL).toBeCloseTo(0.25);
    expect(agdia.values.hold_temperature_c).toBe(65);
    expect(agdia.values.hold_time_min).toBe(20);
  });
});

describe("LAMP numeric recipe change explanation", () => {
  it("reports added, removed and changed source-conditioned values without inventing a second resolver", () => {
    const previous = {
      values: { magnesium_mM: 8, fluorescent_dye_x: 1 },
      origins: { magnesium_mM: "product-baseline", fluorescent_dye_x: "product-baseline" },
      ranges: {},
      appliedOverlays: [],
      unresolved: [],
    };
    const current = {
      values: { magnesium_mM: 6, fluorescent_dye_uL_per_25uL: 0.5 },
      origins: {
        magnesium_mM: "automatic:test-rule",
        fluorescent_dye_uL_per_25uL: "derived-stoichiometry",
      },
      ranges: {},
      appliedOverlays: ["test-rule"],
      unresolved: [],
    };
    expect(diffLampNumericPreview(previous, current)).toEqual([
      {
        key: "fluorescent_dye_uL_per_25uL",
        previous: undefined,
        next: 0.5,
        origin: "derived-stoichiometry",
      },
      { key: "fluorescent_dye_x", previous: 1, next: undefined, origin: undefined },
      { key: "magnesium_mM", previous: 8, next: 6, origin: "automatic:test-rule" },
    ]);
  });

  it("does not report unchanged values", () => {
    const preview = {
      values: { magnesium_mM: 8 },
      origins: { magnesium_mM: "product-baseline" },
      ranges: {},
      appliedOverlays: [],
      unresolved: [],
    };
    expect(diffLampNumericPreview(preview, preview)).toEqual([]);
    expect(diffLampNumericPreview(null, preview)).toEqual([]);
  });
});
