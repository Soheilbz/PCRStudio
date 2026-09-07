import { describe, expect, it } from "vitest";

import moduleCopy from "./module-copy.generated.json";

const MODULE_IDS = [
  "standard-pcr",
  "long-range-pcr",
  "colony-pcr",
  "nested-pcr",
  "inverse-pcr",
  "qpcr-sybr",
  "qpcr-probe",
  "digital-pcr",
  "arms-pcr",
  "tetra-primer-arms",
  "kasp",
  "species-specific-pcr",
  "lamp",
  "rpa",
  "universal-primers",
  "tiled-scheme",
  "race",
  "sequencing-primer",
  "gibson-assembly",
  "restriction-cloning",
  "site-directed-mutagenesis",
] as const;

describe("canonical module page copy", () => {
  it("defines one detailed, module-specific checks explanation for every module", () => {
    expect(Object.keys(moduleCopy.modules)).toEqual(expect.arrayContaining([...MODULE_IDS]));
    expect(Object.keys(moduleCopy.modules)).toHaveLength(MODULE_IDS.length);

    const checks = MODULE_IDS.map((id) => moduleCopy.modules[id].checks);
    expect(checks.every((copy) => copy.trim().length > 0)).toBe(true);
    expect(new Set(checks).size).toBe(MODULE_IDS.length);
  });
});
