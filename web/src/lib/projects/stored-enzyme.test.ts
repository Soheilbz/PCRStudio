/**
 * A saved project, against a catalogue that has narrowed under it.
 *
 * Projects outlive the catalogue. A LAMP project set up when every assay
 * offered every enzyme has `rpa` in its settings; that assay now offers only
 * *Bst*, so the saved value names something not on the list. A `select` whose
 * value matches no option displays the first one while the draft still says
 * the other, and the run is refused for an enzyme the person never saw
 * themselves choose.
 *
 * This was anticipated before it could happen. `docs/audits/findings-for-engine-pass.md`
 * recorded that `preferredPolymerase` only applies where the assay offers it,
 * written that way so "the day an assay narrows its list, a stored preference
 * does not walk straight past the narrowing" — and that day came. A stored
 * *project setting* needed the same guard, which is what this covers.
 */

import { describe, expect, it } from "vitest";

import { settingsWithinReach } from "./seed";
import type { ModuleManifest, Preferences, Presets } from "@/lib/api/types";

/** A catalogue narrowed to one enzyme, the way LAMP's is. */
function narrowed(...ids: string[]): Presets {
  return {
    polymerases: ids.map((id) => ({
      id,
      name: id,
      summary: "",
      reaction: { mv_conc: 50, dv_conc: 2, dntp_conc: 0.8, dna_conc: 200 },
    })),
    purposes: [],
    constraints: {},
    fields: [],
  } as unknown as Presets;
}

const NO_PREFERENCE = {} as Preferences;
const LAMP = { polymerase: "bst" } as ModuleManifest["defaults"];

describe("a stored enzyme the assay no longer offers", () => {
  it("is replaced by what the assay asks for", () => {
    const kept = settingsWithinReach(
      { template: "ACGT", polymerase: "rpa", label: "first pass" },
      narrowed("bst"),
      NO_PREFERENCE,
      LAMP,
    );

    expect(kept.polymerase).toBe("bst");
  });

  it("and everything else the person saved is kept", () => {
    // This is about one field that stopped being valid, not about distrusting
    // a saved draft. Losing the pasted sequence would be a far worse bug than
    // the one being fixed.
    const kept = settingsWithinReach(
      { template: "ACGTACGT", polymerase: "rpa", label: "first pass", howMany: "9" },
      narrowed("bst"),
      NO_PREFERENCE,
      LAMP,
    );

    expect(kept.template).toBe("ACGTACGT");
    expect(kept.label).toBe("first pass");
    expect(kept.howMany).toBe("9");
  });

  it("leaves an enzyme that is still offered exactly as it was", () => {
    // The other direction, and the one that matters most: a person who chose
    // an enzyme deliberately must come back to the one they chose, not to the
    // assay's default.
    const kept = settingsWithinReach(
      { template: "ACGT", polymerase: "taq-high-magnesium" },
      narrowed("taq-standard", "taq-high-magnesium"),
      NO_PREFERENCE,
      { polymerase: "taq-standard" } as ModuleManifest["defaults"],
    );

    expect(kept.polymerase).toBe("taq-high-magnesium");
  });

  it("says nothing about a draft that never named one", () => {
    const kept = settingsWithinReach({ template: "ACGT" }, narrowed("bst"), NO_PREFERENCE, LAMP);
    expect(kept.polymerase).toBeUndefined();
  });
});
