"""Where else a primer could sit down, and whether anything would come of it.

Two layers, because one number cannot answer both questions.

**Could the sequence be a binding site?** Discovery is based on the declared
whole-primer mismatch budget. It does not make a biochemical yes/no rule out of
an exact 3-prime clamp: mismatches near the 3-prime end are often more
consequential, but their effect depends on mismatch identity, position,
polymerase and reaction conditions.

**How strong is the predicted duplex?** Thermodynamics is reported separately
from sequence discovery. A free-energy value can rank or describe candidate
sites, but an arbitrary ΔG cutoff at a model-reference temperature is not used
to make a sequence-compatible site disappear in Scientific-Strict.

The scan is bounded and mismatch-complete over the supplied sequence for the
declared ungapped mismatch budget. Candidate starts are found with a
pigeonhole seed partition: with k allowed mismatches, at least one of k+1
non-empty primer segments must match exactly (or be IUPAC-compatible). The full
window is then checked base by base. Ambiguity is reported rather than promoted
to certainty.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from typing import Any

from .presets import Reaction
from .thermo import pair_dimer, reverse_complement

#: How much background this scan will take before refusing.
#:
#: Measured rather than guessed. Thirty primers -- a fifteen-pair shortlist --
#: over a hundred megabases takes twenty-nine seconds, and the background holds
#: one byte per base. So this covers every plasmid, every bacterial genome,
#: yeast, Drosophila, a plant chromosome, and a whole transcriptome, in about a
#: minute at the ceiling.
#:
#: A mammalian genome is three gigabases: a quarter of an hour and three
#: gigabytes of memory for one design. That is not a scan somebody should wait
#: for inside a request, and the refusal says what to do instead rather than
#: only that it will not.
#:
#: The number was 50 million, chosen when the cost was assumed rather than
#: timed. The scan turned out to be four times faster than that assumption.
# Physical lower bound for a Celsius temperature input.
ABSOLUTE_ZERO_C = -273.15

MAX_BACKGROUND_BASES = 250_000_000

# This is deliberately a named contract rather than a vague label such as
# "specificity checked".  The worker does not call BLAST, Primer-BLAST or an
# indexed alignment database; consumers must be able to tell that fact from
# the result without reading the source code.
METHOD_ID = "bounded-ungapped-mismatch-complete"
# Version 5 removes the exact 3-prime seed as a biological discovery gate.
# Candidate starts are generated from k+1 non-empty seed partitions, which
# guarantees that every ungapped window with <=k definite mismatches has at
# least one exact/compatible seed. The full primer window is then scored.
METHOD_VERSION = 5
DEFAULT_TEMPERATURE_C = 37.0

# Operational ceiling, not a biological pass/fail rule. A very large mismatch
# allowance makes nearly every window a candidate and turns a bounded
# specificity check into avoidable CPU work; use indexed alignment above it.
MAX_MISMATCHES = 20

# DNA ambiguity codes are valid in an assembly or consensus background, but a
# protein word or an arbitrary label is not a sequence. `U` is accepted as an
# RNA spelling and normalised to `T`, matching template intake for RT assays.
BACKGROUND_BASES = frozenset("ACGTRYSWKMBDHVN")
UNAMBIGUOUS_BASES = frozenset("ACGT")
IUPAC_BASES: dict[str, frozenset[str]] = {
    "A": frozenset("A"),
    "C": frozenset("C"),
    "G": frozenset("G"),
    "T": frozenset("T"),
    "R": frozenset("AG"),
    "Y": frozenset("CT"),
    "S": frozenset("GC"),
    "W": frozenset("AT"),
    "K": frozenset("GT"),
    "M": frozenset("AC"),
    "B": frozenset("CGT"),
    "D": frozenset("AGT"),
    "H": frozenset("ACT"),
    "V": frozenset("ACG"),
    "N": frozenset("ACGT"),
}


class BackgroundTooLarge(ValueError):
    """A background this scan will not attempt, with the size that broke it."""


@dataclass(frozen=True)
class Contig:
    """One record of the background."""

    name: str
    sequence: str


def _preflight_background_size(text: str, *, label: str) -> None:
    """Reject an oversized sequence before normalisation allocates a copy."""
    bases = 0
    for character in text:
        if character.isalpha():
            bases += 1
            if bases > MAX_BACKGROUND_BASES:
                raise BackgroundTooLarge(
                    f"The {label} is larger than {MAX_BACKGROUND_BASES:,} bases. "
                    "This scan compares every candidate site directly. Use the "
                    "chromosome, transcriptome or a representative panel for "
                    "the question, or use an indexed search for larger inputs."
                )


def normalise_background(text: str, *, label: str = "background") -> str:
    """Return a DNA sequence or refuse it before it can look clean.

    This boundary accepts raw DNA/RNA/IUPAC text and FASTA sequence lines.
    GenBank coordinates are not a valid background format here: accepting a
    digit and dropping it would shorten a malformed exclusion sequence and
    could turn an off-target into a false clean result. Callers that need a
    flat-file record must extract its ORIGIN sequence before this boundary.
    """
    _preflight_background_size(text, label=label)
    # Whitespace is safe to ignore. Digits and punctuation are not: dropping a
    # coordinate, dash or asterisk can turn a malformed record into a shorter,
    # apparently clean sequence. Refuse them explicitly so an exclusion
    # background cannot be weakened by a formatting error.
    letters: list[str] = []
    invalid_symbols: set[str] = set()
    for character in text.upper():
        if character.isspace():
            continue
        if character.isdigit():
            invalid_symbols.add(character)
            continue
        if character.isalpha():
            # RNA spelling is valid input for a target/background comparison;
            # normalise it before checking the DNA alphabet so U is not
            # accidentally reported as an invalid letter.
            letters.append("T" if character == "U" else character)
        else:
            invalid_symbols.add(character)

    invalid = sorted(set(letters) - BACKGROUND_BASES)
    if invalid_symbols:
        invalid.extend(repr(symbol) for symbol in sorted(invalid_symbols))
    if invalid:
        raise ValueError(
            f"{label} contains "
            + ", ".join(invalid)
            + ", which is neither a DNA base nor an IUPAC ambiguity code"
        )
    return "".join(letters)


def parse_fasta(text: str, *, label: str = "background") -> list[Contig]:
    """Read FASTA into contigs, upper-cased.

    Case is discarded here deliberately and the fact is worth stating: a
    soft-masked background loses its masking at this point, so repeats have to
    be handled as intervals by the caller rather than carried in the letters.
    Unlike the fast scanners, `N` is kept as `N` and never matches a base —
    silently turning an assembly gap into a run of `A` invents binding sites.
    Every non-empty FASTA record must carry sequence and a unique identifier;
    dropping or silently renaming a panel record would weaken provenance.
    """
    contigs: list[Contig] = []
    name = ""
    chunks: list[str] = []
    saw_header = False
    seen_names: set[str] = set()
    observed_bases = 0

    def flush() -> None:
        """Commit one record, refusing an empty FASTA record."""
        if not saw_header and not chunks:
            return
        sequence = normalise_background("".join(chunks), label=label)
        if saw_header and not sequence:
            identifier = name or "unnamed"
            raise ValueError(
                f"{label} was supplied, but record {identifier!r} contains no DNA sequence; "
                "remove the empty record or provide its sequence."
            )
        if sequence:
            identifier = name or "unnamed"
            if identifier in seen_names:
                raise ValueError(
                    f"{label} contains duplicate FASTA record identifier "
                    f"{identifier!r}; use unique identifiers so every screened "
                    "record remains distinguishable."
                )
            seen_names.add(identifier)
            contigs.append(Contig(name=identifier, sequence=sequence))

    for line in text.splitlines():
        header = line.lstrip()
        if header.startswith(">"):
            flush()
            name = header[1:].strip().split()[0] if header[1:].strip() else ""
            chunks = []
            saw_header = True
        else:
            observed_bases += sum(character.isalpha() for character in line)
            if observed_bases > MAX_BACKGROUND_BASES:
                raise BackgroundTooLarge(
                    f"The {label} is larger than {MAX_BACKGROUND_BASES:,} bases. "
                    "This scan compares every candidate site directly. Use the "
                    "chromosome, transcriptome or a representative panel for "
                    "the question, or use an indexed search for larger inputs."
                )
            chunks.append(line)

    flush()
    return contigs


@dataclass(frozen=True)
class Site:
    """One place a primer could sit, and how well."""

    primer: str
    #: Which primer of the pair this was, for the report.
    role: str
    contig: str
    #: Zero-based position of the primer's 3'-most base on the plus strand.
    three_prime_at: int
    #: "forward" means it would extend towards higher coordinates.
    orientation: str
    mismatches: int
    #: Free energy of the duplex it would form, kcal/mol. More negative binds harder.
    dg: float
    tm: float
    #: Number of IUPAC symbols in the background window. Such a site is a
    #: possible binding site, not an observed exact sequence.
    ambiguous_bases: int = 0
    #: Upper bound on mismatches after resolving compatible ambiguity symbols.
    #: ``mismatches`` is the lower bound used for conservative discovery.
    mismatch_upper_bound: int | None = None
    #: Definite mismatch positions measured from the primer 3' end (1 = terminal
    #: base). These are descriptive evidence only: mismatch identity, polymerase,
    #: neighbouring sequence and reaction conditions determine extension.
    mismatch_positions_from_three_prime: tuple[int, ...] = ()
    #: Positions whose background base is IUPAC-ambiguous while remaining
    #: compatible with the primer. They are possible matches, not observed
    #: exact matches, and are kept separate from definite mismatches.
    ambiguous_positions_from_three_prime: tuple[int, ...] = ()
    #: Definite mismatch identities in primer/template pairing orientation. Each
    #: tuple is (distance_from_3_prime, primer_base, template_base,
    #: background_plus_base). This is descriptive evidence only.
    mismatch_base_pairs_from_three_prime: tuple[tuple[int, str, str, str], ...] = ()


@dataclass(frozen=True)
class OffTarget:
    """Two sites facing each other closely enough to make a product."""

    contig: str
    #: The product's first base — the forward primer's 5' end, zero-based.
    start: int
    #: The product's last base — the reverse primer's 5' end.
    end: int
    #: Length of the product a gel would show. Measured 5' end to 5' end, which
    #: is what Primer3 means by product size; measuring between the 3' ends
    #: instead loses a primer's length at each side.
    size: int
    forward: Site
    reverse: Site

    @property
    def worst_dg(self) -> float:
        """The weaker of the two bindings — the one that limits the product."""
        return max(self.forward.dg, self.reverse.dg)


@dataclass
class Specificity:
    """What the scan looked at, and what it found."""

    checked: bool
    background_name: str
    background_bases: int
    max_mismatches: int
    sites: list[Site] = field(default_factory=list)
    products: list[OffTarget] = field(default_factory=list)
    note: str = ""
    #: Whether the caller asks the report to call out terminal mismatches.
    #: Discovery itself always includes them inside the whole-primer mismatch
    #: budget; this flag changes interpretation/reporting, not visibility.
    terminal_mismatch_scan: bool = False
    #: Whether the caller used the target itself as the finite background.
    #: `None` means a lower-level caller did not provide that context.
    template_only: bool | None = None
    #: The weakest duplex free energy retained by the scan, in kcal/mol.
    min_dg: float | None = None
    #: The longest product assembled from opposing sites.
    max_product: int = 3000
    #: Temperature at which site duplex ΔG/Tm was evaluated. Primer3's
    #: thermodynamic API defaults to 37 °C; pipeline callers replace it with
    #: the actual assay anneal/hold temperature.
    temperature_c: float = DEFAULT_TEMPERATURE_C


def method_to_dict(
    *,
    max_mismatches: int,
    min_dg: float | None = None,
    max_product: int = 3000,
    terminal_mismatch_scan: bool = False,
    template_only: bool | None = None,
    temperature_c: float | None = None,
) -> dict[str, Any]:
    """Describe the finite search contract carried by a specificity result.

    This is intentionally explicit about what is *not* being claimed.  A
    bounded scan is useful evidence against a supplied background, but it is
    not a whole-database uniqueness proof and it does not model gaps,
    recombinase kinetics or polymerase extension probability.
    """
    binding_score: dict[str, Any] = {
        "model": "Primer3 nearest-neighbour heterodimer",
        "minimum_dg_kcal_mol": min_dg,
        "dg_filter_applied": min_dg is not None,
    }
    if temperature_c is not None:
        binding_score["temperature_c"] = temperature_c

    return {
        "id": METHOD_ID,
        "version": METHOD_VERSION,
        "scope": (
            "template-only"
            if template_only is True
            else "supplied-background"
            if template_only is False
            else "reported-by-caller"
        ),
        "seed": {
            "strategy": "pigeonhole-k-plus-one-partitions",
            "match": "exact-unambiguous / IUPAC-compatible-possible",
            "position": "partitioned-across-whole-primer",
            "terminal_mismatch_included": True,
        },
        "mismatch_scope": (
            "minimum known mismatches across the whole primer window; compatible "
            "IUPAC ambiguity expands the reported upper bound. Terminal positions "
            "are never hidden by an exact-clamp discovery rule."
        ),
        "mismatch_topology": {
            "position_origin": "primer-3-prime-end",
            "terminal_position": 1,
            "reported_fields": [
                "mismatch_positions_from_three_prime",
                "ambiguous_positions_from_three_prime",
                "mismatch_base_pairs_from_three_prime",
                "nearest_three_prime_mismatch",
            ],
            "decision_role": "descriptive-evidence-not-universal-extension-threshold",
        },
        "max_mismatches": max_mismatches,
        "binding_score": binding_score,
        "product_rule": "same-contig opposing forward/reverse sites within max_product",
        "max_product": max_product,
        "indexed_search": False,
        "alignment_gaps": False,
        "whole_database": False,
        "handoff": {
            "required_above_background_bases": MAX_BACKGROUND_BASES,
            "method": "indexed alignment or Primer-BLAST",
            "automatic": False,
            "reason": (
                "This worker is exhaustive only within the supplied bounded "
                "sequence; larger backgrounds must be searched by an indexed "
                "alignment workflow outside this process."
            ),
        },
        "ambiguity_policy": "possible-base-compatible-surrogate-with-mismatch-bounds",
        "limitations": [
            "Only the supplied background (or explicitly reported template fallback) is examined.",
            "No BLAST, Primer-BLAST, indexed genome search or taxonomic completeness is implied.",
            "Ungapped windows do not model indels or polymerase-specific mismatch kinetics.",
            "Mismatch position is reported from the primer 3' end, but identity/context/polymerase effects are not converted into a universal amplification probability.",
            "Ambiguous background windows use a compatible-base thermodynamic surrogate, expose a mismatch range, and require sequence resolution.",
        ],
    }


def _find_all(haystack: str, needle: str) -> Iterator[int]:
    """Every start position of `needle`, including overlapping ones."""
    start = haystack.find(needle)
    while start != -1:
        yield start
        start = haystack.find(needle, start + 1)


def _possible_seed_starts(haystack: str, seed: str) -> Iterator[int]:
    """Find seed positions that an IUPAC background could contain.

    Literal ``str.find`` is the fast path for an unambiguous background.  For
    ambiguity symbols, a seed is a possible hit when every symbol contains the
    corresponding primer base.  Character classes keep this linear in the
    sequence without expanding an ambiguous seed into up to ``4**n`` strings.
    """
    if not any(base not in UNAMBIGUOUS_BASES for base in haystack):
        yield from _find_all(haystack, seed)
        return

    allowed_symbols: list[str] = []
    for expected in seed:
        symbols = [symbol for symbol, choices in IUPAC_BASES.items() if expected in choices]
        allowed_symbols.append("[" + "".join(sorted(symbols)) + "]")
    pattern = re.compile("".join(allowed_symbols))
    # ``finditer`` normally advances past a match.  That is not exhaustive
    # for seed discovery: adjacent/overlapping binding sites are common in
    # repeats, and the unambiguous fast path above deliberately keeps them via
    # ``_find_all``.  A zero-width lookahead preserves the same overlap
    # semantics for IUPAC backgrounds without expanding the ambiguity codes.
    for match in re.finditer(f"(?={pattern.pattern})", haystack):
        yield match.start()


def _mismatch_bounds(window: str, primer: str) -> tuple[int, int] | None:
    """Return conservative minimum/maximum mismatches over the whole primer.

    A compatible IUPAC background symbol contributes zero to the minimum and
    one to the maximum. This keeps a possible binding site visible without
    claiming that the unresolved base is known to match.
    """
    if len(window) != len(primer):
        return None
    minimum = 0
    maximum = 0
    for observed, expected in zip(window, primer, strict=True):
        choices = IUPAC_BASES.get(observed)
        if choices is None or expected not in choices:
            minimum += 1
            maximum += 1
        elif observed not in UNAMBIGUOUS_BASES:
            maximum += 1
    return minimum, maximum


def _mismatch_topology(
    window: str,
    expected: str,
    *,
    three_prime_at_start: bool,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[tuple[int, str, str, str], ...]]:
    """Return mismatch/ambiguity topology measured from the primer 3' end.

    ``expected`` is written in the background's plus-strand orientation. For a
    forward primer its 3' base is therefore at the end of ``expected``; for a
    reverse primer the plus-strand reverse-complement spelling puts the primer
    3' base at the start. The result is reporting evidence only and must not be
    converted into a universal extension threshold.
    """
    if len(window) != len(expected):
        return (), (), ()

    definite: list[int] = []
    ambiguous: list[int] = []
    identities: list[tuple[int, str, str, str]] = []
    length = len(expected)
    for index, (observed, wanted) in enumerate(zip(window, expected, strict=True)):
        choices = IUPAC_BASES.get(observed)
        distance = index + 1 if three_prime_at_start else length - index
        if choices is None or wanted not in choices:
            definite.append(distance)
            # `expected` is always written in plus-strand coordinates. For a
            # forward site the primer has that same spelling and pairs to the
            # complement of the plus strand. For a reverse site the primer
            # pairs directly to the plus strand, so its base is the complement
            # of `expected`. Keeping both the pairing bases and the literal
            # plus-strand observation makes orientation auditable.
            if three_prime_at_start:
                primer_base = reverse_complement(wanted)
                template_base = observed
            else:
                primer_base = wanted
                template_base = reverse_complement(observed)
            identities.append((distance, primer_base, template_base, observed))
        elif observed not in UNAMBIGUOUS_BASES:
            ambiguous.append(distance)
    return (
        tuple(sorted(definite)),
        tuple(sorted(ambiguous)),
        tuple(sorted(identities, key=lambda item: item[0])),
    )


def _seed_partitions(primer: str, max_mismatches: int) -> list[tuple[int, str]]:
    """k+1 non-empty contiguous seeds that guarantee <=k mismatch discovery.

    By the pigeonhole principle, an ungapped window with at most ``k`` definite
    mismatches must contain at least one exactly matching segment when the
    primer is partitioned into ``k+1`` disjoint non-empty segments.
    """
    length = len(primer)
    parts = max_mismatches + 1
    if parts > length:
        raise ValueError(
            f"specificity max_mismatches={max_mismatches} cannot be guaranteed for a "
            f"{length}-base primer with non-empty exact seed partitions; use a smaller "
            "ungapped mismatch budget or an indexed alignment workflow"
        )
    base, extra = divmod(length, parts)
    out: list[tuple[int, str]] = []
    offset = 0
    for index in range(parts):
        width = base + (1 if index < extra else 0)
        out.append((offset, primer[offset : offset + width]))
        offset += width
    return out


def _candidate_window_starts(haystack: str, expected: str, max_mismatches: int) -> list[int]:
    """Candidate starts complete for the declared whole-primer mismatch budget."""
    starts: set[int] = set()
    for offset, seed in _seed_partitions(expected, max_mismatches):
        for seed_at in _possible_seed_starts(haystack, seed):
            window_start = seed_at - offset
            if 0 <= window_start and window_start + len(expected) <= len(haystack):
                starts.add(window_start)
    return sorted(starts)


def _conservative_thermo_window(window: str, primer: str) -> tuple[str, int]:
    """Make an ambiguity window measurable without treating it as certain.

    The literal mismatch count deliberately does not treat IUPAC symbols as
    wildcards. For the thermodynamic *possibility* screen, however, using a
    compatible concrete base gives a conservative sequence surrogate: if the
    unknown base could match the primer, the site is not silently discarded. It
    is not a mathematical upper bound over every possible nearest-neighbour
    sequence; the ambiguity count keeps that limitation visible.
    The returned count keeps this uncertainty visible to the report.
    """
    concrete: list[str] = []
    ambiguous = 0
    for base, expected in zip(window, primer, strict=True):
        choices = IUPAC_BASES.get(base)
        if choices is None:
            raise ValueError(f"background contains unsupported base {base!r}")
        if base in UNAMBIGUOUS_BASES:
            concrete.append(base)
            continue
        ambiguous += 1
        concrete.append(expected if expected in choices else sorted(choices)[0])
    return "".join(concrete), ambiguous


def _score(
    primer: str,
    hybrid: str,
    reaction: Reaction,
    *,
    temperature_c: float,
) -> tuple[float, float]:
    """Free energy and melting temperature of the duplex actually formed."""
    result = pair_dimer(
        primer,
        hybrid,
        **reaction.as_conditions(),
        temp_c=temperature_c,
    )
    return result.dg, result.tm


def _validate_temperature(temperature_c: float) -> float:
    """Reject a malformed thermodynamic evaluation temperature early."""
    if isinstance(temperature_c, bool) or not isinstance(temperature_c, (int, float)):
        raise ValueError("specificity temperature must be a finite number")
    try:
        finite = math.isfinite(float(temperature_c))
    except OverflowError:
        finite = False
    if not finite or temperature_c <= ABSOLUTE_ZERO_C:
        raise ValueError("specificity temperature must be finite and above absolute zero")
    return float(temperature_c)


def _validate_integer(value: Any, *, name: str, minimum: int) -> int:
    """Validate a discrete scan control without coercing its wire value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, not {value!r}")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, not {value}")
    return value


def _validate_number(value: Any, *, name: str) -> float:
    """Reject non-finite thermodynamic controls before comparisons."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number, not {value!r}")
    try:
        finite = math.isfinite(float(value))
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be finite, not {value!r}")
    return float(value)


def sites_for(
    primer: str,
    role: str,
    contigs: list[Contig],
    *,
    reaction: Reaction,
    max_mismatches: int = 3,
    min_dg: float | None = None,
    include_terminal_mismatch: bool = False,
    temperature_c: float = DEFAULT_TEMPERATURE_C,
) -> list[Site]:
    """Every sequence window compatible with the declared mismatch envelope.

    When `min_dg` is a number it drops thermodynamically weak sites after
    sequence discovery. `None` disables that filter so assay-validity gates
    cannot depend on an arbitrary thermodynamic reference temperature.

    Discovery is mismatch-complete across the whole primer for the declared
    ungapped mismatch budget. `include_terminal_mismatch` is retained as report
    provenance for callers that specifically review 3-prime mismatches; it no
    longer changes which sites are discoverable.
    """
    if not isinstance(primer, str):
        raise ValueError("specificity primer must be a non-empty DNA string")
    primer = primer.upper()
    length = len(primer)
    if not primer:
        raise ValueError("specificity primer must be a non-empty DNA string")
    invalid_primer = sorted(set(primer) - UNAMBIGUOUS_BASES)
    if invalid_primer:
        raise ValueError(
            "specificity primer must use unambiguous DNA bases (ACGT); "
            f"unsupported symbol(s): {', '.join(invalid_primer)}"
        )
    max_mismatches = _validate_integer(max_mismatches, name="specificity max_mismatches", minimum=0)
    if min_dg is not None:
        min_dg = _validate_number(min_dg, name="specificity minimum ΔG")
    temperature_c = _validate_temperature(temperature_c)
    found: list[Site] = []
    rc_primer = reverse_complement(primer)

    for contig in contigs:
        plus = contig.sequence

        # Extending towards higher coordinates. Candidate starts are complete
        # for the declared whole-primer mismatch budget; no terminal exact seed
        # is required.
        for start in _candidate_window_starts(plus, primer, max_mismatches):
            window = plus[start : start + length]
            bounds = _mismatch_bounds(window, primer)
            if bounds is None or bounds[0] > max_mismatches:
                continue
            count, mismatch_upper_bound = bounds
            mismatch_positions, ambiguous_positions, mismatch_identities = _mismatch_topology(
                window,
                primer,
                three_prime_at_start=False,
            )
            thermo_window, ambiguous = _conservative_thermo_window(window, primer)
            dg, tm = _score(
                primer,
                reverse_complement(thermo_window),
                reaction,
                temperature_c=temperature_c,
            )
            if min_dg is not None and dg > min_dg:
                continue
            found.append(
                Site(
                    primer=primer,
                    role=role,
                    contig=contig.name,
                    three_prime_at=start + length - 1,
                    orientation="forward",
                    mismatches=count,
                    dg=dg,
                    tm=tm,
                    ambiguous_bases=ambiguous,
                    mismatch_upper_bound=mismatch_upper_bound,
                    mismatch_positions_from_three_prime=mismatch_positions,
                    ambiguous_positions_from_three_prime=ambiguous_positions,
                    mismatch_base_pairs_from_three_prime=mismatch_identities,
                )
            )

        # Extending towards lower coordinates; the plus strand carries the
        # reverse-complement spelling of the primer.
        for window_start in _candidate_window_starts(plus, rc_primer, max_mismatches):
            window = plus[window_start : window_start + length]
            bounds = _mismatch_bounds(window, rc_primer)
            if bounds is None or bounds[0] > max_mismatches:
                continue
            count, mismatch_upper_bound = bounds
            mismatch_positions, ambiguous_positions, mismatch_identities = _mismatch_topology(
                window,
                rc_primer,
                three_prime_at_start=True,
            )
            thermo_window, ambiguous = _conservative_thermo_window(window, rc_primer)
            dg, tm = _score(primer, thermo_window, reaction, temperature_c=temperature_c)
            if min_dg is not None and dg > min_dg:
                continue
            found.append(
                Site(
                    primer=primer,
                    role=role,
                    contig=contig.name,
                    three_prime_at=window_start,
                    orientation="reverse",
                    mismatches=count,
                    dg=dg,
                    tm=tm,
                    ambiguous_bases=ambiguous,
                    mismatch_upper_bound=mismatch_upper_bound,
                    mismatch_positions_from_three_prime=mismatch_positions,
                    ambiguous_positions_from_three_prime=ambiguous_positions,
                    mismatch_base_pairs_from_three_prime=mismatch_identities,
                )
            )

    return found


def _append_product_stream(
    products: list[OffTarget],
    stream: Iterator[Site],
    *,
    contig: str,
    start: int,
    forward: Site,
    max_product: int,
) -> None:
    """Append one reverse-site stream sorted by product end."""
    for reverse in stream:
        end = reverse.three_prime_at + len(reverse.primer) - 1
        size = end - start + 1
        if size > max_product:
            # Each stream is sorted by product end, so every remaining site
            # in this stream is longer.
            break
        products.append(
            OffTarget(
                contig=contig,
                start=start,
                end=end,
                size=size,
                forward=forward,
                reverse=reverse,
            )
        )


def products_from(
    sites: list[Site],
    *,
    max_product: int,
    circular_length: int | None = None,
    circular_lengths: dict[str, int] | None = None,
) -> list[OffTarget]:
    """Every pair of sites that face each other closely enough to amplify.

    Any orientation of any two primers counts, including a primer against
    itself. A forward site and a reverse site of the same primer make a
    product, and it is one of the classic reasons a reaction produces a band
    nobody designed. When ``circular_length`` is supplied, a reverse site
    before a forward site is also tested one turn later, so a product crossing
    the arbitrary origin is not lost by the linear spelling of a circle.
    """
    max_product = _validate_integer(max_product, name="max_product", minimum=1)
    if circular_length is not None:
        circular_length = _validate_integer(circular_length, name="circular_length", minimum=1)
    checked_circular_lengths: dict[str, int] = {}
    for contig_name, length in (circular_lengths or {}).items():
        checked_circular_lengths[str(contig_name)] = _validate_integer(
            length, name=f"circular_lengths[{contig_name}]", minimum=1
        )
    if circular_length is not None and checked_circular_lengths:
        raise ValueError("choose scalar circular_length or per-contig circular_lengths, not both")

    by_contig: dict[str, list[Site]] = {}
    for site in sites:
        by_contig.setdefault(site.contig, []).append(site)

    products: list[OffTarget] = []
    for contig, group in by_contig.items():
        forwards = sorted(
            (s for s in group if s.orientation == "forward"),
            key=lambda s: s.three_prime_at,
        )
        # Sorted by where each product would *end*, not by where the primer's
        # 3' end sits. Those are the same thing only when every primer is the
        # same length: a site 5 bases further along carrying a primer 12 bases
        # shorter gives a shorter product, not a longer one. Sorted the other
        # way, the early exit below skipped it -- and a missed off-target is
        # the one direction this scan must never fail in, because it reports a
        # design as specific when it is not.
        reverses = sorted(
            (s for s in group if s.orientation == "reverse"),
            key=lambda s: s.three_prime_at + len(s.primer),
        )
        for f in forwards:
            start = f.three_prime_at - len(f.primer) + 1

            # The direct arc is already in the linear coordinate frame. The
            # second loop represents the same circle after one turn: a reverse
            # site near the origin is shifted by the circle length and can now
            # face a forward site near the end. Keep the two sorted streams
            # separate; interleaving them would make the early length break
            # incorrect because their coordinate ranges are different.
            _append_product_stream(
                products,
                (r for r in reverses if r.three_prime_at > f.three_prime_at),
                contig=contig,
                start=start,
                forward=f,
                max_product=max_product,
            )
            contig_circular_length = checked_circular_lengths.get(contig, circular_length)
            if contig_circular_length is not None:
                _append_product_stream(
                    products,
                    (
                        replace(r, three_prime_at=r.three_prime_at + contig_circular_length)
                        for r in reverses
                        if r.three_prime_at <= f.three_prime_at
                    ),
                    contig=contig,
                    start=start,
                    forward=f,
                    max_product=max_product,
                )

    products.sort(key=lambda p: p.worst_dg)
    return products


def scan(
    primers: dict[str, str],
    background: str,
    *,
    background_name: str = "background",
    reaction: Reaction,
    max_mismatches: int = 3,
    max_product: int = 3000,
    min_dg: float | None = None,
    temperature_c: float = DEFAULT_TEMPERATURE_C,
) -> Specificity:
    """Check a set of primers against a background sequence.

    Args:
        primers: Role name to sequence, e.g. `{"left": "ACGT...", "right": "..."}`.
        background: FASTA text, or a bare sequence.

    Raises:
        BackgroundTooLarge: when the background needs an indexed tool instead.
    """
    if not isinstance(background, str):
        raise ValueError("background must be text")
    max_mismatches = _validate_integer(max_mismatches, name="specificity max_mismatches", minimum=0)
    max_product = _validate_integer(max_product, name="max_product", minimum=1)
    if min_dg is not None:
        min_dg = _validate_number(min_dg, name="specificity minimum ΔG")
    temperature_c = _validate_temperature(temperature_c)

    contigs = (
        parse_fasta(background)
        if background.lstrip().startswith(">")
        else [
            Contig(
                name=background_name,
                sequence=normalise_background(background),
            )
        ]
    )
    contigs = [c for c in contigs if c.sequence]
    total = sum(len(c.sequence) for c in contigs)

    if not total:
        return Specificity(
            checked=False,
            background_name=background_name,
            background_bases=0,
            max_mismatches=max_mismatches,
            note="The background held no sequence, so nothing was checked.",
            temperature_c=temperature_c,
        )
    if total > MAX_BACKGROUND_BASES:
        raise BackgroundTooLarge(
            f"The background is {total:,} bases, and this scan stops at "
            f"{MAX_BACKGROUND_BASES:,}. It compares every candidate site "
            "directly, which is exact but linear: a mammalian genome would take "
            "about a quarter of an hour and hold three gigabytes of memory for "
            "one design. "
            "What usually works instead: the chromosome the target is on, the "
            "transcriptome rather than the genome, or the handful of relatives "
            "you actually need to be distinguished from. A background chosen "
            "for the question is a better answer than a whole genome scanned "
            "slowly, because the whole genome mostly contains sequence your "
            "reaction will never meet."
        )

    sites: list[Site] = []
    for role, sequence in primers.items():
        sites.extend(
            sites_for(
                sequence,
                role,
                contigs,
                reaction=reaction,
                max_mismatches=max_mismatches,
                min_dg=min_dg,
                temperature_c=temperature_c,
            )
        )

    return Specificity(
        checked=True,
        background_name=background_name,
        background_bases=total,
        max_mismatches=max_mismatches,
        sites=sites,
        products=products_from(sites, max_product=max_product),
        min_dg=min_dg,
        max_product=max_product,
        temperature_c=temperature_c,
    )


def _site_to_dict(site: Site) -> dict[str, Any]:
    return {
        "role": site.role,
        "contig": site.contig,
        # One-based, like every genome browser.
        "three_prime_at": site.three_prime_at + 1,
        "orientation": site.orientation,
        "mismatches": site.mismatches,
        "ambiguous_bases": site.ambiguous_bases,
        "mismatch_upper_bound": (
            site.mismatch_upper_bound if site.mismatch_upper_bound is not None else site.mismatches
        ),
        "mismatch_positions_from_three_prime": list(site.mismatch_positions_from_three_prime),
        "ambiguous_positions_from_three_prime": list(site.ambiguous_positions_from_three_prime),
        "mismatch_base_pairs_from_three_prime": [
            {
                "position": position,
                "primer_base": primer_base,
                "template_base": template_base,
                "background_plus_base": background_plus_base,
            }
            for position, primer_base, template_base, background_plus_base in site.mismatch_base_pairs_from_three_prime
        ],
        "nearest_three_prime_mismatch": (
            min(site.mismatch_positions_from_three_prime)
            if site.mismatch_positions_from_three_prime
            else None
        ),
        "dg": site.dg,
        "tm": site.tm,
    }


def specificity_to_dict(result: Specificity, *, max_products: int = 20) -> dict[str, Any]:
    """The scan as plain data, with the worst offenders first."""
    return {
        "checked": result.checked,
        "background_name": result.background_name,
        "background_bases": result.background_bases,
        "max_mismatches": result.max_mismatches,
        "terminal_mismatch_scan": result.terminal_mismatch_scan,
        "temperature_c": result.temperature_c,
        "method": method_to_dict(
            max_mismatches=result.max_mismatches,
            min_dg=result.min_dg,
            max_product=result.max_product,
            terminal_mismatch_scan=result.terminal_mismatch_scan,
            template_only=result.template_only,
            temperature_c=result.temperature_c,
        ),
        "site_count": len(result.sites),
        "product_count": len(result.products),
        "note": result.note,
        "products": [
            {
                "contig": p.contig,
                "start": p.start + 1,
                "end": p.end + 1,
                "size": p.size,
                "worst_dg": p.worst_dg,
                "forward": _site_to_dict(p.forward),
                "reverse": _site_to_dict(p.reverse),
            }
            for p in result.products[:max_products]
        ],
    }
