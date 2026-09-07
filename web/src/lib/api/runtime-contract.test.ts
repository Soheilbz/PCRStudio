import { describe, expect, it } from "vitest";

import flankingFixture from "./__fixtures__/historical/rpa__pre-specificity-v5-source-mirrored.json";
import { runResultSchema } from "./types";

describe("generation-1 runtime evidence", () => {
  it("keeps the shared contract and independent-verification state", () => {
    const body = structuredClone(flankingFixture) as Record<string, unknown>;
    body.runtime_contract = {
      contract_version: "1.1.0",
      parameter_map_version: "gen1-2026-08-30.2",
      input_schema_version: "pcrstudio-worker-input-v1",
      output_schema_version: "pcrstudio-worker-output-v2",
      module_id: "rpa",
      engine_id: "flanking-pair",
      coordinate_contract: {
        version: "1.0.0",
        basis: 0,
        interval: "half-open",
        notation: "[start,end)",
        oligo_sequence_orientation: "5prime-to-3prime",
        strand_field_required: true,
        single_base_position: "0-based",
        junction_position: "boundary-between-bases",
      },
      pipeline_stages: [
        "module-resolution",
        "candidate-generation",
        "independent-toolchain-validation",
      ],
      parameter_precedence: [
        "tool-hard-capability",
        "assay-hard-invariant",
        "locked-chemistry-profile",
        "policy-checked-user-override",
        "assay-recommended-default",
        "purpose-default",
        "pcrstudio-default",
        "explicitly-adopted-tool-default",
      ],
      override_policy: { hard_assay_invariant: "forbidden" },
      bindings: [{ tool_id: "primer3_core", role: "PRIMARY", operations: ["design_pair"] }],
    };
    body.module_contract = {
      engine: "flanking-pair",
      command: "run",
      gates: ["rpa_compatible_chemistry", "target_specificity"],
      fallback: "preserve_rpa_chemistry",
    };
    body.toolchain_validation = {
      contract_version: "1.1.0",
      mode: "auto",
      status: "verification-incomplete",
      selected_oligos: 2,
      molecule_contract: {
        specificity: "annealing_sequence",
        interaction: "ordered_sequence",
        tail_position: "5-prime-only",
      },
      checks: [],
      warnings: ["MFEprimer database not configured"],
    };
    body.verification = {
      status: "verification-incomplete",
      computational_design_complete: true,
      external_evidence_complete: false,
      wet_lab_validated: false,
      selected_oligos: 2,
      note: "computational and wet-lab claims are separate",
    };

    const parsed = runResultSchema.parse(body);
    expect(parsed.runtime_contract?.engine_id).toBe("flanking-pair");
    expect(parsed.module_contract?.engine).toBe("flanking-pair");
    expect(parsed.toolchain_validation?.status).toBe("verification-incomplete");
    expect(parsed.verification?.wet_lab_validated).toBe(false);
  });
});
