"""Where an enzyme cuts, and how big a circle that makes.

Inverse PCR begins with a decision this tool cannot make for anybody: which
enzyme to cut with. The choice sets where the molecule opens, how much unknown
sequence the circle carries, and therefore whether the experiment answers the
question at all. Nothing in a pasted sequence says which enzyme somebody has in
the freezer.

What a tool can do is measure. Given a sequence and a list of enzymes it can
say, for each: how many times that enzyme cuts inside what you know, where, and
how big the resulting fragment is likely to be out in the sequence you do not
have.

Two things here are easy to get wrong and both are got right deliberately.

Sites overlap. `GGATCCGGATCC` carries two BamHI sites and a scan that consumes
its match finds one. Counting them is done with a lookahead so nothing is eaten.

And the expected fragment size is not four-to-the-power-of-the-site-length. That
number is the *average fragment*, and it answers a question nobody asks. The
fragment somebody's insertion actually sits in is drawn length-biased: a long
fragment covers more bases, so a randomly chosen base is more likely to be in
one. For a six-cutter the average fragment is about 4 kb and the fragment
containing a random base averages about 8 kb, and quoting the first is how
somebody chooses an enzyme that gives them twice the product they planned for.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from itertools import pairwise

from .thermo import reverse_complement

#: What each IUPAC code stands for, as a character class.
IUPAC = {
    "A": "A",
    "C": "C",
    "G": "G",
    "T": "T",
    "R": "[AG]",
    "Y": "[CT]",
    "S": "[GC]",
    "W": "[AT]",
    "K": "[GT]",
    "M": "[AC]",
    "B": "[CGT]",
    "D": "[AGT]",
    "H": "[ACT]",
    "V": "[ACG]",
    "N": ".",
}


class RestrictionError(ValueError):
    """An enzyme or a sequence this cannot work with."""


@dataclass(frozen=True)
class Enzyme:
    """One enzyme, by what it recognises."""

    name: str
    site: str
    #: How many bases into the site the cut falls on the top strand.
    #:
    #: What decides the exact coordinate the circle opens at. Blunt cutters cut
    #: in the middle; the common sticky ones cut near one end.
    cuts_after: int
    #: First flanking-base count with non-zero activity in the cited supplier table.
    #: None means this catalogue has not yet verified a value for the enzyme.
    first_observed_activity_flanking_bases: int | None = None
    #: Exact supplier/formulation identity behind the close-to-end observation.
    #: This matters because current supplier tables may list only an HF variant
    #: even when the recognition enzyme has a legacy/non-HF name.
    end_cleavage_evidence_identity: str | None = None

    @property
    def length(self) -> int:
        return len(self.site)

    def pattern(self) -> str:
        """The site as a regular expression, ambiguity codes expanded.

        Recognition metadata is executable scientific data. Refuse an empty
        site or a cut coordinate outside the site instead of letting malformed
        catalogue entries turn into a zero-width regex or an impossible cut.
        """
        recognition = self.site.upper()
        if not recognition:
            raise RestrictionError(f"{self.name} has an empty recognition site")
        if self.cuts_after < 0 or self.cuts_after > len(recognition):
            raise RestrictionError(
                f"{self.name} cuts after {self.cuts_after} bases, outside its "
                f"{len(recognition)}-base recognition site `{self.site}`"
            )
        if (
            self.first_observed_activity_flanking_bases is not None
            and self.first_observed_activity_flanking_bases < 0
        ):
            raise RestrictionError(f"{self.name} has a negative flanking-base activity annotation")
        if (
            self.first_observed_activity_flanking_bases is not None
            and not self.end_cleavage_evidence_identity
        ):
            raise RestrictionError(
                f"{self.name} has close-to-end activity data without the exact "
                "supplier/formulation identity that produced it"
            )
        try:
            return "".join(IUPAC[base] for base in recognition)
        except KeyError as error:
            raise RestrictionError(
                f"{self.name} is written as `{self.site}`, which is not a "
                "recognition site: only IUPAC codes belong there"
            ) from error


#: Versioned executable registry.  The JSON lives inside the worker package so
#: source, wheel and persisted release evidence all carry the same identities.
#: Bio.Restriction/pydna remains an independent validator rather than the source
#: that silently changes this curated Generation-1 surface when Biopython updates.
RESTRICTION_REGISTRY_RESOURCE = "data/restriction_enzyme_registry.json"


def _load_enzyme_registry() -> tuple[dict[str, object], tuple[Enzyme, ...]]:
    raw = (
        files("pcr_tools")
        .joinpath(*RESTRICTION_REGISTRY_RESOURCE.split("/"))
        .read_text(encoding="utf-8")
    )
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("schema_version") != "1.0.0":
        raise RestrictionError("restriction-enzyme registry is missing schema_version 1.0.0")
    rows = document.get("enzymes")
    if not isinstance(rows, list) or not rows:
        raise RestrictionError("restriction-enzyme registry contains no enzyme identities")
    enzymes: list[Enzyme] = []
    names: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise RestrictionError(f"restriction-enzyme registry row {index} is not an object")
        name = str(row.get("name") or "").strip()
        site = str(row.get("site") or "").strip().upper()
        cut = row.get("cuts_after")
        flanking = row.get("first_observed_activity_flanking_bases")
        evidence = row.get("end_cleavage_evidence_identity")
        if not name or name in names:
            raise RestrictionError(
                f"restriction-enzyme registry has an empty or duplicate name at row {index}"
            )
        if isinstance(cut, bool) or not isinstance(cut, int):
            raise RestrictionError(f"{name} has a non-integer cuts_after value in the registry")
        if flanking is not None and (isinstance(flanking, bool) or not isinstance(flanking, int)):
            raise RestrictionError(f"{name} has an invalid close-to-end flanking-base annotation")
        enzyme = Enzyme(
            name=name,
            site=site,
            cuts_after=cut,
            first_observed_activity_flanking_bases=flanking,
            end_cleavage_evidence_identity=(
                str(evidence).strip() if evidence is not None else None
            ),
        )
        enzyme.pattern()  # validate site/cut/evidence invariants at import time
        names.add(name)
        enzymes.append(enzyme)
    return document, tuple(enzymes)


RESTRICTION_REGISTRY, ENZYMES = _load_enzyme_registry()

BY_NAME = {enzyme.name: enzyme for enzyme in ENZYMES}


def sites(sequence: str, enzyme: Enzyme, *, circular: bool = False) -> list[int]:
    """Every position this enzyme cuts, zero-based, on the top strand.

    Overlapping sites are all found: `GGATCCGGATCC` carries two BamHI sites,
    and a scan that consumed its match would report one.

    Args:
        circular: Whether the sequence closes on itself, in which case a site
            can straddle the join and would otherwise be missed entirely.
    """
    sequence = sequence.upper()
    # Validate the catalogue entry before building either orientation. Without
    # this explicit call, the reverse-complement implementation would turn an
    # unknown recognition letter into `N` and a malformed enzyme could escape
    # the same actionable error that `Enzyme.pattern()` provides.
    enzyme.pattern()

    scanned = sequence
    if circular and len(sequence) >= enzyme.length:
        # Enough of the start repeated at the end that a straddling site is
        # visible, and no more, so nothing is found twice.
        scanned = sequence + sequence[: enzyme.length - 1]

    # A recognition sequence is written in one strand's 5'-to-3' direction.
    # For a non-palindromic site, the reverse-complement spelling is an equally
    # real site on the other orientation. The cut coordinate is mirrored
    # inside the site: a cut after `c` bases in the written orientation is
    # after `length - c` bases when the top strand carries the reverse
    # complement. Palindromic sites are searched once and then deduplicated.
    #
    # NOTE: the built-in cloning catalogue is palindromic. Type-IIS/other
    # asymmetric cleavage remains outside the flanking-pair cloning contract
    # and must not use this one-coordinate model as evidence of two-strand end
    # geometry. See `tails.end_geometry`, which fails closed for such sites.
    recognition = enzyme.site.upper()
    mirrored = reverse_complement(recognition)
    patterns = [(recognition, enzyme.cuts_after)]
    if mirrored != recognition:
        patterns.append((mirrored, enzyme.length - enzyme.cuts_after))

    found = []
    for site, cut_after in patterns:
        pattern = re.compile(f"(?=({''.join(IUPAC[base] for base in site)}))")
        found.extend(
            (match.start() + cut_after) % len(sequence) for match in pattern.finditer(scanned)
        )
    return sorted(set(found))


@dataclass(frozen=True)
class FragmentSizes:
    """How big the pieces are when an enzyme is finished with a sequence.

    Two averages, because the two answer different questions and quoting the
    first when somebody meant the second is how an inverse PCR ends up twice
    the size that was planned for.
    """

    #: The number of cuts the estimate is drawn from.
    cuts: int
    #: Half the fragments are shorter than this.
    median: int
    #: The plain average fragment.
    mean: int
    #: The average fragment *containing a randomly chosen base*, which is what
    #: an insertion site is. Longer than the mean, always, because a long
    #: fragment covers more bases and so is more likely to be the one you are
    #: in.
    mean_at_a_random_base: int


def fragment_sizes(sequence: str, enzyme: Enzyme, *, circular: bool = False) -> FragmentSizes:
    """What this enzyme does to this sequence, measured rather than assumed.

    Raises:
        RestrictionError: if the enzyme does not cut at all, so there is
            nothing to measure.
    """
    positions = sites(sequence, enzyme, circular=circular)
    if not positions or (len(positions) < 2 and not circular):
        raise RestrictionError(
            f"{enzyme.name} cuts this sequence {len(positions)} time(s), so there "
            "are no fragments to measure. Either the sequence is too short for it "
            "or it is the wrong enzyme for this job."
        )
    if circular and len(positions) == 1:
        # One cut in a circle gives one fragment: the whole molecule, opened.
        whole = len(sequence)
        return FragmentSizes(cuts=1, median=whole, mean=whole, mean_at_a_random_base=whole)

    lengths = [later - earlier for earlier, later in pairwise(positions)]
    if circular:
        lengths.append(len(sequence) - positions[-1] + positions[0])

    lengths.sort()
    middle = len(lengths) // 2
    median = lengths[middle] if len(lengths) % 2 else (lengths[middle - 1] + lengths[middle]) // 2
    total = sum(lengths)
    # Each fragment weighted by how many bases it holds, which is exactly how
    # likely it is to be the one an arbitrary site falls in.
    weighted = sum(length * length for length in lengths) / total

    return FragmentSizes(
        cuts=len(positions),
        median=median,
        mean=total // len(lengths),
        mean_at_a_random_base=round(weighted),
    )


@dataclass(frozen=True)
class Choice:
    """One enzyme considered for one explicitly named restriction question."""

    enzyme: str
    site: str
    #: Where it cuts inside the region the caller knows.
    cuts_inside: list[int]
    #: Whether it satisfies the selected purpose. For `inverse-flank` that
    #: means zero internal sites in the complete known anchor; for `absent` it
    #: means zero sites in the insert; `open-once` is a separate one-cut query.
    usable: bool
    why: str
    #: The fragment this enzyme would be expected to give, from its site
    #: density in the sequence supplied. Absent when it cuts too rarely to say.
    expected: FragmentSizes | None = None


#: Explicit questions somebody asks a restriction catalogue.
#:
#: They are not interchangeable, and that is why the question is a parameter rather than
#: two copies of this function. Standard two-flank inverse PCR needs an enzyme
#: with zero recognition sites inside the complete known anchor; cloning also
#: asks for zero sites, but against the insert and for a different physical
#: reason. `OPEN_ONCE` remains only for an explicitly selected one-cut workflow
#: and is never an alias or fallback for either current question.
OPEN_ONCE = "open-once"
ABSENT = "absent"
INVERSE_FLANK = "inverse-flank"
PURPOSES = (OPEN_ONCE, ABSENT, INVERSE_FLANK)


def choose_enzyme(
    known: str,
    *,
    enzymes: tuple[Enzyme, ...] = ENZYMES,
    background: str | None = None,
    purpose: str = OPEN_ONCE,
) -> list[Choice]:
    """Every enzyme ranked for the question being asked of this sequence.

    Args:
        background: A larger sequence to estimate fragment sizes from, when the
            known region is too short to say anything. The genome or plasmid
            the region came from is the right thing to pass.
        purpose: `INVERSE_FLANK` for standard two-flank inverse PCR, `ABSENT`
            for cloning, or `OPEN_ONCE` only for workflows that explicitly need
            one cut inside the supplied sequence. See the
            note above — they rank the same catalogue in opposite orders.

    Returns:
        Usable enzymes first, then the rest, each with the reason.
    """
    if not known.strip():
        raise RestrictionError("There is no sequence to look for sites in.")
    if purpose not in PURPOSES:
        raise RestrictionError(
            f"`{purpose}` is not a question this answers. It answers: " + ", ".join(PURPOSES) + "."
        )

    ranked: list[Choice] = []
    for enzyme in enzymes:
        inside = sites(known, enzyme)

        if purpose == ABSENT:
            if not inside:
                usable, why = (
                    True,
                    "does not cut the insert, so it can go on a primer end",
                )
            else:
                usable, why = (
                    False,
                    f"cuts the insert {len(inside)} time(s), so digesting the "
                    "product would cut the middle out as well as the ends",
                )
        elif purpose == INVERSE_FLANK:
            if not inside:
                usable, why = (
                    True,
                    "does not cut the known anchor, so the complete anchor can remain "
                    "on one restriction fragment for the standard two-flank inverse-PCR branch",
                )
            else:
                usable, why = (
                    False,
                    f"cuts the known anchor {len(inside)} time(s); standard two-flank "
                    "inverse PCR requires the complete known anchor to remain intact on one fragment",
                )
        elif len(inside) == 1:
            usable, why = (
                True,
                "cuts the supplied sequence once, as this explicitly selected purpose requires",
            )
        elif not inside:
            usable, why = False, "does not cut the supplied sequence"
        else:
            usable, why = (
                False,
                f"cuts the supplied sequence {len(inside)} times, not exactly once",
            )

        expected: FragmentSizes | None = None
        # Fragment-size expectation is evidence about the larger digest
        # background, not about the small known region merely because it is the
        # only sequence available.  Falling back to `known` would rank inverse-
        # PCR enzymes by the cut position inside the anchor while pretending to
        # predict the unknown flank.  Keep the estimate unresolved unless an
        # explicit genome/plasmid background was supplied.
        if background:
            try:
                expected = fragment_sizes(background, enzyme)
            except RestrictionError:
                expected = None

        ranked.append(
            Choice(
                enzyme=enzyme.name,
                site=enzyme.site,
                cuts_inside=inside,
                usable=usable,
                why=why,
                expected=expected,
            )
        )

    # Usable first.  For inverse PCR, an explicit larger digest background can
    # support a fragment-size ranking.  Without that evidence all usable
    # enzymes remain in stable catalogue order; the known anchor alone cannot
    # predict how far the next restriction site lies in an unknown flank.
    # Cloning likewise has no fragment-size ranking.
    ranked.sort(
        key=lambda choice: (
            not choice.usable,
            0
            if purpose in {ABSENT, INVERSE_FLANK}
            else -(choice.expected.mean_at_a_random_base if choice.expected else 0),
        )
    )
    return ranked


def choice_to_dict(choice: Choice) -> dict[str, object]:
    """One ranked enzyme as plain data."""
    return {
        "enzyme": choice.enzyme,
        "site": choice.site,
        "cuts_inside": choice.cuts_inside,
        "usable": choice.usable,
        "why": choice.why,
        "expected_fragment": (
            None
            if choice.expected is None
            else {
                "cuts": choice.expected.cuts,
                "median": choice.expected.median,
                "mean": choice.expected.mean,
                "mean_at_a_random_base": choice.expected.mean_at_a_random_base,
                "note": (
                    "The second number is the one to plan against: a randomly "
                    "chosen site sits in a long fragment more often than in a "
                    "short one, so the fragment you are actually in is larger "
                    "than the average fragment."
                ),
            }
        ),
    }
