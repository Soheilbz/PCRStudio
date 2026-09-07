"""Screening a colony with one primer you already own.

The ordinary colony screen puts both primers inside the insert: a product means
the insert is there. That answers one question and not the one people usually
have, because a plasmid that took up the insert backwards gives exactly the
same band.

Putting one primer in the vector answers both at once. A product appears only
when the insert is present *and* pointing the right way, because the vector
primer reads towards the cloning site and the insert primer has to read back at
it. Turn the insert round and the two primers face away from each other, and
nothing amplifies.

Three things make this a different design problem rather than an ordinary pair
with one primer typed in.

**The partner cannot move.** M13 forward is the sequence it is; you own the
tube. Several of these melt well below the window an ordinary design uses --
the 17-mer M13 reverse is near 49 degrees -- so the insert primer has to be
designed down to the vector primer rather than the two meeting in the middle.
That is what `vectors.partner_window` is for.

**The product length depends on a molecule this cannot see** unless it is
given one. The vector primer sits some distance from the cloning site, and that
distance is a property of the vector -- so with no vector, the result reports
the part it controls (how far the insert primer sits from the end of the
insert) and says plainly that the rest is missing, rather than quoting a number
short by however long the polylinker is. Given the vector, linearised where the
insert goes in, it measures that distance and adds the two.

**The two primers still have to not stick to each other.** A vector primer and
an insert primer were designed by different people years apart, so nothing has
ever checked them as a pair. Here, something does.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import primer3

from .design import Constraints
from .intake import IntakeError, resolve
from .thermo import (
    PRIMER3_TEMP_C,
    analyse,
    count_overlapping,
    pair_dimer,
    reverse_complement,
    salt_correction_for_conditions,
)
from .vectors import BY_NAME, UNIVERSAL, UniversalPrimer, partner_window


class BackboneError(ValueError):
    """A screen that cannot be designed, with what to do about it."""


def _single_sequence(text: str, *, label: str) -> str:
    """Read one exact DNA record through the shared intake contract."""
    try:
        parsed = resolve(text, name=label, lowercase_masking=False)
    except IntakeError as error:
        raise BackboneError(f"The {label} could not be read: {error}") from error
    if parsed.rna_input:
        raise BackboneError(
            f"The {label} contains RNA uracil (U). Vector/insert geometry needs "
            "a DNA sequence; provide DNA/cDNA instead of silently converting RNA."
        )
    if any(note.kind == "multipleRecords" for note in parsed.notes):
        raise BackboneError(
            f"The {label} input contains more than one FASTA record; this screen "
            f"needs one {label} sequence."
        )
    if parsed.ambiguous_at:
        raise BackboneError(
            f"The {label} contains IUPAC ambiguity codes, so exact primer geometry "
            "cannot be established. Paste an unambiguous sequence."
        )
    return parsed.upper


@dataclass(frozen=True)
class InsertPrimer:
    """One candidate primer inside the insert, measured against the partner."""

    sequence: str
    #: Where its 5' end sits on the plus strand of the insert, zero-based.
    start: int
    length: int
    tm: float
    gc_percent: float
    hairpin_dg: float
    self_dimer_dg: float
    #: How far this primer's 3' end is from the end of the insert the vector
    #: primer reads in from. The part of the product this design controls.
    from_the_junction: int
    #: How hard it holds on to the vector primer. The check nobody has ever
    #: done for these two molecules.
    cross_dimer_dg: float
    #: The thermal condition used for the cross-dimer measurement.
    cross_dimer_temperature_c: float
    #: Whether that number came from an assay hold or the Primer3 model reference.
    cross_dimer_temperature_role: str
    #: How far its melting temperature is from the partner's.
    tm_gap: float


def resolve_partner(named: str, sequence: str | None, **conditions: float) -> UniversalPrimer:
    """The vector primer, from a name in the catalogue or from typed bases.

    Raises:
        BackboneError: for a name that is not in the catalogue, or bases that
            are not bases.
    """
    if sequence is not None:
        cleaned = _single_sequence(sequence, label="vector primer")
        if not cleaned or set(cleaned) - set("ACGT"):
            raise BackboneError(
                "A vector primer given as a sequence must be plain A, C, G and "
                f"T. Received: {sequence[:40]}"
            )
        return UniversalPrimer(
            name=named or "your vector primer",
            sequence=cleaned,
            reads="forward",
            family="supplied",
            note="Given as a sequence rather than chosen from the catalogue.",
        )

    known = BY_NAME.get(named)
    if known is None:
        names = "; ".join(primer.name for primer in UNIVERSAL)
        raise BackboneError(
            f"`{named}` is not a primer this build knows. Either choose one of "
            f"these, or give the sequence you have. Known: {names}"
        )
    return known


def _candidates(
    insert: str,
    forward: bool,
    limits: Constraints,
    reaction: dict[str, float],
    how_many: int,
) -> tuple[list[dict[str, Any]], str]:
    """Primer3's list for one side of the insert, and what it said about it."""
    settings = {
        "PRIMER_TASK": "pick_primer_list",
        "PRIMER_PICK_LEFT_PRIMER": 1 if forward else 0,
        "PRIMER_PICK_RIGHT_PRIMER": 0 if forward else 1,
        "PRIMER_PICK_INTERNAL_OLIGO": 0,
        "PRIMER_PICK_ANYWAY": 0,
        "PRIMER_NUM_RETURN": how_many,
        "PRIMER_EXPLAIN_FLAG": 1,
        "PRIMER_MAX_NS_ACCEPTED": 0,
        "PRIMER_LOWERCASE_MASKING": 0,
        "PRIMER_MIN_SIZE": limits.length_min,
        "PRIMER_OPT_SIZE": limits.length_opt,
        "PRIMER_MAX_SIZE": limits.length_max,
        "PRIMER_MIN_TM": limits.tm_min,
        "PRIMER_OPT_TM": limits.tm_opt,
        "PRIMER_MAX_TM": limits.tm_max,
        "PRIMER_MIN_GC": limits.gc_min,
        "PRIMER_MAX_GC": limits.gc_max,
        "PRIMER_MAX_POLY_X": limits.max_poly_x,
        "PRIMER_GC_CLAMP": limits.gc_clamp,
        "PRIMER_MAX_END_GC": limits.max_end_gc,
        "PRIMER_TM_FORMULA": 1,
        "PRIMER_THERMODYNAMIC_OLIGO_ALIGNMENT": 1,
        "PRIMER_THERMODYNAMIC_TEMPLATE_ALIGNMENT": 0,
        "PRIMER_SALT_CORRECTIONS": salt_correction_for_conditions(reaction)[1],
        "PRIMER_SALT_MONOVALENT": reaction["mv_conc"],
        "PRIMER_SALT_DIVALENT": reaction["dv_conc"],
        "PRIMER_DNTP_CONC": reaction["dntp_conc"],
        "PRIMER_DNA_CONC": reaction["dna_conc"],
    }
    if limits.max_end_stability is not None:
        settings["PRIMER_MAX_END_STABILITY"] = limits.max_end_stability

    answer = primer3.bindings.design_primers(
        {"SEQUENCE_ID": "insert", "SEQUENCE_TEMPLATE": insert}, settings
    )

    side = "LEFT" if forward else "RIGHT"
    found: list[dict[str, Any]] = []
    for index in range(answer.get(f"PRIMER_{side}_NUM_RETURNED", 0)):
        start, length = answer[f"PRIMER_{side}_{index}"]
        found.append(
            {
                "sequence": answer[f"PRIMER_{side}_{index}_SEQUENCE"],
                # Primer3 reports a right primer by its 3'-most plus-strand
                # coordinate, which is where it starts reading backwards. Both
                # are turned into a plus-strand 5' position here.
                "start": start if forward else start - length + 1,
                "length": length,
            }
        )

    return found, answer.get(f"PRIMER_{side}_EXPLAIN", "")


def _product(
    vector: str,
    partner: UniversalPrimer,
    primers: list[Any],
    forward: bool,
) -> dict[str, Any]:
    """How long the band is, when the vector is known — and why not, when it is not.

    The vector primer sits some distance from the cloning site and that
    distance belongs to a molecule this module had never seen, so the product
    size was reported as unknown for every screen it ever produced. It is the
    number somebody holds a gel up against.

    The contract is the plasmid **linearised where the insert goes in**, which
    is the molecule they had in their hand before the ligation. Then the
    distance is from the vector primer's 3' end to the end of that string, and
    nothing has to be assumed about where a file begins.

    Raises:
        BackboneError: for a vector the primer does not sit in exactly once. A
            primer that sits twice gives a band that does not say which site it
            came from, and one that sits nowhere is the wrong primer for this
            plasmid — either way, a number computed from it would be fiction.
    """
    if not vector.strip():
        return {
            "known": False,
            "note": (
                "The product is however far the vector primer sits from the cloning "
                "site, plus the distance given for each primer above. That first part "
                "is a property of your plasmid rather than of this design — paste the "
                "vector, linearised where the insert goes in, and this will add it up."
            ),
        }

    sequence = _single_sequence(vector, label="vector")
    forward_at = sequence.find(partner.sequence)
    reverse_at = sequence.find(reverse_complement(partner.sequence))
    hits = count_overlapping(sequence, partner.sequence) + count_overlapping(
        sequence, reverse_complement(partner.sequence)
    )

    if hits == 0:
        raise BackboneError(
            f"{partner.name} is not in the vector you pasted. Plasmids are edited "
            "constantly, and a primer that sits in the published sequence may not "
            "sit in the derivative on your bench — which is exactly the check this "
            "is here to do."
        )
    if hits > 1:
        raise BackboneError(
            f"{partner.name} sits in {hits} places in this vector, so a product "
            "using it would not tell you which one it came from."
        )

    # Reading towards the cloning site, which is the end of a vector linearised
    # there. The primer's 3' end is its last base going forward and its first
    # going back, and the distance is measured from that end.
    if forward_at >= 0:
        reads = "forward"
        to_the_site = len(sequence) - (forward_at + len(partner.sequence))
    else:
        reads = "reverse"
        to_the_site = reverse_at

    if to_the_site < 0:
        raise BackboneError(
            f"{partner.name} reads away from the end of this vector, so it never "
            "reaches the insert. Linearise the plasmid where the insert goes in, "
            "or use the primer on the other side of the site."
        )

    return {
        "known": True,
        "vector_bases": to_the_site,
        "sizes": [
            {
                "primer": one.sequence,
                # Both halves, added up. The vector's part is the same for
                # every candidate; the insert's is what this design chose.
                "bases": to_the_site + one.from_the_junction + len(one.sequence),
            }
            for one in primers
        ],
        "note": (
            f"{partner.name} sits {to_the_site} bases from the end of the vector you "
            f"pasted, reading {reads}. Added to how far each primer sits into the "
            f"insert, that is the band — the whole number rather than the half this "
            f"design controls."
        ),
    }


def design(
    insert: str,
    partner: UniversalPrimer,
    *,
    reads_into: str = "start",
    limits: Constraints | None = None,
    reaction: dict[str, float],
    how_many: int = 5,
    vector: str = "",
    temperature_c: float | None = None,
) -> dict[str, Any]:
    """One insert primer to pair with a vector primer you already own.

    Args:
        reads_into: which end of the insert the vector primer approaches from.
            `start` is the ordinary case -- the vector primer reads forward into
            the beginning of the insert, so the insert primer must read back
            towards it, on the reverse strand.
        vector: the plasmid, linearised where the insert goes in. Optional, and
            what it buys is the product size. Without it this can only report
            the half it controls -- how far the insert primer sits from the end
            of the insert -- because the other half is however far the vector
            primer sits from the cloning site, which is a property of a molecule
            this had never seen. That is a number somebody compares against a
            gel, and one short by the length of a polylinker is worse than none.
        temperature_c: optional shared assay/model temperature when a named
            workflow supplies one. Scientific-Strict does not derive a bench
            annealing temperature from the two measured primer Tm values.

    Raises:
        BackboneError: for a vector the primer does not sit in exactly once, a
            non-finite/out-of-range shared hold, or a sequence/window in which
            Primer3 finds no profile-valid partner primer.
    """
    if reads_into not in {"start", "end"}:
        raise BackboneError("`reads_into` is either `start` or `end`.")
    if temperature_c is not None:
        if isinstance(temperature_c, bool):
            raise BackboneError("`temperature_c` must be a finite number, not a boolean.")
        try:
            temperature_c = float(temperature_c)
        except (TypeError, ValueError) as error:
            raise BackboneError("`temperature_c` must be a finite number.") from error
        if not math.isfinite(temperature_c) or not 0.0 < temperature_c < 100.0:
            raise BackboneError("`temperature_c` must be finite and between 0 and 100 °C.")

    insert = _single_sequence(insert, label="insert")
    # Do not invent a biological/gel minimum for the insert.  Whether a short
    # insert can host a profile-valid partner primer is a geometry/search
    # question owned by Primer3; whether the resulting band is resolvable is a
    # property of the user's electrophoresis workflow.

    # The vector primer reads towards the insert, so the insert primer reads
    # back at it. Approaching the start means the insert primer is on the
    # reverse strand; approaching the end means the forward strand.
    forward = reads_into == "end"

    window = partner_window(partner, **reaction)
    base = limits or Constraints()
    tuned = Constraints(
        **{
            **{field: getattr(base, field) for field in base.__dataclass_fields__},
            "tm_min": window["tm_min"],
            "tm_opt": window["tm_opt"],
            "tm_max": window["tm_max"],
        }
    )

    found, explanation = _candidates(insert, forward, tuned, reaction, how_many * 3)
    if not found:
        raise BackboneError(
            f"No primer in this insert melts near {window['tm_opt']} degrees, "
            f"which is what {partner.name} needs its partner to do. Primer3 "
            f"said: {explanation or 'nothing'}. A longer insert, or a warmer "
            "vector primer, is usually the answer."
        )

    partner_tm = partner.melting_temperature(**reaction)
    measured: list[InsertPrimer] = []
    for entry in found:
        report = analyse(entry["sequence"], **reaction)
        dimer_temperature = float(temperature_c) if temperature_c is not None else PRIMER3_TEMP_C
        dimer_temperature_role = (
            "explicit-assay-temperature"
            if temperature_c is not None
            else "primer3-thermodynamic-model-reference-not-bench-ta"
        )
        cross = pair_dimer(
            partner.sequence,
            entry["sequence"],
            **reaction,
            temp_c=dimer_temperature,
        )
        # How much of the product this design accounts for. The vector adds an
        # unknown amount in front of it.
        junction = entry["start"] + entry["length"] if forward else len(insert) - entry["start"]
        measured.append(
            InsertPrimer(
                sequence=report.sequence,
                start=entry["start"],
                length=report.length,
                tm=report.tm,
                gc_percent=report.gc_percent,
                hairpin_dg=report.hairpin.dg,
                self_dimer_dg=report.self_dimer.dg,
                from_the_junction=junction,
                cross_dimer_dg=cross.dg,
                cross_dimer_temperature_c=dimer_temperature,
                cross_dimer_temperature_role=dimer_temperature_role,
                tm_gap=round(abs(report.tm - partner_tm), 1),
            )
        )

    # Closest temperature first, and a sticky pair pushed down. A primer that
    # melts perfectly and dimerises with the partner is not the better choice.
    measured.sort(key=lambda p: (p.tm_gap, -p.cross_dimer_dg))

    return {
        "partner": {
            "name": partner.name,
            "sequence": partner.sequence,
            "family": partner.family,
            "tm": round(partner_tm, 1),
            "note": partner.note,
        },
        "window": window,
        "reads_into": reads_into,
        "primers": [
            {
                "sequence": p.sequence,
                "start": p.start,
                "length": p.length,
                "tm": p.tm,
                "gc_percent": p.gc_percent,
                "hairpin_dg": p.hairpin_dg,
                "self_dimer_dg": p.self_dimer_dg,
                "cross_dimer_dg": p.cross_dimer_dg,
                "tm_gap": p.tm_gap,
                "from_the_junction": p.from_the_junction,
                "orientation": "forward" if forward else "reverse",
                "cross_dimer_temperature_c": p.cross_dimer_temperature_c,
                "cross_dimer_temperature_role": p.cross_dimer_temperature_role,
            }
            for p in measured[:how_many]
        ],
        "product": _product(vector, partner, measured[:how_many], forward),
        "orientation": (
            "A product appears only if the insert went in the way round that "
            "leaves these two primers facing each other. That is the point of "
            "screening this way rather than with two primers inside the insert, "
            "which gives the same band either way round."
        ),
    }


def reverse_of(sequence: str) -> str:
    """Exported so callers do not import a second reverse-complement."""
    return reverse_complement(sequence)
