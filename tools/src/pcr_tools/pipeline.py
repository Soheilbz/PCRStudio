"""One run, from what somebody pasted to what they should order.

The stages are separate modules because each answers a different question and
each can fail on its own terms. This file is only the order they happen in, the
scoring that combines them, and the account of what was used — which is the
part that makes a result reproducible a year later, when the accession has been
revised and the tool versions have moved.

Nothing here decides silently. A stage that could not run says so in the
result rather than being absent from it, because a missing section reads as
"there was nothing to report" and that is usually the opposite of the truth.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from . import accessibility as access
from . import amplicon as amplicon_mod
from . import backbone, rt, screen, validation_plan
from . import explain as explain_mod
from . import restriction as restriction_mod
from . import specificity as spec
from . import tails as tails_mod
from . import variants as variants_mod
from .cloning_coding import resolve_cloning_coding_context
from .design import (
    CandidatePair,
    Constraints,
    DesignResult,
    design,
    design_terminal_pair,
    result_to_dict,
)
from .flanking_numeric_recipes import resolve_numeric_recipe as resolve_flanking_numeric_recipe
from .flanking_request import (
    _exon_junctions,
    _flanking_numeric_context,
    _number_map,
    _reject_unknown_fields,
    _request_integer,
    _request_optional_text,
    _validate_assay_rna,
    _workflow_evidence,
)
from .intake import Target, resolve, target_to_dict
from .modified_oligos import provenance_block as modified_oligo_provenance
from .presets import (
    Cycling,
    Polymerase,
    Purpose,
    Reaction,
    polymerase,
    purpose,
    thermodynamic_model,
)
from .provenance import provenance
from .registries.flanking_protocols import (
    colony_context,
    digital_context,
    digital_protocol,
    long_range_protocol,
    qpcr_protocol,
    rpa_protocol,
    standard_pcr_protocol,
)
from .registries.restriction_workflows import resolve_restriction_workflow
from .rpa_multiplex import extend_order_sheet as extend_rpa_multiplex_order_sheet
from .rpa_multiplex import resolve as resolve_rpa_multiplex
from .rpa_screening import screening_cohort_for_current_mode as rpa_screening_cohort
from .runtime_contract import validate_required_context
from .scientific_integrity import (
    enforce_constraint_overrides,
    enforce_polymerase_identity,
    enforce_reaction_overrides,
    resolve_purpose,
)
from .settings import _validate_assay_contract, label
from .species_panel import (
    SpeciesPanelError,
    accession_authority_sha256,
    parse_accession_authority_manifest,
    parse_accession_version_manifest,
    parse_record_metadata_manifest,
    record_metadata_sha256,
    validate_accession_authority,
    validate_record_metadata,
)
from .species_panel import manifest_sha256 as species_manifest_sha256
from .species_panel import revalidation_policy as species_revalidation_policy
from .thermo import DEFAULT_CONDITIONS, pair_dimer, reverse_complement

#: How firmly an unwanted site has to bind, as a fraction of how firmly the
#: primers bind the site they were designed for.
#:
#: Relative rather than absolute, and that was measured rather than argued. A
#: fixed -10 kcal/mol called 100 per cent of perfect matches, 99 per cent of
#: one-mismatch sites and 96 per cent of two-mismatch sites serious, so the
#: three-way split was doing the work of "everything is serious". A free energy
#: also scales with length and GC, so one number cannot mean the same thing for
#: a 35-mer at 68 degrees and an 18-mer at 57.
#:
#: Both are tuning parameters. No source gives a fraction; what the measurement
#: gives is that these two separate the mismatch classes where fixed energies
#: did not.
OFF_TARGET_SERIOUS = 0.75
OFF_TARGET_WATCH = 0.55

#: The most an off-target penalty may add to a score.
#:
#: A tuning parameter. Its job is to stop a design in a repetitive background
#: scoring so badly that the ranking among the rest stops meaning anything.
PENALTY_CAP = 5.0

#: How much one order of magnitude of lost template accessibility costs a
#: candidate, and the most it can cost in total. Deliberately small: this is a
#: tie-break between designs Primer3 already considers equivalent, not a
#: verdict of its own.
ACCESSIBILITY_WEIGHT = 0.2
ACCESSIBILITY_CAP = 2.0
# Diagnostic wording threshold only; accessibility is advisory and does not rank.
ACCESSIBILITY_DETAIL_LOG_ORDERS = 0.5

#: Free energy at which two oligos sticking to each other is worth mentioning.
#:
#: Looser than the threshold the search itself uses, because this is a warning
#: about an order rather than a rejection of a design.
#:
#: Measured over 75 candidates on five unrelated templates, this line selects
#: the worst 8 per cent: the median pair binds at -3.8 kcal/mol and only six of
#: the seventy-five fell below -6. That is the right shape for a threshold
#: whose job is to single out the exceptions, so `_score_cross_dimer` uses this
#: one rather than introducing a second number beside it.
CROSS_PAIR_DIMER_WATCH = -6.0

#: What each kcal/mol below that line costs a candidate, and the ceiling on it.
#:
#: The worst pair in that measurement bound at -9.3, which this turns into
#: about half a point -- the whole spread of a candidate field. Deliberately
#: larger than the variant tie-break: a pair whose primers are busy with each
#: other is genuinely a worse pair, not merely a less tidy one.
CROSS_DIMER_WEIGHT = 0.15
CROSS_DIMER_CAP = 0.75

#: How many distinct designs to score for every one that is returned.
#:
#: Primer3 ranks on its own penalty, which knows nothing about the background
#: or about whether the template keeps a site closed. Scoring only as many as
#: were asked for would mean this pipeline's own opinion could reorder Primer3's
#: top five and nothing else -- a pair Primer3 put eighth on melting temperature
#: alone could be the only one that does not amplify a pseudogene, and would
#: never be looked at. Three was measured rather than picked: scoring fifteen
#: pairs instead of five cost no measurable time on a 2.5 kb template.
SHORTLIST_FACTOR = 3

# A junction-spanning RT design is a post-search geometry rule: Primer3 knows
# the transcript sequence, but it cannot be told that one of several supplied
# transcript boundaries must lie inside a primer. Ask for a wider pool before
# applying that rule, or a perfectly valid junction-spanning candidate may sit
# just below the ordinary shortlist. This is a search multiplier, not a claim
# about biology or assay success.
JUNCTION_SHORTLIST_FACTOR = 4

#: The most pairs one run will return.
#:
#: Primer3 refuses fewer than one. The ceiling is ours: past a few dozen the
#: results stop being distinct designs and start being the same design shifted
#: along, which the diversifier would collapse anyway.
MAX_PAIRS = 50

# Keep the direct worker command aligned with the Rust flanking-pair adapter.
# This is a service/runtime boundary, not a biological statement: a larger
# sequence needs an indexed or region-based workflow rather than making this
# in-memory candidate path silently slower and less predictable.
MAX_TEMPLATE_BASES = 1_000_000

# Keep the worker's direct command as strict as the Rust wire adapter. The
# service normally rejects unknown JSON fields before spawning Python, but
# multiplex and local callers can enter this function directly. Silently
# dropping a misspelled setting would make the recorded request differ from
# the experiment that actually ran.
KNOWN_REQUEST_FIELDS = frozenset(
    {
        "template",
        "name",
        "lowercase_masking",
        "target_start",
        "target_length",
        "polymerase",
        "purpose",
        "conditions",
        "constraints",
        "background",
        "inclusivity",
        "inclusivity_panel_provenance",
        "background_panel_provenance",
        "species_panel_selection_rationale",
        "species_target_taxid",
        "species_taxonomy_snapshot",
        "species_database_snapshot",
        "species_panel_accession_manifest",
        "species_panel_accession_authority_manifest",
        "species_panel_record_metadata_manifest",
        "species_panel_retrieved_date",
        "max_mismatches",
        "how_many",
        "assay",
        "excluded",
        "variants",
        "tails",
        "vector_primer",
        "from_rna",
        "exon_junctions",
        "circular",
        "standard_pcr_protocol",
        "qpcr_protocol",
        "rpa_protocol",
        "long_range_protocol",
        "digital_protocol",
        "flanking_numeric_context",
        "digital_partition_format",
        "digital_platform_id",
        "digital_platform_name",
        "digital_instrument_model",
        "digital_fragmentation_state",
        "digital_multiplex_mode",
        "digital_multiplex_panel",
        "digital_run_evidence",
        "rpa_multiplex_panel",
        "colony_host_class",
        "colony_preparation",
        "colony_protocol_id",
        "colony_protocol_name",
        "colony_protocol_provenance",
        "cloning_vector",
        "cloning_vector_name",
        "cloning_vector_topology",
        "restriction_digest_protocol",
        "restriction_dephosphorylation_protocol",
        "restriction_ligation_protocol",
        "cloning_coding_intent",
        "cloning_cds_start",
        "cloning_cds_end",
        "cloning_stop_codon_policy",
        "cloning_fusion_tag",
        "cloning_linker_aa",
        "cloning_vector_junction_frame",
        "workflow_evidence",
        "modified_oligos",
        "multiplex_context",
    }
)
# `assay` is deliberately shared as JSON by the Rust registry and the Python
# worker, so the outer object contains descriptive manifest fields that this
# pipeline does not use. The defaults block is different: every key in it is
# executable configuration, and silently accepting a misspelling there would
# make the result's apparent assay differ from the one that actually ran.
KNOWN_ASSAY_FIELDS = frozenset(
    {
        "id",
        "name",
        "summary",
        "guidance",
        "engine",
        "goal",
        "status",
        # Rust injects this marker at the API boundary so release orchestration
        # can prove the assay came from the canonical profile registry. It is
        # provenance, not executable assay configuration, and must survive the
        # worker's strict field validation.
        "profileAuthority",
        "modifiers",
        "defaults",
        "requires",
        "enzyme",
    }
)
KNOWN_ASSAY_DEFAULT_FIELDS = frozenset(
    {
        "polymerase",
        "chemistryFamily",
        "defaultPurpose",
        "purposes",
        "constraints",
        "constraintPolicy",
        "constraintEnvelope",
        "conditionPolicy",
        "allowedPolymerases",
        "cycling",
    }
)


KNOWN_TAIL_FIELDS = frozenset(
    {
        "tail_protocol",
        "protective_bases",
        "forward_protective_sequence",
        "reverse_protective_sequence",
        "forward_enzyme",
        "reverse_enzyme",
    }
)
KNOWN_VECTOR_PRIMER_FIELDS = frozenset({"name", "sequence", "reads_into", "vector", "how_many"})


def _pair_has_product_on_contig(
    pair: CandidatePair,
    contig: spec.Contig,
    *,
    reaction: Reaction,
    max_mismatches: int,
    min_product: int,
    max_product: int,
    circular: bool = False,
    temperature_c: float = spec.DEFAULT_TEMPERATURE_C,
    min_dg: float | None = None,
    require_unambiguous_sites: bool = False,
) -> bool:
    """Whether both named primers can form a product on one target record.

    Inclusivity is a sequence-coverage gate, not an off-target score. The
    caller chooses the mismatch envelope explicitly; Scientific-Strict calls
    this helper with zero mismatches because a tolerated mismatch is not, by
    itself, evidence of target amplification. The two *different* pair roles
    must face one another. A single binding site or a self-product is not evidence that the
    intended assay works on that record. The product must also remain inside
    the assay's own size window: a remote, incidental product is not evidence
    that the designed target is covered.

    When ``require_unambiguous_sites`` is true, a site is eligible only when
    its IUPAC mismatch interval collapses to an exact unambiguous match. This
    matters for intended-target inclusivity: an ``N``/``R``/other ambiguity
    under a primer is evidence that *some* allele may match, not evidence that
    every represented resolution is covered. The strict inclusivity gate
    therefore fails closed rather than converting a lower-bound mismatch of
    zero into an exact-coverage claim.

    When the target panel represents circular molecules, scan each record with
    the same short repeated head used by the main specificity path. Otherwise
    a valid target pair crossing the arbitrary FASTA origin would be invisible
    to the inclusivity gate even though the primary target search can design it.
    """
    fold_at: int | None = None
    scan_contig = contig
    if circular and len(contig.sequence) > screen.JOIN_WINDOW:
        fold_at = len(contig.sequence)
        scan_contig = spec.Contig(
            name=contig.name,
            sequence=contig.sequence + contig.sequence[: screen.JOIN_WINDOW],
        )

    sites = spec.sites_for(
        pair.left.sequence,
        "left",
        [scan_contig],
        reaction=reaction,
        max_mismatches=max_mismatches,
        include_terminal_mismatch=False,
        min_dg=min_dg,
        temperature_c=temperature_c,
    ) + spec.sites_for(
        pair.right.sequence,
        "right",
        [scan_contig],
        reaction=reaction,
        max_mismatches=max_mismatches,
        include_terminal_mismatch=False,
        min_dg=min_dg,
        temperature_c=temperature_c,
    )
    if fold_at is not None:
        sites = [site for site in sites if screen.leftmost(site) < fold_at]
    if require_unambiguous_sites:
        sites = [
            site
            for site in sites
            if site.ambiguous_bases == 0
            and (
                site.mismatch_upper_bound
                if site.mismatch_upper_bound is not None
                else site.mismatches
            )
            == 0
        ]
    return any(
        {product.forward.role, product.reverse.role} == {"left", "right"}
        and min_product <= product.size <= max_product
        for product in spec.products_from(sites, max_product=max_product, circular_length=fold_at)
    )


# ── Purpose-weighted objectives ──────────────────────────────────────────────
#
# When the product's downstream use is known, these ranking weights are merged
# into the search so Primer3's own penalty prices what that use actually cares
# about. They bias which *valid* candidate ranks first and nothing else: every
# hard limit in `Constraints` still gates the search, so a weighted run offers
# pairs that satisfy exactly the constraints an unweighted one would.
#
# primer3-py 2.3.1 accepts unknown tags in silence -- `PRIMER_WT_PRODUCT_SIZE`
# and `PRIMER_WT_GC_PERCENT`, once shipped here, changed nothing and said
# nothing. So a weight earns its place by behaviour, never by the absence of
# an error: every tag is checked against the manual, and then a run with it is
# compared against a run without on a real template, and it ships only if the
# candidates actually move. Verified as moving: PRIMER_WT_TM_GT reorders
# candidates and shifts their quoted penalties; PRIMER_PAIR_WT_PRODUCT_SIZE_GT
# and _LT pull every product toward PRIMER_PRODUCT_OPT_SIZE hard enough to
# reorder even at a hundredth of the Tm weight (see `design`, which derives
# that optimum from the product window whenever these tags are sent, because
# nothing else in this engine sets one).
#
# Deliberately absent: GC weights. `PRIMER_WT_GC_PERCENT_LT` and `_GT` are
# real tags, but Primer3 raises a hard error unless `PRIMER_OPT_GC_PERCENT` is
# sent alongside them, and introducing an optimal-GC setting would change what
# counts as a good primer in every search, weighted or not -- a new behaviour,
# not a bias. A purpose that genuinely needs one must add it consciously.
#
# Purposes absent from the dict keep Primer3's own balanced defaults. A
# downstream label such as `cloning` must not manufacture universal PCR hard
# constraints; assay/profile chemistry owns those. `genotyping-band` wants its
# alleles separated by product size, which no weight on a single pair can buy.
# An unknown purpose id gets no weights either.
PURPOSE_WEIGHTS: dict[str, dict[str, float]] = {
    # A read runs a long programme and anneals a few degrees under its coolest
    # primer, so a candidate below the ideal loses nothing there -- while a hot
    # primer keeps binding through mismatches at that temperature. Charging the
    # upside extra steers candidates off the ceiling of the window. The size
    # weights price both directions from the middle of the window: a read
    # covers roughly 700 to 900 reliable bases and the first few dozen are
    # poor, so the products worth sequencing end to end are the ones near the
    # read-window sweet spot.
    "sanger": {
        "PRIMER_WT_TM_GT": 0.25,
        "PRIMER_PAIR_WT_PRODUCT_SIZE_GT": 0.05,
        "PRIMER_PAIR_WT_PRODUCT_SIZE_LT": 0.05,
    },
    # Screens run many samples at one conservative temperature on whatever the
    # sample brings with it. The same asymmetry bites harder where the template
    # is dirtiest, so the mispriming end of the window costs more. Size is
    # priced gently, and symmetrically: a band only has to be separable by eye,
    # so the search leans away from the window's edges without pretending there
    # is one ideal band -- a screen tolerates wider than a read does.
    "screen": {
        "PRIMER_WT_TM_GT": 0.5,
        "PRIMER_PAIR_WT_PRODUCT_SIZE_GT": 0.02,
        "PRIMER_PAIR_WT_PRODUCT_SIZE_LT": 0.02,
    },
}

# Onodera & Melcher measured the distribution of the 64 possible terminal
# triplets in 2,137 successful PCR primers and recommended a score rather than
# a universal 3'-end rule.  Keep the published frequencies here, in the
# pipeline that ranks ordinary endpoint-PCR pairs, so the provenance of the
# prior cannot drift into an undocumented magic table.  This is deliberately
# not a hard filter: the study is an observational virus-primer corpus, not a
# universal enzyme/target validation panel.
THREE_PRIME_TRIPLET_FREQUENCIES: dict[str, float] = {
    "AAA": 1.45,
    "AAC": 1.87,
    "AAG": 1.54,
    "AAT": 1.22,
    "ACA": 1.45,
    "ACC": 2.76,
    "ACG": 1.31,
    "ACT": 1.50,
    "AGA": 1.12,
    "AGC": 2.57,
    "AGG": 3.28,
    "AGT": 1.64,
    "ATA": 0.94,
    "ATC": 1.87,
    "ATG": 1.68,
    "ATT": 0.75,
    "CAA": 1.26,
    "CAC": 2.39,
    "CAG": 2.71,
    "CAT": 1.82,
    "CCA": 1.40,
    "CCC": 1.54,
    "CCG": 1.40,
    "CCT": 1.03,
    "CGA": 0.66,
    "CGC": 1.12,
    "CGG": 1.26,
    "CGT": 0.75,
    "CTA": 1.03,
    "CTC": 2.11,
    "CTG": 2.85,
    "CTT": 1.12,
    "GAA": 1.22,
    "GAC": 1.59,
    "GAG": 1.78,
    "GAT": 1.59,
    "GCA": 1.50,
    "GCC": 1.50,
    "GCG": 1.08,
    "GCT": 1.22,
    "GGA": 1.54,
    "GGC": 1.64,
    "GGG": 0.84,
    "GGT": 1.22,
    "GTA": 1.36,
    "GTC": 2.06,
    "GTG": 2.48,
    "GTT": 1.03,
    "TAA": 0.61,
    "TAC": 1.40,
    "TAG": 1.50,
    "TAT": 0.94,
    "TCA": 1.31,
    "TCC": 2.76,
    "TCG": 1.08,
    "TCT": 1.17,
    "TGA": 1.31,
    "TGC": 2.34,
    "TGG": 2.95,
    "TGT": 1.78,
    "TTA": 0.42,
    "TTC": 2.48,
    "TTG": 1.92,
    "TTT": 0.98,
}
THREE_PRIME_TRIPLET_MIN = min(THREE_PRIME_TRIPLET_FREQUENCIES.values())
THREE_PRIME_TRIPLET_MAX = max(THREE_PRIME_TRIPLET_FREQUENCIES.values())
# Keep this below the measured cross-dimer and off-target terms: the triplet
# prior breaks ties among otherwise admissible pairs; it never outranks
# specificity or a pair-dimer problem.
THREE_PRIME_TRIPLET_CAP = 0.5


def _score_three_prime_triplets(pair: CandidatePair) -> tuple[float, str]:
    """Apply the published 3'-triplet distribution as a soft tie-break.

    The pair score is based on the geometric mean of the two terminal-triplet
    frequencies.  Log scaling prevents the most frequent triplet from being
    treated as eight times biologically better than the least frequent one,
    while retaining the ordering measured by the paper.  Every possible A/C/G/T
    triplet is in the table, so an ordinary candidate cannot silently become
    unscored.
    """
    triplets = (pair.left.sequence[-3:].upper(), pair.right.sequence[-3:].upper())
    frequencies = tuple(THREE_PRIME_TRIPLET_FREQUENCIES.get(triplet) for triplet in triplets)
    if any(frequency is None for frequency in frequencies):
        return 0.0, "Not assessed: one primer has fewer than three unambiguous terminal bases."

    geometric_mean = math.sqrt(frequencies[0] * frequencies[1])
    log_range = math.log(THREE_PRIME_TRIPLET_MAX / THREE_PRIME_TRIPLET_MIN)
    preference = _clamp01(math.log(geometric_mean / THREE_PRIME_TRIPLET_MIN) / log_range)
    penalty = round((1.0 - preference) * THREE_PRIME_TRIPLET_CAP, 3)
    return (
        penalty,
        f"3' triplets {triplets[0]} ({frequencies[0]:.2f}%) and "
        f"{triplets[1]} ({frequencies[1]:.2f}%); empirical prior is "
        f"{geometric_mean:.2f}% geometric mean. This is a soft ranking signal, "
        "not a rejection rule.",
    )


# RPA primers are recruited by a recombinase, not by PCR annealing. Primer3
# still applies its ordinary Tm ranking unless these ranking weights are
# explicitly neutralised. The broad Tm bounds remain a finite compatibility
# guard, while these zeros prevent the artificial 75 °C optimum from becoming
# a hidden biological claim. The final pipeline quality score also omits its
# Tm-centredness component for RPA.
ISOTHERMAL_PRIMER3_WEIGHTS = {
    "PRIMER_WT_TM_LT": 0.0,
    "PRIMER_WT_TM_GT": 0.0,
    "PRIMER_PAIR_WT_DIFF_TM": 0.0,
}


@dataclass
class Component:
    """One term of a candidate's score, and why it is there."""

    name: str
    value: float
    detail: str


def _accessibility_windows(
    pairs: list[CandidatePair], around: int | None = None
) -> dict[str, tuple[int, int]]:
    """The template stretches each primer would have to find open.

    `around` is the circle's length, when the fold is being run against the
    sequence with its own head repeated at its end. A pair that spans the join
    had its right primer folded back onto the real sequence, and here that has
    to be undone — a site sitting at base 157 of the circle is at 2843 of the
    string being folded, and asking about 157 would be asking about the wrong
    end of the molecule with none of the sequence that actually precedes it.
    """
    windows: dict[str, tuple[int, int]] = {}
    for index, pair in enumerate(pairs):
        windows[f"{index}:left"] = (pair.left_at.start, pair.left_at.length)
        # Primer3 gives a right primer by its 3' end, reading right to left, so
        # the stretch it occupies starts length-1 bases earlier.
        right = pair.right_at.start
        if pair.crosses_the_join and around is not None:
            right += around
        windows[f"{index}:right"] = (right - pair.right_at.length + 1, pair.right_at.length)
    return windows


def _spans_exon_junction(pair: CandidatePair, junctions: tuple[int, ...]) -> bool:
    """Whether either primer crosses one supplied transcript boundary."""
    if not junctions:
        return True
    left_end = pair.left_at.start + pair.left_at.length
    right_start = pair.right_at.start - pair.right_at.length + 1
    right_end = pair.right_at.start + 1
    return any(
        pair.left_at.start < junction < left_end or right_start < junction < right_end
        for junction in junctions
    )


def _score_off_targets(
    products: list[spec.OffTarget],
    intended_dg: float,
) -> tuple[float, str, int]:
    """A penalty for unwanted products, and a sentence about them.

    The two thresholds are fractions of how hard the primers hold their own
    intended site, not fixed free energies. Fixed ones did not work, and it was
    measured rather than suspected: at -10 kcal/mol, 100 per cent of perfect
    matches, 99 per cent of one-mismatch sites and 96 per cent of two-mismatch
    sites were all called serious, so a three-way split was doing the work of
    "everything is serious". A free energy also scales with primer length and
    GC, so one number cannot mean the same thing for a 35-mer at 68 degrees and
    an 18-mer at 57.

    Against the intended duplex it separates properly: a site that binds nearly
    as well as the real one will compete with it, and one at half the strength
    will not.
    """
    if intended_dg >= 0:
        # Nothing to compare against. Better to say so than to divide by it.
        return (
            0.0,
            "The intended duplex could not be measured, so nothing was scored against it.",
            0,
        )

    serious = [p for p in products if p.worst_dg <= OFF_TARGET_SERIOUS * intended_dg]
    watch = [
        p
        for p in products
        if OFF_TARGET_SERIOUS * intended_dg < p.worst_dg <= OFF_TARGET_WATCH * intended_dg
    ]
    penalty = 1.0 * len(serious) + 0.4 * len(watch)

    if not products:
        detail = "No unwanted product predicted in the background checked."
    elif serious:
        worst = serious[0]
        detail = (
            f"{len(serious)} unwanted product(s) with both primers binding "
            f"firmly — the worst is {worst.size} bp on {worst.contig} at "
            f"{worst.worst_dg} kcal/mol."
        )
    else:
        detail = (
            f"{len(watch)} unwanted product(s) whose primers bind between "
            f"{int(OFF_TARGET_WATCH * 100)} and {int(OFF_TARGET_SERIOUS * 100)} per "
            "cent as firmly as they bind their own site — worth knowing about, "
            "unlikely to compete."
        )

    return round(min(penalty, PENALTY_CAP), 3), detail, len(serious)


def _template_window(sequence: str, start: int, length: int, *, circular: bool) -> str:
    """Return one primer-binding window in the template's orientation.

    Primer3 reports the right primer by its 3-prime coordinate, so callers
    convert that coordinate to a window start before using this helper.  The
    circular branch is needed for a pair that crosses the arbitrary origin of
    a plasmid; slicing the linear spelling there would compare a primer with a
    truncated or unrelated sequence.
    """
    if start < 0 or length < 1 or not sequence:
        return ""
    if not circular:
        return sequence[start : start + length]
    size = len(sequence)
    return "".join(sequence[(start + offset) % size] for offset in range(length))


def _intended_binding_dg(
    pair: CandidatePair,
    template: str,
    *,
    circular: bool,
    conditions: dict[str, float],
    temperature_c: float = spec.DEFAULT_TEMPERATURE_C,
) -> float:
    """Measure each primer against the template window it was designed on.

    Using primer-versus-reverse-complement(primer) as the baseline is only a
    self-duplex measurement.  It can differ from the actual primer-template
    duplex when the target contains a mismatch, an ambiguity or a circular
    join.  Off-target competition must be normalised against the two binding
    sites that this candidate actually uses.
    """
    left_window = _template_window(
        template,
        pair.left_at.start,
        pair.left_at.length,
        circular=circular,
    )
    right_three_prime = pair.right_at.start
    if circular and pair.crosses_the_join:
        # `_fold_onto_the_circle` folds this coordinate back for display.  Put
        # it back after the real origin so the right-hand window is the same
        # one Primer3 searched across the repeated head.
        right_three_prime += len(template)
    right_window = _template_window(
        template,
        right_three_prime - pair.right_at.length + 1,
        pair.right_at.length,
        circular=circular,
    )
    if len(left_window) != pair.left_at.length or len(right_window) != pair.right_at.length:
        raise ValueError(
            "a designed pair does not have complete primer-binding windows in the template"
        )
    left_dg = pair_dimer(
        pair.left.sequence,
        reverse_complement(left_window),
        **conditions,
        temp_c=temperature_c,
    ).dg
    right_dg = pair_dimer(
        pair.right.sequence,
        right_window,
        **conditions,
        temp_c=temperature_c,
    ).dg
    # A product is limited by the weaker of its two primer-template duplexes.
    # In kcal/mol that is the less-negative (larger) value, just as
    # `OffTarget.worst_dg` uses max(forward, reverse). Using the stronger
    # primer as the baseline would make an asymmetric intended pair appear
    # safer than an off-target that competes with its weaker side.
    return max(left_dg, right_dg)


def _score_accessibility(
    openings: dict[str, access.Opening], index: int, best_log: float | None
) -> tuple[float, str]:
    """A small penalty for a binding site the template keeps folded shut."""
    left = openings.get(f"{index}:left")
    right = openings.get(f"{index}:right")
    if left is None or right is None or best_log is None:
        return 0.0, "Not computed."

    # The pair is only as good as its more buried primer.
    worst = min(left.unpaired, right.unpaired)
    if worst <= 0:
        return ACCESSIBILITY_CAP, "One primer's site is predicted to be fully paired."

    orders = best_log - math.log10(worst)
    penalty = min(ACCESSIBILITY_WEIGHT * orders, ACCESSIBILITY_CAP)
    if orders < ACCESSIBILITY_DETAIL_LOG_ORDERS:
        detail = "Both binding sites are about as open as the best candidate's."
    else:
        detail = (
            f"The more buried of the two sites is {orders:.1f} orders of magnitude "
            "less likely to be unpaired than the best candidate's."
        )
    return round(max(penalty, 0.0), 3), detail


def _score_cross_dimer(pair: CandidatePair) -> tuple[float, str]:
    """How hard this pair's two primers hold each other.

    The search already refuses a pair whose primer-dimer is still together at
    annealing temperature -- that ceiling follows the window, in
    `Constraints.to_primer3`. This is what is left afterwards: among pairs that
    all passed, some bind each other much harder than others, and nothing was
    preferring the ones that do not. A gate answers "would this fail"; a score
    answers "which of these is best", and the two are different questions.

    Measured over 75 candidates on five unrelated templates: the median pair
    binds at -3.8 kcal/mol, the tenth percentile at -5.7, the worst at -9.3.
    Six of the seventy-five sat below -6, which is where the order sheet
    already draws its line -- so that constant is the threshold here too rather
    than a second number that could drift from it.

    The weight puts the worst candidate seen at about half a point, which is
    the whole spread of a candidate field. That is deliberate and is where it
    differs from the variant tie-break: a pair that spends its primers on each
    other really is worse, rather than merely less tidy.
    """
    dg = pair.cross_dimer_dg
    if dg >= CROSS_PAIR_DIMER_WATCH:
        return (
            0.0,
            f"The two primers bind each other at {dg:.1f} kcal/mol, above the "
            f"{CROSS_PAIR_DIMER_WATCH:.0f} where it starts being worth mentioning.",
        )

    penalty = min(CROSS_DIMER_WEIGHT * (CROSS_PAIR_DIMER_WATCH - dg), CROSS_DIMER_CAP)
    return (
        round(penalty, 3),
        f"The two primers bind each other at {dg:.1f} kcal/mol. Cool enough to "
        "fall apart before they anneal, or the search would have refused the "
        "pair — but every copy of that duplex is a copy not priming your "
        "template.",
    )


#: How wide a stretch of the product the uniformity check reads at a time. The
#: same window `amplicon.py` reports composition at, so the two numbers on a
#: result describe the product at one scale rather than two.
UNIFORMITY_WINDOW = 50

#: Where a sliding window stops being ordinary composition and starts being
#: worth pointing at. Below the floor a stretch is mostly AT: it melts easily,
#: and long weakly-anchored stretches are where a product slips and deletes.
#: Above the ceiling it is mostly GC, which is where secondary structure forms
#: and the polymerase stalls -- the thresholds bracket the ordinary 40–60 band
#: a primer window already works inside.
UNIFORMITY_LOW_GC = 15.0
UNIFORMITY_HIGH_GC = 85.0


def _uniformity(amplicon: str) -> dict[str, Any]:
    """The GC content of the product, read in sliding windows.

    Purely a report. Nothing is rejected for an uneven product: the sequence
    between the primers is usually the target you have, and what changes for a
    difficult one is what goes in the tube. What this adds to the amplicon
    profile is *where* the composition sits along the product, because a low-GC
    window may slip and a high-GC window may form structures, and both are
    local facts that an overall percentage hides.
    """
    sequence = amplicon.upper()
    length = len(sequence)
    window = min(UNIFORMITY_WINDOW, length)

    # One rolling count across every start position; slicing fifty fresh bases
    # per step is the quadratic version of this loop.
    counted = sum(1 for base in sequence[:window] if base in "GC")
    fewest, most = counted, counted
    low_at, high_at = 0, 0
    for index in range(1, length - window + 1):
        if sequence[index - 1] in "GC":
            counted -= 1
        if sequence[index + window - 1] in "GC":
            counted += 1
        if counted < fewest:
            fewest, low_at = counted, index
        elif counted > most:
            most, high_at = counted, index

    min_gc = round(100.0 * fewest / window, 1)
    max_gc = round(100.0 * most / window, 1)

    notes = []
    if min_gc < UNIFORMITY_LOW_GC:
        notes.append(
            f"a {window}-base window starting at position {low_at + 1} of the "
            f"product holds only {min_gc:.0f}% GC — a low-GC window may slip"
        )
    if max_gc > UNIFORMITY_HIGH_GC:
        notes.append(
            f"a {window}-base window starting at position {high_at + 1} of the "
            f"product holds {max_gc:.0f}% GC — a high-GC window may form structures"
        )

    return {
        "window_bp": window,
        "min_window_gc": min_gc,
        "max_window_gc": max_gc,
        "note": " ".join(notes),
    }


# ── The composite quality score ──────────────────────────────────────────────
#
# `quality.score` folds four normalised, decision-supported components into one
# number from 0 to 100, higher meaning better. Template accessibility is kept
# outside this composite as raw diagnostic evidence because no universal
# calibration to PCR outcome is claimed.
#
#     score = round(100 · Σ(wᵢ·cᵢ) / Σ(wᵢ))   over the components computed
#
#   specificity       c = 1 − off_target_penalty / PENALTY_CAP      w = 3
#                     the existing off-target penalty, normalised against its
#                     own cap, so no unwanted product → 1 and a capped field of
#                     them → 0. Omitted when nothing was scanned.
#   dimer margin      c = clamp01(1 − ΔG_cross / CROSS_PAIR_DIMER_WATCH)   w = 2
#                     the pair's cross-dimer free energy against the −6 watch
#                     line: at the line → 0, no dimer → 0 kcal/mol → 1.
#   3' end stability  c = clamp01(1 − max|ΔG_3'| / 9)               w = 1
#                     each primer's terminal five bases are measured in
#                     `thermo.analyse`; 9 kcal/mol is the stricter
#                     Primer3Plus starting scale, not the base Primer3
#                     default (100) and not a universal hard gate.
#   Tm centeredness   c = clamp01(1 − max|tm − mid| / half-window)  w = 1
#                     how far either primer sits from the middle of the
#                     melting window, worst primer counting.
#
# The weights are heuristic. They are recorded here rather than tuned against
# wet-lab outcomes, and they say specificity dominates because a brilliant
# primer that amplifies the wrong locus is not a brilliant primer.
#
# This is reported beside the existing penalty sum (`score`), never instead of
# it, and takes no part in the sort: the ranking keeps its own account.
QUALITY_WEIGHTS = {
    "specificity": 3.0,
    "dimer_margin": 2.0,
    "end_stability": 1.0,
    "tm_centeredness": 1.0,
}

#: How strong a 3' anchor counts as fully spent, in kcal/mol. The magnitude of
#: Primer3Plus uses ~9 as a stricter starting scale; the base Primer3 default
#: is 100 (effectively no practical ceiling). A pair whose worse end reaches
#: this comparative scale scores zero here, but this is not a universal
#: experimental pass/fail threshold.
END_STABILITY_SCALE = 9.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _validation_plan(assay_id: str, *, from_rna: bool = False) -> dict[str, Any] | None:
    """State what sequence-only design cannot establish for an assay.

    The structured contract lives separately so the same evidence boundary can
    be rendered by the web client and consumed by exported reports without
    copying a second, inevitably stale list into this pipeline. RNA-derived
    requests promote the applicable RNA/RT controls to required evidence.
    """
    return validation_plan.for_assay(assay_id, from_rna=from_rna)


def _quality_score(
    pair: CandidatePair,
    limits: Constraints,
    *,
    off_target_penalty: float | None,
    openings: tuple[Any, Any] | None,
    tm_centeredness_enabled: bool = True,
) -> dict[str, Any]:
    """One number from 0 to 100 saying how good a final pair looks overall.

    See the comment block above `QUALITY_WEIGHTS` for the formula and its
    weights. Components that were not computed are reported as `None` and drop
    out of both sums, so a run without folding is scored on four components
    rather than quietly credited with a perfect fifth.
    """
    parts: dict[str, float | None] = {}

    parts["specificity"] = (
        None if off_target_penalty is None else _clamp01(1 - off_target_penalty / PENALTY_CAP)
    )
    # ΔG_cross runs from about 0 (nothing forms) down through the −6 watch
    # line; dividing by that line maps the whole range onto 1 … 0.
    parts["dimer_margin"] = _clamp01(1 - pair.cross_dimer_dg / CROSS_PAIR_DIMER_WATCH)
    # Accessibility remains visible as raw diagnostic evidence on each pair,
    # but does not enter the composite score: no calibrated mapping from the
    # computed unpaired probability to PCR outcome is available for a universal
    # weighting. Keeping it out prevents optional ViennaRNA availability from
    # changing the apparent quality of an otherwise identical design.
    parts["accessibility"] = None
    worst_end = max(abs(pair.left.three_prime_dg), abs(pair.right.three_prime_dg))
    parts["end_stability"] = _clamp01(1 - worst_end / END_STABILITY_SCALE)
    if tm_centeredness_enabled:
        mid = (limits.tm_min + limits.tm_max) / 2.0
        half = (limits.tm_max - limits.tm_min) / 2.0
        drift = max(abs(pair.left.tm - mid), abs(pair.right.tm - mid))
        parts["tm_centeredness"] = _clamp01(1 - drift / half) if half > 0 else 1.0
    else:
        # RPA primers are loaded by recombinase rather than selected by a
        # thermocycler annealing window. The profile keeps a deliberately broad
        # Tm envelope so Primer3 can measure oligos, but rewarding its midpoint
        # would quietly reintroduce a PCR-specific design assumption.
        parts["tm_centeredness"] = None

    weighted = sum(QUALITY_WEIGHTS[name] * part for name, part in parts.items() if part is not None)
    total_weight = sum(QUALITY_WEIGHTS[name] for name, part in parts.items() if part is not None)
    score = round(100.0 * weighted / total_weight) if total_weight else 0
    return {"score": max(0, min(100, score)), "parts": parts}


def _without_the_intended_product(
    products: list[spec.OffTarget],
    pair: CandidatePair,
    contigs: list[spec.Contig],
    *,
    circular_length: int | None = None,
) -> list[spec.OffTarget]:
    """Drop the product we asked for, and only that one.

    Size and exact primer matches are not enough: a paralogue can have the
    same primer-binding ends and the same product length while carrying a
    different internal sequence. The old implementation removed whichever
    matching-size product happened to sort first, which could hide a real
    off-target and leave the intended product in the report. Compare the
    complete product sequence instead, in either strand orientation, and
    remove exactly one occurrence. This also handles a supplied background
    that contains the target, while preserving a second identical copy as a
    real duplicate.

    ``products`` are coordinates into the exact contig strings that were
    scanned. For a circular template a wrapping product is represented after
    one turn; ``circular_length`` lets the exact comparison read the product
    modulo the real molecule rather than slicing past the short repeated head.
    """
    sequences = {contig.name: contig.sequence.upper() for contig in contigs}
    intended = pair.amplicon.upper()
    reverse_intended = reverse_complement(intended)
    for index, product in enumerate(products):
        if product.size == pair.product_size and {product.forward.role, product.reverse.role} == {
            "left",
            "right",
        }:
            sequence = sequences.get(product.contig, "")
            if circular_length is None:
                observed = sequence[product.start : product.end + 1]
            else:
                circle = sequence[:circular_length]
                observed = "".join(
                    circle[(product.start + offset) % circular_length]
                    for offset in range(product.size)
                )
            if observed in {intended, reverse_intended}:
                return products[:index] + products[index + 1 :]
    return products


def _stage(
    key: str,
    title: str,
    *,
    kind: str,
    went_in: int | None,
    came_out: int | None,
    detail: str,
    unit: str = "candidates",
    rejections: list[dict[str, Any]] | None = None,
    ran: bool = True,
) -> dict[str, Any]:
    """One step of the funnel, in the shape the interface reads.

    `kind` is the honest part. A **filter** removes things, so the gap between
    what went in and what came out is what it discarded. A **scorer** removes
    nothing; it marks some of what passes through, and reporting that the same
    way — "3 in, 0 out" — reads as though everything was thrown away when in
    fact nothing was.

    A stage that did not run says so rather than reporting zero, because zero
    and "not asked" look identical in a number and mean opposite things.
    """
    gap = went_in - came_out if went_in is not None and came_out is not None else None
    return {
        "key": key,
        "title": title,
        "kind": kind,
        "ran": ran,
        "unit": unit,
        "went_in": went_in,
        "came_out": came_out,
        # Only a filter discards. For a scorer this is how many it marked.
        "dropped": gap if kind == "filter" else None,
        "flagged": gap if kind == "scorer" else None,
        "detail": detail,
        "rejections": rejections or [],
    }


def _fold_onto_the_circle(
    result: DesignResult, around: int, how_many: int, *, allow_crossing: bool = True
) -> DesignResult:
    """Put a search over a repeated head back onto the circle it came from.

    The search ran against the sequence with its own beginning repeated at its
    end, so that a product could span the join. Three things follow from that
    and all three are handled here.

    A pair whose left primer *starts* at or past the real end is the same pair
    as one already found near the origin, found a second time in the copy. It
    is dropped rather than reported, because two identical designs offered as
    alternatives is worse than one.

    A pair whose right-primer 3-prime coordinate is in the repeated head is
    the one the repeat exists for. Its coordinates are folded onto the real sequence, where
    the right primer's position is *lower* than the left's — which is true of
    the molecule and looks like a bug to anything that assumes otherwise, so it
    is marked.

    When the requested product ceiling is longer than the molecule, the
    repeated head remains available to keep the search representation stable,
    but origin-crossing candidates are not reported: the requested window is
    not representable by one complete turn of that molecule.
    """
    kept: list[CandidatePair] = []
    for pair in result.pairs:
        if pair.left_at.start >= around:
            continue

        # A repeated head is search scaffolding, not a second traversal of the
        # molecule. A product longer than one circle is a multi-turn artifact,
        # not the single amplicon this assay can report.
        if pair.product_size > around:
            continue

        if pair.right_at.start < around:
            kept.append(pair)
            continue

        if not allow_crossing:
            continue

        kept.append(
            replace(
                pair,
                right_at=replace(pair.right_at, start=pair.right_at.start % around),
                crosses_the_join=True,
            )
        )

    return replace(result, pairs=kept[:how_many])


def _pair_at_effective_temperature(
    pair: CandidatePair, reaction: Reaction, temperature_c: float
) -> CandidatePair:
    """Attach the pair-dimer value measured at the assay's effective hold.

    Primer3's pair gate remains useful as a conservative search limit, but the
    post-search score must answer a different question: how much of this pair
    is tied up at the thermal step where it will actually compete. The
    thermodynamic alignment has a temperature-dependent free energy; carrying
    the low-level default into the report makes a warm PCR look much more
    dimer-prone than the assay it describes. Keep the candidate's positions,
    Tm and Primer3 penalty unchanged, and replace only the value being
    re-evaluated.
    """
    dimer = pair_dimer(
        pair.left.sequence,
        pair.right.sequence,
        **reaction.as_conditions(),
        temp_c=temperature_c,
    )
    return replace(pair, cross_dimer_dg=dimer.dg)


def _resolved_cycling(preset: Polymerase, overrides: dict[str, Any] | None = None) -> Cycling:
    """Resolve and validate the thermal programme before any search runs."""
    plan = preset.cycling
    if overrides:
        strange = sorted(set(overrides) - set(Cycling.__dataclass_fields__))
        if strange:
            raise ValueError(
                f"the assay changes {', '.join(strange)} in the thermal programme, "
                "which is not something this worker programmes"
            )
        plan = replace(plan, **overrides)
    plan.validate()
    return plan


def _specificity_temperature(
    pair: CandidatePair,
    preset: Polymerase,
    overrides: dict[str, Any] | None = None,
    *,
    assay_id: str = "",
) -> float:
    """Temperature used by the thermodynamic *model*, never an inferred bench Ta.

    PCRStudio must not turn primer Tm into a hidden protocol. When the
    selected profile declares an isothermal/two-step calculation context, that
    context can be used for temperature-dependent diagnostics.  Otherwise the
    fixed Primer3-compatible 37 °C reference is used and reported as a model
    reference. Candidate-specific primer-Tm offsets are not part of the current
    execution contract.
    """
    plan = _resolved_cycling(preset, overrides)
    if plan.isothermal_c is not None:
        return plan.isothermal_c
    if plan.two_step:
        return plan.anneal_extend_c if plan.anneal_extend_c is not None else plan.extend_c
    return spec.DEFAULT_TEMPERATURE_C


def _accessibility_temperature(
    pair: CandidatePair,
    preset: Polymerase,
    overrides: dict[str, Any] | None = None,
    *,
    assay_id: str = "",
) -> float:
    """Temperature for OPTIONAL accessibility diagnostics.

    This follows the same explicit model-reference rule as
    specificity; it is not described as the temperature at which a generic PCR
    will actually run. Named protocol records remain the sole bench authority.
    """
    return _specificity_temperature(pair, preset, overrides, assay_id=assay_id)


def _accessibility_profile(
    template: str,
    pairs: list[CandidatePair],
    *,
    around: int | None,
    preset: Polymerase,
    overrides: dict[str, Any] | None,
    assay_id: str = "",
) -> access.Accessibility:
    """Fold candidate-site windows at the declared thermodynamic model context.

    PCRStudio does not infer a candidate-specific PCR annealing temperature
    from primer Tm. Candidates therefore share the explicit profile/model
    reference temperature unless a named assay context supplies one.
    """
    windows = _accessibility_windows(pairs, around)
    by_temperature: dict[float, dict[str, tuple[int, int]]] = {}
    for index, pair in enumerate(pairs):
        temperature = _accessibility_temperature(pair, preset, overrides, assay_id=assay_id)
        by_temperature.setdefault(temperature, {}).update(
            {
                f"{index}:left": windows[f"{index}:left"],
                f"{index}:right": windows[f"{index}:right"],
            }
        )

    results = [
        (temperature, access.profile(template, grouped, celsius=temperature))
        for temperature, grouped in by_temperature.items()
    ]
    if len(results) == 1:
        temperature, result = results[0]
        if not result.temperatures_c:
            result.temperatures_c = (temperature,)
        return result

    successful = [result for _, result in results if result.checked]
    openings = {name: opening for result in successful for name, opening in result.openings.items()}
    models = sorted({result.model for result in successful if result.model})
    notes = [
        f"{temperature:g} °C: {result.note}"
        for temperature, result in results
        if not result.checked and result.note
    ]
    all_checked = bool(results) and all(result.checked for _, result in results)
    return access.Accessibility(
        checked=all_checked,
        model=" / ".join(models),
        celsius=None,
        temperatures_c=tuple(sorted(by_temperature)),
        openings=openings,
        note=(
            "All candidate temperatures were folded."
            if all_checked
            else "Some candidate temperatures were not folded: " + "; ".join(notes)
        ),
    )


def _interactions(
    pairs: list[tuple[CandidatePair, float]], name: str, reaction: Reaction
) -> dict[str, Any]:
    """Every oligo in this result against every other one.

    A pair is checked against itself during the search. This checks the whole
    order: somebody who buys all five pairs has ten oligos that will share a
    freezer box, and two of them from different pairs can be put in one tube by
    somebody who was not thinking about it. Cheap to compute, and the sort of
    thing nobody finds out until a reaction misbehaves.
    """
    name = label(name)
    oligos: list[tuple[str, str, float]] = []
    for index, (pair, temperature_c) in enumerate(pairs, start=1):
        oligos.append((f"{name}_{index}F", pair.left.sequence, temperature_c))
        oligos.append((f"{name}_{index}R", pair.right.sequence, temperature_c))

    worst: list[dict[str, Any]] = []
    for i, (first_name, first, first_temperature) in enumerate(oligos):
        for second_name, second, second_temperature in oligos[i + 1 :]:
            # There is no single annealing temperature when an order contains
            # designs from different candidate pairs. The lower of the two
            # effective assay temperatures is the conservative shared-tube
            # screen: lower temperature makes a competing duplex more stable.
            temperature_c = min(first_temperature, second_temperature)
            structure = pair_dimer(
                first,
                second,
                **reaction.as_conditions(),
                temp_c=temperature_c,
            )
            if structure.dg <= CROSS_PAIR_DIMER_WATCH:
                worst.append(
                    {
                        "a": first_name,
                        "b": second_name,
                        "dg": structure.dg,
                        "tm": structure.tm,
                        "temperature_c": temperature_c,
                        # Two oligos of the same pair are meant to be together.
                        "same_pair": first_name[:-1] == second_name[:-1],
                    }
                )

    worst.sort(key=lambda entry: entry["dg"])
    return {
        "checked": len(oligos),
        "threshold": CROSS_PAIR_DIMER_WATCH,
        "temperature_policy": (
            "Each oligo pair is evaluated at the lower of the two candidate-specific "
            "effective assay temperatures; this is a conservative shared-tube screen."
        ),
        "found": len(worst),
        "worst": worst[:10],
        "note": (
            "Nothing in this order sticks to anything else hard enough to worry about."
            if not worst
            else (
                f"{len(worst)} pair(s) of oligos in this order bind each other at "
                f"{CROSS_PAIR_DIMER_WATCH} kcal/mol or below. Ones from different "
                "designs matter only if they end up in the same tube."
            )
        ),
    }


def _order_sheet(
    pairs: list[CandidatePair],
    name: str,
    *,
    tailed: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """What to actually buy, in the form an order form wants it.

    When tails were applied this is the tailed molecule, because that is what
    gets synthesised. The temperature stays the one the primer anneals at,
    with a note saying so -- the whole oligo melts several degrees higher and
    nobody should set a cycler from that number.
    """
    name = label(name)
    sheet: list[dict[str, Any]] = []
    applied = bool(tailed and tailed.get("applied"))

    for index, pair in enumerate(pairs, start=1):
        for role, oligo, side in (("F", pair.left, "forward"), ("R", pair.right, "reverse")):
            line: dict[str, Any] = {
                "name": f"{name}_{index}{role}",
                "sequence": oligo.sequence,
                "annealing_sequence": oligo.sequence,
                "tail_sequence": "",
                "kind": "primer",
                "length": oligo.length,
                "gc_percent": oligo.gc_percent,
                "tm": oligo.tm,
            }
            if applied:
                tail = tailed["forward"] if side == "forward" else tailed["reverse"]
                line["sequence"] = tail["sequence"] + oligo.sequence
                line["annealing_sequence"] = oligo.sequence
                line["tail_sequence"] = tail["sequence"]
                line["length"] = len(line["sequence"])
                first_observed = tail.get("first_observed_activity_flanking_bases")
                evidence_identity = (
                    tail.get("end_cleavage_evidence_identity") or "the recorded supplier entry"
                )
                recommendation_note = (
                    f" The close-to-end table for {evidence_identity} first reports non-zero "
                    f"activity at {first_observed} flanking base(s); that observation is not an "
                    f"efficiency recommendation. This end uses {len(tail['protective'])}."
                    if first_observed is not None and len(tail["protective"]) < first_observed
                    else ""
                )
                line["note"] = (
                    f"Carries a {tail['enzyme']} site ({tail['site']}) behind "
                    f"{len(tail['protective'])} protective bases. The temperature "
                    f"is what the {oligo.length}-base annealing part melts at, not "
                    f"the whole molecule.{recommendation_note}"
                )
            sheet.append(line)
    return sheet


def _backbone_screen(
    request: dict[str, Any],
    insert: str,
    limits: Constraints,
    conditions: dict[str, float],
    *,
    temperature_c: float | None = None,
) -> dict[str, Any] | None:
    """A primer that pairs with a vector primer you already own.

    `None` unless asked, like the cloning block, so the section is absent
    rather than empty when it does not apply.

    This does not replace the ordinary pair. Both are useful and they answer
    different questions: two primers inside the insert say whether the insert
    is there, and one primer in the vector says whether it went in the right
    way round. A colony screen often runs both, so both come back.

    The window comes from the vector primer rather than from the assay, which
    is the whole reason this is a design step and not a note. M13 forward
    (-47) melts near 69 and the 17-mer M13 reverse near 51 -- eighteen degrees
    apart, and the assay's own window of 57 to 63 contains neither.
    """
    asked = request.get("vector_primer")
    if asked is None:
        return None
    if not isinstance(asked, dict):
        raise ValueError("`vector_primer` must be an object")
    _reject_unknown_fields(asked, name="vector_primer", known=KNOWN_VECTOR_PRIMER_FIELDS)

    name = _request_optional_text(asked.get("name"), name="vector_primer.name") or ""
    sequence = _request_optional_text(asked.get("sequence"), name="vector_primer.sequence")
    reads_into = (
        _request_optional_text(asked.get("reads_into"), name="vector_primer.reads_into") or "start"
    )
    vector = _request_optional_text(asked.get("vector"), name="vector_primer.vector") or ""
    how_many = _request_integer(
        asked.get("how_many"),
        name="vector_primer.how_many",
        default=3,
        minimum=1,
        maximum=MAX_PAIRS,
    )

    partner = backbone.resolve_partner(
        name,
        sequence,
        **conditions,
    )
    return backbone.design(
        insert,
        partner,
        reads_into=reads_into,
        limits=limits,
        reaction=conditions,
        how_many=how_many,
        # Optional, and what it buys is the product size. Without it the screen
        # can only report the half it controls, which is not the number
        # somebody holds a gel up against.
        vector=vector,
        temperature_c=temperature_c,
    )


def _cloning_tails(
    request: dict[str, Any],
    template: str,
    ranked: list[dict[str, Any]],
    conditions: dict[str, float],
) -> dict[str, Any] | None:
    """Restriction sites on the 5-prime ends, when the assay asks for them.

    `None` when nothing asked, which is every module except restriction
    cloning -- the block is absent from the result rather than present and
    empty, so a reader never has to decide whether an empty one means "no
    tails" or "tails that came out empty".

    The enzymes are never chosen for you. Which two are right depends on what
    is in the vector's cloning site, and this function has never seen the
    vector; picking a pair that is merely absent from the insert would produce
    primers that cannot be cloned into anything. So when none is named, the
    answer is the list of enzymes that *would* work on this insert, and the
    primers come back untailed.

    The site has to be absent from the whole template rather than from each
    amplicon. That is the conservative direction: absent from the template
    means absent from every product that could be cut out of it, and it gives
    one answer for the design instead of a different one per pair.
    """
    asked = request.get("tails")
    if asked is None:
        return None
    if not isinstance(asked, dict):
        raise ValueError("`tails` must be an object")
    _reject_unknown_fields(asked, name="tails", known=KNOWN_TAIL_FIELDS)

    tail_protocol = (
        _request_optional_text(asked.get("tail_protocol"), name="tails.tail_protocol") or ""
    )
    forward_named = (
        _request_optional_text(asked.get("forward_enzyme"), name="tails.forward_enzyme") or ""
    )
    reverse_named = (
        _request_optional_text(asked.get("reverse_enzyme"), name="tails.reverse_enzyme") or ""
    )
    if (forward_named or reverse_named) and tail_protocol != "neb-general-6bp":
        raise tails_mod.TailError(
            "Scientific-Strict restriction-tail generation requires the explicit "
            "`neb-general-6bp` end-cleavage authority. Other supplier/enzyme-specific "
            "tail branches remain typed boundaries rather than anonymous protective-base edits."
        )

    protective = _request_integer(
        asked.get("protective_bases"),
        name="tails.protective_bases",
        default=tails_mod.PROTECTIVE_BASES,
        minimum=0,
    )
    # The current named branch has one end-cleavage length authority. Per-end
    # numeric overrides were a development-era second authority and are no
    # longer accepted on input; per-end values in the result are derived from
    # this single reviewed value for audit readability.
    forward_protective = protective
    reverse_protective = protective
    if protective != tails_mod.PROTECTIVE_BASES:
        raise tails_mod.TailError(
            "The named `neb-general-6bp` branch uses six flanking bases outside each site. "
            "Scientific-Strict does not convert arbitrary numeric overrides into a supplier-validated "
            "end-cleavage protocol; use a separately named branch for another requirement."
        )

    forward_protective_sequence = (
        _request_optional_text(
            asked.get("forward_protective_sequence"),
            name="tails.forward_protective_sequence",
        )
        or ""
    )
    reverse_protective_sequence = (
        _request_optional_text(
            asked.get("reverse_protective_sequence"),
            name="tails.reverse_protective_sequence",
        )
        or ""
    )

    usable = [enzyme.name for enzyme in tails_mod.usable_enzymes(template)]
    forward = forward_named
    reverse = reverse_named

    if bool(forward) != bool(reverse):
        raise tails_mod.TailError(
            "Restriction cloning needs an enzyme for both primer ends, or none. "
            "A one-sided tail would not define the two junctions to be ordered."
        )

    if forward and reverse:
        if not forward_protective_sequence or not reverse_protective_sequence:
            raise tails_mod.TailError(
                "Scientific-Strict restriction cloning requires the exact six-base protective "
                "sequence for each primer end. NEB supplies the six-base length rule, not one "
                "universal filler sequence; PCRStudio will not invent those bases."
            )
        if (
            len(forward_protective_sequence) != tails_mod.PROTECTIVE_BASES
            or len(reverse_protective_sequence) != tails_mod.PROTECTIVE_BASES
        ):
            raise tails_mod.TailError(
                "tailProtocol=`neb-general-6bp` requires exactly six explicit protective bases "
                "on each end. Another length requires a separately named supplier/enzyme-specific branch."
            )

    if not forward or not reverse:
        return {
            "applied": False,
            "tail_protocol": tail_protocol or None,
            "usable_enzymes": usable,
            "protective_bases": protective,
            "forward_protective_bases": forward_protective,
            "reverse_protective_bases": reverse_protective,
            "note": (
                "No enzymes were named, so the primers are untailed. The list above is the "
                "PCRStudio built-in catalogue subset whose sites do not appear in this template; "
                "it is not an exhaustive supplier catalogue. Choose a pair your vector's cloning "
                "site and digest workflow can accept, or use a separately modelled enzyme branch."
            ),
        }

    same_enzyme = forward == reverse

    left_tail = tails_mod.build_tail(
        forward, template, protective_sequence=forward_protective_sequence
    )
    right_tail = tails_mod.build_tail(
        reverse, template, protective_sequence=reverse_protective_sequence
    )

    # The user-supplied protective sequence must not create additional digest
    # sites in the ordered tail. This is exact sequence geometry, not a
    # thermodynamic heuristic: each end should carry exactly its intended site
    # and, for a two-enzyme digest, no site for the enzyme assigned to the
    # opposite end.
    forward_enzyme = tails_mod.BY_NAME[forward]
    reverse_enzyme = tails_mod.BY_NAME[reverse]
    left_own = tails_mod.occurrences(left_tail.sequence, forward_enzyme)
    right_own = tails_mod.occurrences(right_tail.sequence, reverse_enzyme)
    if left_own != 1 or right_own != 1:
        raise tails_mod.TailError(
            "A protective sequence creates an additional occurrence of its intended "
            "restriction site in the ordered tail. Choose different protective bases "
            "so each primer end contains exactly one intended cleavage site."
        )
    if not same_enzyme:
        left_other = tails_mod.occurrences(left_tail.sequence, reverse_enzyme)
        right_other = tails_mod.occurrences(right_tail.sequence, forward_enzyme)
        if left_other or right_other:
            raise tails_mod.TailError(
                "A protective sequence creates the opposite enzyme's recognition site "
                "in an ordered tail. That would add an unintended cut in the two-enzyme "
                "digest; choose different protective bases."
            )

    for entry in ranked:
        left = tails_mod.attach(entry["left"]["sequence"], left_tail, **conditions)
        right = tails_mod.attach(entry["right"]["sequence"], right_tail, **conditions)
        entry["tailed"] = {
            "left": {
                "sequence": left.whole.sequence,
                "length": left.whole.length,
                "anneals_at": left.anneals.tm,
                "whole_tm": left.whole.tm,
                "hairpin_dg": left.whole.hairpin.dg,
                "self_dimer_dg": left.whole.self_dimer.dg,
                "tail": tails_mod.describe(left_tail),
            },
            "right": {
                "sequence": right.whole.sequence,
                "length": right.whole.length,
                "anneals_at": right.anneals.tm,
                "whole_tm": right.whole.tm,
                "hairpin_dg": right.whole.hairpin.dg,
                "self_dimer_dg": right.whole.self_dimer.dg,
                "tail": tails_mod.describe(right_tail),
            },
            "interaction": tails_mod.tails_interact(left, right, **conditions),
        }

    # Different enzyme names are not proof of directional cloning. For the
    # palindromic sites in the built-in catalogue, however, the second-strand
    # cut is fixed by symmetry and the insert-end geometry can be derived from
    # the recorded top-strand cut. That lets PCRStudio distinguish genuinely
    # incompatible insert ends from isocaudomer-like compatible ends without
    # pretending it has seen the vector. Directionality itself remains
    # unresolved for any two-enzyme branch until vector sites/order are known.
    forward_end = tails_mod.end_geometry(forward_enzyme)
    reverse_end = tails_mod.end_geometry(reverse_enzyme)
    insert_ends_compatible = tails_mod.end_compatibility(forward_enzyme, reverse_enzyme)
    if same_enzyme:
        strategy = "nondirectional-same-enzyme"
    elif insert_ends_compatible is True:
        strategy = "two-enzyme-compatible-ends-directionality-unverified"
    elif insert_ends_compatible is False:
        strategy = "two-enzyme-incompatible-insert-ends-vector-geometry-unverified"
    else:
        strategy = "two-enzyme-end-compatibility-unresolved"
    directional: bool | None = False if same_enzyme else None
    bench_controls = (
        [
            "Dephosphorylate the vector when appropriate for the cloning workflow to reduce vector self-ligation.",
            "Run a vector-only ligation/background control.",
            "Screen clone orientation by colony PCR, diagnostic digest or sequencing because insertion orientation is not encoded by identical ends.",
        ]
        if same_enzyme
        else [
            (
                "The two selected enzymes generate compatible insert-end families despite having different names; do not treat this pair as directional without the exact vector-end geometry and site order."
                if insert_ends_compatible is True
                else "The two insert-end families are sequence-incompatible, but directionality still depends on the exact vector sites and their order; verify the vector geometry before making that claim."
                if insert_ends_compatible is False
                else "Insert-end compatibility could not be resolved from the built-in cleavage record; verify both strand cuts and the exact vector-end geometry before making a directionality claim."
            ),
            "Confirm the two enzymes are compatible with the intended digest workflow and supplier conditions.",
            "Screen the final construct by colony PCR, diagnostic digest or sequencing regardless of the expected orientation control.",
        ]
    )
    digest_validation = {
        "methylation_sensitivity_status": "exact-enzyme-formulation-and-substrate-context-required",
        "star_activity_status": "reaction-condition-dependent-not-computed",
        "double_digest_compatibility_status": "exact-formulation/current-supplier-buffer-chart-required",
        "heat_inactivation_status": "exact-formulation/current-supplier-record-required",
        "ligation_junction_recleavage_status": "exact-insert-vector-junction-required",
        "enzyme_formulation_scope": "enzyme-name-alone-insufficient-for-current-HF/buffer/activity-claims",
        "required_records": [
            "exact purchased enzyme name/formulation and supplier revision",
            "substrate DNA source and relevant Dam/Dcm/CpG methylation context",
            "current supplier buffer/activity compatibility for the exact enzyme pair or sequential-digest decision",
            "digest buffer, temperature, duration, enzyme units, DNA mass and final glycerol fraction",
            "heat-inactivation or cleanup plan for the exact formulations when relevant",
            "exact vector sites/order and final insert-vector junction sequences",
        ],
        "note": (
            "Restriction-site sequence geometry alone cannot establish digestion success. Methylation can block or impair "
            "cleavage for particular enzyme/site/substrate combinations, and star activity depends on the actual digest "
            "conditions. Double-digest compatibility and heat inactivation are also formulation/buffer-specific rather than "
            "properties of a recognition sequence. Re-cleavage after ligation is a property of the exact reconstructed junction, "
            "not of the two insert tails in isolation."
        ),
    }

    return {
        "applied": True,
        "tail_protocol": tail_protocol,
        "strategy": strategy,
        "directional": directional,
        "usable_enzymes": usable,
        "protective_bases": protective,
        "forward_protective_bases": forward_protective,
        "reverse_protective_bases": reverse_protective,
        "protective_sequence_authority": "user-supplied; NEB general rule supplies length, not sequence identity",
        "forward": tails_mod.describe(left_tail),
        "reverse": tails_mod.describe(right_tail),
        "insert_end_geometry": {"forward": forward_end, "reverse": reverse_end},
        "insert_ends_compatible": insert_ends_compatible,
        "insert_end_compatibility_scope": "insert-end-sequence-geometry-only",
        "ligation_product_recleavage": "not-modeled",
        "directionality_evidence": "vector-sites-and-order-required",
        "digest_validation": digest_validation,
        "bench_controls": [
            *bench_controls,
            "Confirm methylation sensitivity for the exact purchased enzyme formulation against the actual DNA source; enzyme names alone are not enough to infer Dam/Dcm/CpG behavior.",
            "Use the supplier-recommended digest buffer/temperature/time and record enzyme units, DNA mass and final glycerol fraction; star activity is a reaction-condition risk, not a sequence-derived verdict.",
            "Verify double-digest compatibility (or use a sequential digest) and heat-inactivation/cleanup for the exact purchased enzyme formulations; recognition-site names alone do not establish either property.",
            "Determine whether the ligated junction is re-cleavable from the exact insert-plus-vector junction sequence before relying on post-ligation digestion behavior.",
        ],
        "note": (
            (
                f"Both ends use {forward}. This is a valid non-directional restriction-cloning branch, "
                "but the insert can ligate in either orientation and the vector can self-ligate; keep the "
                "dephosphorylation/background/orientation-screening controls above explicit. "
            )
            if same_enzyme
            else (
                "Two different recognition sites were requested. PCRStudio now reports the insert-end "
                "geometry when it is derivable from a palindromic recognition site, including whether the "
                "two insert-end families are compatible with one another; it still does not claim directionality "
                "from enzyme names or insert ends alone. Exact vector sites/order and digest compatibility must "
                "be verified before calling this a directional cloning branch. "
            )
        )
        + (
            "Neither site appears in this template, so the enzymes cut only at the ends. "
            "The six protective bases outside each site come from the explicitly named NEB "
            "general-rule branch. This is not an enzyme-specific optimum and must not be silently "
            "transferred to another supplier/formulation."
        ),
    }


def run(
    request: dict[str, Any], *, most: int = MAX_PAIRS, pool: int | None = None
) -> dict[str, Any]:
    """Design primers for one template and report everything that was checked.

    Args:
        most: The largest number of pairs this call may return. The default is
            what makes sense as an *answer*: past a few dozen, the designs stop
            being different from each other and a person cannot use them. A set
            search wants something else -- a pool to choose from, where a
            hundred is normal -- so it says so rather than inheriting a limit
            that was reasoned about a different question.
        pool: How wide to search before this pipeline's own scoring narrows the
            field, when that should not be capped at `most`. The default keeps
            three times what was asked for, which suits ranking one answer; a
            caller choosing between sets wants every candidate it asked for,
            and names its own ceiling here.

    Raises:
        IntakeError: the input is not a usable template.
        ValueError: a constraint, preset or reaction that cannot hold.
        BackgroundTooLarge: the background needs an indexed search.
    """
    if not isinstance(request, dict):
        raise ValueError("a flanking-pair request must be a JSON object")
    modified_oligos = modified_oligo_provenance(request.get("modified_oligos"))
    unknown = sorted(
        (
            repr(key)
            for key in request
            if not isinstance(key, str) or key not in KNOWN_REQUEST_FIELDS
        ),
        key=str,
    )
    if unknown:
        raise ValueError("unknown flanking-pair request field(s): " + ", ".join(unknown))

    # Validate nested tail schema before resolving chemistry or starting any
    # scientific search. Structural request errors should never be hidden by a
    # later context requirement (for example a missing cloning vector) or by a
    # native tool call. The full tail semantics are still resolved in
    # `_cloning_tails`; this is only the fail-fast shape boundary.
    raw_tails = request.get("tails")
    if raw_tails is not None:
        if not isinstance(raw_tails, dict):
            raise ValueError("`tails` must be an object")
        _reject_unknown_fields(raw_tails, name="tails", known=KNOWN_TAIL_FIELDS)

    # These are keyword-only because the public worker request cannot name
    # them, but multiplex enters through this function and supplies them from
    # another JSON boundary. Validate them here too: a float or zero would
    # otherwise become an accidental empty shortlist or a type error several
    # stages later.
    most = _request_integer(most, name="most", minimum=1)
    if pool is not None:
        pool = _request_integer(pool, name="pool", minimum=1)

    raw_assay = request.get("assay")
    if raw_assay is None:
        assay: dict[str, Any] = {}
    elif not isinstance(raw_assay, dict):
        raise ValueError("`assay` must be an object")
    else:
        assay = raw_assay

    unknown_assay = sorted(set(assay) - KNOWN_ASSAY_FIELDS)
    if unknown_assay:
        raise ValueError("unknown assay field(s): " + ", ".join(unknown_assay))

    raw_assay_defaults = assay.get("defaults")
    if raw_assay_defaults is None:
        assay_defaults: dict[str, Any] = {}
    elif not isinstance(raw_assay_defaults, dict):
        raise ValueError("`assay.defaults` must be an object")
    else:
        assay_defaults = raw_assay_defaults

    unknown_defaults = sorted(set(assay_defaults) - KNOWN_ASSAY_DEFAULT_FIELDS)
    if unknown_defaults:
        raise ValueError("unknown assay default field(s): " + ", ".join(unknown_defaults))

    assay_id = str(assay.get("id") or "")
    if assay_id:
        validate_required_context(request, assay_id)

    template = request.get("template")
    if not isinstance(template, str):
        raise ValueError("`template` must be text")
    name = _request_optional_text(request.get("name"), name="name") or ""

    target_start = request.get("target_start")
    target_length = request.get("target_length")
    if target_start is not None:
        target_start = _request_integer(target_start, name="target_start", minimum=0)
    if target_length is not None:
        target_length = _request_integer(target_length, name="target_length", minimum=1)
    if (target_start is None) != (target_length is None):
        raise ValueError("`target_start` and `target_length` must be supplied together")

    circular = request.get("circular")
    if circular is not None and not isinstance(circular, bool):
        raise ValueError("`circular` must be a boolean")
    requested_from_rna = request.get("from_rna")
    if requested_from_rna is not None and not isinstance(requested_from_rna, bool):
        raise ValueError("`from_rna` must be a boolean")

    # ── 1. Resolve ──────────────────────────────────────────────────────────
    lowercase_masking = request.get("lowercase_masking")
    if lowercase_masking is not None and not isinstance(lowercase_masking, bool):
        raise ValueError("`lowercase_masking` must be true or false")
    target: Target = resolve(template, name=name, lowercase_masking=lowercase_masking)
    if target.length > MAX_TEMPLATE_BASES:
        raise ValueError(
            f"The template is {target.length:,} bases. This flanking-pair path "
            f"takes up to {MAX_TEMPLATE_BASES:,}; provide a target region or "
            "use an indexed search for a larger sequence."
        )
    if any(note.kind == "multipleRecords" for note in target.notes):
        raise ValueError(
            "The template contains multiple FASTA records. Flanking-pair designs "
            "need exactly one target sequence; provide other records through the "
            "background or inclusivity field instead."
        )

    # User-facing coordinates are always expressed in the canonical molecule
    # frame. Circular search later appends a repeated head solely as Primer3
    # scaffolding; coordinates in that synthetic copy must never become valid
    # request coordinates. A circular target may cross the FASTA origin, but it
    # may not start in the repeated copy or span more than one complete turn.
    if target_start is not None and target_length is not None:
        if target_start >= target.length:
            raise ValueError(
                f"target_start {target_start} is outside the canonical template frame "
                f"0..{target.length - 1}; repeated circular-search scaffolding is not "
                "a second coordinate system."
            )
        if bool(circular):
            if target_length > target.length:
                raise ValueError(
                    f"target_length {target_length} exceeds the {target.length}-base circular "
                    "molecule. A target interval may cross the FASTA origin once, but it may "
                    "not require more than one traversal."
                )
        elif target_start + target_length > target.length:
            raise ValueError(
                f"the target at {target_start}..{target_start + target_length} falls outside "
                f"the {target.length}-base linear template"
            )

    # An RNA alphabet cannot be treated as ordinary DNA merely because intake
    # normalises U to T for the primer search. A DNA polymerase amplifies the
    # cDNA product; it does not make the RT step disappear. Auto-enabling RT
    # keeps the common low-effort path safe, while an explicit contradiction is
    # refused instead of generating a protocol that cannot use the supplied
    # molecule.
    if target.rna_input and requested_from_rna is False:
        raise ValueError(
            "The input contains RNA (U bases), but `from_rna` was set to false. "
            "RNA requires reverse transcription; provide DNA/cDNA or enable the "
            "RT-PCR option."
        )

    _validate_assay_rna(
        assay,
        target_has_rna=target.rna_input,
        requested_from_rna=bool(requested_from_rna),
    )
    # RT says what was in the tube; it cannot reveal how a transcript was
    # spliced. Junction coordinates are therefore an explicit annotation, and
    # a junction rule is only meaningful for a cDNA workflow.
    from_rna = rt.wanted(request) or target.rna_input
    exon_junctions = _exon_junctions(
        request.get("exon_junctions"), length=target.length, from_rna=from_rna
    )
    if exon_junctions and circular:
        raise ValueError("`exon_junctions` cannot be combined with a circular template")

    # ── 2. Conditions ───────────────────────────────────────────────────────
    # The assay's own enzyme, unless one was named. Long-range PCR is not
    # ordinary PCR with a bigger number in it -- it is a different enzyme, with
    # a different extension rate and, for some, a two-step programme.
    requested_polymerase = _request_optional_text(request.get("polymerase"), name="polymerase")
    assay_polymerase = _request_optional_text(
        assay_defaults.get("polymerase"), name="assay.defaults.polymerase"
    )
    expected_preset: Polymerase = polymerase(assay_polymerase)
    preset: Polymerase = polymerase(requested_polymerase or assay_polymerase)
    allowed_polymerases = assay_defaults.get("allowedPolymerases") or []
    if not isinstance(allowed_polymerases, list) or not all(
        isinstance(value, str) for value in allowed_polymerases
    ):
        raise ValueError("`assay.defaults.allowedPolymerases` must be a list of preset ids")
    enforce_polymerase_identity(
        preset.id,
        expected_preset.id,
        assay_id=str(assay.get("id") or ""),
        allowed=allowed_polymerases,
    )
    overrides = _number_map(request.get("conditions"), name="conditions")
    unknown = sorted(set(overrides) - set(DEFAULT_CONDITIONS))
    if unknown:
        raise ValueError(f"unknown reaction condition(s): {', '.join(unknown)}")
    enforce_reaction_overrides(
        overrides,
        preset.reaction.as_conditions(),
        context=f"assay `{assay.get('id') or 'unprofiled'}`",
    )
    reaction = Reaction(**{**preset.reaction.as_conditions(), **overrides})
    reaction.validate()

    # ── 3. Constraints ──────────────────────────────────────────────────────
    #
    # Three layers, in this order: the module's own defaults, then what the
    # product is for, then whatever was typed. Each is visible in the result,
    # so an override reads as a decision rather than as a mystery.
    assay_name = (
        _request_optional_text(assay.get("name"), name="assay.name")
        or _request_optional_text(assay.get("id"), name="assay.id")
        or "this assay"
    )
    _validate_assay_contract(assay, preset, assay_name, request)
    standard_pcr_named = request.get("standard_pcr_protocol")
    qpcr_named = request.get("qpcr_protocol")
    rpa_named = request.get("rpa_protocol")
    long_range_named = request.get("long_range_protocol")
    digital_named = request.get("digital_protocol")
    named_overlays = [
        value
        for value in (standard_pcr_named, qpcr_named, rpa_named, long_range_named, digital_named)
        if value not in (None, "not-selected")
    ]
    if len(named_overlays) > 1:
        raise ValueError("select only one named flanking-pair chemistry overlay")
    selected_standard_pcr_protocol = standard_pcr_protocol(
        standard_pcr_named,
        assay_id=str(assay.get("id", "")),
        multiplex_context=bool(request.get("multiplex_context", False)),
    )
    selected_qpcr_protocol = qpcr_protocol(
        qpcr_named, assay_id=str(assay.get("id", "")), from_rna=from_rna
    )
    selected_rpa_protocol = rpa_protocol(
        rpa_named, assay_id=str(assay.get("id", "")), from_rna=from_rna
    )
    selected_long_range_protocol = long_range_protocol(
        long_range_named, assay_id=str(assay.get("id", ""))
    )
    selected_digital_protocol = digital_protocol(
        digital_named, assay_id=str(assay.get("id", "")), from_rna=from_rna
    )
    selected_colony_context = colony_context(request, assay_id=str(assay.get("id", "")))
    selected_colony_protocol = (
        selected_colony_context.get("source_conditioned_protocol")
        if selected_colony_context is not None
        and selected_colony_context.get("protocol_id") != "custom-sop"
        else None
    )
    selected_protocol = (
        selected_standard_pcr_protocol
        or selected_qpcr_protocol
        or selected_rpa_protocol
        or selected_long_range_protocol
        or selected_digital_protocol
        or selected_colony_protocol
    )
    selected_digital_context = digital_context(request, assay_id=str(assay.get("id", "")))
    assay_id = str(assay.get("id", ""))
    flanking_numeric_context = _flanking_numeric_context(
        request.get("flanking_numeric_context"), assay_id=assay_id
    )
    flanking_numeric_recipe: dict[str, Any] | None = None
    rpa_panel_context: dict[str, Any] | None = None
    if selected_protocol is not None:
        protocol_id = str(selected_protocol.get("protocol_id") or "not-selected")
        scenario = dict(flanking_numeric_context or {})
        scenario["from_rna"] = from_rna
        if selected_colony_context is not None:
            scenario["preparation"] = selected_colony_context.get("preparation")
        overrides: dict[str, float] = {}
        if "primer_each_um" in scenario:
            overrides["primer_each_uM"] = float(scenario.pop("primer_each_um"))
        if "primer_each_nm" in scenario:
            overrides["primer_each_nM"] = float(scenario.pop("primer_each_nm"))
        if "gc_enhancer_percent" in scenario:
            overrides["high_gc_enhancer_percent"] = float(scenario.pop("gc_enhancer_percent"))
        if "rpa_multiplex" in scenario:
            scenario["multiplex"] = bool(scenario.pop("rpa_multiplex"))
        rpa_panel_context = resolve_rpa_multiplex(
            request.get("rpa_multiplex_panel"), enabled=bool(scenario.get("multiplex"))
        )
        if "rpa_temperature_c" in scenario:
            scenario["temperature_c"] = float(scenario.pop("rpa_temperature_c"))
        if "rpa_time_min" in scenario:
            scenario["time_min"] = float(scenario.pop("rpa_time_min"))
        if "rpa_bst_units_per_ul" in scenario:
            scenario["bst_units_per_uL"] = float(scenario.pop("rpa_bst_units_per_ul"))
        flanking_numeric_recipe = resolve_flanking_numeric_recipe(
            protocol_id, assay_id, scenario=scenario, overrides=overrides or None
        )
    # An assay that cannot serve a purpose says so before designing, rather
    # than returning something neither party wanted. A colony screen asked for
    # a three-kilobase cloning product is not a preference to be balanced.
    allowed_value = assay_defaults.get("purposes")
    if allowed_value is None:
        allowed_value = []
    if not isinstance(allowed_value, list) or not all(
        isinstance(entry, str) for entry in allowed_value
    ):
        raise ValueError("`assay.defaults.purposes` must be a list of names")
    allowed = list(allowed_value)
    requested_purpose = _request_optional_text(request.get("purpose"), name="purpose")
    default_purpose = _request_optional_text(
        assay_defaults.get("defaultPurpose"), name="assay.defaults.defaultPurpose"
    )
    wanted_purpose = resolve_purpose(
        requested_purpose, default_purpose, allowed, assay_name=assay_name
    )
    if wanted_purpose and allowed and wanted_purpose not in allowed:
        raise ValueError(
            f"{assay_name} cannot be used for `{wanted_purpose}`. It serves: "
            + ", ".join(sorted(allowed))
            + "."
        )

    intent: Purpose = purpose(wanted_purpose)
    supplied = _number_map(request.get("constraints"), name="constraints")
    unknown = sorted(set(supplied) - set(Constraints.__dataclass_fields__))
    if unknown:
        raise ValueError(f"unknown constraint(s): {', '.join(unknown)}")

    # Three layers, in this order, and the order is the argument:
    #
    #   the purpose    what the product is for afterwards. Sanger wants a
    #                  length its read can cover; cloning wants the whole gene.
    #   the assay      what the reaction physically is. A colony lysate cannot
    #                  give a four-kilobase product however good the primers
    #                  are, and no downstream wish changes that -- which is why
    #                  the assay sits above the purpose rather than below it.
    #                  Where the two cannot both be served, the purposes list
    #                  above has already refused the combination outright.
    #   what was typed the person in front of it, who can see something we
    #                  cannot and is allowed to overrule both.
    cycling_value = assay_defaults.get("cycling")
    if cycling_value is None:
        cycling_value = {}
    if not isinstance(cycling_value, dict):
        raise ValueError("`assay.defaults.cycling` must be an object")
    cycling_overrides = dict(cycling_value)
    # Validate the profile contract even when Primer3 later returns no pair.
    # A malformed programme is an invalid request, not a property of the
    # sequence's candidate pool.
    _resolved_cycling(preset, cycling_overrides)
    constraint_defaults = _number_map(
        assay_defaults.get("constraints"), name="assay.defaults.constraints"
    )
    strange = sorted(set(constraint_defaults) - set(Constraints.__dataclass_fields__))
    if strange:
        # A profile naming a field the worker does not have is a mistake in
        # profiles.toml, and one that would otherwise be invisible: the setting
        # would simply never take effect.
        raise ValueError(
            f"the assay `{assay.get('id', '?')}` sets {', '.join(strange)}, which "
            "is not a constraint this worker knows"
        )

    raw_policy = assay_defaults.get("constraintPolicy") or {}
    if not isinstance(raw_policy, dict):
        raise ValueError("`assay.defaults.constraintPolicy` must be an object")
    constraint_policy = {str(k): str(v) for k, v in raw_policy.items()}
    constraint_envelope = assay_defaults.get("constraintEnvelope") or {}
    if not isinstance(constraint_envelope, dict):
        raise ValueError("`assay.defaults.constraintEnvelope` must be an object")
    if selected_protocol is not None:
        # A caller who selects a named vendor/protocol branch may not widen the
        # numeric envelope carried by that same identity while keeping its name
        # attached. A protocol-owned envelope can be narrower *or broader* than
        # the generic cross-platform starting profile when the supplier
        # explicitly qualifies that range; once the protocol name is attached,
        # its own reviewed bounds are the authority for that run.
        for field in selected_protocol.get("constraints", {}):
            constraint_policy[field] = "bounded"
    generic_defaults = {
        field: getattr(Constraints(), field) for field in Constraints.__dataclass_fields__
    }
    scientific_baseline = {**generic_defaults, **intent.constraints, **constraint_defaults}
    # A named protocol may narrow the assay profile but may not be selected and
    # then silently widened while its vendor/protocol identity remains attached.
    if selected_protocol is not None:
        scientific_baseline.update(selected_protocol.get("constraints", {}))
    override_classifications = enforce_constraint_overrides(
        supplied,
        scientific_baseline,
        policies=constraint_policy,
        envelopes=constraint_envelope,
        context=f"assay `{assay.get('id') or assay_name}`",
    )

    layers = {
        **intent.constraints,
        **constraint_defaults,
        **(selected_protocol.get("constraints", {}) if selected_protocol else {}),
        **supplied,
    }
    overruled = [
        {
            "field": field,
            "assay_wanted": constraint_defaults[field],
            "used": layers[field],
            "because": "you set it",
        }
        for field in sorted(constraint_defaults)
        if constraint_defaults[field] != layers[field]
    ]
    if selected_protocol is not None:
        overruled.extend(
            {
                "field": field,
                "assay_wanted": constraint_defaults[field],
                "used": layers[field],
                "because": selected_protocol["selection"],
            }
            for field in selected_protocol.get("constraints", {})
            if field in constraint_defaults
            and field not in supplied
            and constraint_defaults[field] != layers[field]
        )
    limits = Constraints(**layers)

    # Restriction-cloning Gen-1 has one unambiguous topology: the submitted
    # sequence *is the insert*.  Ordinary flanking-pair search is allowed to
    # move both primers inward and can therefore clone only a convenient
    # subamplicon while the UI still says "the insert".  In Scientific-Strict
    # the complete submitted insert is the PCR product, so product size is
    # derived from sequence identity rather than from a generic cloning-purpose
    # preset. Donor-plasmid + target-region extraction is a different workflow
    # and needs its own reviewed branch.
    workflow_evidence = _workflow_evidence(request.get("workflow_evidence"))

    restriction_exact_insert = assay.get("id") == "restriction-cloning"
    cloning_vector_target: Target | None = None
    if restriction_exact_insert:
        raw_tails = request.get("tails")
        if not isinstance(raw_tails, dict) or not str(raw_tails.get("tail_protocol") or "").strip():
            raise ValueError(
                "restriction-cloning requires `tails.tail_protocol` before returning orderable primers"
            )
        raw_vector = _request_optional_text(request.get("cloning_vector"), name="cloning_vector")
        if raw_vector is None or not raw_vector.strip():
            raise ValueError(
                "restriction-cloning requires the exact `cloning_vector` recipient sequence for cut-site validation"
            )
        topology = _request_optional_text(
            request.get("cloning_vector_topology"), name="cloning_vector_topology"
        )
        if topology != "circular":
            raise ValueError(
                "restriction-cloning Gen-1 requires `cloning_vector_topology=circular`"
            )
        cloning_vector_target = resolve(
            raw_vector,
            name=_request_optional_text(
                request.get("cloning_vector_name"), name="cloning_vector_name"
            )
            or "recipient-vector",
            lowercase_masking=False,
        )
    elif any(
        request.get(key) is not None
        for key in ("cloning_vector", "cloning_vector_name", "cloning_vector_topology")
    ):
        raise ValueError("cloning_vector fields belong to the restriction-cloning assay")

    restriction_workflow: dict[str, Any] | None = None
    restriction_workflow_fields = (
        "restriction_digest_protocol",
        "restriction_dephosphorylation_protocol",
        "restriction_ligation_protocol",
    )
    if restriction_exact_insert:
        restriction_workflow = resolve_restriction_workflow(
            digest_protocol=_request_optional_text(
                request.get("restriction_digest_protocol"), name="restriction_digest_protocol"
            ),
            dephosphorylation_protocol=_request_optional_text(
                request.get("restriction_dephosphorylation_protocol"),
                name="restriction_dephosphorylation_protocol",
            ),
            ligation_protocol=_request_optional_text(
                request.get("restriction_ligation_protocol"), name="restriction_ligation_protocol"
            ),
        )
    elif any(request.get(field) is not None for field in restriction_workflow_fields):
        raise ValueError(
            "restriction-cloning digest/dephosphorylation/ligation workflow fields belong only to restriction-cloning"
        )

    restriction_donor_context: dict[str, Any] | None = None
    if restriction_exact_insert:
        donor_region_requested = (
            target_start is not None or target_length is not None or circular is True
        )
        if donor_region_requested:
            if circular is not True or target_start is None or target_length is None:
                raise ValueError(
                    "restriction-cloning donor-plasmid extraction requires circular=true plus both target_start and target_length; "
                    "otherwise submit the exact linear insert sequence."
                )
            if isinstance(target_start, bool) or isinstance(target_length, bool):
                raise ValueError(
                    "restriction-cloning donor target_start/target_length must be integer coordinates"
                )
            start = int(target_start)
            length = int(target_length)
            if (
                start != target_start
                or length != target_length
                or not 0 <= start < target.length
                or not 0 < length <= target.length
            ):
                raise ValueError(
                    f"restriction-cloning donor region must use 0-based start within 0..{target.length - 1} and length 1..{target.length}"
                )
            donor = target
            end = start + length
            if end <= donor.length:
                insert_sequence = donor.sequence[start:end]
            else:
                wrap = end - donor.length
                insert_sequence = donor.sequence[start:] + donor.sequence[:wrap]
            target = resolve(
                insert_sequence,
                name=f"{donor.name}:donor-region-{start}+{length}",
                lowercase_masking=False,
            )
            restriction_donor_context = {
                "mode": "circular-donor-region-extraction",
                "donor_name": donor.name,
                "donor_length_bp": donor.length,
                "donor_sha256": hashlib.sha256(donor.sequence.encode("ascii")).hexdigest(),
                "coordinate_convention": "0-based-start-plus-length-on-circular-sequence",
                "target_start": start,
                "target_length": length,
                "crosses_origin": end > donor.length,
                "insert_sha256": hashlib.sha256(insert_sequence.encode("ascii")).hexdigest(),
            }
        elif circular is True:
            raise ValueError(
                "restriction-cloning exact-insert mode expects a linear submitted insert; use target_start/target_length to extract from a circular donor"
            )
        if any(field in supplied for field in ("product_min", "product_max")):
            raise ValueError(
                "restriction-cloning derives product size from the exact insert or explicitly extracted donor region. "
                "Remove product_min/product_max overrides; changing them would permit a subamplicon."
            )
        limits = replace(limits, product_min=target.length, product_max=target.length)

    cloning_coding_context: dict[str, Any] | None = None
    cloning_coding_fields = (
        "cloning_coding_intent",
        "cloning_cds_start",
        "cloning_cds_end",
        "cloning_stop_codon_policy",
        "cloning_fusion_tag",
        "cloning_linker_aa",
        "cloning_vector_junction_frame",
    )
    if restriction_exact_insert:
        cloning_coding_context = resolve_cloning_coding_context(
            request, insert_sequence=target.sequence
        )
    elif any(request.get(field) is not None for field in cloning_coding_fields):
        raise ValueError("cloning coding/fusion fields belong only to restriction-cloning")

    # A template of nothing but ambiguity codes is not a template. Caught here
    # so a run does not spend its time proving it.
    if len(target.ambiguous_at) == target.length:
        raise ValueError(
            "Every base of this sequence is an ambiguity code, so there is nothing "
            "to design against."
        )
    if target.length < limits.product_min:
        raise ValueError(
            f"The template is {target.length} bases and the shortest product asked "
            f"for is {limits.product_min}. Either the wrong sequence arrived or the "
            "product size range needs lowering."
        )

    how_many = _request_integer(
        request.get("how_many"), name="how_many", default=5, minimum=1, maximum=most
    )
    if pool is not None and pool < how_many:
        raise ValueError(f"`pool` must be at least `how_many` ({how_many}), not {pool}")

    # ── 4-5. Search and diversify ───────────────────────────────────────────
    raw_excluded = request.get("excluded")
    if raw_excluded is None:
        raw_excluded = []
    if not isinstance(raw_excluded, list):
        raise ValueError("`excluded` must be a list of [start, length] regions")
    excluded: list[tuple[int, int]] = []
    for entry in raw_excluded:
        try:
            start, length = entry
            start = _request_integer(start, name="excluded.start", minimum=0)
            length = _request_integer(length, name="excluded.length", minimum=1)
            if start >= target.length:
                raise ValueError(
                    f"excluded.start {start} is outside the canonical template frame "
                    f"0..{target.length - 1}"
                )
            if bool(circular):
                if length > target.length:
                    raise ValueError(
                        f"excluded region length {length} exceeds the {target.length}-base "
                        "circular molecule; one region may cross the FASTA origin once but "
                        "may not cover more than one traversal"
                    )
            elif start + length > target.length:
                raise ValueError(
                    f"excluded region {start}..{start + length} falls outside the "
                    f"{target.length}-base linear template"
                )
            excluded.append((start, length))
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"an excluded region should be a start and a length in the canonical "
                f"template frame, not {entry!r}: {error}"
            ) from error

    if restriction_exact_insert and excluded:
        raise ValueError(
            "restriction-cloning Gen-1 does not accept `excluded` primer-placement regions. "
            "The supported branch pins both primers to the exact submitted insert boundaries; "
            "submit a different exact insert or use a future donor-template extraction branch."
        )

    # Positions this template is known to be polymorphic at.
    #
    # Refused here rather than ignored: a position off the end of the template
    # is somebody working in the wrong coordinate frame, and silently masking
    # nothing would let them believe a primer had been checked when it had not.
    known_variants = variants_mod.parse(request.get("variants"), length=target.length)

    # Design more than will be returned, so this pipeline's own scoring has
    # something to choose between rather than just reordering what Primer3
    # already ranked first.
    #
    # Wider still when variants are masked, because this post-search layer
    # knows which template coordinates each primer actually occupies. In
    # Scientific-Strict any supplied polymorphic coordinate under an oligo is
    # avoided rather than translated into an arbitrary terminal-distance law,
    # so the shortlist has to absorb candidates removed after placement.
    shortlist_ceiling = pool if pool is not None else MAX_PAIRS
    shortlist = min(shortlist_ceiling, how_many * SHORTLIST_FACTOR)
    if known_variants:
        shortlist = min(shortlist_ceiling, shortlist * 2)
    if exon_junctions:
        shortlist = min(shortlist_ceiling, max(shortlist, how_many * JUNCTION_SHORTLIST_FACTOR))

    # ── A circle has no last base ────────────────────────────────────────────
    #
    # The scan learned to look across the join; the search did not, so a
    # plasmid could be told it was a circle and still never be offered a
    # product spanning its origin — which is wherever whoever exported the file
    # happened to start it. Primer3 takes a string, so the way to ask for a
    # product over the join is to give it a string where the join is in the
    # middle: the sequence with enough of its own beginning repeated at its end
    # to hold the longest product asked for.
    #
    # Every coordinate that comes back is folded onto the real sequence
    # afterwards, and the pairs that are only a second copy of one already
    # found are dropped. See `_fold_onto_the_circle`.
    around = len(target.sequence) if circular else None
    searched = target.sequence
    if around is not None:
        # A crossing product needs the right primer's 3-prime coordinate to
        # appear in a repeated head. The head is capped at one molecule or the
        # requested product ceiling; `_fold_onto_the_circle` then rejects any
        # candidate that would need more than one traversal.
        searched = target.sequence + target.sequence[: min(limits.product_max, around)]
        # The appended head is a second copy of the beginning, so an excluded
        # stretch near the origin exists twice in what Primer3 sees. Passing
        # only the original would leave the copy unmasked and let a primer sit
        # on bases somebody asked to keep out of every copy of the product.
        # Clipped to the head's length, because beyond it there is no sequence.
        masked_head: list[tuple[int, int]] = []
        for start, length in excluded:
            overlap_end = min(start + length, limits.product_max)
            if start < overlap_end:
                masked_head.append((around + start, overlap_end - start))
        excluded.extend(masked_head)

    search_weights = PURPOSE_WEIGHTS.get(intent.id)
    if assay.get("id") == "rpa":
        search_weights = {
            **(search_weights or {}),
            **ISOTHERMAL_PRIMER3_WEIGHTS,
        }

    if restriction_exact_insert:
        # Endpoint-pinned search: the full insert is retained. Primer3 still
        # judges the annealing cores and pair interactions; only the product
        # boundary is no longer allowed to drift inward.
        result = design_terminal_pair(
            target.sequence,
            constraints=limits,
            conditions=reaction.as_conditions(),
            how_many=shortlist,
        )
    else:
        result = design(
            searched,
            target_start=target_start,
            target_length=target_length,
            excluded=excluded or None,
            constraints=limits,
            conditions=reaction.as_conditions(),
            how_many=shortlist if around is None else shortlist * 2,
            masked=target.soft_masked,
            weights=search_weights,
        )
    if around is not None:
        result = _fold_onto_the_circle(
            result,
            around,
            shortlist,
            allow_crossing=limits.product_max <= around,
        )
    junction_rejected = 0
    if exon_junctions:
        before_junction_filter = len(result.pairs)
        result = replace(
            result,
            pairs=[pair for pair in result.pairs if _spans_exon_junction(pair, exon_junctions)],
        )
        junction_rejected = before_junction_filter - len(result.pairs)
    designed = result_to_dict(result)

    accounts = [
        explain_mod.parse(result.considered.get("left", ""), stage="left primers"),
        explain_mod.parse(result.considered.get("right", ""), stage="right primers"),
        explain_mod.parse(result.considered.get("pair", ""), stage="pairs"),
    ]

    # ── 6. Accessibility ────────────────────────────────────────────────────
    if result.pairs and access.available():
        profile = _accessibility_profile(
            # The same string the search ran against. For a circle that is the
            # sequence with its head repeated, so a site near the origin is
            # folded with the sequence that really continues past it rather
            # than against the end of a file.
            searched,
            result.pairs,
            around=around,
            preset=preset,
            overrides=cycling_overrides,
            assay_id=str(assay.get("id") or ""),
        )
    else:
        profile = access.Accessibility(
            checked=False,
            model="",
            openings={},
            note=(
                "No candidates to check."
                if not result.pairs
                else "ViennaRNA is not installed, so template folding was not checked."
            ),
        )

    # Opening probabilities are only comparable at the same temperature.
    # Keep a separate baseline for each worker group so a warmer PCR candidate
    # is not rewarded merely because its fold was computed under a different
    # physical condition.
    best_log_by_temperature: dict[float, float] = {}
    for pair_index, pair in enumerate(result.pairs):
        temperature = _accessibility_temperature(pair, preset, cycling_overrides)
        positive = [
            profile.openings[f"{pair_index}:{side}"].unpaired
            for side in ("left", "right")
            if f"{pair_index}:{side}" in profile.openings
            and profile.openings[f"{pair_index}:{side}"].unpaired > 0
        ]
        if positive:
            best_log_by_temperature[temperature] = max(
                best_log_by_temperature.get(temperature, float("-inf")),
                math.log10(max(positive)),
            )

    # ── 7. Specificity ──────────────────────────────────────────────────────
    #
    # The same function the other five workers call. It decides what to scan
    # against, falls back to the template when nothing else was given, wraps a
    # circle across its own join, and refuses a background too large to search.
    contigs, scanning_the_template, fold_at = screen.contigs_for(
        request, template=target.sequence, name=target.name
    )
    if assay.get("id") == "species-specific-pcr" and scanning_the_template:
        # A species-specific claim requires a real exclusivity background. The
        # generic scanner falls back to the target itself for ordinary assays,
        # which is useful there but would silently turn this assay into
        # target-only PCR when a malformed/empty FASTA was supplied.
        raise ValueError(
            "Species-specific PCR needs a background with at least one sequence "
            "record from the organisms or genomes it must exclude. Checking the "
            "target alone cannot establish species specificity."
        )
    # A circular fallback background has a repeated head solely so a primer
    # crossing the arbitrary FASTA origin can be found. It is not additional
    # biological sequence, and reporting the scaffold length would make the
    # specificity provenance disagree with the background summary below.
    background_bases = screen.reported_bases(contigs, fold_at)
    background_ambiguous_bases = sum(
        sum(base not in {"A", "C", "G", "T"} for base in contig.sequence.upper())
        for contig in contigs
    )
    background_panel_sha256 = (
        hashlib.sha256(
            b"".join(
                contig.name.encode("utf-8")
                + b"\0"
                + contig.sequence.upper().encode("ascii")
                + b"\0"
                for contig in contigs
            )
        ).hexdigest()
        if contigs and not scanning_the_template
        else None
    )

    # Species specificity has two independent claims. The exclusion
    # background asks "what must not amplify?"; the inclusivity panel asks
    # "does this pair still amplify the target diversity we intend to cover?"
    # Keeping only the former can return a beautifully exclusive pair that
    # misses the very strain the assay is meant to detect.
    species_specific = assay.get("id") == "species-specific-pcr"
    species_provenance_fields = (
        "inclusivity_panel_provenance",
        "background_panel_provenance",
        "species_panel_selection_rationale",
        "species_target_taxid",
        "species_taxonomy_snapshot",
        "species_database_snapshot",
        "species_panel_accession_manifest",
        "species_panel_accession_authority_manifest",
        "species_panel_record_metadata_manifest",
        "species_panel_retrieved_date",
    )
    if (
        request.get("inclusivity") is not None
        or any(request.get(field) is not None for field in species_provenance_fields)
    ) and not species_specific:
        # This field is a species-specific target-panel contract. Accepting it
        # on another assay and then ignoring it would make the request audit
        # disagree with the experiment that ran.
        raise ValueError(
            "`inclusivity` and species-panel provenance fields are only supported by the species-specific-pcr assay"
        )
    inclusivity_contigs: list[spec.Contig] = []
    inclusivity_panel_provenance: str | None = None
    background_panel_provenance: str | None = None
    species_panel_selection_rationale: str | None = None
    species_target_taxid: int | None = None
    species_taxonomy_snapshot: str | None = None
    species_database_snapshot: str | None = None
    species_panel_accession_manifest: str | None = None
    species_panel_record_metadata_manifest: str | None = None
    species_panel_accession_authority_manifest: str | None = None
    species_accession_authority_sha256: str | None = None
    species_accession_authority_summary: dict[str, object] | None = None
    species_record_metadata = ()
    species_record_metadata_summary: dict[str, object] | None = None
    species_record_metadata_sha256: str | None = None
    species_topology_by_record: dict[str, str] = {}
    species_panel_retrieved_date: str | None = None
    species_panel_manifest_sha256: str | None = None
    species_panel_accession_count: int | None = None
    if species_specific:
        inclusivity_panel_provenance = _request_optional_text(
            request.get("inclusivity_panel_provenance"),
            name="inclusivity_panel_provenance",
        )
        background_panel_provenance = _request_optional_text(
            request.get("background_panel_provenance"),
            name="background_panel_provenance",
        )
        species_panel_selection_rationale = _request_optional_text(
            request.get("species_panel_selection_rationale"),
            name="species_panel_selection_rationale",
        )
        species_target_taxid = _request_integer(
            request.get("species_target_taxid"),
            name="species_target_taxid",
            default=0,
            minimum=1,
            maximum=2_147_483_647,
        )
        species_taxonomy_snapshot = _request_optional_text(
            request.get("species_taxonomy_snapshot"), name="species_taxonomy_snapshot"
        )
        species_database_snapshot = _request_optional_text(
            request.get("species_database_snapshot"), name="species_database_snapshot"
        )
        species_panel_accession_manifest = _request_optional_text(
            request.get("species_panel_accession_manifest"), name="species_panel_accession_manifest"
        )
        species_panel_record_metadata_manifest = _request_optional_text(
            request.get("species_panel_record_metadata_manifest"),
            name="species_panel_record_metadata_manifest",
        )
        species_panel_accession_authority_manifest = _request_optional_text(
            request.get("species_panel_accession_authority_manifest"),
            name="species_panel_accession_authority_manifest",
        )
        species_panel_retrieved_date = _request_optional_text(
            request.get("species_panel_retrieved_date"), name="species_panel_retrieved_date"
        )
        missing_provenance = [
            label
            for label, value in (
                ("inclusivity_panel_provenance", inclusivity_panel_provenance),
                ("background_panel_provenance", background_panel_provenance),
                ("species_panel_selection_rationale", species_panel_selection_rationale),
                ("species_taxonomy_snapshot", species_taxonomy_snapshot),
                ("species_database_snapshot", species_database_snapshot),
                ("species_panel_accession_manifest", species_panel_accession_manifest),
                ("species_panel_record_metadata_manifest", species_panel_record_metadata_manifest),
                (
                    "species_panel_accession_authority_manifest",
                    species_panel_accession_authority_manifest,
                ),
                ("species_panel_retrieved_date", species_panel_retrieved_date),
            )
            if not value
        ]
        if missing_provenance:
            raise ValueError(
                "Species-specific PCR requires traceable panel provenance, taxonomy/database snapshots, accession manifest and a biological "
                "selection rationale; missing: " + ", ".join(missing_provenance) + "."
            )
        try:
            assert species_panel_retrieved_date is not None
            date.fromisoformat(species_panel_retrieved_date)
        except ValueError as exc:
            raise ValueError(
                "species_panel_retrieved_date must be a valid ISO YYYY-MM-DD calendar date"
            ) from exc
        assert species_panel_accession_manifest is not None
        versioned_accessions = parse_accession_version_manifest(species_panel_accession_manifest)
        species_panel_accession_count = len(versioned_accessions)
        species_panel_manifest_sha256 = species_manifest_sha256(versioned_accessions)
        assert species_panel_accession_authority_manifest is not None
        assert species_database_snapshot is not None and species_taxonomy_snapshot is not None
        try:
            accession_authority_rows = parse_accession_authority_manifest(
                species_panel_accession_authority_manifest
            )
            species_accession_authority_summary = validate_accession_authority(
                accession_authority_rows,
                accessions=versioned_accessions,
                target_taxid=species_target_taxid,
                sequence_database_snapshot=species_database_snapshot,
                taxonomy_snapshot=species_taxonomy_snapshot,
            )
        except SpeciesPanelError as exc:
            raise ValueError(str(exc)) from exc
        species_accession_authority_sha256 = accession_authority_sha256(accession_authority_rows)
        inclusivity_value = request.get("inclusivity")
        if inclusivity_value is None:
            raise ValueError(
                "Species-specific PCR requires an explicit intended-target inclusivity panel in addition to the exclusion background; one representative template is not enough for a species-specific claim."
            )
        inclusivity_contigs = screen.contigs_from_text(
            inclusivity_value,
            label="inclusivity panel",
            default_name="inclusivity",
        )
        if not inclusivity_contigs:
            raise ValueError(
                "Species-specific PCR requires at least one non-empty inclusivity record."
            )

        # Panel taxonomy is user-declared provenance, not something PCRStudio
        # can infer from FASTA labels. We can nevertheless reject a logically
        # impossible sequence contract: the same molecule cannot simultaneously
        # be classified as must-amplify and must-exclude. FASTA orientation is
        # arbitrary, so compare each record against an orientation-invariant
        # canonical spelling rather than only literal text equality. This is an
        # exact content-overlap guard only; it does not infer taxonomy, circular
        # origin equivalence, or panel representativeness.
        def _orientation_key(sequence: str) -> str:
            forward = sequence.upper()
            reverse = reverse_complement(forward)
            return min(forward, reverse)

        background_sequences = {_orientation_key(contig.sequence) for contig in contigs}
        overlapping_sequences = sorted(
            {_orientation_key(contig.sequence) for contig in inclusivity_contigs}
            & background_sequences
        )
        if overlapping_sequences:
            raise ValueError(
                "Species-specific PCR inclusivity and exclusion panels contain at least one "
                "identical sequence record in the same or reverse-complement orientation. The same "
                "molecule cannot be both a required target and an excluded background under a "
                "sequence-discrimination claim; correct the panel classification/provenance or "
                "choose a discriminating locus."
            )
        assert species_panel_record_metadata_manifest is not None
        try:
            species_record_metadata = parse_record_metadata_manifest(
                species_panel_record_metadata_manifest
            )
            species_record_metadata_summary = validate_record_metadata(
                species_record_metadata,
                accessions=versioned_accessions,
                inclusivity_record_ids=tuple(contig.name for contig in inclusivity_contigs),
                exclusivity_record_ids=tuple(contig.name for contig in contigs),
            )
        except SpeciesPanelError as exc:
            raise ValueError(str(exc)) from exc
        species_record_metadata_sha256 = record_metadata_sha256(species_record_metadata)
        species_topology_by_record = {
            row.record_id: row.topology for row in species_record_metadata
        }
    inclusivity_bases = sum(len(contig.sequence) for contig in inclusivity_contigs)
    inclusivity_ambiguous_bases = sum(
        1
        for contig in inclusivity_contigs
        for base in contig.sequence
        if base not in {"A", "C", "G", "T"}
    )
    inclusivity_digest = hashlib.sha256()
    for contig in inclusivity_contigs:
        inclusivity_digest.update(contig.name.encode("utf-8"))
        inclusivity_digest.update(b"\0")
        inclusivity_digest.update(contig.sequence.encode("ascii"))
        inclusivity_digest.update(b"\0")
    inclusivity_panel_sha256 = inclusivity_digest.hexdigest() if inclusivity_contigs else None

    # Specificity v5 is mismatch-complete across the whole primer. The former
    # exact-terminal-clamp control is not part of the current request contract.
    max_mismatches = _request_integer(
        request.get("max_mismatches"),
        name="max_mismatches",
        default=3,
        minimum=0,
        maximum=spec.MAX_MISMATCHES,
    )
    terminal_mismatch_scan = assay.get("id") == "species-specific-pcr"
    if terminal_mismatch_scan:
        if request.get("max_mismatches") is not None and max_mismatches != 3:
            raise ValueError(
                "Species-specific PCR fixes the internal mismatch discovery budget at 3; changing it changes the screening method and requires a new versioned specificity contract."
            )
    if max_mismatches < 0:
        raise ValueError("specificity max_mismatches cannot be negative")

    # ── 8. Score, with the parts kept separate ──────────────────────────────
    scored: list[dict[str, Any]] = []
    # `design()` measured the pair structure with its low-level default. Keep
    # a parallel list so every selected output (including the order sheet) can
    # carry the assay-temperature measurement without mutating the frozen
    # design result used by the earlier funnel stages.
    effective_pairs = list(result.pairs)
    refused_for_a_variant = 0
    refused_for_specificity = 0
    refused_for_inclusivity = 0
    refused_for_named_protocol_amplicon_composition = 0
    named_protocol_amplicon_composition_considered = 0
    inclusivity_considered = 0
    for index, pair in enumerate(result.pairs):
        # Where a known variant falls under each primer.
        #
        # Before anything else is computed, because one in the last few bases
        # ends this candidate and there is no point pricing a pair that will
        # not be offered.
        under_left = variants_mod.under_left(
            pair.left_at.start,
            pair.left_at.length,
            known_variants,
            circular_length=len(target.sequence) if circular else None,
        )
        under_right = variants_mod.under_right(
            pair.right_at.start,
            pair.right_at.length,
            known_variants,
            circular_length=len(target.sequence) if circular else None,
        )
        variant_conflict = under_left.overlaps or under_right.overlaps
        if variant_conflict:
            refused_for_a_variant += 1
            continue

        specificity_temperature = _specificity_temperature(
            pair, preset, cycling_overrides, assay_id=str(assay.get("id") or "")
        )
        pair = _pair_at_effective_temperature(pair, reaction, specificity_temperature)
        effective_pairs[index] = pair
        if species_specific:
            inclusivity_considered += 1
            missing_records = [
                contig.name
                for contig in inclusivity_contigs
                if not _pair_has_product_on_contig(
                    pair,
                    contig,
                    reaction=reaction,
                    # Inclusivity and exclusivity have asymmetric evidence
                    # requirements. A mismatch-tolerant hit is useful for a
                    # conservative exclusion sweep, but without alternate-
                    # allele/chemistry calibration it is not proof that an
                    # intended strain is covered. Scientific-Strict therefore
                    # requires exact primer-sequence compatibility on every
                    # supplied inclusivity record. IUPAC ambiguity under a
                    # binding site is not promoted to exact coverage: every
                    # retained binding site must be unambiguous.
                    max_mismatches=0,
                    min_product=limits.product_min,
                    max_product=limits.product_max,
                    circular=species_topology_by_record.get(contig.name) == "circular",
                    temperature_c=specificity_temperature,
                    min_dg=None,
                    require_unambiguous_sites=True,
                )
            ]
            if missing_records:
                refused_for_inclusivity += 1
                continue

        # Some named chemistries publish sequence guidance for the *product*,
        # not for the primers.  Preserve that distinction explicitly.  The
        # Thermo Lyo-ready RPA branch specifies 35–60% amplicon GC; applying
        # those numbers to primer GC would be scientifically wrong, while only
        # displaying them after ranking would falsely imply that the selected
        # pair satisfies the named protocol's published sequence envelope.
        if (
            selected_rpa_protocol is not None
            and selected_rpa_protocol.get("protocol_id") == "thermo-lyo-ready-rpa"
        ):
            named_protocol_amplicon_composition_considered += 1
            product_gc = amplicon_mod.profile(pair.amplicon).gc
            amplicon_gc = selected_rpa_protocol["amplicon_gc_percent"]
            if not (float(amplicon_gc["min"]) <= product_gc <= float(amplicon_gc["max"])):
                refused_for_named_protocol_amplicon_composition += 1
                continue

        components = [
            Component(
                name="Primer3 penalty",
                value=pair.penalty,
                detail=(
                    "How far the pair sits from the ideal length, melting "
                    "temperature and GC it was asked for."
                ),
            )
        ]

        off_target_dict: dict[str, Any] = {"checked": False}
        if contigs:
            specificity_contigs = contigs
            per_contig_circular_lengths: dict[str, int] = {}
            if species_specific and species_topology_by_record:
                specificity_contigs = []
                for contig in contigs:
                    if species_topology_by_record.get(contig.name) == "circular":
                        per_contig_circular_lengths[contig.name] = len(contig.sequence)
                        specificity_contigs.append(
                            spec.Contig(
                                name=contig.name,
                                sequence=contig.sequence + contig.sequence[: screen.JOIN_WINDOW],
                            )
                        )
                    else:
                        specificity_contigs.append(contig)
            sites = spec.sites_for(
                pair.left.sequence,
                "left",
                specificity_contigs,
                reaction=reaction,
                max_mismatches=max_mismatches,
                include_terminal_mismatch=terminal_mismatch_scan,
                min_dg=None,
                temperature_c=specificity_temperature,
            ) + spec.sites_for(
                pair.right.sequence,
                "right",
                specificity_contigs,
                reaction=reaction,
                max_mismatches=max_mismatches,
                include_terminal_mismatch=terminal_mismatch_scan,
                min_dg=None,
                temperature_c=specificity_temperature,
            )
            if fold_at is not None:
                # A circle was scanned with its head repeated at its tail, so
                # that a primer crossing the join could be seen whole. A site
                # that *begins* past the real end is that same primer found a
                # second time near the origin, not a second place it sits.
                sites = [site for site in sites if screen.leftmost(site) < fold_at]
            if per_contig_circular_lengths:
                sites = [
                    site
                    for site in sites
                    if site.contig not in per_contig_circular_lengths
                    or screen.leftmost(site) < per_contig_circular_lengths[site.contig]
                ]

            products = spec.products_from(
                sites,
                max_product=screen.product_ceiling(limits.product_max),
                circular_length=fold_at,
                circular_lengths=per_contig_circular_lengths or None,
            )
            products = _without_the_intended_product(
                products,
                pair,
                contigs,
                circular_length=fold_at,
            )
            # How hard these two primers hold the actual template windows they
            # were designed on. A primer self-duplex is not the intended
            # primer-template duplex, especially for a circular join or a
            # candidate whose template contains a non-identical base.
            intended = _intended_binding_dg(
                pair,
                target.sequence,
                circular=circular,
                conditions=reaction.as_conditions(),
                temperature_c=specificity_temperature,
            )
            penalty, detail, serious = _score_off_targets(products, intended)
            if assay.get("id") == "species-specific-pcr" and products:
                # Species-specific PCR makes an exclusivity claim. Any complete
                # sequence-possible opposing-site product within the versioned
                # supplied-panel mismatch envelope is treated conservatively as
                # an exclusivity contradiction. This is not a claim that the
                # product is experimentally amplifiable; it avoids certifying a
                # pair when the supplied sequence evidence cannot exclude it.
                # OFF_TARGET_SERIOUS remains a ranking heuristic for assays that
                # do not claim exclusivity; it is not an exclusivity gate.
                refused_for_specificity += 1
                continue
            components.append(Component(name="Off-target products", value=penalty, detail=detail))
            off_target_dict = {
                "checked": True,
                "serious": serious,
                **spec.specificity_to_dict(
                    spec.Specificity(
                        checked=True,
                        background_name=contigs[0].name if contigs else "background",
                        background_bases=background_bases,
                        max_mismatches=max_mismatches,
                        sites=sites,
                        products=products,
                        terminal_mismatch_scan=terminal_mismatch_scan,
                        template_only=scanning_the_template,
                        min_dg=None,
                        max_product=screen.product_ceiling(limits.product_max),
                        temperature_c=specificity_temperature,
                    ),
                    max_products=8,
                ),
            }
        else:
            # Said rather than left out. A missing penalty and a penalty of
            # zero look identical in a total, and they mean opposite things:
            # one is a design checked against a genome and found unique, the
            # other is a design nobody checked at all. Leaving the component
            # out made the second look like the first.
            components.append(
                Component(
                    name="Off-target products",
                    value=0.0,
                    detail=(
                        "Not assessed. Nothing was available to scan — not even the "
                        "template, which should not happen."
                    ),
                )
            )

        penalty, detail = _score_cross_dimer(pair)
        components.append(Component(name="Primer-dimer", value=penalty, detail=detail))

        accessibility_temperature = _accessibility_temperature(
            pair, preset, cycling_overrides, assay_id=str(assay.get("id") or "")
        )
        # Template accessibility is OPTIONAL diagnostic evidence only. There is
        # no wet-lab calibration that justifies converting ViennaRNA unpaired
        # probability into a universal PCR success penalty. It therefore may
        # be reported, but it must not change deterministic candidate ranking.
        _accessibility_penalty_preview, _accessibility_detail = _score_accessibility(
            profile.openings,
            index,
            best_log_by_temperature.get(accessibility_temperature),
        )

        # Any candidate that overlaps a supplied variant coordinate has already
        # been removed. A coordinate alone cannot justify a universal
        # terminal-distance effect model.
        penalty, detail = (
            (0.0, "No supplied variant lies under either primer.")
            if known_variants
            else variants_mod.not_assessed()
        )
        components.append(Component(name="Known variants", value=penalty, detail=detail))

        # The empirical triplet prior is specific to conventional endpoint
        # PCR. Applying it to qPCR, dPCR, RPA or probe/chemistry-specific
        # assays would transfer a virus-primer observation beyond its evidence
        # boundary. Standard PCR has no hard clamp now; this soft term is the
        # replacement that lets the rest of the candidate field be considered.
        if assay.get("id") == "standard-pcr":
            penalty, detail = _score_three_prime_triplets(pair)
            components.append(Component(name="3′-end triplet prior", value=penalty, detail=detail))

        total = round(sum(c.value for c in components), 3)
        entry = designed["pairs"][index]
        # Kept so the order sheet can follow the ranking back to the candidate
        # it came from once `scored` has been re-sorted.
        entry["candidate"] = index
        entry["score"] = total
        entry["cross_dimer_dg"] = pair.cross_dimer_dg
        entry["score_components"] = [
            {"name": c.name, "value": c.value, "detail": c.detail} for c in components
        ]
        # Generic primer Tm must never become a bench annealing/cycling programme.
        # Named assay/platform overlays own executable protocol records elsewhere.
        entry["annealing_temperature"] = None
        entry.pop("cycling", None)
        # Temperature-dependent diagnostics use the explicit assay/model
        # context. In Scientific-Strict this is metadata for a thermodynamic
        # calculation, not an inferred PCR block temperature.
        entry["specificity_temperature_c"] = specificity_temperature
        entry["cross_dimer_temperature_c"] = specificity_temperature
        entry["accessibility_temperature_c"] = accessibility_temperature
        entry["thermodynamic_temperature_role"] = "model-reference-not-bench-annealing"
        entry["off_targets"] = off_target_dict
        left = profile.openings.get(f"{index}:left")
        right = profile.openings.get(f"{index}:right")
        entry["accessibility"] = (
            {"left": left.unpaired, "right": right.unpaired} if left and right else None
        )
        # What the product between them will be like to amplify. Reported
        # rather than scored: a GC-rich target is usually the target you have,
        # and what changes is the buffer rather than which pair to pick.
        entry["amplicon_profile"] = amplicon_mod.profile(pair.amplicon).to_dict(assay_id=assay_id)
        # And where its composition sits along the product, window by window.
        # Reported for the same reason and never a rejection.
        entry["uniformity"] = _uniformity(pair.amplicon)
        # The composite 0–100 view beside the penalty sum above. Additive:
        # the ranking still sorts on `score`.
        entry["quality"] = _quality_score(
            pair,
            limits,
            off_target_penalty=(
                next(
                    (
                        component.value
                        for component in components
                        if component.name == "Off-target products"
                    ),
                    None,
                )
                if off_target_dict.get("checked")
                else None
            ),
            openings=(left, right) if left and right else None,
            tm_centeredness_enabled=assay.get("id") != "rpa",
        )
        # `None` says nobody asked, which is not the same as asked and clean.
        entry["variants"] = (
            {"left": under_left.to_dict(), "right": under_right.to_dict()}
            if known_variants
            else None
        )
        scored.append(entry)

    scored.sort(key=lambda e: e["score"])
    ranked = scored[:how_many]

    # After ranking, because a tail does not change which pair is best: it is
    # the same bases on both of them. Before the result, because the order
    # sheet has to carry what you order rather than what anneals.
    cloning = _cloning_tails(request, target.sequence, ranked, reaction.as_conditions())
    if cloning is not None and restriction_exact_insert:
        cloning["insert_boundary_contract"] = {
            "mode": "circular-donor-region-extraction"
            if restriction_donor_context
            else "exact-submitted-insert",
            "product_size_bp": target.length,
            "terminal_primers_required": True,
            "donor_plasmid_region_extraction": "implemented-and-explicit"
            if restriction_donor_context
            else "not-requested",
            "donor_context": restriction_donor_context,
            "note": (
                "Scientific-Strict pins both annealing cores to the exact insert boundaries. "
                "When a circular donor region is requested, PCRStudio first extracts the explicit 0-based start+length region, including origin wrapping, then treats that extracted sequence as the immutable insert."
            ),
        }
        assert cloning_vector_target is not None
        forward_enzyme_name = str(cloning["forward"]["enzyme"])
        reverse_enzyme_name = str(cloning["reverse"]["enzyme"])
        forward_enzyme = restriction_mod.BY_NAME[forward_enzyme_name]
        reverse_enzyme = restriction_mod.BY_NAME[reverse_enzyme_name]
        forward_sites = restriction_mod.sites(
            cloning_vector_target.sequence, forward_enzyme, circular=True
        )
        reverse_sites = restriction_mod.sites(
            cloning_vector_target.sequence, reverse_enzyme, circular=True
        )
        if len(forward_sites) != 1 or len(reverse_sites) != 1:
            raise ValueError(
                "restriction-cloning requires each selected enzyme to cut the exact circular recipient vector exactly once; "
                f"{forward_enzyme_name} cuts {len(forward_sites)} time(s) and "
                f"{reverse_enzyme_name} cuts {len(reverse_sites)} time(s)."
            )
        cloning["recipient_vector"] = {
            "name": cloning_vector_target.name,
            "length_bp": cloning_vector_target.length,
            "sha256": hashlib.sha256(cloning_vector_target.sequence.encode("ascii")).hexdigest(),
            "topology": "circular",
            "registry": {
                "id": restriction_mod.RESTRICTION_REGISTRY.get("registry_id"),
                "schema_version": restriction_mod.RESTRICTION_REGISTRY.get("schema_version"),
                "effective_date": restriction_mod.RESTRICTION_REGISTRY.get("effective_date"),
                "scope": restriction_mod.RESTRICTION_REGISTRY.get("scope"),
                "limitations": restriction_mod.RESTRICTION_REGISTRY.get("limitations", []),
            },
            "sites": {
                forward_enzyme_name: forward_sites,
                reverse_enzyme_name: reverse_sites,
            },
            "site_count_contract": "exactly-one-site-per-selected-enzyme",
        }
        cloning["directional"] = bool(
            forward_enzyme_name != reverse_enzyme_name
            and forward_sites[0] != reverse_sites[0]
            and cloning.get("insert_ends_compatible") is False
        )
        cloning["directionality_evidence"] = (
            "exact-vector-sites-plus-incompatible-insert-end-families"
            if cloning["directional"]
            else "not-established-from-exact-vector-geometry"
        )

    # Beside the pair rather than instead of it: the two answer different
    # questions and a colony screen often runs both.
    backbone_plan = _resolved_cycling(preset, cycling_overrides)
    backbone_temperature = (
        backbone_plan.isothermal_c
        if backbone_plan.isothermal_c is not None
        else (backbone_plan.anneal_extend_c if backbone_plan.two_step else None)
    )
    backbone_screen = _backbone_screen(
        request,
        target.sequence,
        limits,
        reaction.as_conditions(),
        temperature_c=backbone_temperature,
    )

    # ── 9. The funnel, so no step is a black box ────────────────────────────
    stages: list[dict[str, Any]] = [
        _stage(
            "intake",
            "Reading the sequence",
            kind="filter",
            went_in=target.raw_length,
            came_out=target.length,
            unit="characters",
            detail=(
                f"{target.raw_length} characters arrived and {target.length} bases "
                "survived. "
                + (
                    " ".join(note.message for note in target.notes)
                    or "Nothing had to be stripped or converted."
                )
            ),
        )
    ]

    for account in accounts:
        # Primer3 keeps two counters for pairs and they do not agree: the one
        # in its explain string counts every pair it found acceptable during
        # the search, and the list it hands back is shorter, because it goes on
        # pruning after it has counted. Measured on a real template: 54 counted
        # against 47 handed over. The handed-over list is the one every step
        # after this uses, so that is the number this step ends on -- otherwise
        # the next step would start below where this one finished, and the
        # missing pairs would look like an unexplained loss.
        handed_over = result.returned if account.stage == "pairs" else account.accepted
        aside = (
            f" Primer3 counted {account.accepted} acceptable pairs while searching and "
            f"handed back {result.returned}; the {result.returned} are what everything "
            "below works from."
            if account.stage == "pairs" and account.accepted != result.returned
            else ""
        )
        stages.append(
            _stage(
                f"search:{account.stage.replace(' ', '-')}",
                f"Primer3: {account.stage}",
                kind="filter",
                went_in=account.considered,
                came_out=handed_over,
                unit=account.stage,
                detail=(account.sentence() or f"{account.considered} considered.") + aside,
                rejections=[
                    {
                        "reason": r.reason,
                        "count": r.count,
                        "share": round(100.0 * r.count / account.considered, 1)
                        if account.considered
                        else 0.0,
                        "advice": r.advice,
                    }
                    for r in account.rejections
                ],
            )
        )

    stages.append(
        _stage(
            "diversify",
            "Removing designs that are the same design",
            kind="filter",
            # What Primer3 handed over, not what was examined: a stage that
            # starts from a smaller number than the one before it ended on
            # reads as though pairs vanished, when in fact the walk down
            # Primer3's ranking simply stopped once it had enough.
            went_in=result.returned,
            came_out=len(result.pairs),
            unit="pairs",
            detail=(
                f"Primer3 returned {result.returned} pairs"
                + (
                    f", fewer than the {result.wanted} asked for"
                    if result.returned < result.wanted
                    else ""
                )
                + f". {result.examined} were looked at before {shortlist} distinct "
                "designs were in hand, and the rest were never opened"
                + (
                    f", and {result.collapsed} of those were another pair shifted by "
                    f"fewer than {limits.min_three_prime_distance} bases at the 3' "
                    "end, so they would behave the same in the tube."
                    if result.collapsed
                    else ", and none of them duplicated each other."
                )
            ),
            rejections=(
                [
                    {
                        "reason": "same design, shifted",
                        "count": result.collapsed,
                        "share": round(100.0 * result.collapsed / result.returned, 1)
                        if result.returned
                        else 0.0,
                        "advice": "raise min_three_prime_distance for more variety",
                    }
                ]
                if result.collapsed
                else []
            ),
        )
    )

    if exon_junctions:
        junction_considered = junction_rejected + len(result.pairs)
        stages.append(
            _stage(
                "transcript-junction",
                "Keeping primers that span a transcript junction",
                kind="filter",
                went_in=junction_considered,
                came_out=len(result.pairs),
                unit="pairs",
                detail=(
                    f"{junction_considered} candidate pair(s) were checked against "
                    f"{len(exon_junctions)} supplied exon-junction boundary/boundaries. "
                    f"{junction_rejected} did not cross any boundary and were removed. "
                    "The sequence is treated as cDNA; the boundaries must come from "
                    "a transcript annotation."
                ),
                rejections=(
                    [
                        {
                            "reason": "neither primer spans a supplied exon junction",
                            "count": junction_rejected,
                            "share": round(100.0 * junction_rejected / junction_considered, 1)
                            if junction_considered
                            else 0.0,
                            "advice": "provide a wider biologically correct transcript window or choose a separately reviewed assay/profile; do not relax a required junction gate to force a candidate",
                        }
                    ]
                    if junction_rejected
                    else []
                ),
            )
        )

    penalised = sum(
        1
        for entry in scored
        if entry["off_targets"].get("checked") and entry["off_targets"].get("serious")
    )
    if species_specific:
        inclusivity_passed = inclusivity_considered - refused_for_inclusivity
        stages.append(
            _stage(
                "inclusivity",
                "Checking coverage across the target panel",
                kind="filter",
                went_in=inclusivity_considered,
                came_out=inclusivity_passed,
                unit="pairs",
                ran=True,
                detail=(
                    f"{inclusivity_considered} candidate pair(s) were required to have "
                    f"unambiguous exact left/right primer-sequence compatibility in product geometry on all {len(inclusivity_contigs)} target "
                    f"record(s) ({inclusivity_bases:,} bases). {refused_for_inclusivity} "
                    "did not cover the complete panel and were removed. "
                    "This is an in-silico finite-panel screen; laboratory inclusivity still requires a representative strain panel, and panel completeness is not inferred from FASTA count."
                ),
                rejections=(
                    [
                        {
                            "reason": "pair lacks unambiguous exact primer-sequence coverage on at least one inclusivity record",
                            "count": refused_for_inclusivity,
                            "share": round(
                                100.0 * refused_for_inclusivity / inclusivity_considered,
                                1,
                            )
                            if inclusivity_considered
                            else 0.0,
                            "advice": "add a broader target panel or choose a more conserved target window",
                        }
                    ]
                    if refused_for_inclusivity
                    else []
                ),
            )
        )
    if (
        selected_rpa_protocol is not None
        and selected_rpa_protocol.get("protocol_id") == "thermo-lyo-ready-rpa"
    ):
        composition_went_in = named_protocol_amplicon_composition_considered
        composition_came_out = composition_went_in - refused_for_named_protocol_amplicon_composition
        stages.append(
            _stage(
                "named-protocol-amplicon-composition",
                "Applying named RPA amplicon-composition guidance",
                kind="filter",
                went_in=composition_went_in,
                came_out=composition_came_out,
                unit="pairs",
                ran=True,
                detail=(
                    "The selected Thermo Fisher Lyo-ready RPA/RT-RPA protocol publishes a "
                    "35–60% whole-amplicon GC design range. PCRStudio applies that range to the "
                    f"predicted amplicon, not to primer GC. {refused_for_named_protocol_amplicon_composition} "
                    f"of {composition_went_in} pair(s) fell outside the named branch and were removed."
                ),
                rejections=(
                    [
                        {
                            "reason": "predicted amplicon falls outside the named RPA 35–60% GC range",
                            "count": refused_for_named_protocol_amplicon_composition,
                            "share": round(
                                100.0
                                * refused_for_named_protocol_amplicon_composition
                                / composition_went_in,
                                1,
                            )
                            if composition_went_in
                            else 0.0,
                            "advice": "choose another candidate window or a separately reviewed chemistry branch; do not reinterpret the amplicon-GC range as a primer-GC limit",
                        }
                    ]
                    if refused_for_named_protocol_amplicon_composition
                    else []
                ),
            )
        )
    specificity_went_in = (
        len(scored) + refused_for_specificity + refused_for_inclusivity
        if species_specific
        else len(scored)
    )
    stages.append(
        _stage(
            "specificity",
            "Checking against the background",
            kind="scorer",
            went_in=specificity_went_in if contigs else None,
            came_out=len(scored) if contigs else None,
            unit="pairs",
            ran=bool(contigs),
            detail=(
                (
                    f"{specificity_went_in} pair(s) checked against {background_bases:,} bases. "
                    f"{refused_for_specificity} had at least one sequence-possible unwanted product within the declared mismatch envelope and were removed because this assay "
                    "makes an exclusivity claim."
                    if assay.get("id") == "species-specific-pcr"
                    else f"{len(scored)} pair(s) checked against {background_bases:,} bases. "
                    f"{penalised} had at least one sequence-possible unwanted product within the declared mismatch envelope. Nothing is removed for this — it is scored, so you can "
                    "still choose a pair we marked down."
                )
                if contigs
                else "No background was given, so no pair has been checked for "
                "specificity. These primers are only known to fit the sequence you "
                "pasted."
            ),
        )
    )

    if known_variants:
        considered_for_variants = len(scored) + refused_for_a_variant
        stages.append(
            _stage(
                "variants",
                "Masking supplied polymorphic coordinates from primer sites",
                kind="filter",
                went_in=considered_for_variants,
                came_out=len(scored),
                unit="pairs",
                detail=(
                    f"{len(known_variants)} known variant(s) were given. "
                    f"{refused_for_a_variant} of {considered_for_variants} pair(s) "
                    "placed at least one primer across a supplied polymorphic coordinate "
                    "and were removed. PCRStudio does not infer a universal safe distance "
                    "from the 3-prime end when alternate alleles, allele frequencies and "
                    "chemistry-specific mismatch evidence were not supplied."
                ),
                rejections=(
                    [
                        {
                            "reason": ("a supplied polymorphic coordinate lies under a primer"),
                            "count": refused_for_a_variant,
                            "share": round(
                                100.0 * refused_for_a_variant / considered_for_variants,
                                1,
                            ),
                            "advice": "allow the search more placement room or provide a different target region",
                        }
                    ]
                    if refused_for_a_variant
                    else []
                ),
            )
        )

    stages.append(
        _stage(
            "accessibility",
            "Asking whether the template is open there",
            kind="scorer",
            went_in=len(profile.openings) or None,
            came_out=len(profile.openings) or None,
            unit="binding sites",
            ran=profile.checked,
            detail=(
                f"{len(profile.openings)} binding sites folded with "
                f"{profile.model}. Sites the template keeps closed are ranked below "
                "ones it leaves open; none is removed for it."
                if profile.checked
                else profile.note
            ),
        )
    )

    # The loop applies these checks in this order: variant rejection, target
    # inclusivity, then background specificity. Keep the report in the same
    # order even though each stage is assembled in a different section below;
    # an audit trail must describe the execution that actually happened.
    funnel_keys = {"variants", "inclusivity", "specificity", "accessibility"}
    funnel = {stage["key"]: stage for stage in stages if stage["key"] in funnel_keys}
    if funnel:
        stages[:] = [stage for stage in stages if stage["key"] not in funnel_keys]
        stages.extend(
            funnel[key]
            for key in ("variants", "inclusivity", "specificity", "accessibility")
            if key in funnel
        )

    # ── 10. The account ─────────────────────────────────────────────────────
    if len(scored) > len(ranked):
        cut = scored[len(ranked) :]
        stages.append(
            _stage(
                "rank",
                "Ranking on everything Primer3 does not score",
                kind="filter",
                went_in=len(scored),
                came_out=len(ranked),
                unit="pairs",
                detail=(
                    f"{len(scored)} distinct designs were scored on specificity, on "
                    "whether the template keeps each site open, and on how far each "
                    f"pair sits from the middle of its window. The best {len(ranked)} "
                    f"are shown. The {len(cut)} not shown scored between "
                    f"{cut[0]['score']:.2f} and {cut[-1]['score']:.2f}, against "
                    f"{ranked[-1]['score']:.2f} for the last one that is."
                ),
                rejections=[
                    {
                        "reason": "ranked below the ones shown",
                        "count": len(cut),
                        "share": round(100.0 * len(cut) / len(scored), 1),
                        "advice": "ask for more pairs to see them",
                    }
                ],
            )
        )

    answer: dict[str, Any] = {
        "engine": "flanking-pair",
        # What produced these numbers, so a result a year old can be repeated
        # or disbelieved on the evidence rather than on trust.
        "provenance": provenance(reaction.as_conditions()),
        "interactions": _interactions(
            [
                (
                    effective_pairs[entry["candidate"]],
                    float(entry["specificity_temperature_c"]),
                )
                for entry in ranked
            ],
            target.name,
            reaction,
        ),
        # A property of the run rather than of a pair: the same hold, at the
        # same temperature, whichever design you pick. `None` says the question
        # was never put — this assay's page does not ask it.
        # Isothermal from the programme this run actually produced, not from a
        # list of assay names. RPA runs on this same engine and holds at one
        # temperature: a hold placed "before the initial denaturation" of a
        # reaction that never denatures is an instruction nobody can follow.
        "reverse_transcription": (
            {
                "one_step": True,
                "hold": {
                    "celsius": float(
                        selected_qpcr_protocol["reverse_transcription"]["temperature_c"]
                    ),
                    "seconds": int(
                        selected_qpcr_protocol["reverse_transcription"]["incubation_minutes"] * 60
                    ),
                },
                "before": "initial-denaturation-and-qpcr-cycling",
                "note": selected_qpcr_protocol["reverse_transcription"]["note"],
                "authority_status": selected_qpcr_protocol["reverse_transcription"][
                    "authority_status"
                ],
            }
            if from_rna
            and selected_qpcr_protocol
            and selected_qpcr_protocol.get("reverse_transcription")
            else (
                {
                    "one_step": True,
                    "hold": {
                        "celsius": float(
                            selected_digital_protocol["reverse_transcription"]["temperature_c"]
                        ),
                        "seconds": int(
                            selected_digital_protocol["reverse_transcription"]["incubation_minutes"]
                            * 60
                        ),
                    },
                    "before": selected_digital_protocol["reverse_transcription"].get(
                        "before", "dpcr-cycling"
                    ),
                    "note": selected_digital_protocol["reverse_transcription"]["note"],
                    "authority_status": selected_digital_protocol["reverse_transcription"][
                        "authority_status"
                    ],
                }
                if from_rna
                and selected_digital_protocol
                and selected_digital_protocol.get("reverse_transcription")
                # The shared result schema keeps RT timing/authority compact. The
                # named RPA protocol retains the exact enzyme/inhibitor/RNase-H
                # recipe in its own provenance object.
                else (
                    {
                        "one_step": True,
                        "hold": {
                            "celsius": float(
                                selected_rpa_protocol["reverse_transcription"]["temperature_c"]
                            ),
                            "seconds": int(
                                selected_rpa_protocol["reverse_transcription"]["incubation_minutes"]
                                * 60
                            ),
                        },
                        "before": "concurrent-with-rpa",
                        "note": selected_rpa_protocol["reverse_transcription"]["note"],
                        "authority_status": selected_rpa_protocol["reverse_transcription"][
                            "authority_status"
                        ],
                    }
                    if from_rna
                    and selected_rpa_protocol
                    and selected_rpa_protocol.get("reverse_transcription")
                    else (rt.block(isothermal=False, polymerase=preset.name) if from_rna else None)
                )
            )
        ),
        "transcript": {
            "exon_junctions": list(exon_junctions),
            "junction_spanning_required": bool(exon_junctions),
            "coordinate_system": "zero-based-boundary-between-bases",
            "note": (
                "At least one primer in every reported pair spans a supplied "
                "transcript boundary. This is an in-silico geometry rule; it does "
                "not replace no-RT controls or genomic alignment."
                if exon_junctions
                else "No exon-junction boundary was supplied."
            ),
        },
        "stages": stages,
        "target": target_to_dict(target),
        # The effective request is the audit ledger for this run. It records
        # decisions and coordinate conventions without duplicating the raw
        # template/background into every saved result.
        "request": {
            "coordinates": {
                "system": "zero-based-half-open",
                "target_start": target_start,
                "target_length": target_length,
            },
            "circular": bool(circular),
            "rna": {
                "requested": requested_from_rna,
                "effective": from_rna,
            },
            "transcript": {
                "exon_junctions": list(exon_junctions),
                "junction_spanning_required": bool(exon_junctions),
                "coordinate_system": "zero-based-boundary-between-bases",
            },
            "polymerase": {
                "requested": requested_polymerase,
                "effective": preset.id,
                "condition_overrides": overrides,
            },
            "purpose": {
                "requested": requested_purpose,
                "effective": intent.id,
            },
            "constraint_overrides": supplied,
            "constraint_override_classification": override_classifications,
            "constraint_qualification_envelope": constraint_envelope,
            "excluded_regions": len(raw_excluded),
            "known_variants": len(known_variants),
            "background_supplied": request.get("background") is not None,
            "inclusivity_supplied": request.get("inclusivity") is not None,
            "inclusivity_records": len(inclusivity_contigs),
            "specificity": {
                "method": spec.METHOD_ID,
                "method_version": spec.METHOD_VERSION,
                "max_mismatches": max_mismatches,
                "terminal_mismatch_reported": terminal_mismatch_scan,
            },
            "search": {
                "how_many": how_many,
                "shortlist": shortlist,
                "pool": pool,
                "primer3_returned": result.returned,
                "primer3_examined": result.examined,
            },
        },
        "reaction": {
            "polymerase": preset.id,
            "polymerase_name": preset.name,
            "summary": preset.summary,
            "context_role": "primer-design-thermodynamic-screening-context",
            "context_note": (
                "Long-range bench chemistry/cycling is owned by the explicit named protocol. "
                "These ionic/oligo inputs define the reproducible Primer3 screening model and "
                "must not be read as a reconstruction of a proprietary supplier buffer."
                if assay_id == "long-range-pcr"
                else (
                    "Digital-PCR primer thermodynamics are a platform-neutral screening model. "
                    "Bench cycling is emitted only by an explicit platform/chemistry overlay."
                    if assay_id == "digital-pcr"
                    else (
                        "Colony-PCR primer thermodynamics use a generic screening context only. "
                        "The user-named colony SOP owns cell preparation, lysis and the executable cycle programme; "
                        "PCRStudio does not infer those bench steps from this preset."
                        if assay_id == "colony-pcr"
                        else (
                            "These ionic and oligo values make Primer3 thermodynamic calculations reproducible. "
                            "They are a generic primer-design screening context, not a named supplier buffer or a universal bench PCR programme."
                        )
                    )
                )
            ),
            **reaction.as_conditions(),
            "chemistry": {
                "strand_displacing": preset.strand_displacing,
                "five_prime_exonuclease": preset.five_prime_exonuclease,
                "proofreading": preset.proofreading,
                "thermostable": preset.thermostable,
                "rpa_compatible": preset.rpa_compatible,
            },
            "model": thermodynamic_model(preset, reaction),
        },
        "constraints": {
            field: getattr(limits, field) for field in Constraints.__dataclass_fields__
        },
        "assay": {
            "id": assay.get("id", ""),
            "name": assay.get("name", ""),
            "engine": assay.get("engine", ""),
            "status": assay.get("status", ""),
            "profile_authority": dict(assay.get("profileAuthority") or {}),
            "defaults": constraint_defaults,
            "purposes": allowed,
            # Keep the complete executable profile contract beside the
            # resolved numbers. A result that records only the assay name can
            # look reproducible while hiding the modifier, input requirement
            # or enzyme capability that constrained the run.
            "modifiers": list(assay.get("modifiers", [])),
            "requires": list(assay.get("requires", [])),
            "enzyme": list(assay.get("enzyme", [])),
            # Where the assay's own number was not the one used, and why. A
            # layer nobody can see is a layer nobody can argue with.
            "overruled": overruled,
        },
        # A computationally clean pair is not the same thing as a validated
        # assay. Keep the required wet-lab checks in the result so the UI and
        # exported report cannot accidentally imply otherwise.
        "validation": _validation_plan(str(assay.get("id", "")), from_rna=from_rna),
        "purpose": {
            "id": intent.id,
            "name": intent.name,
            "summary": intent.summary,
            "constraints": intent.constraints,
            # The ranking weights this purpose contributed to the search, if
            # any. A bias nobody can see is a bias nobody can argue with.
            "ranking_weights": search_weights or {},
            # What the person typed over the top of it, so the layers stay
            # legible after the fact.
            "overridden": sorted(set(supplied) & set(intent.constraints)),
        },
        "pairs": ranked,
        "considered": [explain_mod.account_to_dict(a) for a in accounts],
        "why_nothing": (
            "Every candidate produced at least one complete sequence-compatible unintended opposing-site product "
            "within the supplied exclusion panel and declared mismatch/product-size search envelope. "
            "That is sufficient for this conservative finite-panel screen to refuse the candidate; it is not a "
            "claim that the unintended product has been experimentally shown to amplify. Add a better target "
            "window or review the exclusion panel."
            if not scored and refused_for_specificity
            else "Every candidate failed to form a complete product across the supplied "
            "inclusivity panel, so none can be called inclusive for this target set. "
            "Add representative target records or choose a more conserved window."
            if not scored and refused_for_inclusivity
            else ""
            if scored
            else explain_mod.why_nothing(accounts)
        ),
        "accessibility": access.accessibility_to_dict(profile),
        # A property of the run: the same positions were masked whichever
        # design you pick. `checked: false` says nobody gave any, which the
        # interface has to word differently from "checked, and none of them
        # lands on a primer".
        "variants": variants_mod.summary(
            known_variants,
            considered=len(scored) + refused_for_a_variant,
            rejected=refused_for_a_variant,
        ),
        # The same function the other five workers call, so a LAMP set and a
        # pair cannot come to different conclusions about the same genome.
        "background": screen.summary(
            contigs,
            scanning_the_template,
            max_mismatches=max_mismatches,
            min_dg=None,
            max_product=screen.product_ceiling(limits.product_max),
            terminal_mismatch_scan=terminal_mismatch_scan,
            fold_at=fold_at,
        ),
        "order_sheet": _order_sheet(
            [effective_pairs[entry["candidate"]] for entry in ranked],
            target.name,
            tailed=cloning,
        ),
    }

    if modified_oligos is not None:
        answer["modified_oligos"] = modified_oligos

    if workflow_evidence is not None:
        answer["workflow_evidence"] = {
            "recorded": True,
            "decision_impact": "none",
            "observed": workflow_evidence,
            "note": "Experimental/QC evidence is stored for reproducibility and validation review; it does not alter primer generation or ranking.",
        }

    # Sequence topology is part of specificity provenance, not something the
    # exclusion FASTA can safely inherit from the target. The request carries
    # one target-level circular flag; explicit background records have no
    # per-record topology metadata in GEN1 and are therefore scanned exactly as
    # supplied (linear coordinate strings). This keeps a circular plasmid
    # target from silently circularising unrelated genomic/background records.
    if scanning_the_template:
        if fold_at is not None:
            background_topology_assumption = "template-circular-from-request"
            background_topology_note = (
                "No explicit background was supplied. The target template was scanned as a "
                "circular molecule because circular=true, with only the arbitrary FASTA-origin "
                "join repaired for specificity discovery."
            )
        else:
            background_topology_assumption = "template-linear-from-request"
            background_topology_note = (
                "No explicit background was supplied. The fallback target template was scanned "
                "as a linear sequence."
            )
    else:
        if species_specific and species_topology_by_record:
            background_topology_assumption = (
                "explicit-per-record-topology-from-pinned-metadata-manifest"
            )
            background_topology_note = (
                "Each species-panel record uses the explicitly pinned per-record topology (linear/circular/fragment) in the record-metadata manifest. "
                "Circular records are scanned across their own FASTA origin; fragment records remain linear and do not prove absence outside the supplied fragment."
            )
        else:
            background_topology_assumption = "explicit-records-linear-no-topology-inference"
            background_topology_note = (
                "Explicit background FASTA records are scanned as supplied linear coordinate strings. "
                "No record topology was declared, so PCRStudio does not infer or copy the target circular flag onto exclusion records."
            )
    answer["background"].update(
        {
            "sequence_topology_assumption": background_topology_assumption,
            "topology_note": background_topology_note,
        }
    )
    # Absent rather than null when nothing asked for tails, so a reader never
    # has to tell "no tails" from "tails that came back empty".
    if cloning is not None:
        answer["cloning"] = cloning
    if restriction_workflow is not None:
        answer["restriction_workflow"] = restriction_workflow
    if cloning_coding_context is not None:
        answer["cloning_coding_context"] = cloning_coding_context
    if assay_id == "rpa":
        answer["rpa_screening_cohort"] = rpa_screening_cohort(scored, maximum=10)
        answer["rpa_multiplex_panel"] = rpa_panel_context
        extend_rpa_multiplex_order_sheet(answer["order_sheet"], rpa_panel_context)
    if backbone_screen is not None:
        answer["backbone"] = backbone_screen
    if species_specific:
        answer["species_panel_snapshot"] = {
            "target_taxid": species_target_taxid,
            "taxonomy_snapshot": species_taxonomy_snapshot,
            "database_snapshot": species_database_snapshot,
            "accession_manifest_sha256": species_panel_manifest_sha256,
            "accession_manifest_count": species_panel_accession_count,
            "record_metadata_manifest_sha256": species_record_metadata_sha256,
            "record_metadata_summary": species_record_metadata_summary,
            "accession_authority_manifest_sha256": species_accession_authority_sha256,
            "accession_authority_summary": species_accession_authority_summary,
            "accession_manifest_contract": "unique-versioned-accessions-canonicalized-before-hashing",
            "retrieved_date": species_panel_retrieved_date,
            "taxonomy_resolution_status": "offline-accession-authority-snapshot-validated; no-network-taxonomy-inference",
            "panel_completeness_status": "not-inferred-or-claimed",
            "surveillance_status": "snapshot-pinned; future-database-diff-required-for-continued-specificity-claim",
            "revalidation_policy": species_revalidation_policy(),
            "sequence_decision_impact": "none-beyond-explicit-inclusivity-and-background-sequences",
        }
        answer["background"].update(
            {
                "panel_sha256": background_panel_sha256,
                "ambiguous_bases": background_ambiguous_bases,
                "panel_role": "exclusivity",
                "panel_hash_scope": "ordered-normalized-fasta-record-name-and-sequence",
                "panel_identity_claim": "content-identity-only-not-taxonomic-completeness",
                "panel_provenance": background_panel_provenance,
                "panel_selection_rationale": species_panel_selection_rationale,
                "taxonomy_resolution_status": "not-resolved-from-fasta-labels",
                "biological_traceability_status": "user-declared-provenance-recorded-not-independently-validated",
                "diversity_coverage_status": "not-computed-from-panel-hash",
                "population_frequency_status": "not-computed",
                "surveillance_status": "external-versioned-review-required",
            }
        )
        answer["inclusivity"] = {
            "checked": True,
            "supplied": True,
            "template_only": False,
            "bases": inclusivity_bases,
            "contigs": len(inclusivity_contigs),
            "pairs_checked": inclusivity_considered,
            "pairs_rejected": refused_for_inclusivity,
            "panel_sha256": inclusivity_panel_sha256,
            "ambiguous_bases": inclusivity_ambiguous_bases,
            "panel_hash_scope": "ordered-normalized-fasta-record-name-and-sequence",
            "panel_identity_claim": "content-identity-only-not-taxonomic-completeness",
            "panel_provenance": inclusivity_panel_provenance,
            "panel_selection_rationale": species_panel_selection_rationale,
            "taxonomy_resolution_status": "not-resolved-from-fasta-labels",
            "biological_traceability_status": "user-declared-provenance-recorded-not-independently-validated",
            "diversity_coverage_status": "not-computed-from-panel-hash",
            "population_frequency_status": "not-computed",
            "surveillance_status": "external-versioned-review-required",
            "binding_ambiguity_policy": "fail-closed-at-primer-sites",
            "sequence_topology_assumption": "explicit-per-record-topology-from-pinned-metadata-manifest",
            "topology_note": (
                "Each inclusivity record uses its pinned topology. Circular records are tested across their own FASTA origin; "
                "linear and fragment records are not wrapped. Fragment metadata is evidence-limited and does not imply whole-genome coverage."
            ),
            "note": (
                "Every retained pair had unambiguous exact primer-sequence coverage in valid opposing geometry on every supplied target record. "
                "This is a conservative finite-panel sequence-coverage claim, not evidence of laboratory amplification or population representativeness; representative wet-lab inclusivity testing is still required."
            ),
        }

    if flanking_numeric_recipe is not None:
        answer["flanking_numeric_recipe"] = flanking_numeric_recipe
    if selected_protocol is not None:
        answer["protocol"] = selected_protocol
    if selected_colony_context is not None:
        answer["colony_context"] = selected_colony_context
    if selected_digital_context is not None:
        answer["digital_context"] = selected_digital_context

    return answer
