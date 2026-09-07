import { TriangleAlert } from "lucide-react";

import type { RunResult } from "@/lib/api/types";

/**
 * A run that was saved before its assay was being applied.
 *
 * For a period, designs saved inside a project reached the engine without the
 * assay profile attached: the module was looked up to choose the engine and
 * then its parameters were dropped. Every such run was computed with the
 * generic defaults rather than its own — measured on qPCR-probe against TP53,
 * the Taq buffer instead of the qPCR one, and a 359 bp product where that assay
 * allows 70 to 200.
 *
 * Those runs are still in the database and they still render. Saying nothing
 * would leave somebody citing a number that was computed for a different
 * reaction from the one named at the top of the page.
 *
 * The marker is exact rather than a guess: the preparation those runs skipped
 * is what writes `assay.id`, so a stored result with an empty one is a stored
 * result that skipped it. A run made since carries its assay and never sees
 * this.
 */
export function staleRun(result: RunResult): boolean {
  // The consensus engine never emits an `assay` block at all, for any run,
  // so the marker cannot mean anything there. Returning false rather than true
  // is the honest reading: a missing field that is always missing is not
  // evidence of anything, and flagging every one of those runs would be a
  // warning nobody could act on.
  if (!("assay" in result)) return false;
  return !result.assay?.id;
}

export function StaleRunNotice() {
  return (
    <div
      role="status"
      className="flex gap-2.5 rounded-xl border border-warning/40 bg-warning/5 p-3.5 text-sm leading-relaxed"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
      <div className="space-y-1.5">
        <p className="font-medium">
          This run was computed before this module&apos;s own parameters were being applied.
        </p>
        <p className="text-muted-foreground">
          It was saved during a period when a design kept inside a project reached the engine
          without its assay attached, so it used the general-purpose defaults — a different
          polymerase, a different product-size window, and temperatures computed in a different
          buffer — rather than this module&apos;s.
        </p>
        <p className="text-muted-foreground">
          The primers below are real primers and the numbers beside them are real measurements. They
          are simply measurements of a different reaction from the one this page is named after. Run
          it again to get the design this module actually specifies; the result will not match what
          is shown here, and that difference is the point.
        </p>
      </div>
    </div>
  );
}
