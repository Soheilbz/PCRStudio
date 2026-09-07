"""One primer, reading into something rather than amplifying across it.

Two assays live here and they are the same engine for one reason: neither has a
partner. A sequencing primer reads a trace outward from where it sits; a RACE
primer amplifies towards an end nobody has sequenced yet, against a partner
that comes out of a kit rather than out of a search. In both, exactly one oligo
is being designed, and every pair-level idea — product size, melting
temperatures matched, cross-dimers — is either absent or somebody else's
problem.

What replaces them is placement, and placement is the whole design.

A Sanger trace does not start where the primer ends. The first few dozen bases
are unreadable, and the trace degrades again after several hundred, so a
sequencing primer has a *window* it must place its target inside: far enough
ahead that the target has cleared the unreadable start, close enough that the
target is still legible when the read reaches it. A primer that is beautiful by
every thermodynamic measure and sitting thirty bases from its target is a
wasted reaction, and no amount of melting temperature fixes it.

For Sanger the engine reports the provider-declared read window and target
placement. For RACE it instead searches an explicit region of known cDNA for a
GSP oriented toward the requested unknown transcript end, and screens that GSP
against the exact amplification partner selected by the RACE protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import primer3

from .design import Constraints, clean_template
from .intake import target_to_dict
from .presets import thermodynamic_model
from .provenance import provenance
from .registries.authorities import RACE_AUTHORITY, SEQUENCING_AUTHORITY, record as authority_record
from .scientific_integrity import enforce_constraint_overrides
from .workflow_evidence import evidence_block
from .sanger_trace import SangerTraceError, parse_ab1_base64
from .settings import excluded_from, how_many_from, label, prepare
from .thermo import (
    DEFAULT_CONDITIONS,
    analyse,
    pair_dimer,
    report_to_dict,
    salt_correction_for_conditions,
    reverse_complement,
)


class SinglePrimerError(ValueError):
    """A placement that could not be asked for."""


# Sequencing design and cycle-sequencing chemistry are separate authorities.
# Provider submission quantities never mutate the primer ranking.
SEQUENCING_PROTOCOLS = tuple(SEQUENCING_AUTHORITY["groups"]["chemistry_protocols"])
SEQUENCING_DESIGN_PROFILES = tuple(SEQUENCING_AUTHORITY["groups"]["design_profiles"])
SHA256_HEX_LENGTH = 64

SEQUENCING_INSTRUMENTS = (
    "unresolved", "seqstudio", "seqstudio-flex", "3500", "3500xl", "3730", "3730xl", "other"
)


def sequencing_protocol(named: str | None) -> dict[str, Any] | None:
    selected = str(named or "not-selected")
    if selected not in SEQUENCING_PROTOCOLS:
        raise SinglePrimerError("sequencing_protocol must be one of: " + ", ".join(SEQUENCING_PROTOCOLS) + ".")
    if selected == "not-selected":
        return None
    record = authority_record(SEQUENCING_AUTHORITY, selected)
    record["protocol_id"] = selected
    return record


def sequencing_design_profile(named: str | None) -> dict[str, Any]:
    selected = str(named or "generic-cycle-sequencing")
    if selected not in SEQUENCING_DESIGN_PROFILES:
        raise SinglePrimerError(
            "sequencing_design_profile must be one of: " + ", ".join(SEQUENCING_DESIGN_PROFILES) + "."
        )
    record = authority_record(SEQUENCING_AUTHORITY, selected)
    if record.get("execution_status") != "executable":
        raise SinglePrimerError(f"sequencing design profile `{selected}` is not executable")
    record["profile_id"] = selected
    return record


def universal_primer_candidates(template: str, *, direction: str) -> list[dict[str, Any]]:
    """Exact-binding diagnostic for the provider-curated universal-primer library.

    A library hit is only a reusable option. It never silently replaces the
    designed primer because read-window suitability still depends on the actual
    target and provider/instrument context.
    """
    seq = clean_template(template).upper()
    records = SEQUENCING_AUTHORITY.get("universal_primers", {}).get("records", {})
    hits: list[dict[str, Any]] = []
    for name, raw in records.items():
        if raw.get("direction") != direction:
            continue
        oligo = str(raw["sequence"]).upper()
        binding = oligo if direction == "forward" else reverse_complement(oligo)
        start = seq.find(binding)
        if start >= 0:
            hits.append({
                "name": name,
                "sequence": oligo,
                "direction": direction,
                "template_start": start,
                "exact_binding": True,
                "decision_impact": "diagnostic-only",
            })
    return hits


def sequencing_context(request: dict[str, Any], *, assay_id: str) -> dict[str, Any] | None:
    """Record the capillary handoff without pretending a trace has been reviewed."""
    fields = ("sequencing_instrument", "sequencing_instrument_name", "sequencing_facility_sop")
    supplied = any(request.get(field) not in (None, "") for field in fields)
    if assay_id != "sequencing-primer":
        if supplied:
            raise SinglePrimerError(
                "sequencing_instrument/sequencing_instrument_name/sequencing_facility_sop belong to sequencing-primer"
            )
        return None

    instrument = str(request.get("sequencing_instrument") or "unresolved").strip() or "unresolved"
    if instrument not in SEQUENCING_INSTRUMENTS:
        raise SinglePrimerError(
            "sequencing_instrument must be one of: " + ", ".join(SEQUENCING_INSTRUMENTS)
        )
    instrument_name = str(request.get("sequencing_instrument_name") or "").strip()
    if instrument == "other" and not instrument_name:
        raise SinglePrimerError("sequencing_instrument=other requires sequencing_instrument_name")
    if instrument != "other" and instrument_name:
        raise SinglePrimerError("sequencing_instrument_name is only valid with sequencing_instrument=other")
    facility_sop = str(request.get("sequencing_facility_sop") or "").strip()
    return {
        "instrument": instrument,
        "instrument_name": instrument_name or None,
        "facility_sop": facility_sop or None,
        "trace_status": "not-reviewed",
        "basecalling_status": "external-run-required",
        "quality_status": "unresolved-until-trace",
        "required_run_evidence": [
            "capillary trace/electropherogram",
            "basecalling/quality metrics from the facility workflow",
            "mixed-template or secondary-peak review",
            "read-length assessment for the actual instrument/run module",
        ],
        "note": (
            "Instrument identity is preserved for handoff only. Primer placement does not establish "
            "trace quality, usable read length or sequence confirmation."
        ),
    }


# ── The partner that comes out of a kit ────────────────────────────────────
#
# A RACE primer is not alone in its tube. It amplifies towards an end nobody
# has sequenced by pairing against an adapter primer of fixed sequence, so
# whether the two get on is checkable before anybody orders anything — and it
# was not checked, because the adapter never appeared anywhere in this engine.
# These are the common ones:

#: Exact PCR partner primers for the versioned GeneRacer Kit branch are
#: generated from the canonical RACE authority, not repeated in worker source.
GENERACER_25_0355_VL_ID = "generacer-kit-25-0355-vl"
_GENERACER_RECORD = authority_record(RACE_AUTHORITY, GENERACER_25_0355_VL_ID)
GENERACER_25_0355_VL_PARTNERS: dict[tuple[str, str], dict[str, str]] = {
    tuple(key.split(":")): dict(value)
    for key, value in _GENERACER_RECORD["partners"].items()
}
FIRSTCHOICE_RLM_RACE_ID = "firstchoice-rlm-race"
SMARTER_RACE_ID = "smarter-race-current"
_FIRSTCHOICE_RECORD = authority_record(RACE_AUTHORITY, FIRSTCHOICE_RLM_RACE_ID)
FIRSTCHOICE_RLM_RACE_PARTNERS: dict[tuple[str, str], dict[str, str]] = {
    tuple(key.split(":")): dict(value)
    for key, value in _FIRSTCHOICE_RECORD["partners"].items()
}
EXECUTABLE_NAMED_RACE_PARTNERS: dict[str, tuple[dict[str, Any], dict[tuple[str, str], dict[str, str]]]] = {
    GENERACER_25_0355_VL_ID: (_GENERACER_RECORD, GENERACER_25_0355_VL_PARTNERS),
    FIRSTCHOICE_RLM_RACE_ID: (_FIRSTCHOICE_RECORD, FIRSTCHOICE_RLM_RACE_PARTNERS),
}

# Keep the selectable branch deliberately narrow. The legacy 5′ AAP contains
# inosines and cannot be represented faithfully by Primer3's ordinary A/C/G/T
# thermodynamic model; the old code incorrectly substituted the 20-mer AUAP
# sequence under the AAP name. Legacy 3′ RACE likewise amplifies with UAP/AUAP
# after oligo-dT-adapter cDNA synthesis, not with the oligo-dT primer itself.
# Those older workflows can still be supplied as `custom` when the *actual PCR
# partner sequence* for the chosen round is known and is unambiguous DNA.
RACE_ADAPTERS = ("not-selected", GENERACER_25_0355_VL_ID, FIRSTCHOICE_RLM_RACE_ID, SMARTER_RACE_ID, "custom")
RACE_CHEMISTRIES = tuple(RACE_AUTHORITY["groups"]["chemistries"])
UNSUPPORTED_AMBIGUOUS_RACE_ADAPTERS = ("generacer", "AAP")
RACE_DIRECTIONS = ("5prime", "3prime")
RACE_DIRECTION_TO_READ = {"5prime": "reverse", "3prime": "forward"}

#: Input-sanity bound for a user-supplied RACE partner sequence. It is not a
#: performance threshold or a claim about all commercial RACE adapters.
MAX_CUSTOM_RACE_PARTNER_LENGTH = 200


def race_chemistry(named: str | None, legacy_adapter: str | None = None) -> dict[str, Any] | None:
    selected = str(named or legacy_adapter or "not-selected")
    if selected == "not-selected":
        return None
    if selected not in RACE_CHEMISTRIES:
        raise SinglePrimerError("race_chemistry must be one of: " + ", ".join(RACE_CHEMISTRIES) + ".")
    record = authority_record(RACE_AUTHORITY, selected)
    record["chemistry_id"] = selected
    status = record.get("execution_status")
    if status not in {"executable", "executable-if-complete"}:
        raise SinglePrimerError(
            f"RACE chemistry `{selected}` is {status}; exact PCR-partner identity/manual revision is required before execution."
        )
    return record


def race_direction(named: str | None) -> str | None:
    """Return the declared transcript end, or no RACE direction."""
    if named is None or str(named).strip() == "":
        return None
    selected = str(named)
    if selected not in RACE_DIRECTIONS:
        raise SinglePrimerError(
            "race_direction must be one of: " + ", ".join(RACE_DIRECTIONS) + "."
        )
    return selected


def race_adapter(
    named: str | None,
    custom_sequence: str | None = None,
    *,
    direction: str | None = None,
    round_name: str | None = None,
) -> dict[str, str] | None:
    """Resolve the exact amplification partner that will share the RACE PCR tube.

    Named executable branches are resolved from the canonical, versioned kit
    authority by transcript direction plus primary/nested round. `custom`
    requires the literal unambiguous PCR-partner sequence. Family-only
    ``generacer`` and ambiguous AAP identities are refused because they do not
    uniquely identify the exact PCR oligo.
    """
    selected = str(named or "not-selected")
    if selected in UNSUPPORTED_AMBIGUOUS_RACE_ADAPTERS:
        raise SinglePrimerError(
            f"race_adapter={selected} is an ambiguous, non-executable identity in the current contract. "
            f"Select {GENERACER_25_0355_VL_ID} for the GeneRacer Kit 25-0355 Version L branch, "
            "or provide the exact current PCR partner with race_adapter=custom."
        )
    if selected not in RACE_ADAPTERS:
        raise SinglePrimerError(
            "race_adapter must be one of: " + ", ".join(RACE_ADAPTERS) + "."
        )
    if selected == "not-selected":
        return None
    if selected == SMARTER_RACE_ID:
        if custom_sequence is None or not str(custom_sequence).strip():
            raise SinglePrimerError(
                "SMARTer RACE requires race_partner_sequence containing the exact current kit/SOP PCR partner; PCRStudio does not infer proprietary adapter primers from obsolete documents."
            )
        sequence = clean_template(str(custom_sequence)).upper()
        if len(sequence) > MAX_CUSTOM_RACE_PARTNER_LENGTH or any(base not in "ACGT" for base in sequence):
            raise SinglePrimerError(f"race_partner_sequence must be 1–{MAX_CUSTOM_RACE_PARTNER_LENGTH} unambiguous DNA bases (A/C/G/T)")
        record=authority_record(RACE_AUTHORITY, SMARTER_RACE_ID)
        return {
            "id":SMARTER_RACE_ID,"name":"SMARTer current caller-supplied exact PCR partner","sequence":sequence,
            "direction":direction,"round":round_name,"protocol_identity":record["selection"],
            "source_identity":record["source_identity"],"source_url":record["source_url"],"source_reviewed_date":record["source_reviewed_date"],
            "authority":"caller-supplied exact current kit/SOP partner",
        }
    if selected == "custom":
        if custom_sequence is None or not str(custom_sequence).strip():
            raise SinglePrimerError("race_adapter=custom requires race_partner_sequence")
        sequence = clean_template(str(custom_sequence)).upper()
        if (
            len(sequence) > MAX_CUSTOM_RACE_PARTNER_LENGTH
            or any(base not in "ACGT" for base in sequence)
        ):
            raise SinglePrimerError(
                f"race_partner_sequence must be 1–{MAX_CUSTOM_RACE_PARTNER_LENGTH} unambiguous DNA bases (A/C/G/T)"
            )
        return {
            "id": "custom",
            "name": "custom protocol PCR partner",
            "sequence": sequence,
            "authority": "user-supplied exact PCR-partner sequence",
        }
    if custom_sequence not in (None, ""):
        raise SinglePrimerError(
            "race_partner_sequence is only valid with race_adapter=custom or smarter-race-current"
        )
    if direction not in RACE_DIRECTIONS or round_name not in {"primary", "nested"}:
        raise SinglePrimerError(
            f"race_adapter={selected} requires explicit race_direction and race_round so the exact kit PCR partner can be selected."
        )
    record, partners = EXECUTABLE_NAMED_RACE_PARTNERS[selected]
    partner = partners[(direction, round_name)]
    return {
        "id": selected,
        **partner,
        "direction": direction,
        "round": round_name,
        "protocol_identity": record["selection"],
        "source_identity": record["source_identity"],
        "source_url": record["source_url"],
        "source_reviewed_date": record["source_reviewed_date"],
        **({"source_revision": record["source_revision"]} if record.get("source_revision") else {}),
        **({"source_revision_date": record["source_revision_date"]} if record.get("source_revision_date") else {}),
    }


#: How weak a cross-dimer has to be before it is worth saying.
#:
#: The same figure the order-level interaction screen watches at
#: (pipeline.CROSS_PAIR_DIMER_WATCH), for the same reason: below about six
#: kcal/mol a duplex competes with the primers rather than falling apart
#: around them, and unlike most cross-dimers this pair *will* share a tube —
#: that is what the assay is.
ADAPTER_DIMER_WATCH = -6.0


def adapter_screen(
    sequence: str, *, partner: dict[str, str], **conditions: float
) -> dict[str, Any]:
    """Diagnostic GSP/partner dimer evidence for the exact RACE PCR partner.

    The -6 kcal/mol line is an internal watch flag only. It neither rejects nor
    ranks a RACE GSP and is evaluated in the thermodynamic model's declared
    reference conditions, not at an invented PCR annealing temperature.
    """
    partner_sequence = partner["sequence"]
    structure = pair_dimer(sequence, partner_sequence, **conditions)
    flagged = structure.dg <= ADAPTER_DIMER_WATCH
    return {
        "partner": partner["name"],
        "partner_sequence": partner_sequence,
        "dg": structure.dg,
        "tm": structure.tm,
        "watch_threshold_dg": ADAPTER_DIMER_WATCH,
        "flagged": flagged,
        "decision_role": "diagnostic-watch-only-not-validity-or-ranking",
        "temperature_role": "Primer3 thermodynamic model context; not inferred bench Ta",
        "note": (
            f"GSP/partner cross-dimer is {structure.dg:.2f} kcal/mol. The internal "
            f"{ADAPTER_DIMER_WATCH:g} kcal/mol line is only a review flag; named kit/SOP "
            "conditions and wet-lab behaviour remain authoritative."
        ),
    }


#: How much of a Sanger trace is unreadable before it settles.
#:
#: The bases immediately after the primer come back as a smear of unresolved
#: peaks. Forty is conservative among the numbers service providers quote; some
#: say twenty and some say fifty, and the cost of being conservative is a
#: primer placed slightly further away, while the cost of being optimistic is a
#: read that does not cover what it was ordered for.
DEAD_ZONE = 40

#: How far a Sanger read stays legible.
#:
#: Eight hundred, which is the working figure rather than the best case. A good
#: capillary run reaches a thousand or more; quoting the best case is how
#: somebody orders one read for a region that needs two.
READ_LENGTH = 800

#: Which direction a primer reads.
DIRECTIONS = ("forward", "reverse")

#: How far either side of the ideal placement the search looks first.
#:
#: The ideal 3' end is `DEAD_ZONE` bases before the target: any closer and the
#: target is in the smear, any further and read is being thrown away. Twenty
#: bases either side of that is a band, not a point, so there is room to find a
#: good oligo without giving up the placement.
ACCURACY = 20

#: How many times the band may double before the search gives up.
#:
#: Each doubling is recorded, because a primer found only after the band grew
#: eightfold is a different fact from one found straight away, and the person
#: reading the result is the one who has to decide whether it will do.
MOST_WIDENINGS = 5


@dataclass(frozen=True)
class Window:
    """Where a primer has to sit for its target to be readable.

    Both bounds are distances from the target, measured to the primer's 3' end,
    because that is where the read begins.
    """

    #: Nearest the primer may be: any closer and the target is in the smear.
    nearest: int
    #: Furthest: any further and the read has faded before it arrives.
    furthest: int
    #: Where in the template that puts the primer, as a start and a length.
    region: tuple[int, int]
    #: How many times the search had to double its band before finding
    #: anything. Zero means the primer sits where it ideally would.
    widened: int = 0
    #: The stretch actually searched, which is the band rather than the whole
    #: legal window unless the search had to widen all the way out.
    searched: tuple[int, int] = (0, 0)

    def holds(self) -> bool:
        return self.furthest > self.nearest


def window_for(
    template_length: int,
    target_start: int,
    target_length: int,
    direction: str,
    *,
    dead_zone: int = DEAD_ZONE,
    read_length: int = READ_LENGTH,
) -> Window:
    """Where a primer must sit to read this target.

    Raises:
        SinglePrimerError: for a target the template does not hold, or a read
            that could not reach across it however it were placed.
    """
    if direction not in DIRECTIONS:
        raise SinglePrimerError(
            f"`{direction}` is not a direction to read in. It reads: " + ", ".join(DIRECTIONS) + "."
        )
    if dead_zone < 0:
        raise SinglePrimerError(f"The unreadable start cannot be negative: {dead_zone}.")
    if read_length < 1:
        raise SinglePrimerError(f"The readable trace length must be positive: {read_length}.")
    if target_start < 0 or target_start + target_length > template_length:
        raise SinglePrimerError(
            f"The target at {target_start}..{target_start + target_length} is not "
            f"inside a {template_length}-base template."
        )
    if target_length + dead_zone > read_length:
        raise SinglePrimerError(
            f"A {target_length}-base target cannot be read in one go: the first "
            f"{dead_zone} bases of a trace are unreadable and it stays legible for "
            f"about {read_length}, which leaves {read_length - dead_zone} usable. "
            "Two reads from opposite ends, or a primer walking the region, is what "
            "this needs."
        )

    # The far end of the target is what has to be reached, so the read has to
    # cover the whole of it rather than just arrive at its start.
    nearest = dead_zone
    furthest = read_length - target_length

    if direction == "forward":
        # Reading towards higher coordinates, so the primer sits before the
        # target and its 3' end is what the distance is measured from.
        end_lowest = max(0, target_start - furthest)
        end_highest = target_start - nearest
        region = (end_lowest, max(0, end_highest - end_lowest))
    else:
        # Reading towards lower coordinates: the primer sits after the target.
        after = target_start + target_length
        region = (after + nearest, max(0, furthest - nearest))

    return Window(nearest=nearest, furthest=furthest, region=region)


@dataclass(frozen=True)
class Candidate:
    """One primer, and where it puts the target in its own read."""

    sequence: str
    #: Zero-based start on the plus strand.
    at: int
    length: int
    direction: str
    #: How far the target is from this primer's 3' end. Sanger-only.
    reaches: int | None
    #: How much readable trace is left after the target ends. Sanger-only.
    spare: int | None
    penalty: float
    #: Whether reaching the target meant going round the join of a circle.
    #:
    #: True means the read starts after the target's coordinate and arrives at
    #: it by coming round the origin — which is what the molecule does and what
    #: a coordinate on its own cannot show. Reading a target near base zero of
    #: a plasmid was impossible before this: the string has nothing in front of
    #: it, and the molecule has two and a half thousand bases.
    wrapped_to_reach: bool = False


def design(
    template: str,
    *,
    target_start: int,
    target_length: int,
    direction: str = "forward",
    constraints: Constraints | None = None,
    conditions: dict[str, float] | None = None,
    how_many: int = 5,
    dead_zone: int = DEAD_ZONE,
    read_length: int = READ_LENGTH,
    excluded: list[tuple[int, int]] | None = None,
    circular: bool = False,
) -> tuple[list[Candidate], Window, str]:
    """Primers that would read this target, best first.

    Returns:
        The candidates, the window they had to sit in, and Primer3's own
        account of what it rejected.

    Raises:
        SinglePrimerError: for a placement that could not be asked for.
        SequenceError: if the template is not unambiguous DNA.
    """
    sequence = clean_template(template)
    limits = constraints or Constraints()
    limits.validate()
    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}

    # ── A plasmid has no end to run out of ──────────────────────────────────
    #
    # Reading a target near the origin was impossible: the primer has to sit
    # `dead_zone` bases in front of it, and in front of base 50 there are only
    # fifty bases of string. On the molecule there are two and a half thousand,
    # they are just written after it rather than before. So for a circle the
    # sequence is rotated: enough of its tail is moved to its front that the
    # window in front of the target is real sequence.
    #
    # Rotating rather than repeating, because unlike a pair search this one
    # places a single primer relative to one target — there is no second copy
    # of anything to confuse, and every coordinate folds back with one modulo.
    around = len(sequence) if circular else None
    rotation = 0
    if around is not None:
        reach = read_length + limits.length_max
        if target_start < reach and around > reach:
            # Move the origin back far enough that the whole read window is in
            # front of the target rather than off the end of the string.
            rotation = (target_start - reach) % around
            sequence = sequence[rotation:] + sequence[:rotation]
            target_start = (target_start - rotation) % around

    window = window_for(
        len(sequence),
        target_start,
        target_length,
        direction,
        dead_zone=dead_zone,
        read_length=read_length,
    )
    _start, span = window.region
    if span < limits.length_min:
        raise SinglePrimerError(
            f"Reading {direction} leaves only {span} bases to place a primer in, "
            f"and the shortest allowed is {limits.length_min}. The target is too "
            "close to that end of the template — read from the other direction, or "
            "supply more flanking sequence."
        )

    forward = direction == "forward"

    # Where the primer's 3' end would ideally be: just clear of the unreadable
    # start of the trace, so the read arrives at the target as early as it can
    # and every base after it is spent on sequence somebody wanted.
    ideal = (
        target_start - window.nearest if forward else target_start + target_length + window.nearest
    )

    # Search a band around that, widening only if nothing is there.
    #
    # This is the difference between an engine that places a primer and one
    # that merely finds a good oligo somewhere legal. Ranking on Primer3's
    # penalty alone, measured on pUC19 reading 400..454: the best-scoring
    # candidate sat 372 bases from its target and burned that much of the read,
    # while one 93 bases away scored 0.272 against its 0.007. Both are legal
    # oligos; only one of them is the design.
    found: list[Candidate] = []
    explain = ""
    widened = 0
    reach = ACCURACY
    while True:
        region = _band(ideal, reach, limits.length_max, forward, window.region)
        found, explain = _pick(
            sequence,
            region,
            forward,
            limits,
            reaction,
            # Ask for more than wanted: some of what comes back is the same
            # design nudged along, and that is thinned out below.
            how_many * 4,
            direction,
            target_start,
            target_length,
            read_length,
            excluded,
        )
        found = _thin(found, limits.min_three_prime_distance, how_many)
        if found or widened >= MOST_WIDENINGS or region == window.region:
            break
        widened += 1
        reach *= 2

    if rotation and around is not None:
        # Back onto the sequence somebody pasted. Everything above worked in a
        # rotated copy, and a coordinate reported in it would point at the
        # wrong base of the file they are holding.
        found = [
            replace(one, at=(one.at + rotation) % around, wrapped_to_reach=True) for one in found
        ]
        window = replace(
            window,
            region=((window.region[0] + rotation) % around, window.region[1]),
        )

    return found, replace(window, widened=widened, searched=region), explain


def _band(
    ideal: int,
    reach: int,
    longest: int,
    forward: bool,
    limit: tuple[int, int],
) -> tuple[int, int]:
    """The stretch to search, clamped to what the read allows.

    Primer3 is given a region the whole primer must fit inside, and the two
    directions measure from opposite ends of it: a forward primer's 3' end is
    its last base, a reverse primer's is its first on the plus strand.
    """
    if forward:
        low = ideal - reach - longest + 1
        high = ideal + reach
    else:
        low = ideal - reach
        high = ideal + reach + longest - 1

    floor, span = limit
    low = max(low, floor)
    high = min(high, floor + span)
    return (low, max(0, high - low))


def _thin(candidates: list[Candidate], distance: int, how_many: int) -> list[Candidate]:
    """Drop candidates that are one design nudged along.

    Primer3 does this for pairs and not for a primer list: its documentation
    scopes the setting to "when returning multiple primer pairs", and measured
    on pUC19 a single-primer list came back with 3' ends at 307 and 308 — two
    of five "options" that were one. A list of five that is really three is
    worse than a list of three, because nobody counts them.
    """
    kept: list[Candidate] = []
    for candidate in candidates:
        end = (
            candidate.at + candidate.length - 1
            if candidate.direction == "forward"
            else candidate.at
        )
        if any(
            abs(end - (other.at + other.length - 1 if other.direction == "forward" else other.at))
            < distance
            for other in kept
        ):
            continue
        kept.append(candidate)
        if len(kept) == how_many:
            break
    return kept


def _pick(
    sequence: str,
    region: tuple[int, int],
    forward: bool,
    limits: Constraints,
    reaction: dict[str, float],
    how_many: int,
    direction: str,
    target_start: int,
    target_length: int,
    read_length: int | None,
    excluded: list[tuple[int, int]] | None = None,
) -> tuple[list[Candidate], str]:
    """Whatever Primer3 finds in this stretch, measured and placed."""
    settings = {
        "PRIMER_TASK": "pick_primer_list",
        "PRIMER_PICK_LEFT_PRIMER": 1 if forward else 0,
        "PRIMER_PICK_RIGHT_PRIMER": 0 if forward else 1,
        "PRIMER_PICK_INTERNAL_OLIGO": 0,
        "PRIMER_NUM_RETURN": how_many,
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
        "PRIMER_SALT_CORRECTIONS": salt_correction_for_conditions(reaction)[1],
        "PRIMER_SALT_MONOVALENT": reaction["mv_conc"],
        "PRIMER_SALT_DIVALENT": reaction["dv_conc"],
        "PRIMER_DNTP_CONC": reaction["dntp_conc"],
        "PRIMER_DNA_CONC": reaction["dna_conc"],
    }

    sequence_args: dict[str, Any] = {
        "SEQUENCE_ID": "template",
        "SEQUENCE_TEMPLATE": sequence,
        "SEQUENCE_INCLUDED_REGION": [region[0], region[1]],
    }
    if excluded:
        # A stretch the primer may not overlap. On a sequencing primer this is
        # usually a repeat or a homopolymer: one that sits on it reads through
        # a stretch the basecaller cannot resolve, and the trace is unusable
        # from there on rather than merely faint.
        sequence_args["SEQUENCE_EXCLUDED_REGION"] = [list(one) for one in excluded]

    answer = primer3.bindings.design_primers(sequence_args, settings)

    side = "LEFT" if forward else "RIGHT"
    found: list[Candidate] = []
    for index in range(answer.get(f"PRIMER_{side}_NUM_RETURNED", 0)):
        primer = answer[f"PRIMER_{side}_{index}_SEQUENCE"]
        # Primer3 reports a left primer by its 5' base and a right primer by its
        # 3'-most coordinate on the plus strand, which is its own 5' end read
        # the other way. Both are converted to a plus-strand start here so
        # every position in a result means the same thing.
        reported, length = answer[f"PRIMER_{side}_{index}"]
        at = reported if forward else reported - length + 1

        if read_length is None:
            reaches = None
            spare = None
        elif forward:
            three_prime = at + length - 1
            reaches = target_start - three_prime
            spare = read_length - (target_start + target_length - three_prime)
        else:
            three_prime = at
            reaches = three_prime - (target_start + target_length)
            spare = read_length - (three_prime - target_start)

        found.append(
            Candidate(
                sequence=primer,
                at=at,
                length=length,
                direction=direction,
                reaches=reaches,
                spare=spare,
                penalty=round(answer[f"PRIMER_{side}_{index}_PENALTY"], 3),
            )
        )

    return found, str(answer.get(f"PRIMER_{side}_EXPLAIN", ""))


def candidate_to_dict(candidate: Candidate, window: Window | None, **conditions: float) -> dict[str, Any]:
    """One primer as plain data without inventing assay-specific placement fields."""
    measured = analyse(candidate.sequence, **conditions)
    result: dict[str, Any] = {
        **report_to_dict(measured),
        "at": candidate.at,
        "direction": candidate.direction,
        "penalty": candidate.penalty,
        "wrapped_to_reach": candidate.wrapped_to_reach,
    }
    if window is not None and candidate.reaches is not None and candidate.spare is not None:
        result.update(
            {
                "reads": "into the target",
                "reaches": candidate.reaches,
                "spare": candidate.spare,
                "window": {
                    "nearest": window.nearest,
                    "furthest": window.furthest,
                    "searched": list(window.searched),
                    "widened": window.widened,
                },
                "note": (
                    f"The target starts {candidate.reaches} bases from this primer's 3' end, "
                    f"clear of the first {window.nearest} declared unreadable bases, and "
                    f"{candidate.spare} declared usable bases remain after it ends. These "
                    "placement figures come from the user/facility read envelope, not a "
                    "universal Sanger constant."
                ),
            }
        )
    else:
        result.update(
            {
                "reads": "toward the selected transcript end",
                "note": (
                    "Gene-specific RACE primer selected inside the declared known-sequence "
                    "search region and oriented toward the requested transcript end. No "
                    "Sanger dead-zone/read-length model is applied to RACE placement."
                ),
            }
        )
    return result


def design_race(
    template: str,
    *,
    search_start: int,
    search_length: int,
    direction: str,
    constraints: Constraints,
    conditions: dict[str, float],
    how_many: int,
    excluded: list[tuple[int, int]] | None = None,
) -> tuple[list[Candidate], str]:
    """Pick RACE GSPs inside an explicit known-sequence search region.

    RACE placement is not a capillary-read problem. The selected interval is
    the region in known sequence where a gene-specific primer may be placed;
    the RACE direction determines which strand points toward the unknown end.
    """
    sequence = clean_template(template)
    if direction not in DIRECTIONS:
        raise SinglePrimerError(f"unsupported RACE primer direction `{direction}`")
    if search_start < 0 or search_length < 1 or search_start + search_length > len(sequence):
        raise SinglePrimerError(
            f"RACE GSP search region {search_start}..{search_start + search_length} is outside "
            f"the {len(sequence)}-base known sequence."
        )
    if search_length < constraints.length_min:
        raise SinglePrimerError(
            f"The RACE GSP search region is {search_length} bases, shorter than the "
            f"minimum primer length {constraints.length_min}."
        )
    found, explain = _pick(
        sequence,
        (search_start, search_length),
        direction == "forward",
        constraints,
        conditions,
        how_many * 4,
        direction,
        search_start,
        search_length,
        None,
        excluded,
    )
    return _thin(found, constraints.min_three_prime_distance, how_many), explain


#: The most primers one request may ask for.
MOST_PRIMERS = 10


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One single-primer design, end to end, in the shape the interface reads.

    Raises:
        IntakeError: the input is not a usable template.
        SinglePrimerError: a placement that could not be asked for.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    # There is no product, so a template shorter than the shortest product is
    # not the contradiction it is for a pair.
    chosen = prepare(request, require_product_room=False)
    selected_protocol = sequencing_protocol(request.get("sequencing_protocol"))
    selected_design_profile = (
        sequencing_design_profile(request.get("sequencing_design_profile"))
        if chosen.assay_id == "sequencing-primer"
        else None
    )
    selected_sequencing_context = sequencing_context(request, assay_id=chosen.assay_id)
    selected_race_direction = race_direction(request.get("race_direction"))
    race_substrate = str(request.get("race_substrate") or "").strip()
    race_preparation = str(request.get("race_preparation") or "").strip()
    race_round = str(request.get("race_round") or "").strip()
    selected_race_chemistry = race_chemistry(
        request.get("race_chemistry"),
        request.get("race_adapter") if request.get("race_adapter") in {GENERACER_25_0355_VL_ID, FIRSTCHOICE_RLM_RACE_ID, SMARTER_RACE_ID, "custom"} else None,
    )
    requested_race_adapter = request.get("race_adapter")
    if (
        selected_race_chemistry
        and requested_race_adapter not in (None, "", "not-selected")
        and selected_race_chemistry.get("chemistry_id") in {GENERACER_25_0355_VL_ID, FIRSTCHOICE_RLM_RACE_ID, SMARTER_RACE_ID, "custom"}
        and requested_race_adapter != selected_race_chemistry.get("chemistry_id")
    ):
        raise SinglePrimerError(
            "race_chemistry and race_adapter identify different RACE branches; "
            "cross-wiring kit PCR partners is not allowed."
        )
    race_adapter_id = (
        selected_race_chemistry.get("chemistry_id")
        if selected_race_chemistry and selected_race_chemistry.get("chemistry_id") in {GENERACER_25_0355_VL_ID, FIRSTCHOICE_RLM_RACE_ID, SMARTER_RACE_ID, "custom"}
        else requested_race_adapter
    )
    selected_race_adapter = race_adapter(
        race_adapter_id,
        request.get("race_partner_sequence"),
        direction=selected_race_direction,
        round_name=race_round or None,
    )
    if selected_protocol is not None and selected_race_adapter is not None:
        raise SinglePrimerError(
            "a sequencing chemistry overlay and a RACE adapter cannot be selected together"
        )
    if selected_race_adapter is not None and chosen.assay_id not in ("", "race"):
        raise SinglePrimerError(
            "the RACE adapter overlay belongs to the `race` assay, "
            f"not `{chosen.assay_id}`. Choose a sequencing workflow instead."
        )
    if selected_race_direction is not None and chosen.assay_id not in ("", "race"):
        raise SinglePrimerError(
            "the RACE direction belongs to the `race` assay, "
            f"not `{chosen.assay_id}`. Choose a single-primer workflow instead."
        )
    if chosen.assay_id == "race" and selected_race_direction is None:
        raise SinglePrimerError(
            "RACE requires an explicit `race_direction`: choose `5prime` or `3prime`."
        )
    if chosen.assay_id == "race" and selected_race_chemistry is None:
        raise SinglePrimerError("RACE requires explicit race_chemistry; chemistry identity is not inferred from primer direction.")
    if chosen.assay_id == "race" and selected_race_adapter is None:
        raise SinglePrimerError(
            "The selected RACE chemistry is not executable without an exact PCR-partner sequence; use a reviewed named kit branch (GeneRacer or FirstChoice) or a complete custom SOP."
        )
    if chosen.assay_id == "race" and race_substrate not in {"total-rna", "mrna", "cdna"}:
        raise SinglePrimerError(
            "RACE requires `race_substrate`: total-rna, mrna or cdna."
        )
    if chosen.assay_id == "race" and not race_preparation:
        raise SinglePrimerError(
            "RACE requires `race_preparation` provenance (kit/SOP/RT or template-switch branch)."
        )
    if chosen.assay_id == "race" and race_round not in {"primary", "nested"}:
        raise SinglePrimerError("RACE requires `race_round`: primary or nested.")
    race_sop_revision = str(request.get("race_sop_revision") or "").strip()
    race_sop_sha256 = str(request.get("race_sop_sha256") or "").strip().lower()
    if chosen.assay_id == "race" and selected_race_chemistry and selected_race_chemistry.get("chemistry_id") in {"custom", SMARTER_RACE_ID}:
        if not race_sop_revision:
            raise SinglePrimerError("custom/SMARTer RACE requires race_sop_revision for the caller-reviewed SOP/manual authority")
        if len(race_sop_sha256) != SHA256_HEX_LENGTH or any(ch not in "0123456789abcdef" for ch in race_sop_sha256):
            raise SinglePrimerError("custom/SMARTer RACE requires race_sop_sha256 as a 64-character SHA-256 digest")
    if chosen.assay_id == "race" and selected_race_chemistry and selected_race_chemistry.get("chemistry_id") == SMARTER_RACE_ID:
        if selected_race_direction == "3prime" and request.get("race_polyadenylated") is not True:
            raise SinglePrimerError("SMARTer 3-prime RACE requires explicit racePolyadenylated=true; PCRStudio will not infer a poly(A) tail.")
    if selected_protocol is not None and chosen.assay_id not in ("", "sequencing-primer"):
        raise SinglePrimerError(
            "the BigDye v3.1 overlay belongs to the `sequencing-primer` assay, "
            f"not `{chosen.assay_id}`. Choose a RACE-specific workflow instead."
        )
    how_many = how_many_from(request, MOST_PRIMERS)

    if request.get("target_start") is None or request.get("target_length") is None:
        raise SinglePrimerError(
            "A single primer is placed relative to something, so this needs a "
            "target: which stretch the read has to cover. Without one there is "
            "nothing to be near or far from, and every primer on the template "
            "would be equally good."
        )

    if chosen.assay_id == "sequencing-primer" and request.get("direction") in (None, ""):
        raise SinglePrimerError(
            "Scientific-Strict sequencing-primer requires explicit `direction`: forward or reverse; read orientation is not inferred from omission."
        )
    direction = (
        RACE_DIRECTION_TO_READ[selected_race_direction]
        if selected_race_direction is not None
        else str(request.get("direction") or "forward")
    )
    supplied_direction = request.get("direction")
    if selected_race_direction is not None and supplied_direction not in (None, ""):
        if str(supplied_direction) != direction:
            raise SinglePrimerError(
                f"RACE `{selected_race_direction}` reads `{direction}`; "
                f"it cannot be combined with `{supplied_direction}`."
            )
    effective_limits = chosen.limits
    explicit_constraints = request.get("constraints") or {}
    if chosen.assay_id == "sequencing-primer" and selected_design_profile is not None:
        design_profile = dict(selected_design_profile.get("design") or {})
        applicable = {key: value for key, value in design_profile.items() if key in Constraints.__dataclass_fields__}
        baseline = {field: getattr(effective_limits, field) for field in Constraints.__dataclass_fields__}
        baseline.update(applicable)
        if "tm_min" in applicable and "tm_max" in applicable and "tm_opt" not in applicable:
            baseline["tm_opt"] = round((float(applicable["tm_min"]) + float(applicable["tm_max"])) / 2.0, 1)
            applicable["tm_opt"] = baseline["tm_opt"]
        if "length_min" in applicable and "length_max" in applicable and "length_opt" not in applicable:
            applicable["length_opt"] = max(int(applicable["length_min"]), min(int(chosen.limits.length_opt), int(applicable["length_max"])))
            baseline["length_opt"] = applicable["length_opt"]
        enforce_constraint_overrides(explicit_constraints, baseline, context=f"sequencing profile {selected_design_profile['profile_id']}")
        effective_limits = replace(chosen.limits, **{k:v for k,v in applicable.items() if k not in explicit_constraints})
    elif chosen.assay_id == "race" and selected_race_chemistry is not None:
        gsp = dict(selected_race_chemistry.get("gsp_profile") or {})
        applicable: dict[str, Any] = {}
        for key in ("length_min", "length_max", "gc_min", "gc_max", "tm_min"):
            if key in gsp:
                applicable[key] = gsp[key]
        if "length_min" in applicable and "length_max" in applicable:
            applicable["length_opt"] = max(int(applicable["length_min"]), min(int(chosen.limits.length_opt), int(applicable["length_max"])))
        if "tm_min" in applicable and float(chosen.limits.tm_max) <= float(applicable["tm_min"]):
            # GeneRacer specifies a lower Tm relationship, not a universal upper bound.
            # 80 C is a PCRStudio search ceiling and is reported as such, not vendor truth.
            applicable["tm_opt"] = float(applicable["tm_min"]) + 2.0
            applicable["tm_max"] = float(applicable["tm_min"]) + 8.0
        baseline = {field: getattr(effective_limits, field) for field in Constraints.__dataclass_fields__}
        baseline.update(applicable)
        enforce_constraint_overrides(explicit_constraints, baseline, context=f"RACE chemistry {selected_race_chemistry['chemistry_id']}")
        effective_limits = replace(chosen.limits, **{k:v for k,v in applicable.items() if k not in explicit_constraints})

    reaction = chosen.reaction.as_conditions()
    if chosen.assay_id == "race":
        if request.get("dead_zone") is not None or request.get("read_length") is not None:
            raise SinglePrimerError(
                "dead_zone/read_length are Sanger placement inputs and are not valid for RACE."
            )
        if bool(request.get("circular")):
            raise SinglePrimerError("RACE requires a linear transcript/cDNA coordinate context; circular is invalid.")
        found, explain = design_race(
            chosen.target.sequence,
            search_start=int(request["target_start"]),
            search_length=int(request["target_length"]),
            direction=direction,
            constraints=effective_limits,
            conditions=reaction,
            how_many=how_many,
            excluded=excluded_from(request),
        )
        window = None
        read_length = None
    else:
        dead_zone_value = request.get("dead_zone")
        read_length_value = request.get("read_length")
        if not chosen.assay_id:
            # Direct low-level research callers predate the named sequencing
            # profile. Preserve their deterministic placement defaults while
            # keeping the executable named-assay path explicit and fail-closed.
            dead_zone_value = 40 if dead_zone_value is None else dead_zone_value
            read_length_value = 800 if read_length_value is None else read_length_value
        if dead_zone_value is None or read_length_value is None:
            raise SinglePrimerError(
                "sequencing-primer requires explicit `dead_zone` and `read_length` from the "
                "sequencing provider/instrument/SOP; the current runtime does not assume 40/800."
            )
        dead_zone = int(dead_zone_value)
        read_length = int(read_length_value)
        found, window, explain = design(
            chosen.target.sequence,
            target_start=int(request["target_start"]),
            target_length=int(request["target_length"]),
            direction=direction,
            constraints=effective_limits,
            conditions=reaction,
            how_many=how_many,
            dead_zone=dead_zone,
            read_length=read_length,
            excluded=excluded_from(request),
            circular=bool(request.get("circular")),
        )

    primers = [candidate_to_dict(one, window, **reaction) for one in found]
    name = label(chosen.target.name)

    trace_review = None
    if chosen.assay_id == "sequencing-primer" and request.get("sequencing_trace_ab1_base64") not in (None, ""):
        try:
            trace_review = parse_ab1_base64(
                request.get("sequencing_trace_ab1_base64"),
                filename=str(request.get("sequencing_trace_filename") or "trace.ab1"),
            )
        except SangerTraceError as exc:
            raise SinglePrimerError(str(exc)) from exc
        if selected_sequencing_context is None:
            selected_sequencing_context = {}
        else:
            selected_sequencing_context = dict(selected_sequencing_context)
        selected_sequencing_context.update({"trace_status":"reviewed-abif","quality_status":"observed-trace-evidence","trace_filename":trace_review.get("filename")})

    walking_plan = None
    if chosen.assay_id == "sequencing-primer" and bool(request.get("sequencing_primer_walking")):
        if read_length is None:
            raise SinglePrimerError("sequencing primer walking requires an explicit read_length")
        overlap=int(request.get("sequencing_walking_overlap") or 100)
        usable=int(read_length)-int(dead_zone)
        if overlap < 0 or overlap >= usable:
            raise SinglePrimerError("sequencingWalkingOverlap must be >=0 and smaller than usable read length")
        step=max(1,usable-overlap)
        target_start=int(request["target_start"]); target_end=target_start+int(request["target_length"])
        windows=[]; at=target_start; index=1
        while at < target_end and len(windows)<100:
            end=min(target_end,at+usable)
            windows.append({"walk_index":index,"target_start":at,"target_end":end,"target_length":end-at,"overlap":overlap if index>1 else 0,"status":"design-handoff"})
            if end>=target_end: break
            at=end-overlap; index+=1
        walking_plan={"requested":True,"usable_read_length":usable,"overlap":overlap,"step":step,"windows":windows,"decision_impact":"route-and-coverage-plan","note":"Each walk window is an independent single-primer design/trace; observed traces determine actual usable coverage."}

    nested_gsp_plan = None
    if chosen.assay_id == "race" and len(primers) >= 2:
        ordered=sorted(primers,key=lambda x:int(x.get("at",0)),reverse=(selected_race_direction=="3prime"))
        nested_gsp_plan={
            "status":"candidate-plan","primary":ordered[0],"nested":ordered[1],"direction":selected_race_direction,
            "partner_primary":selected_race_adapter,"partner_nested":selected_race_adapter,
            "decision_impact":"geometry-plan",
            "note":"Primary/nested GSP candidates are kept in transcript-end order; exact kit partner identity remains explicit and experimental product identity still requires sequencing evidence.",
        }

    # ── Where else this primer could sit ────────────────────────────────────
    #
    # A single primer makes no band, which is exactly why this check was easy
    # to leave out and exactly why it matters. A sequencing primer that anneals
    # in two places gives one trace with two sequences superimposed on it: not
    # a faint band to squint at, an unreadable read. A RACE primer that sits
    # twice does the same to the product it is supposed to walk out of.
    #
    # Products are reported too, from this primer against itself: a forward
    # site and a reverse site of one oligo make a band, and it is one of the
    # classic reasons a reaction produces something nobody designed.
    from . import screen

    contigs, template_only, fold_at = screen.contigs_for(
        request, template=chosen.target.sequence, name=chosen.target.name
    )
    for entry, candidate in zip(primers, found, strict=True):
        entry["off_targets"] = screen.oligos(
            {direction: candidate.sequence},
            contigs,
            reaction=chosen.reaction,
            fold_at=fold_at,
            max_product=screen.product_ceiling(effective_limits.product_max),
        )
        # ── The partner the kit supplies ────────────────────────────────────
        #
        # For a RACE primer this is the pair-dimer question against the exact
        # amplification partner selected by the named kit/round (or supplied
        # literally by the user). A sequencing primer has no PCR partner, so it
        # receives no synthetic adapter-dimer section.
        if selected_race_adapter is not None:
            entry["adapter_dimer"] = adapter_screen(
                candidate.sequence, partner=selected_race_adapter, **reaction
            )

    universal_hits = (
        universal_primer_candidates(chosen.target.sequence, direction=direction)
        if chosen.assay_id == "sequencing-primer" and bool(request.get("sequencing_universal_primer_scan"))
        else []
    )
    workflow = evidence_block(
        request.get("workflow_evidence"),
        note="RACE/Sanger run evidence is retained for validation only and never changes the saved primer ranking.",
    )

    return {
        "engine": "single-primer",
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **(
                {
                    "context_role": "gene-specific-primer-thermodynamic-screening-context",
                    "context_note": (
                        "These ionic/oligo values make RACE GSP thermodynamic screening reproducible. "
                        "They do not identify or reconstruct the RT/PCR enzyme, adapter chemistry, "
                        "buffer or cycling of the selected RACE kit/SOP."
                    ),
                }
                if chosen.assay_id == "race"
                else {}
            ),
            **(
                {
                    "context_role": "single-primer-thermodynamic-screening-context",
                    "context_note": (
                        "These ionic/oligo values support sequencing-primer thermodynamic ranking only. "
                        "They do not identify the cycle-sequencing polymerase, dye terminator mix, "
                        "instrument or facility SOP."
                    ),
                }
                if chosen.assay_id == "sequencing-primer"
                else {}
            ),
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {
            field: getattr(effective_limits, field) for field in Constraints.__dataclass_fields__
        },
        # How far the scan looked, said once rather than implied per primer.
        "background": screen.summary(contigs, template_only),
        "workflow_evidence": workflow,
        "sequencing_design_profile": selected_design_profile if chosen.assay_id == "sequencing-primer" else None,
        "sequencing_submission": (
            {
                "profile": selected_design_profile.get("profile_id"),
                "requirements": selected_design_profile.get("submission"),
                "decision_impact": "none",
                "note": "Provider submission quantities are handoff metadata and do not alter primer ranking."
            }
            if chosen.assay_id == "sequencing-primer" and selected_design_profile is not None
            else None
        ),
        "universal_primer_scan": {
            "checked": bool(request.get("sequencing_universal_primer_scan")),
            "hits": universal_hits,
            "decision_impact": "explicit-reuse-option",
            "note": "Only exact, uniquely mapped authority-library hits are reusable options; PCRStudio never silently replaces the ranked designed primer."
        } if chosen.assay_id == "sequencing-primer" else None,
        **(
            {
                "race_placement": {
                    "direction": direction,
                    "race_direction": selected_race_direction,
                    "search_region": [int(request["target_start"]), int(request["target_length"])],
                    "semantics": "known-sequence-gsp-search-region",
                    "note": (
                        "The selected interval is where the gene-specific primer may bind in known "
                        "sequence. Direction points from that primer toward the requested unknown "
                        "transcript end; Sanger read-length/dead-zone assumptions are not used."
                    ),
                }
            }
            if chosen.assay_id == "race"
            else {
                "read": {
                    "direction": direction,
                    "dead_zone": window.nearest,
                    "read_length": read_length,
                    "nearest": window.nearest,
                    "furthest": window.furthest,
                    "region": list(window.region),
                    "note": (
                        f"The primer has to sit between {window.nearest} and {window.furthest} "
                        "bases from the target under the explicitly supplied sequencing-provider "
                        "read envelope. These are not PCRStudio universal defaults."
                    ),
                }
            }
        ),
        "primer_walking": walking_plan,
        "trace_review": trace_review,
        "nested_gsp_plan": nested_gsp_plan,
        "primers": primers,
        "considered": explain,
        "why_nothing": (
            ""
            if primers
            else (
                f"No primer inside the declared {int(request['target_length'])}-base known-sequence "
                "RACE GSP search region satisfied the constraints."
                if chosen.assay_id == "race"
                else f"No primer in the {window.region[1]}-base sequencing placement window satisfied the constraints."
            )
        ),
        "order_sheet": [
            {
                "name": f"{name}_{index}{'F' if direction == 'forward' else 'R'}",
                "sequence": one["sequence"],
                "annealing_sequence": one["sequence"],
                "tail_sequence": "",
                "kind": "primer",
                "length": one["length"],
                "gc_percent": one["gc_percent"],
                "tm": one["tm"],
            }
            for index, one in enumerate(primers, start=1)
        ],
        **({"protocol": selected_protocol} if selected_protocol is not None else {}),
        **(
            {
                "bidirectional_plan": {
                    "requested": True,
                    "opposite_direction": "reverse" if direction == "forward" else "forward",
                    "status": "separate-single-primer-design-required",
                    "decision_impact": "route-only",
                    "note": "Bidirectional confirmation consists of two independent single-primer reactions; the opposite primer is not inferred from this ranked list."
                }
            }
            if chosen.assay_id == "sequencing-primer" and bool(request.get("sequencing_bidirectional"))
            else {}
        ),
        **(
            {"sequencing_context": selected_sequencing_context}
            if selected_sequencing_context is not None
            else {}
        ),
        **(
            {"race_direction": selected_race_direction}
            if selected_race_direction is not None
            else {}
        ),
        **({"race_adapter": selected_race_adapter} if selected_race_adapter is not None else {}),
        **({"race_chemistry": selected_race_chemistry} if selected_race_chemistry is not None else {}),
        **(
            {
                "race_context": {
                    "substrate": race_substrate,
                    "preparation": race_preparation,
                    **({"caller_sop_revision": race_sop_revision, "caller_sop_sha256": race_sop_sha256} if race_sop_revision and race_sop_sha256 else {}),
                    "round": race_round,
                    "polyadenylated": request.get("race_polyadenylated"),
                    "end_status": "candidate-transcript-end",
                    "validation_required": [
                        "sequence the RACE product",
                        "review negative/RT-minus controls as applicable",
                        "support transcript-end completeness with independent evidence",
                    ],
                    "note": (
                        "RACE primer placement can nominate a transcript end but cannot establish "
                        "a complete transcription start/polyadenylation end without run and sequence evidence."
                    ),
                }
            }
            if chosen.assay_id == "race"
            else {}
        ),
    }
