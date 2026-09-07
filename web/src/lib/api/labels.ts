/**
 * The words this interface puts on the API's vocabulary.
 *
 * A separate module from `types.ts` for one measurable reason: `types.ts`
 * begins `import { z } from "zod"`, and importing a *value* from it — even a
 * three-line record of strings — pulls the whole module, every schema in it,
 * and zod itself into whatever bundle did the importing.
 *
 * Three client components imported `STATUS_LABELS` from there. The result was
 * a 299 KB chunk of validation library shipped to every browser, to render the
 * word "Experimental" on a badge. Nothing validates anything in the browser:
 * responses are checked server-side, which is the only side where checking them
 * means anything.
 *
 * So values that a client component might want live here, where there is
 * nothing to drag in. Types can stay in `types.ts` — a `import type` is erased
 * before the bundler ever sees it.
 */

import type { EngineId, ModuleStatus } from "./types";

/** How finished a module is, in the word shown on its badge. */
export const STATUS_LABELS: Record<ModuleStatus, string> = {
  planned: "Planned",
  experimental: "Needs review",
  stable: "Stable",
};

/**
 * Engines with no region to point at.
 *
 * A tiling scheme and a loop set both cover the whole sequence; a mutagenesis
 * is told what to change rather than where to amplify; a genotyping assay is
 * anchored on one base; an assembly is given a plan instead of a template; a
 * degenerate pair comes from an alignment; and standard inverse PCR treats the
 * complete submitted sequence as the intact known anchor rather than choosing
 * a sub-region to amplify inward.
 * Offering any of them a region picker offers a control whose value is thrown
 * away at the edge.
 */
export const NO_REGION: readonly EngineId[] = [
  "tiling-scheme",
  "mutagenic-pair",
  "loop-set",
  "discriminating-pair",
  "junction-primers",
  // Measured against the engine structs rather than assumed: neither of these
  // declares `targetStart`, `targetLength` or `excluded`, so every value the
  // picker collected was dropped at the edge. A degenerate pair is designed
  // from what a family shares — there is no single template to point at — and
  // inverse PCR uses the complete submitted sequence as its intact known anchor.
  "consensus-pair",
  "outward-pair",
];

/**
 * Engines that take an exclusion but no target region.
 *
 * A loop set covers the whole sequence and a genotyping assay is anchored on one
 * base, so neither has a region to point at — but both have somewhere a primer
 * must not go. Tiled-scheme uses the same standalone exclusion control because
 * its Rust request accepts avoided intervals but it has no target region picker.
 *
 * The membership is asserted against the engine structs in
 * `page-plan.wiring.test.ts`, so this cannot drift from what the core accepts.
 */
export const EXCLUSION_ONLY: readonly EngineId[] = [
  "loop-set",
  "discriminating-pair",
  "tiling-scheme",
];
