"""What the product itself is going to be like to amplify.

Everything else in this pipeline judges the primers. Nothing judged the thing
between them, and a GC-rich product is one of the ordinary ways a design with
faultless primers still comes back empty: the polymerase stalls in a stretch
that will not stay melted, and no amount of primer quality fixes it.

This is deliberately not a model. The GC content of a window is arithmetic, and
arithmetic is the only claim made here -- where the published thresholds are
quoted they are quoted as what somebody measured, with the paper beside them,
because "this product looks hard" is exactly the kind of sentence that gets
believed without evidence.

Nothing here removes or reranks a candidate. A GC-rich target is usually the
target you have; what changes is what goes in the tube, and that is a decision
for whoever is standing at the bench.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: How long a stretch to report the composition of.
#:
#: Reported, not judged. The first version of this file set the verdict from
#: the richest window and that was wrong in a way worth recording: the maximum
#: of many windows is an extreme-value statistic, so it drifts upwards with
#: product length whatever the sequence is made of. Measured on 400 random
#: products of 300 bases, which are 50 per cent GC by construction, the richest
#: 50-base window averaged 63 per cent and reached 76 -- and 10 per cent of
#: perfectly ordinary products were called "hard". A 3 kb product would have
#: been called hard nearly always.
#:
#: So the window says *where* the GC sits and the verdict comes from the whole
#: product, which is also what the sources actually measured: Chang et al.
#: speak of samples with a high GC content, Sahdev et al. of genes whose 5' and
#: 3' sequences are above 80 per cent. Neither reports a maximal window.
WINDOW = 50

#: Report flag anchored to a cited high-GC assay study; not a universal mix limit.
#:
#: Chang, Seyfert and Shen took a SYBR Green kit that failed above 70 per cent
#: GC, added DMSO and betaine and raised the polymerase, and got reliable
#: amplification and quantitation of templates exceeding that
#: (Genet Mol Res 14:8509-8515, 2015, doi:10.4238/2015.July.28.20). Jensen,
#: Fukushima and Davis found the same two additives greatly improved both
#: specificity and yield when amplifying GC-rich constructs
#: (PLoS ONE 5:e11024, 2010, doi:10.1371/journal.pone.0011024).
HARD_GC = 70.0

#: Higher report flag anchored to cited difficult-template examples; not a validity gate.
#:
#: Sahdev et al. took two human genes whose 5' and 3' sequences are above 80
#: per cent GC and needed primer redesign, DMSO-betaine combinations *and* a
#: raised denaturation temperature together to amplify them
#: (Mol Cell Probes 21:303-307, 2007, doi:10.1016/j.mcp.2007.03.004). Above
#: this line, one additive is not the whole answer.
VERY_HARD_GC = 80.0


@dataclass(frozen=True)
class Amplicon:
    """The product's composition, and the worst stretch in it."""

    length: int
    gc: float
    #: The GC of the richest `WINDOW` bases, or the whole product if it is
    #: shorter than one window.
    worst_window_gc: float
    #: Where that window starts, counted from the start of the product.
    worst_window_at: int
    #: True when the product was too short to hold a window, so the two GC
    #: figures are the same number rather than two measurements.
    one_window_only: bool

    @property
    def difficulty(self) -> str:
        """`easy`, `hard` or `very hard`, from the product's own GC.

        From `gc` rather than from `worst_window_gc`, for the reason recorded
        on `WINDOW`: the richest window of a long product is high by
        construction, and the thresholds below were measured on whole
        templates.
        """
        if self.gc >= VERY_HARD_GC:
            return "very hard"
        if self.gc >= HARD_GC:
            return "hard"
        return "easy"

    def to_dict(self, *, assay_id: str | None = None) -> dict[str, Any]:
        return {
            "length": self.length,
            "gc": self.gc,
            "window": WINDOW,
            "worst_window_gc": self.worst_window_gc,
            # Counted from one, like every other position a person reads.
            "worst_window_at": self.worst_window_at + 1,
            "one_window_only": self.one_window_only,
            "difficulty": self.difficulty,
            "difficulty_scope": (
                "composition-only-not-rpa-performance-threshold"
                if assay_id == "rpa"
                else "generic-pcr-family-composition-review-flag-not-validity-gate"
            ),
            "note": advice(self, assay_id=assay_id),
        }


def _gc(sequence: str) -> float:
    if not sequence:
        return 0.0
    return 100.0 * sum(1 for base in sequence if base in "GCgc") / len(sequence)


def profile(amplicon: str) -> Amplicon:
    """The product's overall GC and its richest window.

    A rolling count rather than a slice per position: a tiling scheme asks this
    of a hundred amplicons at once, and recomputing fifty bases each step turns
    a linear pass into a quadratic one.
    """
    sequence = amplicon.upper()
    length = len(sequence)
    overall = round(_gc(sequence), 1)

    if length <= WINDOW:
        return Amplicon(
            length=length,
            gc=overall,
            worst_window_gc=overall,
            worst_window_at=0,
            one_window_only=True,
        )

    counted = sum(1 for base in sequence[:WINDOW] if base in "GC")
    best_count, best_at = counted, 0
    for index in range(1, length - WINDOW + 1):
        if sequence[index - 1] in "GC":
            counted -= 1
        if sequence[index + WINDOW - 1] in "GC":
            counted += 1
        if counted > best_count:
            best_count, best_at = counted, index

    return Amplicon(
        length=length,
        gc=overall,
        worst_window_gc=round(100.0 * best_count / WINDOW, 1),
        worst_window_at=best_at,
        one_window_only=False,
    )


def advice(product: Amplicon, *, assay_id: str | None = None) -> str:
    """Interpret composition without turning a shared flag into a chemistry recipe."""
    if assay_id == "rpa":
        return (
            f"The product is {product.gc:.0f}% GC. The 70/80% labels retained by this shared "
            "amplicon diagnostic are PCR-family composition review flags, not validated RPA "
            "performance thresholds. PCRStudio therefore does not transfer DMSO, betaine, "
            "denaturation or other PCR rescue recipes into RPA; use the selected RPA/RT-RPA "
            "protocol and empirical screening to judge this product."
        )

    where = (
        ""
        if product.one_window_only
        else (
            f" Its richest {WINDOW} bases start at position "
            f"{product.worst_window_at + 1} of the product and run to "
            f"{product.worst_window_gc:.0f}% — the richest stretch of any long "
            "product is high by construction, so read that as where to look "
            "rather than as a verdict."
        )
    )

    if product.difficulty == "very hard":
        return (
            f"The product is {product.gc:.0f}% GC. In the high-GC templates "
            "studied by Sahdev et al., successful optimization combined primer "
            "redesign, DMSO/betaine and a higher denaturation temperature. "
            "That study is a review flag for this sequence, not a universal "
            "recipe or proof that the same interventions are required here "
            "(Sahdev et al. 2007, doi:10.1016/j.mcp.2007.03.004)." + where
        )
    if product.difficulty == "hard":
        return (
            f"The product is {product.gc:.0f}% GC, above this module's "
            f"{HARD_GC:.0f}% literature-anchored review flag. Chang et al. "
            "reported failure of the tested SYBR mix on high-GC templates and "
            "improvement after chemistry optimization; Jensen et al. likewise "
            "reported DMSO/betaine benefits in their systems. These observations "
            "motivate bench review, not a universal additive prescription "
            "(Chang et al. 2015, doi:10.4238/2015.July.28.20; Jensen et al. "
            "2010, doi:10.1371/journal.pone.0011024)." + where
        )
    return (
        f"The product is {product.gc:.0f}% GC, below this module's "
        f"{HARD_GC:.0f}% high-GC review flag. That does not establish that the "
        "template is easy or that additives are unnecessary; it only means the "
        "whole-product GC metric did not trigger this particular literature-"
        "anchored warning." + where
    )


def hardest(products: list[Amplicon]) -> Amplicon | None:
    """The most difficult of several, for a run-level summary."""
    return max(products, key=lambda one: one.worst_window_gc, default=None)
