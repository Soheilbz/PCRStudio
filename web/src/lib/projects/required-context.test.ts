import { describe, expect, it } from "vitest";

import {
  draftFieldForContext,
  requiredDraftFields,
  requiredDraftFieldsForStep,
} from "./required-context";

describe("canonical runtime context drives browser readiness", () => {
  it("maps nested request paths onto their actual flat controls", () => {
    expect(draftFieldForContext("tails.forward_protective_sequence")).toBe(
      "forwardProtectiveSequence",
    );
    expect(draftFieldForContext("edit.replacing")).toBe("editReplacing");
    expect(draftFieldForContext("digital_platform_id")).toBe("digitalPlatformId");
  });

  it("adds conditional digital-PCR platform provenance only for a custom platform", () => {
    expect(
      requiredDraftFields("digital-pcr", { digitalPlatformId: "bio-rad-qx200" }),
    ).not.toContain("digitalPlatformName");
    expect(requiredDraftFields("digital-pcr", { digitalPlatformId: "other-validated" })).toContain(
      "digitalPlatformName",
    );
  });

  it("tracks tiled-scheme lifecycle-specific required artifacts", () => {
    expect(
      requiredDraftFields("tiled-scheme", {
        tilingBackend: "primalscheme3",
        tilingOperation: "repair-mode",
      }),
    ).toEqual(
      expect.arrayContaining([
        "tilingOperation",
        "tilingAlignmentMode",
        "existingBed",
        "schemeConfig",
      ]),
    );
    expect(
      requiredDraftFields("tiled-scheme", {
        tilingBackend: "primalscheme3",
        tilingOperation: "scheme-replace",
      }),
    ).toContain("primerName");
  });

  it("tracks mutagenesis requirements by edit branch", () => {
    expect(
      requiredDraftFields("site-directed-mutagenesis", {
        editInputMode: "dna",
        editKind: "substitute",
      }),
    ).toEqual(
      expect.arrayContaining([
        "postAmplificationProtocol",
        "editKind",
        "editAt",
        "editTo",
        "editReplacing",
      ]),
    );
  });

  it("assigns missing context to the step where the browser can actually fix it", () => {
    expect(requiredDraftFieldsForStep("digital-pcr", {}, "reaction")).toContain(
      "digitalPlatformId",
    );
    expect(requiredDraftFieldsForStep("digital-pcr", {}, "target")).toContain(
      "digitalFragmentationState",
    );
    expect(requiredDraftFieldsForStep("colony-pcr", {}, "target")).toEqual(["colonyHostClass"]);
    expect(
      requiredDraftFieldsForStep("colony-pcr", { colonyProtocolId: "custom-sop" }, "reaction"),
    ).toEqual(
      expect.arrayContaining([
        "colonyPreparation",
        "colonyProtocolName",
        "colonyProtocolProvenance",
      ]),
    );
    expect(requiredDraftFieldsForStep("species-specific-pcr", {}, "specificity")).toEqual(
      expect.arrayContaining(["background", "inclusivity"]),
    );
    expect(requiredDraftFieldsForStep("nested-pcr", {}, "design")).toContain("shares");
    expect(requiredDraftFieldsForStep("nested-pcr", {}, "reaction")).toContain(
      "carryoverPrevention",
    );
    expect(requiredDraftFieldsForStep("inverse-pcr", {}, "strategy")).toEqual(
      expect.arrayContaining(["inverseBranch", "circularizationProvenance"]),
    );
    expect(requiredDraftFieldsForStep("tetra-primer-arms", {}, "validation")).toContain(
      "tetraMinBandSeparationBp",
    );
    expect(requiredDraftFieldsForStep("universal-primers", {}, "design")).toContain(
      "alignmentMode",
    );
    expect(requiredDraftFieldsForStep("race", {}, "design")).toContain("raceDirection");
    expect(requiredDraftFieldsForStep("race", {}, "reaction")).toContain("raceChemistry");
    expect(requiredDraftFieldsForStep("sequencing-primer", {}, "design")).toEqual(
      expect.arrayContaining(["direction", "deadZone", "readLength"]),
    );
    expect(requiredDraftFieldsForStep("gibson-assembly", {}, "design")).toContain("circular");
    expect(
      requiredDraftFieldsForStep(
        "site-directed-mutagenesis",
        { editInputMode: "dna", editKind: "insert" },
        "design",
      ),
    ).toEqual(expect.arrayContaining(["editKind", "editAt", "editTo"]));
  });
});
