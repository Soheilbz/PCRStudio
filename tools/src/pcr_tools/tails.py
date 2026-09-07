"""Five-prime tails, and what adding one does to a primer.

A restriction-cloning primer is an ordinary primer with a restriction site and
a few protective bases stuck on its 5' end. That sounds like string
concatenation and is not, for four reasons -- each of which is a way the design
fails at a bench rather than on screen.

**The site must not already be in the insert.** If it is, the enzyme cuts the
product in the middle as well as at its ends, and what goes into the vector is
a fragment. This is the check the whole assay turns on and it is exact: no
model, no threshold, just whether the sequence contains the site. Both strands
are searched, because not every recognition site is palindromic.

**The tail does not anneal in the first cycle.** It hangs off the end with
nothing to pair with, so the temperature that decides whether the first cycle
works is the temperature of the annealing part alone. Reporting the melting
temperature of the whole oligo would overstate it by several degrees and send
somebody to an annealing temperature that does not prime.

**The tail is real DNA.** Twelve extra bases can fold back on the primer, pair
with the other primer's tail, or put a run of G or C at the 5' end that makes
the oligo sticky. So the finished oligo is measured again in full, and both
numbers are reported: what anneals, and what you order.

**The enzyme needs something to hold on to.** A site flush with the end of a
PCR product is cut poorly or not at all, because the enzyme's footprint is
wider than its recognition sequence. Hence the protective bases -- and see
`PROTECTIVE_BASES` for why this module will not tell you how many yours needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .degenerate import EXPANSION
from .intake import IntakeError, resolve
from .restriction import BY_NAME, ENZYMES, Enzyme
from .thermo import OligoReport, analyse, pair_dimer, reverse_complement

#: The named NEB general end-cleavage branch uses six bases outside the site.
#:
#: NEB publishes the *length* as a general rule of thumb, but explicitly says
#: the extra bases should be chosen so that palindromes and primer dimers are
#: not formed and, in most cases, no particular bases are required.  Therefore
#: PCRStudio must never invent the six-base sequence or present one as an NEB
#: sequence.  The actual protective bases are an explicit design input.
PROTECTIVE_BASES = 6


class TailError(ValueError):
    """A tail that cannot be built, with what to do about it."""


@dataclass(frozen=True)
class Tail:
    """One 5' addition, and where it came from."""

    #: The bases added: protective first, then the recognition site.
    sequence: str
    #: The enzyme this tail carries a site for.
    enzyme: str
    #: The recognition site alone.
    site: str
    #: The bases outside the site.
    protective: str
    #: Supplier-table first flanking-base count with non-zero observed activity, when
    #: this catalogue has a value. It is descriptive evidence, not an efficiency recommendation.
    first_observed_activity_flanking_bases: int | None = None
    #: Exact supplier/formulation identity behind that close-to-end observation.
    end_cleavage_evidence_identity: str | None = None

    @property
    def length(self) -> int:
        return len(self.sequence)


@dataclass(frozen=True)
class TailedPrimer:
    """A primer with a tail, measured twice."""

    #: What anneals in the first cycle: the primer without its tail.
    anneals: OligoReport
    #: What you order: tail and primer together.
    whole: OligoReport
    tail: Tail

    @property
    def sequence(self) -> str:
        return self.whole.sequence


def _single_sequence(text: str, *, label: str) -> str:
    """Read one insert without making a dangerous best-effort guess.

    Restriction-site screening may retain IUPAC ambiguity, but it must not
    silently discard punctuation, alignment gaps, or a second FASTA record.
    """
    try:
        target = resolve(text, name=label, lowercase_masking=False)
    except IntakeError as exc:
        raise TailError(f"The {label} could not be read: {exc}") from exc

    if any(note.kind == "multipleRecords" for note in target.notes):
        raise TailError(
            f"The {label} contains multiple FASTA records. Provide exactly one "
            "insert so restriction-site screening is unambiguous."
        )
    if target.rna_input:
        raise TailError(
            f"The {label} contains RNA uracil (U). Restriction-cloning tails "
            "need a DNA/cDNA insert; provide DNA/cDNA instead of silently "
            "converting RNA to DNA."
        )
    return target.upper


def _possible_site_count(sequence: str, site: str) -> int:
    """Count sites that are possible under the sequence's IUPAC ambiguity.

    A possible site is treated as present. That conservative rule prevents an
    ambiguous base from allowing an enzyme that could cut the insert through
    to cloning.
    """
    sequence_bases = [frozenset(EXPANSION[base]) for base in sequence.upper()]
    site_bases = [frozenset(EXPANSION[base]) for base in site.upper()]
    width = len(site_bases)
    if width == 0 or len(sequence_bases) < width:
        return 0
    return sum(
        all(sequence_bases[start + offset] & site_bases[offset] for offset in range(width))
        for start in range(len(sequence_bases) - width + 1)
    )


def occurrences(sequence: str, enzyme: Enzyme) -> int:
    """How many times this enzyme's site appears, counting both strands.

    Both strands, because a site is only guaranteed to be findable on the top
    strand when it is palindromic and not all of them are.
    """
    upper = _single_sequence(sequence, label="insert")
    found = _possible_site_count(upper, enzyme.site)

    mirrored = reverse_complement(enzyme.site).upper()
    if mirrored == enzyme.site.upper():
        return found

    other = Enzyme(
        enzyme.name,
        mirrored,
        enzyme.cuts_after,
        enzyme.first_observed_activity_flanking_bases,
        enzyme.end_cleavage_evidence_identity,
    )
    return found + _possible_site_count(upper, other.site)


def usable_enzymes(insert: str, *, catalogue: tuple[Enzyme, ...] | None = None) -> list[Enzyme]:
    """Catalogue enzymes whose recognition site is absent from this insert.

    Recognition-site length is not used as a suitability gate. A short site
    may be common in expectation yet genuinely absent from the submitted
    insert; the actual sequence occurrence check is the relevant executable
    evidence. Supplier-specific cloning suitability remains a separate
    protocol/catalogue question.
    """
    return [enzyme for enzyme in (catalogue or ENZYMES) if occurrences(insert, enzyme) == 0]


def build_tail(
    enzyme_name: str,
    insert: str,
    *,
    protective_sequence: str,
) -> Tail:
    """Build one restriction tail from an explicit protective sequence.

    The supplier rule determines how *many* bases the named branch needs.  It
    does not determine their identity, so this low-level constructor never
    synthesises a filler sequence.  The caller must provide the actual DNA that
    will be ordered.

    Raises:
        TailError: for an unknown enzyme, one whose site is in the insert, or
        a malformed protective sequence.
    """
    enzyme = BY_NAME.get(enzyme_name)
    if enzyme is None:
        known = ", ".join(sorted(BY_NAME))
        raise TailError(f"`{enzyme_name}` is not an enzyme this build knows. Known: {known}")

    found = occurrences(insert, enzyme)
    if found:
        times = "time" if found == 1 else "times"
        raise TailError(
            f"{enzyme.name} cuts inside what you are amplifying: its site "
            f"`{enzyme.site}` appears {found} {times} there. The enzyme would "
            "cut the product in the middle as well as at its ends, so choose "
            "one whose site is absent."
        )

    if not isinstance(protective_sequence, str):
        raise TailError("Protective sequence must be explicit DNA text.")
    protective = protective_sequence.strip().upper()
    if any(base not in "ACGT" for base in protective):
        raise TailError(
            "Protective sequence must contain only A/C/G/T. Degenerate or non-DNA "
            "bases require a separately modelled cloning branch."
        )
    if protective and reverse_complement(protective) == protective:
        raise TailError(
            "The protective sequence is self reverse-complementary (palindromic). "
            "Choose different flanking bases; the NEB end-cleavage guidance says "
            "the added bases should avoid palindromes and primer dimers."
        )
    return Tail(
        sequence=protective + enzyme.site,
        enzyme=enzyme.name,
        site=enzyme.site,
        protective=protective,
        first_observed_activity_flanking_bases=enzyme.first_observed_activity_flanking_bases,
        end_cleavage_evidence_identity=enzyme.end_cleavage_evidence_identity,
    )


def end_geometry(enzyme: Enzyme) -> dict[str, Any]:
    """Derive the cohesive-end geometry when the catalogue supports it.

    The built-in cloning catalogue stores the top-strand cut position. For a
    palindromic recognition site the opposite-strand cut is fixed by symmetry,
    so blunt versus 5-prime/3-prime stagger and the exposed overhang can be
    derived without inventing supplier data. Non-palindromic sites need an
    explicit second-strand cleavage coordinate and therefore remain unresolved.
    """
    recognition = enzyme.site.upper()
    if reverse_complement(recognition) != recognition:
        return {
            "status": "unresolved-non-palindromic-site",
            "polarity": None,
            "overhang": None,
            "overhang_length": None,
            "ambiguous": any(base not in "ACGT" for base in recognition),
            "note": (
                "The catalogue stores one strand's cut position only. A non-palindromic "
                "recognition site needs an explicit opposite-strand cleavage coordinate before "
                "PCRStudio can claim its cohesive-end geometry."
            ),
        }

    top_cut = enzyme.cuts_after
    bottom_cut = enzyme.length - enzyme.cuts_after
    if top_cut == bottom_cut:
        return {
            "status": "derived-palindromic-site",
            "polarity": "blunt",
            "overhang": "",
            "overhang_length": 0,
            "ambiguous": False,
            "top_cut_after": top_cut,
            "bottom_cut_after": bottom_cut,
        }

    lo, hi = sorted((top_cut, bottom_cut))
    overhang = recognition[lo:hi]
    return {
        "status": "derived-palindromic-site",
        "polarity": "5-prime" if top_cut < bottom_cut else "3-prime",
        "overhang": overhang,
        "overhang_length": len(overhang),
        "ambiguous": any(base not in "ACGT" for base in overhang),
        "top_cut_after": top_cut,
        "bottom_cut_after": bottom_cut,
    }


def end_compatibility(left: Enzyme, right: Enzyme) -> bool | None:
    """Whether the two enzyme end families can ligate by sequence geometry.

    ``None`` is deliberate when either end cannot be resolved from this
    catalogue or contains an ambiguous overhang. This only answers compatibility
    between the *insert ends*. It does not prove vector compatibility, site order,
    digest efficiency, ligation efficiency or construct directionality.
    """
    left_end = end_geometry(left)
    right_end = end_geometry(right)
    if (
        left_end["status"] != "derived-palindromic-site"
        or right_end["status"] != "derived-palindromic-site"
    ):
        return None
    if left_end["ambiguous"] or right_end["ambiguous"]:
        return None
    if left_end["polarity"] == "blunt" or right_end["polarity"] == "blunt":
        return left_end["polarity"] == right_end["polarity"] == "blunt"
    if left_end["polarity"] != right_end["polarity"]:
        return False
    left_overhang = str(left_end["overhang"])
    right_overhang = str(right_end["overhang"])
    return left_overhang == right_overhang or left_overhang == reverse_complement(right_overhang)


def attach(primer: str, tail: Tail, **conditions: float) -> TailedPrimer:
    """Put the tail on, and measure the result as well as the original.

    Both, deliberately. The annealing temperature comes from the primer alone
    because the tail has nothing to pair with in the first cycle; the hairpin
    and self-dimer come from the whole oligo, because that is the molecule in
    the tube.
    """
    return TailedPrimer(
        anneals=analyse(primer, **conditions),
        whole=analyse(tail.sequence + primer, **conditions),
        tail=tail,
    )


def tails_interact(left: TailedPrimer, right: TailedPrimer, **conditions: float) -> dict[str, Any]:
    """Whether the two finished oligos hold on to each other.

    Measured on the whole molecules, not on the primers. Two tails that each
    end in a six-base site can pair with each other even when the primers they
    are attached to cannot, and a primer-dimer made of tails amplifies as
    happily as any other.
    """
    before = pair_dimer(left.anneals.sequence, right.anneals.sequence, **conditions)
    after = pair_dimer(left.whole.sequence, right.whole.sequence, **conditions)

    return {
        "without_tails": {"dg": before.dg, "tm": before.tm},
        "with_tails": {"dg": after.dg, "tm": after.tm},
        # How much worse the tails made it. A pair that was fine and is now
        # sticky is a pair the tails broke, which is a different problem from
        # a pair that was always sticky.
        "worsened_by": round(before.dg - after.dg, 2),
    }


def describe(tail: Tail) -> dict[str, Any]:
    """One tail, for the wire."""
    return {
        "enzyme": tail.enzyme,
        "site": tail.site,
        "protective": tail.protective,
        "first_observed_activity_flanking_bases": tail.first_observed_activity_flanking_bases,
        "end_cleavage_evidence_identity": tail.end_cleavage_evidence_identity,
        "sequence": tail.sequence,
        "length": tail.length,
    }
