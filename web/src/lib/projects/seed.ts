/**
 * What a draft starts as, before anybody has answered anything.
 *
 * Two pure decisions, kept out of the workspace so they can be tested: the
 * workspace imports its server actions, which import `server-only`, so nothing
 * in that file can be reached from a test at all.
 */

import type { ModuleManifest, Preferences, Presets } from "@/lib/api/types";
import type { RawDraftValues } from "@/lib/projects/draft";

/** Every field the workspace holds, as the strings a form deals in. */
type Draft = RawDraftValues;

/**
 * A saved draft, with any enzyme this assay no longer offers taken out.
 *
 * Projects outlive the catalogue. A LAMP project set up when every assay
 * offered every enzyme has `rpa` in its settings, and now that assay offers
 * only *Bst* — so the saved value names something not on the list. A `select`
 * whose value matches no option displays the first one while the draft still
 * says the other, and the run is then refused for an enzyme the person never
 * saw themselves choose.
 *
 * Replaced rather than corrected in place, so the ordinary seeding runs and
 * the page goes on explaining where the enzyme came from. Everything else in
 * the draft is kept: this is about one field that stopped being valid, not
 * about distrusting what somebody saved — losing their pasted sequence would
 * be a far worse bug than the one being fixed.
 */
export function settingsWithinReach(
  settings: Draft,
  presets: Presets,
  preferences: Preferences,
  assay: ModuleManifest["defaults"] | undefined,
): Draft {
  const named = settings.polymerase;
  if (!named || presets.polymerases.some((entry) => entry.id === named)) {
    return settings;
  }

  const { polymerase: _replaced, ...rest } = settings;
  const seed = seededPolymerase(presets, preferences, assay).id;
  return seed ? { ...rest, polymerase: seed } : rest;
}

/**
 * Which enzyme a new draft starts on, and which of three sources chose it.
 *
 * The assay's own first, then what somebody keeps on their bench, then
 * whatever the engine lists — and each only if this assay offers it. A default
 * that quietly differs from what the assay will accept is the kind of thing
 * somebody discovers from a run they cannot reproduce.
 */
export function seededPolymerase(
  presets: Presets,
  preferences: Preferences,
  assay: ModuleManifest["defaults"] | undefined,
): { id: string | undefined; from: "assay" | "preference" | "engine" } {
  const offers = (id: string | null | undefined) =>
    Boolean(id) && presets.polymerases.some((entry) => entry.id === id);

  const pinned = assay?.polymerase;
  if (offers(pinned)) return { id: pinned!, from: "assay" };

  const owned = preferences.preferredPolymerase;
  if (offers(owned)) return { id: owned!, from: "preference" };

  return { id: presets.polymerases[0]?.id, from: "engine" };
}
