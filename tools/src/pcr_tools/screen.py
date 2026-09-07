"""Where else these oligos could sit, for every worker that designs any.

Six of the twenty-one assays showed a specificity step whose answer went
nowhere. The engines behind them have no `background` field, so a pasted genome
was dropped on the way in and the result said nothing about it — the worst
shape a check can take, because a design nobody looked at reads exactly like a
design that came back clean.

The scan itself already existed in :mod:`specificity` and was used by one
worker. What was missing was the part around it: deciding what to scan against,
falling back to the template when nothing else was given, and turning the
answer into the block every result already renders. That is what this module
is, and it is one module rather than six so that a LAMP set and a KASP pair
cannot come to different conclusions about the same genome.
"""

from __future__ import annotations

from typing import Any

from . import specificity as spec
from .presets import Reaction
from .thermo import reverse_complement


#: How far past the longest intended product a second band still counts.
#:
#: Three times, floored at three kilobases: a product much longer than the one
#: asked for will not out-compete it in a tube, and scanning for it costs time
#: on every candidate. The same number the pair pipeline has always used.
def product_ceiling(longest_intended: int) -> int:
    """The longest unwanted product worth reporting."""
    return max(longest_intended * 3, 3000)


#: How much of a circle's beginning is repeated at its end when scanning it.
#:
#: A plasmid has no ends, but the string somebody pastes does, and a primer
#: sitting across the join falls in the gap between them. Repeating the first
#: `JOIN_WINDOW` bases at the end puts that site back inside a linear string,
#: which is the only place the scanner can see it.
#:
#: Sixty is longer than any primer this build will design — the longest a
#: constraint window allows is 36 — so a primer that spans the join is found
#: whole. Making it larger only invents duplicate sites for primers that sit
#: near the origin without crossing it.
JOIN_WINDOW = 60


def contigs_from_text(
    value: str,
    *,
    label: str,
    default_name: str,
) -> list[spec.Contig]:
    """Parse one sequence field without silently weakening its scope."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    if value.lstrip().startswith(">"):
        contigs = spec.parse_fasta(value, label=label)
    elif value.strip():
        contigs = [
            spec.Contig(
                name=default_name,
                sequence=spec.normalise_background(value, label=label),
            )
        ]
    else:
        contigs = []

    contigs = [contig for contig in contigs if contig.sequence]
    if not contigs:
        raise ValueError(
            f"The {label} was supplied but contained no DNA sequence. Fix the "
            "FASTA records instead of silently treating coverage as complete."
        )
    bases = sum(len(contig.sequence) for contig in contigs)
    if bases > spec.MAX_BACKGROUND_BASES:
        raise spec.BackgroundTooLarge(
            f"The {label} is {bases:,} bases. This scan compares every candidate "
            f"site directly and stops at {spec.MAX_BACKGROUND_BASES:,}; use a "
            "representative panel or an indexed search for larger inputs."
        )
    return contigs


def contigs_for(
    request: dict[str, Any],
    *,
    template: str,
    name: str = "",
) -> tuple[list[spec.Contig], bool, int | None]:
    """What to scan against, and whether it is only the template itself.

    The template is the fallback rather than an addition, and the restriction
    is the point: a background is usually the genome the target lives in, so
    scanning both would find the target's own locus twice — once on the
    template, once in the background — and report the second as an off-target.
    A false second band is worse than a missing check, because it is believed.

    Returns:
        The sequences to scan, whether they are only the template, and — for a
        circle scanned across its own join — where the real sequence ends, so
        a site found in the repeated head can be told from a real one.

    Raises:
        BackgroundTooLarge: when the background needs an indexed tool instead.
    """
    background_value = request.get("background")
    if background_value is not None and not isinstance(background_value, str):
        raise ValueError("background must be text")
    # Presence matters. An explicitly supplied empty/whitespace background is a
    # malformed exclusion scope, not the same request as omitting the field.
    # Treating both alike would silently weaken a specificity claim after a
    # failed paste or a UI serialisation bug.
    background_supplied = background_value is not None
    background = background_value or ""
    contigs = (
        contigs_from_text(
            background,
            label="background",
            default_name="background",
        )
        if background_supplied
        else []
    )
    only_the_template = not contigs
    fold_at: int | None = None
    if only_the_template and template:
        # A circle is scanned across its own join. Without this, a primer
        # sitting over a plasmid's origin is invisible to a scan of the string
        # somebody pasted — and the origin is arbitrary, so which primers are
        # invisible depends on where the file happens to begin.
        if request.get("circular") and len(template) > JOIN_WINDOW:
            fold_at = len(template)
            template = template + template[:JOIN_WINDOW]
        contigs = [
            spec.Contig(
                name=f"{name or 'your sequence'} (the template itself)",
                # Lowercase is meaningful to Primer3 as soft masking, but the
                # specificity scanner's DNA alphabet is uppercase. The scan
                # must still see a masked repeat as sequence when asking
                # whether a primer has another possible site on the template;
                # masking is a search-placement rule, not deletion from the
                # molecule.
                sequence=template.upper(),
            )
        ]

    bases = sum(len(contig.sequence) for contig in contigs)
    if bases > spec.MAX_BACKGROUND_BASES:
        raise spec.BackgroundTooLarge(
            f"The background is {bases:,} bases. This scan compares every "
            f"candidate site directly and stops at "
            f"{spec.MAX_BACKGROUND_BASES:,}; anything larger needs an indexed "
            f"search."
        )
    return contigs, only_the_template, fold_at


def note_for(contigs: list[spec.Contig], only_the_template: bool) -> str:
    """What this run does not know, said rather than left out."""
    if not contigs:
        return (
            "Nothing was scanned. No background was given and there was no "
            "template to fall back on."
        )
    if only_the_template:
        return (
            "Only the pasted sequence was checked, because no background was "
            "given. A second site on your own sequence would have been found; "
            "nothing here speaks for anywhere else in the genome, the vector or "
            "the host."
        )
    return ""


def reported_bases(contigs: list[spec.Contig], fold_at: int | None = None) -> int:
    """Count the real sequence represented by a scan.

    Circular scans repeat the beginning of a molecule so a primer crossing the
    arbitrary FASTA origin can be found in a linear string. That repeated head
    is search scaffolding, not additional biological background. Reports must
    therefore use the real molecule length while the scanner continues to use
    the extended string internally.
    """
    if fold_at is None:
        return sum(len(contig.sequence) for contig in contigs)
    return sum(min(len(contig.sequence), fold_at) for contig in contigs)


def summary(
    contigs: list[spec.Contig],
    only_the_template: bool,
    *,
    max_mismatches: int = 3,
    min_dg: float | None = None,
    max_product: int = 3000,
    terminal_mismatch_scan: bool = False,
    fold_at: int | None = None,
) -> dict[str, Any]:
    """The block a result carries once, describing how far the scan looked.

    The result carries the versioned method and mismatch envelope because that
    is the answer to "how hard did it look". Specificity v5 discovery is
    mismatch-complete across the whole primer and has no exact-terminal-clamp
    request control.
    """
    return {
        "checked": bool(contigs),
        "bases": reported_bases(contigs, fold_at),
        "contigs": len(contigs),
        "max_mismatches": max_mismatches,
        "method": spec.method_to_dict(
            max_mismatches=max_mismatches,
            min_dg=min_dg,
            max_product=max_product,
            terminal_mismatch_scan=terminal_mismatch_scan,
            template_only=only_the_template,
        ),
        # Distinguishable from a real background, always. "Checked against a
        # genome and found unique" and "checked against your own sequence and
        # nothing else" are different claims, and only one of them is about the
        # sample.
        "template_only": only_the_template,
        "note": note_for(contigs, only_the_template),
    }


def _effective_temperature(
    named: dict[str, str],
    reaction: Reaction,
    temperature_c: float | None,
) -> float:
    """Resolve the temperature for a shared oligo screen.

    Callers with a named hold pass it explicitly. PCRStudio does not infer a
    thermal-cycler setting from primer Tm: unresolved workers use the fixed
    Primer3-compatible 37 °C model reference, reported as a calculation context
    rather than a bench protocol.
    """
    if temperature_c is not None:
        return spec._validate_temperature(temperature_c)
    return spec.DEFAULT_TEMPERATURE_C


def oligos(
    named: dict[str, str],
    contigs: list[spec.Contig],
    *,
    reaction: Reaction,
    max_mismatches: int = 3,
    max_product: int = 3000,
    intended_sizes: list[int] | None = None,
    intended_products: list[str] | None = None,
    max_products: int = 8,
    non_extending: dict[str, str] | None = None,
    fold_at: int | None = None,
    temperature_c: float | None = None,
) -> dict[str, Any]:
    """Every place this set of oligos could sit, and what could come of it.

    `named` maps a role to a sequence — `{"left": ..., "right": ...}` for a
    pair, `{"F3": ..., "B3": ..., "FIP": ...}` for a loop set, one entry for a
    sequencing primer. Roles that do not oppose each other simply produce no
    products, which is the honest answer: a single primer that binds twice
    ruins a trace without ever making a band.

    `intended_sizes` excuses one product per listed length as one somebody
    asked for. A list rather than a number because a genotyping assay has
    several: a tetra-primer tube is meant to give three bands, and a scan that
    called all three unwanted would be reporting every design as broken, which
    is the same as reporting none. When the caller knows the complete intended
    amplicon, `intended_products` is preferred: it excuses only one product
    with that exact sequence (in either strand orientation), so a same-size
    paralogue remains visible. Entries are paired by index; a missing product
    sequence deliberately falls back to the corresponding size rule.

    `fold_at` is where a circle's real sequence ends, when it was scanned with
    its own head repeated at the tail. A site that begins past that point is
    the same site as one already found at the start — the repeat exists only so
    that a primer *crossing* the join can be seen whole — and counting it twice
    would invent a second copy of every primer near the origin.

    `non_extending` holds oligos whose second sites matter but which cannot
    start a product — a hydrolysis probe is blocked at its 3' end, and pairing
    it with a primer to invent a band would be reporting a reaction that
    chemistry forbids. Their sites are found and reported; they take no part in
    forming products.
    """
    if not contigs:
        return {"checked": False}

    effective_temperature = _effective_temperature(named, reaction, temperature_c)

    sites: list[spec.Site] = []
    for role, sequence in named.items():
        if not sequence:
            continue
        sites += spec.sites_for(
            sequence,
            role,
            contigs,
            reaction=reaction,
            max_mismatches=max_mismatches,
            min_dg=None,
            temperature_c=effective_temperature,
        )

    if fold_at is not None:
        sites = [site for site in sites if leftmost(site) < fold_at]

    products = spec.products_from(
        sites,
        max_product=max_product,
        circular_length=fold_at,
    )

    # Found and reported, but never paired into a band.
    for role, sequence in (non_extending or {}).items():
        if not sequence:
            continue
        sites += spec.sites_for(
            sequence,
            role,
            contigs,
            reaction=reaction,
            max_mismatches=max_mismatches,
            min_dg=None,
            temperature_c=effective_temperature,
        )
    sizes = intended_sizes or []
    sequences = intended_products or []
    for index, size in enumerate(sizes):
        products = _without_the_intended(
            products,
            size,
            intended_sequence=sequences[index] if index < len(sequences) else None,
            contigs=contigs,
            circular_length=fold_at,
        )
    # A caller may have exact sequences but no convenient size list. Their
    # lengths are still sufficient to identify the intended product's size,
    # while the sequence remains the deciding comparison.
    for sequence in sequences[len(sizes) :]:
        products = _without_the_intended(
            products,
            len(sequence),
            intended_sequence=sequence,
            contigs=contigs,
            circular_length=fold_at,
        )

    return {
        "checked": True,
        "thermodynamic_temperature_role": (
            "model-reference-not-bench-annealing"
            if temperature_c is None
            else "caller-declared-hold"
        ),
        **spec.specificity_to_dict(
            spec.Specificity(
                checked=True,
                background_name=contigs[0].name,
                background_bases=reported_bases(contigs, fold_at),
                max_mismatches=max_mismatches,
                sites=sites,
                products=products,
                min_dg=None,
                max_product=max_product,
                temperature_c=effective_temperature,
            ),
            max_products=max_products,
        ),
    }


def leftmost(site: spec.Site) -> int:
    """The lowest coordinate this site occupies on the plus strand.

    `three_prime_at` is the primer's 3' end, which is the *right* edge of a
    forward site and the *left* edge of a reverse one — so neither can be
    compared to a boundary without knowing which way the site faces.
    """
    if site.orientation == "forward":
        return site.three_prime_at - len(site.primer) + 1
    return site.three_prime_at


def _without_the_intended(
    products: list[spec.OffTarget],
    size: int,
    *,
    intended_sequence: str | None = None,
    contigs: list[spec.Contig] | None = None,
    circular_length: int | None = None,
) -> list[spec.OffTarget]:
    """Drop exactly one intended product, never a same-size neighbour.

    One, not all of them: a target present twice — a tandem duplication, a
    paralogue, the plasmid and the chromosome — gives two bands of the same
    length, and the second is the failure this scan exists to find.
    """
    if intended_sequence is not None:
        if contigs is None:
            raise ValueError("exact intended-product matching needs the scanned contigs")
        wanted = intended_sequence.upper()
        reverse_wanted = reverse_complement(wanted)
        sequences = {contig.name: contig.sequence.upper() for contig in contigs}
        for index, product in enumerate(products):
            if product.size != size:
                continue
            sequence = sequences.get(product.contig, "")
            if circular_length is None:
                observed = sequence[product.start : product.end + 1]
            else:
                circle = sequence[:circular_length]
                observed = "".join(
                    circle[(product.start + offset) % circular_length]
                    for offset in range(product.size)
                )
            if observed in {wanted, reverse_wanted}:
                return products[:index] + products[index + 1 :]
        return products

    dropped = False
    kept = []
    for product in products:
        if not dropped and product.size == size:
            dropped = True
            continue
        kept.append(product)
    return kept
