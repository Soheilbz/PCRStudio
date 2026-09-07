import type { RunResult } from "@/lib/api/types";

/**
 * Number of assay-level designs represented by one result.
 *
 * This is deliberately engine-aware. Some results contain arrays that are
 * components of one design (tiles in one tiling scheme, junctions in one
 * assembly plan), while other arrays are genuinely alternative designs.
 */
export function countAssayDesigns(result: RunResult): number | null {
  switch (result.engine) {
    case "flanking-pair":
    case "consensus-pair":
    case "outward-pair":
    case "mutagenic-pair":
      return result.pairs.length;
    case "pair-and-probe":
      return result.assays.length;
    case "discriminating-pair":
      return result.primers.length;
    case "single-primer":
      return result.primers.length;
    case "loop-set":
      return result.sets.length;
    case "nested":
      return result.nests.length;
    case "tiling-scheme":
      return result.tiles.length > 0 ? 1 : 0;
    case "junction-primers":
      return result.junctions.length > 0 || result.primers.length > 0 ? 1 : 0;
    default:
      return null;
  }
}
