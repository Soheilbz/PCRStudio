"""Primers that deliberately disagree with the template, to change it.

Site-directed mutagenesis amplifies a whole plasmid with a pair that carries
the change, so what comes out is the same molecule with the edit in it. The
geometry is the outward-facing one: the two primers sit back to back at the
edit site and read away from each other, all the way round.

One thing about these primers is unlike every other primer this project
designs, and it is the reason this is its own engine rather than a flag on
another.

A mutagenic primer has distinct template-facing and edited-product
thermodynamic contexts.  PCRStudio reports both as *screening evidence* because
the deliberately mismatched parental-template duplex and the fully matched
product duplex are not thermodynamically identical.  Neither value is promoted
to a bench annealing programme: the named Q5/E0554 branch delegates annealing
temperature to current Q5/NEBaseChanger guidance or an experimentally resolved
gradient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import primer3

from . import mutagenesis_workflows as workflows
from .design import clean_template
from .intake import target_to_dict
from .presets import thermodynamic_model
from .provenance import provenance
from .registries.authorities import MUTAGENESIS_AUTHORITY
from .registries.authorities import record as authority_record
from .settings import how_many_from, label, prepare
from .thermo import DEFAULT_CONDITIONS, analyse, pair_dimer, report_to_dict, reverse_complement
from .workflow_evidence import evidence_block


class MutagenesisError(ValueError):
    """An edit that could not be described."""


#: What kinds of edit this makes.
EDITS = ("substitute", "insert", "delete")

# Parental-template removal and post-amplification recovery are properties of
# the named mutagenesis protocol, not of every pair carrying an edit. Keeping
# an explicit empty choice prevents a QuikChange/DpnI workflow from being
# silently attached to a custom mutagenesis design.
#: Q5/E0554 primer-design boundaries used by the executable Gen-1 branch.
#:
#: NEB requires at least 10 template-complementary nucleotides at the 3' end
#: of a mutagenic primer. The current NEBaseChanger/Q5 guidance supports
#: small insertions (<=6 nt) as a 5' tail on the forward primer and larger
#: reviewed routine insertions by splitting the insert between both 5' ends. Generation 1
#: implements both source-backed forms and routes insertions above the reviewed 100-nt
#: envelope to a separately reviewed assembly strategy.
_Q5_AUTHORITY = authority_record(MUTAGENESIS_AUTHORITY, "neb-q5-e0554")
Q5_MIN_3PRIME_COMPLEMENT = int(_Q5_AUTHORITY["minimum_3prime_template_complement_nt"])
Q5_MAX_SMALL_INSERTION = int(_Q5_AUTHORITY["small_insertion_max_nt"])
Q5_ROUTINE_INSERTION_MAX = int(_Q5_AUTHORITY["routine_insertion_max_nt"])
Q5_SPLIT_INSERTION_PER_PRIMER_MAX = int(_Q5_AUTHORITY["split_insertion_per_primer_max_nt"])
Q5_PURIFICATION_RECOMMENDED_OVER = int(_Q5_AUTHORITY["purification_recommended_over_primer_nt"])
Q5_DOCUMENTED_PLASMID_ENVELOPE = int(_Q5_AUTHORITY["documented_successful_plasmid_bp"])

# Implementation search bounds, not vendor chemistry limits.  The >60-nt rule above is
# a purification recommendation, not a maximum allowed oligo length.  These caps bound
# Generation-1 enumeration and must never be presented as kit specifications.
Q5_SEARCH_PRIMER_LENGTH_MIN = 15
Q5_SEARCH_PRIMER_LENGTH_MAX = 60

#: A difference worth calling out in the explanatory Tm evidence. This is a
#: wording threshold only; it does not accept/reject or rank a candidate.
GAP_WORTH_MENTIONING = 3.0

#: Named recovery/routing protocols are topology-specific. Q5, QuikChange Lightning
#: single-site, Lightning Multi and NEBuilder multi-site are never treated as
#: interchangeable presets; each branch validates its own protocol identity.
POST_AMPLIFICATION_PROTOCOLS = (
    "neb-q5-e0554",
    "agilent-quikchange-lightning-210518",
    "agilent-quikchange-lightning-multi-210513-210516",
    "neb-nebuilder-multisite",
)
MUTAGENESIS_TOPOLOGIES = (
    "q5-back-to-back",
    "quikchange-complementary",
    "quikchange-lightning-multi",
    "nebuilder-multisite",
)


@dataclass(frozen=True)
class Edit:
    """What is being changed, and where."""

    kind: str
    #: Zero-based position on the template where the edit begins.
    at: int
    #: The sequence to put there. Empty for a deletion.
    to: str = ""
    #: How many template bases the edit replaces or removes.
    replacing: int = 0

    def check(self, template_length: int) -> None:
        """Whether this edit could be made to that template.

        Raises:
            MutagenesisError: naming what was asked for and what exists.
        """
        if self.kind not in EDITS:
            raise MutagenesisError(
                f"`{self.kind}` is not an edit this makes. It makes: " + ", ".join(EDITS) + "."
            )
        # An insertion is a boundary edit: placing it immediately after the
        # final base (``at == template_length``) is meaningful even though no
        # existing base is replaced. Substitutions and deletions still need an
        # existing base at their start.
        last_valid = template_length if self.kind == "insert" else template_length - 1
        if not 0 <= self.at <= last_valid:
            raise MutagenesisError(
                f"The edit is at base {self.at} of a {template_length}-base "
                "sequence, which is outside it."
            )
        if self.at + self.replacing > template_length:
            raise MutagenesisError(
                f"The edit replaces {self.replacing} bases from {self.at}, which "
                f"runs past the end of a {template_length}-base sequence."
            )
        if self.kind == "substitute":
            if not self.to:
                raise MutagenesisError("A substitution needs something to put there.")
            if len(self.to) != self.replacing:
                raise MutagenesisError(
                    f"A substitution puts {len(self.to)} bases where {self.replacing} "
                    "were. For different lengths, an insertion or a deletion is what "
                    "this is."
                )
        if self.kind == "insert":
            if not self.to:
                raise MutagenesisError("An insertion needs something to insert.")
            if self.replacing:
                raise MutagenesisError(
                    "An insertion replaces nothing. To swap a stretch for a longer "
                    "one, delete it and insert."
                )
        if self.kind == "delete":
            if self.to:
                raise MutagenesisError("A deletion puts nothing back.")
            if self.replacing < 1:
                raise MutagenesisError("A deletion of no bases changes nothing.")

    def describe(self) -> str:
        if self.kind == "substitute":
            return f"{self.replacing} base(s) at {self.at} replaced by {self.to}"
        if self.kind == "insert":
            return f"{self.to} inserted at {self.at}"
        return f"{self.replacing} base(s) removed from {self.at}"


@dataclass(frozen=True)
class MutagenicPair:
    """A Q5-style back-to-back pair with ordered and annealing molecules separated."""

    forward: str
    reverse: str
    forward_annealing: str
    reverse_annealing: str
    forward_tail: str
    reverse_tail: str
    forward_at: int
    reverse_at: int
    on_template: float
    on_product: float
    reverse_tm: float
    cross_dimer_dg: float
    #: How far the substitution midpoint sits from the primer midpoint.
    #: This is a vendor-guidance ranking term, never a validity threshold.
    centrality_error: float = 0.0

    @property
    def gap(self) -> float:
        return round(self.on_product - self.on_template, 1)


def apply_edit(template: str, edit: Edit) -> str:
    """The sequence this edit would produce."""
    if edit.kind == "insert":
        return template[: edit.at] + edit.to + template[edit.at :]
    return template[: edit.at] + edit.to + template[edit.at + edit.replacing :]


def _q5_lengths() -> range:
    return range(Q5_SEARCH_PRIMER_LENGTH_MIN, Q5_SEARCH_PRIMER_LENGTH_MAX + 1)


def design(
    template: str,
    edit: Edit,
    *,
    conditions: dict[str, float] | None = None,
    how_many: int = 5,
) -> list[MutagenicPair]:
    """Design the documented Q5/E0554 Gen-1 primer topology, best first.

    Scientific-Strict deliberately implements only rules that are explicit in
    the Q5 guidance. Substitutions use a mutagenic forward primer with at least
    10 template-complementary 3' bases and are ranked toward a central mismatch.
    Deletions use two standard primers flanking the deleted interval. Small
    insertions (<=6 nt) are a 5' forward tail with a template-complementary core.
    Reviewed 7–100 nt insertions are split across both 5' tails; insertions beyond that remain a typed boundary until an assembly-
    oligo/product reconstruction is implemented and independently validated.
    """
    sequence = clean_template(template)
    edit.check(len(sequence))
    if len(sequence) > Q5_DOCUMENTED_PLASMID_ENVELOPE:
        raise MutagenesisError(
            f"The template is {len(sequence):,} bases. The current Gen-1 Q5/E0554 "
            f"branch is bounded to the documented <= {Q5_DOCUMENTED_PLASMID_ENVELOPE:,}-base "
            "plasmid envelope; add a separately reviewed protocol/profile rather than extrapolating."
        )
    if edit.kind == "insert" and len(edit.to) > Q5_ROUTINE_INSERTION_MAX:
        raise MutagenesisError(
            f"The requested insertion is {len(edit.to)} nt. The reviewed Q5 guidance routinely accommodates "
            f"up to {Q5_ROUTINE_INSERTION_MAX} nt by splitting at most {Q5_SPLIT_INSERTION_PER_PRIMER_MAX} nt "
            "onto each 5' primer tail; larger insertions require a separately reviewed assembly strategy."
        )

    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}
    after = edit.at + edit.replacing
    found: list[MutagenicPair] = []

    if edit.kind == "substitute":
        # The mismatch is ranked toward the primer centre, while the only hard
        # Q5 anchor rule used here is >=10 complementary 3' bases.
        for total_length in _q5_lengths():
            matched = total_length - len(edit.to)
            if matched < Q5_MIN_3PRIME_COMPLEMENT:
                continue
            max_left = matched - Q5_MIN_3PRIME_COMPLEMENT
            # The only hard complementary-anchor rule is >=10 nt on the 3'
            # side.  Ordinary substitutions rank toward the centre, while NEB
            # explicitly allows larger changes to be incorporated at the 5'
            # end; requiring a left-side match would turn that preference into
            # an unsupported validity rule.
            for left_match in range(0, max_left + 1):
                right_match = matched - left_match
                start = edit.at - left_match
                if start < 0 or after + right_match > len(sequence):
                    continue
                forward = (
                    sequence[start : edit.at] + edit.to + sequence[after : after + right_match]
                )
                template_window = sequence[start : after + right_match]
                measured = analyse(forward, **reaction)
                on_template = round(
                    primer3.calc_heterodimer(
                        forward, reverse_complement(template_window), **reaction
                    ).tm,
                    1,
                )
                mutation_midpoint = left_match + len(edit.to) / 2.0
                centrality = abs(mutation_midpoint - total_length / 2.0)
                for reverse_length in _q5_lengths():
                    if start - reverse_length < 0:
                        continue
                    reverse = reverse_complement(sequence[start - reverse_length : start])
                    reverse_report = analyse(reverse, **reaction)
                    found.append(
                        MutagenicPair(
                            forward=forward,
                            reverse=reverse,
                            forward_annealing=forward,
                            reverse_annealing=reverse,
                            forward_tail="",
                            reverse_tail="",
                            forward_at=start,
                            reverse_at=start - reverse_length,
                            on_template=on_template,
                            on_product=measured.tm,
                            reverse_tm=reverse_report.tm,
                            cross_dimer_dg=pair_dimer(forward, reverse, **reaction).dg,
                            centrality_error=centrality,
                        )
                    )

    elif edit.kind == "delete":
        # The primers flank the deleted interval; there is no invented sliding
        # junction because the deletion boundaries define the Q5 topology.
        for forward_length in _q5_lengths():
            if after + forward_length > len(sequence):
                continue
            forward = sequence[after : after + forward_length]
            forward_report = analyse(forward, **reaction)
            for reverse_length in _q5_lengths():
                if edit.at - reverse_length < 0:
                    continue
                reverse = reverse_complement(sequence[edit.at - reverse_length : edit.at])
                reverse_report = analyse(reverse, **reaction)
                found.append(
                    MutagenicPair(
                        forward=forward,
                        reverse=reverse,
                        forward_annealing=forward,
                        reverse_annealing=reverse,
                        forward_tail="",
                        reverse_tail="",
                        forward_at=after,
                        reverse_at=edit.at - reverse_length,
                        on_template=forward_report.tm,
                        on_product=forward_report.tm,
                        reverse_tm=reverse_report.tm,
                        cross_dimer_dg=pair_dimer(forward, reverse, **reaction).dg,
                    )
                )

    else:  # Q5 insertion: small one-tail or reviewed split-5'-tail topology
        if len(edit.to) <= Q5_MAX_SMALL_INSERTION:
            left_insert = ""
            right_insert = edit.to
        else:
            # Final construct order is upstream + left_insert + right_insert + downstream.
            # The reverse primer's 5' tail is the reverse complement of the
            # upstream-adjacent insert half; the forward primer carries the
            # downstream-adjacent half. This reconstructs the exact insertion
            # after whole-plasmid amplification/KLD rather than duplicating or
            # reversing the split sequence.
            split = len(edit.to) // 2
            left_insert = edit.to[:split]
            right_insert = edit.to[split:]
            if max(len(left_insert), len(right_insert)) > Q5_SPLIT_INSERTION_PER_PRIMER_MAX:
                raise MutagenesisError(
                    "Q5 split insertion would exceed the reviewed 50-nt 5' tail per primer boundary."
                )
        for core_length in _q5_lengths():
            if core_length < Q5_MIN_3PRIME_COMPLEMENT or edit.at + core_length > len(sequence):
                continue
            forward_core = sequence[edit.at : edit.at + core_length]
            forward_tail = right_insert
            forward = forward_tail + forward_core
            forward_product = (
                analyse(forward_core, **reaction) if forward_tail else analyse(forward, **reaction)
            )
            forward_template = analyse(forward_core, **reaction)
            for reverse_length in _q5_lengths():
                if edit.at - reverse_length < 0:
                    continue
                reverse_core = reverse_complement(sequence[edit.at - reverse_length : edit.at])
                reverse_tail = reverse_complement(left_insert) if left_insert else ""
                reverse = reverse_tail + reverse_core
                reverse_report = analyse(reverse_core, **reaction)
                found.append(
                    MutagenicPair(
                        forward=forward,
                        reverse=reverse,
                        forward_annealing=forward_core,
                        reverse_annealing=reverse_core,
                        forward_tail=forward_tail,
                        reverse_tail=reverse_tail,
                        forward_at=edit.at,
                        reverse_at=edit.at - reverse_length,
                        on_template=forward_template.tm,
                        on_product=forward_product.tm,
                        reverse_tm=reverse_report.tm,
                        cross_dimer_dg=pair_dimer(forward, reverse, **reaction).dg,
                    )
                )

    # Q5 topology first, then a reproducible thermodynamic screening tie-break.
    # Tm balance is not a Q5 validity law and therefore never raises/refuses.
    found.sort(
        key=lambda pair: (
            pair.centrality_error,
            abs(pair.on_template - pair.reverse_tm),
            -min(pair.on_template, pair.reverse_tm),
            len(pair.forward) + len(pair.reverse),
        )
    )
    return found[:how_many]


def why_none(
    template: str,
    edit: Edit,
    *,
    conditions: dict[str, float] | None = None,
) -> str:
    """Explain a topology/search failure without recommending gate relaxation."""
    sequence = clean_template(template)
    edit.check(len(sequence))
    if edit.kind == "insert" and len(edit.to) > Q5_ROUTINE_INSERTION_MAX:
        return (
            f"This insertion exceeds the reviewed Q5 routine {Q5_ROUTINE_INSERTION_MAX}-nt split-tail boundary. "
            "Use a separately reviewed assembly/mutagenesis strategy rather than extrapolating Q5."
        )
    return (
        "No Q5-style candidate could be constructed within the documented Generation-1 topology "
        f"(Generation-1 searches 15–60 nt ordered primers as an implementation envelope and requires at least {Q5_MIN_3PRIME_COMPLEMENT} template-complementary "
        "3' bases where the Q5 guidance requires them). Check the edit coordinate/template sequence "
        "or use NEBaseChanger/current Q5 guidance for a separately reviewed design; PCRStudio will "
        "not relax the topology to manufacture a pair."
    )


def pair_to_dict(pair: MutagenicPair, edit: Edit, **conditions: float) -> dict[str, Any]:
    """One Q5-style pair with ordered molecule and initial annealing core separated."""
    gap = pair.gap
    forward_report = report_to_dict(analyse(pair.forward, **conditions))
    reverse_report = report_to_dict(analyse(pair.reverse, **conditions))
    return {
        "forward": {
            **forward_report,
            "at": pair.forward_at,
            "carries": edit.to or "a deletion",
            "annealing_sequence": pair.forward_annealing,
            "tail_sequence": pair.forward_tail,
        },
        "reverse": {
            **reverse_report,
            "at": pair.reverse_at,
            "annealing_sequence": pair.reverse_annealing,
            "tail_sequence": pair.reverse_tail,
        },
        "melting": {
            "on_template": pair.on_template,
            "on_product": pair.on_product,
            "reverse": pair.reverse_tm,
            "gap": gap,
            "authority": "Primer3 thermodynamic screening; Q5 annealing temperature remains protocol/NEBaseChanger validated",
            "note": (
                f"The forward ordered oligo screens at {pair.on_product} °C against its edited product "
                f"and at {pair.on_template} °C for the template-facing annealing molecule. The reverse "
                f"screens at {pair.reverse_tm} °C. These are reproducible in-silico values, not a "
                "replacement for the Q5/NEBaseChanger annealing-temperature decision."
            ),
        },
        "order_guidance": {
            "forward_ordered_length_nt": len(pair.forward),
            "reverse_ordered_length_nt": len(pair.reverse),
            "purification_recommended": max(len(pair.forward), len(pair.reverse))
            > Q5_PURIFICATION_RECOMMENDED_OVER,
            "authority": "NEB Q5 current primer-design guidance: purification recommended for primers >60 nt",
            "note": "Purification is an ordering recommendation, not a thermodynamic validity gate.",
        },
        "centrality_error_nt": pair.centrality_error if edit.kind == "substitute" else None,
        "cross_dimer_dg": pair.cross_dimer_dg,
        "edit": {"kind": edit.kind, "at": edit.at, "describes": edit.describe()},
    }


#: The most pairs one request may ask for.
MOST_PAIRS = 10


def _workflow_result(
    request: dict[str, Any], chosen: Any, *, topology: str, protocol_id: str
) -> dict[str, Any] | None:
    """Run non-Q5 topologies without pretending they share Q5 geometry."""
    if topology == "q5-back-to-back":
        return None
    seq = clean_template(chosen.target.sequence)
    reaction = chosen.reaction.as_conditions()
    codon_policy = str(request.get("codon_policy") or "minimum-nucleotide-changes")
    edits = (
        workflows.normalize_edits(request, len(seq)) if not request.get("amino_acid_edit") else []
    )
    amino_evidence = None
    if request.get("amino_acid_edit") is not None:
        raw = request.get("amino_acid_edit")
        if not isinstance(raw, dict):
            raise MutagenesisError("amino_acid_edit must be an object")
        edit, amino_evidence = workflows.amino_acid_edit(
            seq,
            raw,
            codon_policy=codon_policy,
            codon_usage=request.get("codon_usage")
            if isinstance(request.get("codon_usage"), dict)
            else None,
        )
        edits = [edit]
    changed = workflows.apply_edits(seq, edits)
    base = {
        "engine": "mutagenic-pair",
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "mutagenesis_topology": topology,
        "post_amplification_protocol": protocol_id,
        "edits": [e.as_dict() for e in edits],
        "amino_acid_evidence": amino_evidence,
        "construct": workflows.sequence_diff(seq, changed, edits),
        "template_methylation_status": str(request.get("template_methylation_status") or "unknown"),
        "workflow_evidence": evidence_block(request.get("workflow_evidence")),
        "validation_contract": {
            "sequence_confirmation_required": True,
            "parental_template_removal_must_be_recorded_when_protocol_depends_on_it": topology.startswith(
                "quikchange"
            ),
            "claim_boundary": "A predicted edited construct is not a verified clone. Record transformation, clone identity and sequence confirmation as empirical evidence.",
        },
    }
    name = label(chosen.target.name)
    if topology == "quikchange-complementary":
        if protocol_id != "agilent-quikchange-lightning-210518":
            raise MutagenesisError(
                "quikchange-complementary requires post_amplification_protocol=agilent-quikchange-lightning-210518"
            )
        if len(edits) != 1:
            raise MutagenesisError(
                "QuikChange Lightning single-site topology requires exactly one edit; use Lightning Multi or NEBuilder multi-site for multiple edits."
            )
        planned = workflows.quikchange_single(seq, edits[0])
        pairs = planned.get("pairs", [])
        base.update(
            {
                "design": planned,
                "protocol": {
                    "selection": "Agilent QuikChange Lightning Site-Directed Mutagenesis",
                    "source_identity": "Agilent QuikChange Lightning Instruction Manual 210518",
                    "source_url": "https://www.agilent.com/cs/library/usermanuals/public/210518.pdf",
                    "topology": "complementary mutagenic primers / linear amplification / DpnI",
                    "numeric_authority": "Use the current kit manual for bench recipe and cycling; PCRStudio exposes only reviewed primer-geometry rules here.",
                },
                "orderability": {
                    "orderable": bool(pairs),
                    "status": "orderable-manual-faithful-quikchange" if pairs else "not-orderable",
                    "note": "Orderable only when the public QuikChange Lightning manual rules implemented by PCRStudio are satisfied; GC/end and structure review are reported. This is not Agilent Primer Design Program/Energy Cost equivalence.",
                },
                "order_sheet": [
                    entry
                    for i, pair in enumerate(pairs, 1)
                    for entry in (
                        {
                            "name": f"{name}_{i}F",
                            "sequence": pair["forward"],
                            "kind": "primer",
                            "length": len(pair["forward"]),
                            "tm_formula_c": pair["tm_formula_c"],
                            "gc_percent": pair["gc_percent"],
                            "note": "Mutagenic complementary primer; Agilent-specific Tm formula.",
                        },
                        {
                            "name": f"{name}_{i}R",
                            "sequence": pair["reverse"],
                            "kind": "primer",
                            "length": len(pair["reverse"]),
                            "tm_formula_c": pair["tm_formula_c"],
                            "gc_percent": pair["gc_percent"],
                            "note": "Exact reverse complement of the mutagenic forward primer.",
                        },
                    )
                ],
            }
        )
        return base
    if topology == "quikchange-lightning-multi":
        if protocol_id != "agilent-quikchange-lightning-multi-210513-210516":
            raise MutagenesisError(
                "quikchange-lightning-multi requires the named Agilent Lightning Multi protocol"
            )
        planned = workflows.quikchange_multi(seq, edits)
        primers = planned.get("primers", [])
        base.update(
            {
                "design": planned,
                "protocol": {
                    "selection": "Agilent QuikChange Lightning Multi",
                    "source_identity": "Agilent manual 210514",
                    "source_url": "https://www.agilent.com/Library/usermanuals/Public/210514.pdf",
                    "topology": "one same-orientation non-overlapping primer per mutation site",
                },
                "orderability": {
                    "orderable": bool(planned.get("orderable")),
                    "status": "orderable-manual-faithful-lightning-multi"
                    if planned.get("orderable")
                    else "not-orderable",
                    "note": "Orderable only when the public Lightning Multi geometry, formula-Tm and dimer rules implemented by PCRStudio are satisfied; this is not Agilent web-tool equivalence.",
                },
                "order_sheet": [
                    {
                        "name": f"{name}_M{i}",
                        "sequence": p["sequence"],
                        "kind": "primer",
                        "length": p["length"],
                        "tm_formula_c": p["tm_formula_c"],
                        "gc_percent": p["gc_percent"],
                        "note": "Same-template-strand Lightning Multi mutagenic primer.",
                    }
                    for i, p in enumerate(primers, 1)
                ],
            }
        )
        return base
    if topology == "nebuilder-multisite":
        if protocol_id != "neb-nebuilder-multisite":
            raise MutagenesisError(
                "nebuilder-multisite requires post_amplification_protocol=neb-nebuilder-multisite"
            )
        planned = workflows.nebuilder_multisite_route(seq, edits)
        base.update(
            {
                "design": planned,
                "protocol": {
                    "selection": "PCRStudio multi-site NEBuilder HiFi routing informed by NEBaseChanger workflow",
                    "source_identity": "NEBaseChanger v2.8.4 workflow reference",
                    "source_url": "https://nebasechanger.neb.com/",
                    "execution_status": "route-to-junction-engine",
                    "vendor_tool_equivalent": False,
                },
                "orderability": {
                    "orderable": False,
                    "status": "route-to-junction-primers",
                    "note": "This engine reconstructs the exact edited construct and routing graph; Junction Primers owns overlap/primer ordering.",
                },
                "order_sheet": [],
            }
        )
        return base
    raise MutagenesisError("unknown mutagenesis_topology: " + topology)


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One mutagenic design, end to end, in the shape the interface reads.

    Raises:
        IntakeError: the input is not a usable template.
        MutagenesisError: an edit this template could not take.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    # The product is the whole plasmid, so it is never made of the template in
    # the way a flanking pair's is, and the usual product-room check does not
    # describe anything here.
    chosen = prepare(request, require_product_room=False)
    how_many = how_many_from(request, MOST_PAIRS)

    topology = str(request.get("mutagenesis_topology") or "q5-back-to-back").strip()
    if topology not in MUTAGENESIS_TOPOLOGIES:
        raise MutagenesisError(
            "mutagenesis_topology must be one of: " + ", ".join(MUTAGENESIS_TOPOLOGIES)
        )
    post_amplification_protocol = str(request.get("post_amplification_protocol") or "").strip()

    # Library requests are explicit design-space declarations. They are never
    # silently converted into a single deterministic mutation or a claimed
    # equal-abundance oligo pool.
    if request.get("library_mode") not in (None, "", "none"):
        raw = request.get("library_edit")
        if not isinstance(raw, dict):
            raise MutagenesisError("library_mode requires library_edit={at,codon}")
        lib = workflows.library_edit(
            clean_template(chosen.target.sequence),
            at=int(raw.get("at")),
            codon=str(raw.get("codon") or request.get("library_mode")),
        )
        return {
            "engine": "mutagenic-pair",
            "provenance": provenance(chosen.reaction.as_conditions()),
            "assay": chosen.assay_to_dict(),
            "target": target_to_dict(chosen.target),
            "mutagenesis_topology": "library-degenerate",
            "library_design": lib,
            "orderability": {
                "orderable": False,
                "status": "requires-topology-specific-library-primer-design",
                "note": "PCRStudio records the IUPAC library construct and theoretical sequence space but does not claim equal synthesis abundance or emit a primer until a reviewed library topology is selected.",
            },
            "workflow_evidence": evidence_block(request.get("workflow_evidence")),
            "order_sheet": [],
        }

    alternate = _workflow_result(
        request, chosen, topology=topology, protocol_id=post_amplification_protocol
    )
    if alternate is not None:
        return alternate

    # Q5 is a single-edit topology. Multi-site requests route to the dedicated
    # Lightning Multi or NEBuilder branches rather than being approximated.
    if isinstance(request.get("edits"), list):
        normalized = workflows.normalize_edits(request, len(clean_template(chosen.target.sequence)))
        if len(normalized) != 1:
            raise MutagenesisError(
                "q5-back-to-back accepts exactly one edit per PCRStudio design; use quikchange-lightning-multi or nebuilder-multisite for multiple edits."
            )
        supplied = normalized[0].as_dict()
    elif request.get("amino_acid_edit") is not None:
        raw_aa = request.get("amino_acid_edit")
        if not isinstance(raw_aa, dict):
            raise MutagenesisError("amino_acid_edit must be an object")
        aa_edit, _aa_evidence = workflows.amino_acid_edit(
            clean_template(chosen.target.sequence),
            raw_aa,
            codon_policy=str(request.get("codon_policy") or "minimum-nucleotide-changes"),
            codon_usage=request.get("codon_usage")
            if isinstance(request.get("codon_usage"), dict)
            else None,
        )
        supplied = aa_edit.as_dict()
    else:
        supplied = request.get("edit")
    if not isinstance(supplied, dict):
        raise MutagenesisError(
            "This needs an `edit`: what to change, and where. It takes a `kind` "
            "of " + ", ".join(EDITS) + ", an `at`, and — for a substitution or an "
            "insertion — the sequence `to` put there."
        )
    strange = sorted(set(supplied) - set(Edit.__dataclass_fields__))
    if strange:
        raise MutagenesisError(f"unknown field(s) on the edit: {', '.join(strange)}")

    kind = str(supplied.get("kind") or "").strip()
    if not kind:
        raise MutagenesisError("The edit needs an explicit `kind`; no edit type is inferred.")
    if "at" not in supplied or supplied.get("at") is None:
        raise MutagenesisError(
            "The edit needs an explicit zero-based `at`; omission is not base 0."
        )
    if kind in {"substitute", "insert"} and not str(supplied.get("to") or "").strip():
        raise MutagenesisError(f"A {kind} edit needs an explicit non-empty `to` sequence.")
    if kind in {"substitute", "delete"} and (
        "replacing" not in supplied or supplied.get("replacing") is None
    ):
        raise MutagenesisError(
            f"A {kind} edit needs an explicit `replacing` count; omission is not zero."
        )

    edit = Edit(
        kind=kind,
        at=int(supplied["at"]),
        to=str(supplied.get("to") or "").upper(),
        replacing=int(supplied.get("replacing") or 0),
    )

    reaction = chosen.reaction.as_conditions()

    if post_amplification_protocol not in POST_AMPLIFICATION_PROTOCOLS:
        raise MutagenesisError(
            "post_amplification_protocol must be one of: "
            + ", ".join(POST_AMPLIFICATION_PROTOCOLS)
            + "."
        )
    if request.get("flank") is not None:
        raise MutagenesisError(
            "`flank` was a legacy unsourced tuning control and is no longer executable. "
            "The Q5 branch uses its documented >=10-nt 3-prime complement rule internally."
        )
    if request.get("constraints"):
        raise MutagenesisError(
            "Site-directed Mutagenesis does not accept generic PCR constraint overrides. "
            "Q5 primer topology is assay-specific; add a sourced/versioned mutagenesis profile "
            "instead of tuning generic PCR windows."
        )
    if post_amplification_protocol != "neb-q5-e0554":
        raise MutagenesisError(
            "Generation-1 Site-directed Mutagenesis is the Q5/E0554 branch and requires "
            "`post_amplification_protocol=neb-q5-e0554`; design-only or alternative chemistries "
            "need a separate versioned profile rather than a policy fallback."
        )
    found = design(
        chosen.target.sequence,
        edit,
        conditions=reaction,
        how_many=how_many,
    )

    pairs = [pair_to_dict(pair, edit, **reaction) for pair in found]
    name = label(chosen.target.name)
    changed = apply_edit(clean_template(chosen.target.sequence), edit)
    orderability = (
        {
            "orderable": True,
            "status": "orderable-named-q5-e0554",
            "note": "Primer sequences are supplier-orderable under the explicitly selected Q5/E0554 branch; annealing temperature remains owned by current Q5/NEBaseChanger guidance or an experimental gradient.",
        }
        if pairs
        else {
            "orderable": False,
            "status": "not-orderable-no-valid-q5-pair",
            "note": "No Q5/E0554 primer pair survived the current topology and thermodynamic screening, so no supplier order is emitted.",
        }
    )

    return {
        "engine": "mutagenic-pair",
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {
            "topology": "q5-back-to-back-non-overlapping",
            "min_3prime_complement_nt": Q5_MIN_3PRIME_COMPLEMENT,
            "search_primer_length_min_nt": Q5_SEARCH_PRIMER_LENGTH_MIN,
            "search_primer_length_max_nt": Q5_SEARCH_PRIMER_LENGTH_MAX,
            "search_length_is_vendor_limit": False,
            "small_insertion_max_nt": Q5_MAX_SMALL_INSERTION,
            "routine_insertion_max_nt": Q5_ROUTINE_INSERTION_MAX,
            "split_insertion_per_primer_max_nt": Q5_SPLIT_INSERTION_PER_PRIMER_MAX,
            "purification_recommended_over_ordered_primer_nt": Q5_PURIFICATION_RECOMMENDED_OVER,
            "large_insertion_status": "executable-reviewed-split-tail-topology",
        },
        "construct": workflows.sequence_diff(
            clean_template(chosen.target.sequence),
            changed,
            [workflows.EditSpec(edit.kind, edit.at, edit.to, edit.replacing)],
        ),
        "template_methylation_status": str(request.get("template_methylation_status") or "unknown"),
        "validation_contract": {
            "sequence_confirmation_required": True,
            "claim_boundary": "Predicted construct sequence; clone-level sequence confirmation is required.",
        },
        "edit": {
            "kind": edit.kind,
            "at": edit.at,
            "to": edit.to,
            "replacing": edit.replacing,
            "describes": edit.describe(),
            "was": clean_template(chosen.target.sequence)[
                max(0, edit.at - 10) : edit.at + max(edit.replacing, 1) + 10
            ],
            "becomes": changed[max(0, edit.at - 10) : edit.at + len(edit.to) + 10],
            "product_length": len(changed),
        },
        "pairs": pairs,
        # A post-amplification protocol is returned only when somebody chose
        # one. A design with no selection is still useful, but it must not
        # pretend that parental-template removal or clone recovery was chosen.
        **(
            {
                "protocol": {
                    "selection": "NEB Q5 Site-Directed Mutagenesis Kit E0554",
                    "source_identity": "NEB manualE0554",
                    "source_revision": "Version 2.0_7/20",
                    "source_revision_date_precision": "month",
                    "topology": "back-to-back/non-overlapping exponential whole-plasmid PCR",
                    "pcr": {
                        "reaction_volume_uL": 25,
                        "primer_final_uM_each": 0.5,
                        "template_ng_total": {"min": 1, "max": 25},
                        "cycles": 25,
                        "initial_denaturation": {"temperature_c": 98, "seconds": 30},
                        "denaturation": {"temperature_c": 98, "seconds": 10},
                        "annealing": {
                            "temperature_c": {"min": 50, "max": 72},
                            "seconds": {"min": 10, "max": 30},
                            "authority": "NEBaseChanger/Q5-specific; not inferred from PCRStudio screening Tm",
                        },
                        "extension": {
                            "temperature_c": 72,
                            "seconds_per_kb": {"min": 20, "max": 30},
                        },
                        "final_extension": {"temperature_c": 72, "seconds": 120},
                    },
                    "kld": {
                        "pcr_product_uL": 1,
                        "buffer_2x_uL": 5,
                        "enzyme_mix_10x_uL": 1,
                        "water_uL": 3,
                        "room_temperature_minutes": 5,
                    },
                    "note": (
                        "Named Q5/E0554 branch only. Confirm the current kit revision and use "
                        "NEBaseChanger or a gradient for annealing temperature. Classical QuikChange "
                        "uses a different primer architecture and is not approximated here."
                    ),
                }
            }
            if pairs and post_amplification_protocol != "not-selected"
            else {}
        ),
        "workflow_evidence": evidence_block(request.get("workflow_evidence")),
        "why_nothing": (
            ""
            if pairs
            else why_none(
                chosen.target.sequence,
                edit,
                conditions=reaction,
            )
        ),
        "orderability": orderability,
        "order_sheet": [
            entry
            for index, one in enumerate(pairs, start=1)
            for entry in (
                {
                    "name": f"{name}_{index}F",
                    "sequence": one["forward"]["sequence"],
                    "annealing_sequence": one["forward"]["annealing_sequence"],
                    "tail_sequence": one["forward"]["tail_sequence"],
                    "kind": "primer",
                    "length": one["forward"]["length"],
                    "gc_percent": one["forward"]["gc_percent"],
                    "tm": one["forward"]["tm"],
                    "note": f"Carries the edit: {edit.describe()}.",
                },
                {
                    "name": f"{name}_{index}R",
                    "sequence": one["reverse"]["sequence"],
                    "annealing_sequence": one["reverse"]["annealing_sequence"],
                    "tail_sequence": one["reverse"]["tail_sequence"],
                    "kind": "primer",
                    "length": one["reverse"]["length"],
                    "gc_percent": one["reverse"]["gc_percent"],
                    "tm": one["reverse"]["tm"],
                },
            )
        ],
    }
