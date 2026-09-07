import { describe, expect, it } from "vitest";

import { diffFlankingNumericPreview, resolveFlankingNumericPreview } from "./flanking-contract";

describe("Flanking source-conditioned numeric contract", () => {
  it("keeps OneTaq GC enhancer inside the reviewed range", () => {
    const ok = resolveFlankingNumericPreview({
      moduleId: "standard-pcr",
      protocol: "neb-onetaq-hot-start-gc-m0485",
      gcEnhancerPercent: "15",
    });
    expect(ok.values.high_gc_enhancer_percent).toBe(15);
    expect(ok.origins.high_gc_enhancer_percent).toBe("user-override-within-source-bound");
    expect(ok.issues).toEqual([]);

    const invalid = resolveFlankingNumericPreview({
      moduleId: "standard-pcr",
      protocol: "neb-onetaq-hot-start-gc-m0485",
      gcEnhancerPercent: "25",
    });
    expect(invalid.issues.some((issue) => issue.field === "flankingGcEnhancerPercent")).toBe(true);
  });

  it("does not invent the M0488 colony lysis duration", () => {
    const unresolved = resolveFlankingNumericPreview({
      moduleId: "colony-pcr",
      protocol: "neb-onetaq-hotstart-m0488-colony",
      preparation: "direct-transfer",
    });
    expect(unresolved.unresolved.some((entry) => entry.id === "m0488-colony-lysis-time")).toBe(
      true,
    );

    const resolved = resolveFlankingNumericPreview({
      moduleId: "colony-pcr",
      protocol: "neb-onetaq-hotstart-m0488-colony",
      preparation: "direct-transfer",
      initialDenaturationTimeMin: "3",
    });
    expect(resolved.values.initial_denaturation_time_min).toBe(3);
    expect(resolved.issues).toEqual([]);
  });

  it("resolves PCRBIO overnight-culture input only on the documented preparation branch", () => {
    const preview = resolveFlankingNumericPreview({
      moduleId: "colony-pcr",
      protocol: "pcrbio-hs-taq-pb10-22-colony",
      preparation: "liquid-culture",
    });
    expect(preview.values.liquid_culture_input_uL).toBe(5);
    expect(preview.appliedOverlays).toContain("pcrbio-overnight-culture-input");
  });

  it("keeps PowerTrack Yellow Sample Buffer optional and derives it only when selected", () => {
    const without = resolveFlankingNumericPreview({
      moduleId: "qpcr-sybr",
      protocol: "thermo-powertrack-sybr-a46xxx",
      cyclingProfile: "fast",
      reactionVolumeUl: "20",
    });
    expect(without.values.yellow_sample_buffer_uL).toBeUndefined();

    const withBuffer = resolveFlankingNumericPreview({
      moduleId: "qpcr-sybr",
      protocol: "thermo-powertrack-sybr-a46xxx",
      cyclingProfile: "fast",
      reactionVolumeUl: "20",
      additive: "yellow-sample-buffer",
    });
    expect(withBuffer.values.yellow_sample_buffer_uL).toBe(0.5);
    expect(withBuffer.appliedOverlays).toContain("powertrack-yellow-sample-buffer");
  });

  it("projects Thermo Lyo-ready RPA protein chemistry, multiplex start, bounded conditions, and RT components", () => {
    const preview = resolveFlankingNumericPreview({
      moduleId: "rpa",
      protocol: "thermo-lyo-ready-rpa",
      rpaMultiplex: true,
      rpaTemperatureC: "40",
      rpaTimeMin: "25",
      rpaBstUnitsPerUl: "0.05",
      fromRna: true,
    });
    expect(preview.values.primer_each_nM).toBe(100);
    expect(preview.values.uvsx_mg_per_mL).toBe(0.03);
    expect(preview.values.gene32_mg_per_mL).toBe(0.4);
    expect(preview.values.bst_polymerase_U_per_uL).toBe(0.05);
    expect(preview.values.reverse_transcriptase_U_per_uL).toBe(2);
    expect(preview.values.rnase_inhibitor_U_per_uL).toBe(1.6);
    expect(preview.values.rnase_h_U_per_uL).toBe(0.1);
    expect(preview.issues).toEqual([]);

    const invalid = resolveFlankingNumericPreview({
      moduleId: "rpa",
      protocol: "thermo-lyo-ready-rpa",
      rpaTemperatureC: "46",
    });
    expect(invalid.issues.some((issue) => issue.field === "rpaTemperatureC")).toBe(true);
  });

  it("uses target length to resolve KOD Long extension rather than a universal long-PCR rate", () => {
    const short = resolveFlankingNumericPreview({
      moduleId: "long-range-pcr",
      protocol: "toyobo-kod-long-kml101",
      targetLengthKb: "8",
    });
    const long = resolveFlankingNumericPreview({
      moduleId: "long-range-pcr",
      protocol: "toyobo-kod-long-kml101",
      targetLengthKb: "20",
    });
    expect(short.values.extension_seconds_per_kb).toBe(5);
    expect(short.values.extension_time_sec).toBe(40);
    expect(long.values.extension_seconds_per_kb).toBe(10);
    expect(long.values.extension_time_sec).toBe(200);
  });

  it("requires explicit QIAcuity Nanoplate context before resolving reaction volume", () => {
    const unresolved = resolveFlankingNumericPreview({
      moduleId: "digital-pcr",
      protocol: "qiagen-qiacuity-eg",
    });
    expect(unresolved.unresolved.some((entry) => entry.id === "qiacuity-nanoplate-format")).toBe(
      true,
    );
  });

  it("explains numeric changes without becoming an independent scientific authority", () => {
    const before = resolveFlankingNumericPreview({
      moduleId: "standard-pcr",
      protocol: "neb-onetaq-hot-start-m0484",
      reactionVolumeUl: "25",
    });
    const after = resolveFlankingNumericPreview({
      moduleId: "standard-pcr",
      protocol: "neb-onetaq-hot-start-m0484",
      reactionVolumeUl: "50",
    });
    const changes = diffFlankingNumericPreview(before, after);
    expect(
      changes.some((change) => change.key === "reaction_volume_uL" && change.kind === "changed"),
    ).toBe(true);
    expect(after.sequenceDecisionImpact).toBe("none");
  });
});
