import { describe, expect, it } from "vitest";

import probe from "./probe-authority.generated.json";
import race from "./race-authority.generated.json";
import tiling from "./tiling-authority.generated.json";
import capabilities from "./engine-capability-matrix.generated.json";

type AuthorityRecord = {
  execution_status?: string;
  source_revision?: string;
  selection?: string;
  probe_constraints?: Record<string, unknown>;
  source_kind?: string;
  source_url?: string;
  requires?: { sop_revision?: boolean; sop_sha256?: boolean };
};

describe("Current engine canonical projections", () => {
  it("keeps conventional qPCR executable and MGB external-authority-bound", () => {
    const records = probe.records as Record<string, AuthorityRecord>;
    expect(records["thermofisher-taqman-conventional"]!.execution_status).toBe("executable");
    expect(records["idt-primetime-conventional"]!.execution_status).toBe("executable");
    expect(records["idt-primetime-conventional"]!.probe_constraints).toEqual({ length_max: 28 });
    expect(records["taqman-mgb-reference"]!.execution_status).toBe("external-authority-required");
  });

  it("exposes current FirstChoice without cross-wiring SMARTer", () => {
    const records = race.records as Record<string, AuthorityRecord>;
    expect(records["firstchoice-rlm-race"]!.execution_status).toBe("executable");
    expect(records["firstchoice-rlm-race"]!.source_revision).toBe("Rev A");
    expect(records["smarter-race-source-limited"]!.execution_status).toBe("source-limited");
    expect(records["smarter-race-current"]!.execution_status).toBe("executable-if-complete");
    expect(records["smarter-race-current"]!.requires?.sop_revision).toBe(true);
    expect(records["smarter-race-current"]!.requires?.sop_sha256).toBe(true);
    expect(records["custom"]!.source_kind).toBe("caller-supplied-sop");
    expect(records["custom"]!.source_url).toBeUndefined();
  });

  it("keeps Olivar and PrimalScheme as independent current backends", () => {
    const records = tiling.records as Record<string, AuthorityRecord>;
    expect(records["olivar-1.3.3"]!.execution_status).toBe("executable-if-installed");
    expect(records["primalscheme3-3.3.0"]!.execution_status).toBe("executable-if-installed");
    expect(records["olivar-1.3.3"]!.selection).not.toEqual(
      records["primalscheme3-3.3.0"]!.selection,
    );
  });

  it("keeps FirstChoice executable and SMARTer context-gated", () => {
    const single = (
      capabilities.engines as unknown as Record<
        string,
        { feature_capabilities: Record<string, { status: string }> }
      >
    )["single-primer"]!.feature_capabilities;
    expect(single["rlm-race"]!.status).toBe("executable");
    expect(single["smarter-race"]!.status).toBe("executable-with-complete-context");
  });
});
