import { describe, expect, it } from "vitest";

import { multiplexCapabilityFor } from "./multiplex-capabilities";

describe("multiplex capability presentation", () => {
  it("keeps the executable builder route on the three endpoint assays", () => {
    for (const moduleId of ["standard-pcr", "colony-pcr", "species-specific-pcr"]) {
      const capability = multiplexCapabilityFor(moduleId);
      expect(capability?.genericBuilder).toBe(true);
    }
  });

  it("exposes specialised multiplex workflows without claiming a generic route", () => {
    for (const moduleId of ["qpcr-probe", "digital-pcr", "lamp", "rpa", "tiled-scheme"]) {
      const capability = multiplexCapabilityFor(moduleId);
      expect(capability?.genericBuilder).toBe(false);
      expect(capability?.title).toBeTruthy();
      expect(capability?.description).toBeTruthy();
    }
  });

  it("does not advertise multiplex for unrelated assays", () => {
    expect(multiplexCapabilityFor("nested-pcr")).toBeNull();
    expect(multiplexCapabilityFor("site-directed-mutagenesis")).toBeNull();
  });
});
