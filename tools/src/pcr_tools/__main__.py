"""One JSON object in on stdin, one JSON object out on stdout.

    echo '{"sequences": ["GTAAAACGACGGCCAGT"]}' | python -m pcr_tools thermo

Failures come back as `{"error": {"kind": ..., "detail": ...}}` with a non-zero
exit code, so the Rust side branches on `kind` rather than parsing prose. The
vocabulary matches `pcr_core::CoreError` on purpose.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from typing import Any

from . import rt, tail_5p
from .align import AlignError, align, aligned_to_dict
from .align import available as aligners_available
from .consensus import ConsensusError, consensus_to_dict
from .consensus import build as build_consensus
from .design import Constraints, design, result_to_dict
from .discriminate import DiscriminationError
from .discriminate import run as discriminate_run
from .external_validation import validate_result
from .fetch import FetchError, fetch, parse_fasta, records_to_dict
from .intake import IntakeError
from .ipc import IpcError, RequestEnvelope, failure as ipc_failure, parse_request, success as ipc_success
from .inverse import InverseError
from .inverse import run as inverse_run
from .junction import JunctionError
from .junction import run as junction_run
from .loop_set import LoopSetError
from .loop_set import run as loop_set_run
from .multiplex import MultiplexError
from .multiplex import run as multiplex_run
from .mutagenic import MutagenesisError
from .mutagenic import run as mutagenic_run
from .nested import NestedError
from .nested import run as nested_run
from .orchestrator import orchestrate
from .fingerprints import toolchain_fingerprint
from .method_fidelity import active_for_run as method_fidelity_for_run, context_references as method_fidelity_context_references, enforce_scientific_strict as enforce_method_fidelity, references_for_module as method_fidelity_references_for_module, registry_identity as method_fidelity_registry_identity
from .scientific_authority import for_module as scientific_authorities_for_module
from .pipeline import MAX_PAIRS
from .pipeline import run as run_pipeline
from .presets import Cycling, fields_for, polymerases_to_dict, purposes_to_dict
from .probe import ProbeError
from .probe import run as probe_run
from .provenance import provenance
from .restriction import (
    RestrictionError,
    choice_to_dict,
    choose_enzyme,
)
from .runtime_contract import (
    COMMAND_TO_ENGINE,
    CONTRACT_VERSION,
    COORDINATE_CONTRACT,
    ENGINE_BINDINGS,
    MODULE_TO_ENGINE,
    assay_identity,
    engine_contract,
    module_contract,
    resolved_parameters,
    validate_required_context,
)
from .scientific_integrity import (
    enforce_polymerase_identity,
    enforce_reaction_overrides,
    require_named_assay,
)
from .settings import how_many_from
from .single import SinglePrimerError
from .single import run as single_run
from .specificity import BackgroundTooLarge
from .thermo import DEFAULT_CONDITIONS, SequenceError, analyse, pair_dimer, report_to_dict
from .tiling import TilingError
from .tiling import run as tiling_run
from .tool_runtime import (
    ToolRuntimeError,
    require_engine_toolchain,
    toolchain_mode,
    toolchain_snapshot,
)
from .universal import (
    AlignmentError,
    limits_from_request,
)
from .universal import (
    Limits as UniversalLimits,
)
from .universal import (
    design as design_universal,
)
from .universal_panel import (
    CONSENSUS_POLICIES,
    FORMULATION_MODES,
    alternative_alignment_evidence,
    coverage_evidence,
    formulation_for_pair,
    panel_qc,
    parse_panel_metadata,
    scan_nontarget_pair,
    split_pool_alternative,
    amplicon_informativeness,
)
from .workflow_evidence import evidence_block
from .validate import ValidationError
from .validate import run as validate_run
from .vectors import (
    BY_NAME,
    UNIVERSAL,
    check_against,
    partner_window,
    placement_to_dict,
)

COMMANDS = (
    "thermo",
    "design",
    "run",
    "presets",
    "fetch",
    "consensus",
    "align",
    "aligners",
    "universal",
    "universal_presets",
    "nested",
    "inverse",
    "multiplex",
    "vector_primers",
    "enzymes",
    "check",
    "probe",
    "single",
    "mutagenic",
    "tiling",
    "junction",
    "discriminate",
    "loop_set",
    "toolchain",
)

#: The most sequence one oligo or template may carry.
#:
#: More than a few million characters and the request wants a job rather than a
#: request; refusing it by name beats spending minutes proving how slow it is.
MAX_REQUEST_SEQUENCE_CHARS = 4_000_000


def _fail(kind: str, detail: str, request_id: str = "unbound") -> int:
    json.dump(ipc_failure(request_id, kind, detail), sys.stdout)
    sys.stdout.write("\n")
    return 1


def run_thermo(request: dict[str, Any]) -> dict[str, Any]:
    """Measure oligos on their own, and optionally against each other."""
    sequences = request.get("sequences") or []
    if not isinstance(sequences, list) or not sequences:
        raise SequenceError("`sequences` must be a non-empty list of oligos")
    for sequence in sequences:
        if len(sequence) > MAX_REQUEST_SEQUENCE_CHARS:
            raise SequenceError(
                f"{len(sequence):,} characters in one oligo, and this measures "
                f"up to {MAX_REQUEST_SEQUENCE_CHARS:,}."
            )

    conditions = request.get("conditions") or {}
    unknown = sorted(set(conditions) - set(DEFAULT_CONDITIONS))
    if unknown:
        raise ValueError(f"unknown reaction condition(s): {', '.join(unknown)}")
    answer: dict[str, Any] = {
        "oligos": [report_to_dict(analyse(s, **conditions)) for s in sequences]
    }
    if len(sequences) == 2:
        structure = pair_dimer(sequences[0], sequences[1], **conditions)
        answer["cross_dimer"] = {
            "dg": structure.dg,
            "tm": structure.tm,
            "found": structure.found,
        }
    return answer


def run_design(request: dict[str, Any]) -> dict[str, Any]:
    """Generate distinct candidate pairs for a template."""
    template = request.get("template")
    if not isinstance(template, str):
        raise SequenceError("`template` must be a DNA sequence")
    if len(template) > MAX_REQUEST_SEQUENCE_CHARS:
        raise SequenceError(
            f"{len(template):,} characters arrived, and this designs up to "
            f"{MAX_REQUEST_SEQUENCE_CHARS:,}."
        )

    supplied = request.get("constraints") or {}
    unknown = sorted(set(supplied) - set(Constraints.__dataclass_fields__))
    if unknown:
        raise SequenceError(f"unknown constraint(s): {', '.join(unknown)}")

    return result_to_dict(
        design(
            template,
            target_start=request.get("target_start"),
            target_length=request.get("target_length"),
            constraints=Constraints(**supplied),
            conditions=request.get("conditions"),
            how_many=how_many_from(request, most=MAX_PAIRS),
        )
    )


def run_presets(_request: dict[str, Any]) -> dict[str, Any]:
    """What the form needs to offer, so it does not restate any of it."""
    return {
        "polymerases": polymerases_to_dict(),
        "purposes": purposes_to_dict(),
        "constraints": {
            name: field.default for name, field in Constraints.__dataclass_fields__.items()
        },
        # Published so a profile that overrides part of the thermal programme
        # can be checked against what this worker actually programmes, rather
        # than against a second copy of the list kept somewhere else.
        "cycling": sorted(Cycling.__dataclass_fields__),
        "fields": fields_for(
            {name: field.default for name, field in Constraints.__dataclass_fields__.items()}
        ),
    }


def run_fetch(request: dict[str, Any]) -> dict[str, Any]:
    """Get one or more records from NCBI by accession."""
    email = str(request.get("email") or "")
    api_key = str(request.get("apiKey") or "")
    return records_to_dict(fetch(request.get("accessions") or "", email=email, api_key=api_key))


def run_universal_presets(_request: dict[str, Any]) -> dict[str, Any]:
    """What a degenerate design form needs to offer."""
    return {
        "polymerases": polymerases_to_dict(),
        "purposes": [],
        "constraints": {
            name: field.default for name, field in UniversalLimits.__dataclass_fields__.items()
        },
        "fields": fields_for(
            {name: field.default for name, field in UniversalLimits.__dataclass_fields__.items()}
        ),
    }


def run_aligners(_request: dict[str, Any]) -> dict[str, Any]:
    """Which aligners the current host can use, so a form knows what to offer."""
    return aligners_available()


def run_align(request: dict[str, Any]) -> dict[str, Any]:
    """Align sequences with whatever standard aligner is installed."""
    text = request.get("fasta")
    if not isinstance(text, str) or not text.strip():
        raise AlignError("`fasta` must hold the sequences to align")
    return aligned_to_dict(align(text))


def run_universal(request: dict[str, Any]) -> dict[str, Any]:
    """Design degenerate pairs covering every sequence in an alignment."""
    from .presets import Reaction, polymerase

    text = request.get("template")
    if not isinstance(text, str) or not text.strip():
        raise AlignmentError("`template` must hold the aligned sequences")

    lowercase_masking = request.get("lowercase_masking")
    if lowercase_masking is not None and not isinstance(lowercase_masking, bool):
        raise AlignmentError("`lowercase_masking` must be true or false")
    has_lowercase = any(base.islower() for base in text if base.isalpha())
    if has_lowercase and lowercase_masking is None:
        raise AlignmentError(
            "PCRStudio does not infer whether lowercase alignment bases are masking or formatting in any policy mode. "
            "Set `lowercase_masking=false` to normalise case. The universal-primer engine does not currently model lowercase masking inside an MSA."
        )
    if lowercase_masking is True:
        raise AlignmentError(
            "Universal-primer design does not currently implement lowercase soft-mask semantics across an MSA. "
            "Use explicit alignment curation/exclusions or set `lowercase_masking=false` only when case is formatting."
        )

    assay = request.get("assay") or {}
    if not isinstance(assay, dict):
        raise ValueError("`assay` must be an object")
    defaults = assay.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("`assay.defaults` must be an object")
    assay_id = require_named_assay(request, command="universal")
    expected_preset = polymerase(defaults.get("polymerase"))
    preset = polymerase(request.get("polymerase") or defaults.get("polymerase"))
    raw_allowed = defaults.get("allowedPolymerases") or []
    if not isinstance(raw_allowed, list) or not all(isinstance(item, str) for item in raw_allowed):
        raise ValueError("`assay.defaults.allowedPolymerases` must be a list of preset ids")
    enforce_polymerase_identity(
        preset.id,
        expected_preset.id,
        assay_id=assay_id,
        allowed=raw_allowed,
    )
    overrides = request.get("conditions") or {}
    if not isinstance(overrides, dict):
        raise ValueError("`conditions` must be an object")
    baseline_conditions = preset.reaction.as_conditions()
    enforce_reaction_overrides(overrides, baseline_conditions, context=f"assay `{assay_id}`")
    reaction = Reaction(**{**baseline_conditions, **overrides})
    reaction.validate()

    assay_id = str(assay.get("id") or "")
    if assay_id == "universal-primers" and request.get("alignment_mode") in (None, ""):
        raise AlignmentError(
            "universal-primers requires explicit `alignment_mode`: auto or prealigned; alignment authority is not inferred."
        )
    alignment_mode = str(request.get("alignment_mode") or "auto")
    if alignment_mode not in {"auto", "prealigned"}:
        raise AlignmentError("`alignment_mode` must be `auto` or `prealigned`")

    alignment_run: dict[str, Any]
    if alignment_mode == "auto":
        aligned = align(text)
        aligned_payload = aligned_to_dict(aligned)
        records = parse_fasta(aligned_payload["fasta"])
        alignment_run = {
            "mode": "auto",
            "tool": aligned_payload["tool"],
            "tool_version": aligned_payload["tool_version"],
            "tool_role": aligned_payload["tool_role"],
            "warnings": list(aligned_payload.get("warnings") or []),
            "depth": aligned_payload["depth"],
            "width": aligned_payload["width"],
            "input_record_count": len(records),
            "decision": "The submitted family was aligned by the declared alignment backend before universal-primer design.",
        }
    else:
        records = parse_fasta(text)
        widths = {len(record.sequence) for record in records}
        if len(widths) != 1:
            raise AlignmentError(
                "`prealigned` mode requires every FASTA row to have the same alignment width; "
                "choose `auto` to align unaligned inputs."
            )
        alignment_run = {
            "mode": "prealigned",
            "tool": "caller-supplied-alignment",
            "tool_version": "not-applicable",
            "tool_role": "INPUT",
            "warnings": [
                "PCRStudio validated row width and sequence symbols but did not independently reconstruct the supplied alignment."
            ],
            "depth": len(records),
            "width": next(iter(widths), 0),
            "input_record_count": len(records),
            "decision": "Caller-supplied alignment retained as the explicit design input.",
        }

    # Resolve panel truth before candidate generation.  These names/weights are
    # scientific inputs to weighted/stratified consensus, not post-hoc labels.
    names = [record.id for record in records]
    rows = [record.sequence for record in records]
    panel_metadata = parse_panel_metadata(request.get("panel_metadata"), names)
    consensus_policy = str(request.get("consensus_policy") or "strict-all-members")
    if consensus_policy not in CONSENSUS_POLICIES:
        raise ValueError("consensus_policy must be one of: " + ", ".join(CONSENSUS_POLICIES))

    # Resolve the declared panel policy before candidate generation so weighted
    # and stratified consensus decisions are part of the scientific design, not
    # a post-hoc reporting decoration. User weights remain explicit panel
    # weights; PCRStudio never interprets them as population prevalence.
    # names/rows/panel metadata/policy were resolved before design above and
    # are reused here for evidence so the report exactly matches the design
    # semantics.
    design_weights = {name: float(panel_metadata.get(name, {}).get("weight", 1.0)) for name in names}
    design_strata = {name: str(panel_metadata.get(name, {}).get("stratum") or "") for name in names}
    if consensus_policy == "stratified" and any(not value for value in design_strata.values()):
        raise ValueError("stratified consensus_policy requires panel_metadata.stratum for every FASTA record")

    resolved_limits = limits_from_request(request)
    answer = design_universal(
        [(record.id, record.sequence) for record in records],
        limits=resolved_limits,
        reaction=reaction,
        how_many=int(request.get("how_many", 5)),
        consensus_policy=consensus_policy,
        weights=design_weights if consensus_policy in {"weighted", "stratified"} else None,
        strata=design_strata if consensus_policy == "stratified" else None,
    )
    answer["alignment_pipeline"] = alignment_run
    answer["reaction"] = {
        "polymerase": preset.id,
        "polymerase_name": preset.name,
        **reaction.as_conditions(),
        "dna_conc_role": "effective-pool-reference-for-nominal-equal-member-tm-model",
    }
    answer["degenerate_thermodynamics"] = {
        "member_concentration_model": "nominal-equal-member-effective-concentration",
        "pool_effective_dna_conc_nM": reaction.dna_conc,
        "formula": "member_effective_dna_conc_nM = pool_effective_dna_conc_nM / primer_degeneracy",
        "authority": "explicit-screening-assumption-not-measured-formulation",
        "note": (
            "Primer3 PRIMER_DNA_CONC is an empirical effective concentration for each annealing oligo. "
            "For a degenerate IUPAC pool PCRStudio divides the declared effective pool reference equally "
            "among concrete members for Tm screening. Mixed-base synthesis can deviate from equal member "
            "abundance, so these Tm values are model-conditioned evidence rather than measured pool composition."
        ),
    }
    answer["provenance"] = provenance(reaction.as_conditions())
    answer["constraints"] = asdict(resolved_limits)
    answer["assay"] = {
        "id": str(assay.get("id", "")),
        "name": str(assay.get("name", "")),
        "engine": str(assay.get("engine", "consensus-pair")),
        "status": str(assay.get("status", "")),
        "profile_authority": dict(assay.get("profileAuthority") or {}),
        "chemistry_family": str(defaults.get("chemistryFamily") or ""),
        "defaults": dict(defaults.get("constraints") or {}),
        "purposes": list(defaults.get("purposes") or []),
        "modifiers": list(assay.get("modifiers") or []),
        "requires": list(assay.get("requires") or []),
        "enzyme": list(assay.get("enzyme") or []),
        "overruled": [],
    }
    # A property of the run rather than of a pair. `None` says the question was
    # never put — this assay's page does not ask it.
    answer["reverse_transcription"] = (
        rt.block(polymerase=preset.name) if rt.wanted(request) else None
    )

    # ── Panel / formulation / bounded specificity evidence ──────────────────
    # These are explicit requested semantics. They do not silently turn a
    # finite alignment into a population-wide universality claim.
    formulation_mode = str(request.get("formulation_mode") or "mixed-base-synthesis")
    if formulation_mode not in FORMULATION_MODES:
        raise ValueError("formulation_mode must be one of: " + ", ".join(FORMULATION_MODES))
    total_nm_raw = request.get("formulation_total_concentration_nm")
    if total_nm_raw in (None, ""):
        total_nm = None
    else:
        if isinstance(total_nm_raw, bool) or not isinstance(total_nm_raw, (int, float)):
            raise ValueError("formulation_total_concentration_nm must be numeric")
        total_nm = float(total_nm_raw)
        if total_nm <= 0:
            raise ValueError("formulation_total_concentration_nm must be positive")

    answer["panel"] = {
        "policy": consensus_policy,
        "qc": panel_qc(list(zip(names, rows, strict=True)), panel_metadata),
        "metadata": panel_metadata,
        "coverage_claim": "observed-supplied-panel-only",
        "population_inference": "not-established",
    }
    for pair in answer.get("pairs", []):
        pair["coverage_evidence"] = coverage_evidence(pair, names, rows, panel_metadata)
        pair["formulation"] = formulation_for_pair(pair, formulation_mode, total_nm)
        pair["split_pool_alternative"] = split_pool_alternative(pair, names, rows)
        pair["amplicon_informativeness"] = amplicon_informativeness(pair, names, rows)

    nontarget_text = request.get("nontarget")
    if nontarget_text not in (None, ""):
        if not isinstance(nontarget_text, str):
            raise ValueError("nontarget must be FASTA text")
        nontarget_records = parse_fasta(nontarget_text)
        for pair in answer.get("pairs", []):
            pair["nontarget_evidence"] = scan_nontarget_pair(
                pair,
                [(record.id, record.sequence) for record in nontarget_records],
                resolved_limits.product_min,
                resolved_limits.product_max,
            )
        answer["nontarget_panel"] = {
            "records": [record.id for record in nontarget_records],
            "count": len(nontarget_records),
            "claim_boundary": "finite user-supplied non-target panel; not global specificity",
        }
    else:
        answer["nontarget_panel"] = None

    alternative_text = request.get("alternative_alignment")
    if alternative_text not in (None, ""):
        if not isinstance(alternative_text, str):
            raise ValueError("alternative_alignment must be FASTA text")
        alt_records = parse_fasta(alternative_text)
        for pair in answer.get("pairs", []):
            pair["alignment_sensitivity"] = alternative_alignment_evidence(
                pair, [(record.id, record.sequence) for record in alt_records]
            )
        answer["alignment_audit"] = {
            "backend": str(request.get("alignment_audit_backend") or "caller-supplied-alternative"),
            "record_count": len(alt_records),
            "role": "VALIDATOR",
            "primary_ranking_mutated": False,
        }
    else:
        answer["alignment_audit"] = None

    # ── What goes in front of every oligo ───────────────────────────────────
    #
    # A degenerate pair is usually read by Sanger off a universal primer, so
    # both oligos carry M13 or similar. Which one is decided by the sequencing
    # service, not by anything derivable from an alignment, so it is asked for
    # rather than chosen — and it is put on the ordered sequence rather than
    # only mentioned, because the sequence in this result is what gets ordered.
    asked = request.get("tails") or {}
    forward = tail_5p.clean(asked.get("forward"))
    reverse = tail_5p.clean(asked.get("reverse"))
    answer["tails"] = None
    if (forward or reverse) and answer.get("pairs"):
        first = answer["pairs"][0]
        conditions = reaction.as_conditions()
        answer["tails"] = {
            "forward": (
                tail_5p.describe(forward, first["left"]["sequence"], "forward", **conditions)
                if forward
                else None
            ),
            "reverse": (
                tail_5p.describe(reverse, first["right"]["sequence"], "reverse", **conditions)
                if reverse
                else None
            ),
        }
        for pair in answer["pairs"]:
            # The temperatures stay the annealing halves': a degenerate pool is
            # already the coolest-member problem, and adding thirty bases that
            # bind nothing in round one to that calculation would raise every
            # number in this result by about ten degrees.
            pair["left"]["sequence"] = forward + pair["left"]["sequence"]
            pair["right"]["sequence"] = reverse + pair["right"]["sequence"]

    workflow = evidence_block(request.get("workflow_evidence"))
    if workflow is not None:
        answer["workflow_evidence"] = workflow

    answer["order_sheet"] = [
        {
            "name": f"universal_{index}{role}",
            "sequence": oligo["sequence"],
            "annealing_sequence": oligo["sequence"][len(tail):] if tail else oligo["sequence"],
            "tail_sequence": tail,
            "kind": "primer",
            "length": len(oligo["sequence"]),
            "gc_percent": oligo.get("gc_percent", oligo.get("gc_min", 0.0)),
            "tm": oligo.get("tm_min", oligo.get("tm", 0.0)),
            "note": (
                "The ordered molecule carries a 5-prime sequencing tail; specificity is evaluated on the annealing core."
                if tail else ""
            ),
        }
        for index, pair in enumerate(answer.get("pairs") or [], start=1)
        for role, oligo, tail in (("F", pair["left"], forward), ("R", pair["right"], reverse))
    ]

    return answer


def run_consensus(request: dict[str, Any]) -> dict[str, Any]:
    """Collapse an alignment into one sequence with IUPAC codes."""
    text = request.get("fasta")
    if not isinstance(text, str) or not text.strip():
        raise ConsensusError("`fasta` must hold the sequences to collapse")

    records = parse_fasta(text)
    if len(records) < 2:
        raise ConsensusError(
            f"A consensus needs at least two sequences. This input holds {len(records)}."
        )
    return consensus_to_dict(
        build_consensus([r.sequence for r in records], names=[r.id for r in records])
    )


def run_check(request: dict[str, Any]) -> dict[str, Any]:
    """Measure a pair somebody already has against the template they have."""
    return validate_run(request)


def run_vector_primers(request: dict[str, Any]) -> dict[str, Any]:
    """The universal primers, and where they really sit in a given vector.

    Without a vector this is the catalogue. With one it is an answer about that
    vector, which is the only kind worth acting on -- a primer sitting once in
    the published pUC19 may sit twice in the derivative on somebody's bench.
    """
    vector = request.get("vector")
    conditions = request.get("conditions") or {}
    if not isinstance(vector, str) or not vector.strip():
        return {
            "checked_against": "",
            "primers": [
                {
                    "name": primer.name,
                    "sequence": primer.sequence,
                    "reads": primer.reads,
                    "family": primer.family,
                    "tm": primer.melting_temperature(**conditions),
                    "note": primer.note,
                }
                for primer in UNIVERSAL
            ],
            "note": (
                "No vector was given, so this is the list rather than an answer. "
                "Send the sequence you actually have and each primer will be "
                "placed in it."
            ),
        }

    placed = check_against(vector, **conditions)
    return {
        "checked_against": str(request.get("vector_name") or "the sequence given"),
        "primers": [placement_to_dict(place) for place in placed],
        "partner_windows": {
            place.name: partner_window(BY_NAME[place.name], **conditions)
            for place in placed
            if place.usable
        },
        "note": (
            f"{sum(1 for p in placed if p.usable)} of {len(placed)} sit in exactly "
            "one place in this vector. The rest are listed with the reason, "
            "because a primer that is absent and one that is there twice are "
            "different problems."
        ),
    }


def run_enzymes(request: dict[str, Any]) -> dict[str, Any]:
    """Every enzyme ranked for the question being asked of this sequence.

    Distinct questions share this command because they share a catalogue:
    standard two-flank inverse PCR needs enzymes absent from the known anchor,
    cloning has its own absent-from-insert question, and `open-once` is retained
    only for a separately explicit one-cut workflow. `purpose` is required.
    """
    sequence = request.get("template")
    if not isinstance(sequence, str) or not sequence.strip():
        raise RestrictionError("`template` must hold the region to look for sites in")
    background = request.get("background")
    purpose = request.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip():
        raise RestrictionError("`purpose` is required; enzyme ranking never infers the scientific question")
    return {
        "purpose": purpose,
        "enzymes": [
            choice_to_dict(choice)
            for choice in choose_enzyme(
                sequence,
                background=background if isinstance(background, str) else None,
                purpose=str(purpose),
            )
        ],
    }


def _multiplex_assay_identity(request: dict[str, Any]) -> tuple[str, str]:
    """Resolve one shared module identity from the per-target assay contracts.

    The public multiplex HTTP route injects the canonical assay into every
    target, not at the outer request level. Looking only at the outer object
    therefore collapses a Standard/Colony/Species multiplex into a generic
    flanking-pair run and loses module-specific toolchain/runtime provenance.
    Mixed target identities are refused here before an expensive panel search;
    target-level scientific context is still validated by ``multiplex.run``.
    """
    targets = request.get("targets")
    identities: list[tuple[str, str]] = []
    if isinstance(targets, list) and targets:
        for index, target in enumerate(targets, start=1):
            if not isinstance(target, dict):
                raise ValueError(f"multiplex target {index} must be an object with a canonical assay identity")
            assay = target.get("assay")
            if not isinstance(assay, dict):
                raise ValueError(
                    f"multiplex target {index} is missing its canonical assay/module identity; "
                    "do not fall back to generic flanking-pair provenance"
                )
            module_id, engine_id = assay_identity(target, "run")
            if not module_id:
                raise ValueError(f"multiplex target {index} has an unresolved assay/module identity")
            identities.append((module_id, engine_id or "flanking-pair"))
    if not identities:
        module_id, engine_id = assay_identity(request, "run")
        return module_id, engine_id or "flanking-pair"
    first = identities[0]
    if any(identity != first for identity in identities[1:]):
        raise ValueError(
            "Every target in one multiplex request must declare the same assay/module identity; "
            "split different assay modules into separate multiplex requests."
        )
    return first


def _multiplex_resolved_parameters(
    request: dict[str, Any], answer: dict[str, Any]
) -> dict[str, Any]:
    """Preserve policy-resolved parameter provenance for every multiplex target.

    Multiplex keeps assay/default authority inside each target. The outer
    request therefore cannot explain user-vs-profile constraint resolution on
    its own. Resolve each target against the shared reaction and that target's
    emitted constraint envelope, then expose one shared block only when the
    worker explicitly says the envelopes are identical.
    """
    request_targets = request.get("targets")
    result_targets = answer.get("targets")
    if not isinstance(request_targets, list) or not isinstance(result_targets, list):
        return resolved_parameters(request, answer)

    scope = str(answer.get("constraint_scope") or "")
    if scope not in {"shared", "per-target"}:
        raise ValueError(
            "multiplex result is missing a valid constraint_scope; refusing to invent shared provenance"
        )

    reaction_value = answer.get("reaction")
    if not isinstance(reaction_value, dict):
        raise ValueError(
            "multiplex result is missing its shared reaction contract; refusing to invent runtime provenance"
        )

    per_target: list[dict[str, Any]] = []
    shared_reaction: dict[str, Any] | None = None
    shared_constraints: dict[str, Any] | None = None
    for index, (target_request, target_result) in enumerate(
        zip(request_targets, result_targets, strict=True), start=1
    ):
        if not isinstance(target_request, dict) or not isinstance(target_result, dict):
            raise ValueError(
                f"multiplex target/result provenance row {index} is not an object; refusing partial provenance"
            )
        constraints_value = target_result.get("constraints")
        if not isinstance(constraints_value, dict):
            raise ValueError(
                f"multiplex target/result provenance row {index} is missing its resolved constraints"
            )
        target_name = target_result.get("name")
        if not isinstance(target_name, str) or not target_name.strip():
            raise ValueError(
                f"multiplex target/result provenance row {index} is missing its stable target name"
            )
        resolved = resolved_parameters(
            target_request,
            {
                "reaction": reaction_value,
                "constraints": constraints_value,
            },
        )
        reaction = resolved.get("reaction") if isinstance(resolved.get("reaction"), dict) else {}
        constraints = resolved.get("constraints") if isinstance(resolved.get("constraints"), dict) else {}
        if shared_reaction is None:
            shared_reaction = dict(reaction)
        elif reaction != shared_reaction:
            raise ValueError(
                "multiplex runtime-parameter provenance diverged across targets despite a shared reaction contract"
            )
        if shared_constraints is None:
            shared_constraints = dict(constraints)
        elif constraints != shared_constraints:
            shared_constraints = {}
        per_target.append(
            {
                "name": target_name.strip(),
                "constraints": constraints,
            }
        )

    return {
        "reaction": shared_reaction or {},
        "constraints": shared_constraints if scope == "shared" and shared_constraints is not None else {},
        "constraint_scope": scope,
        "per_target_constraints": per_target,
    }


def run_multiplex(request: dict[str, Any]) -> dict[str, Any]:
    """Several targets chosen to share one or more tubes, then independently audited."""
    module_id, engine_id = _multiplex_assay_identity(request)
    require_engine_toolchain(engine_id, module_id, request)
    answer = multiplex_run(request)
    answer["runtime_contract"] = engine_contract(engine_id, module_id)
    answer["module_contract"] = module_contract(module_id) if module_id else {}
    answer["runtime_contract"]["resolved_parameters"] = _multiplex_resolved_parameters(request, answer)
    answer["toolchain_validation"] = validate_result(
        command="multiplex",
        request=request,
        result=answer,
        engine_id=engine_id,
        module_id=module_id,
    )
    validation = answer["toolchain_validation"]
    selected_oligos = int(validation.get("selected_oligos") or 0)
    computational_complete = selected_oligos > 0 and bool(answer.get("tubes"))
    if (
        toolchain_mode() == "strict"
        and computational_complete
        and validation["status"] in {"verification-incomplete", "validator-error", "evidence-collected-limited"}
    ):
        raise ToolRuntimeError(
            "multiplex design refused: strict final-panel validation did not complete; repair the configured tools/databases and retry"
        )
    answer["verification"] = {
        "status": validation["status"] if computational_complete else "computational-incomplete",
        "computational_design_complete": computational_complete,
        "external_evidence_complete": (
            validation["status"] in {"evidence-collected", "not-applicable"}
            and validation.get("interpretation_complete") is True
        ),
        "wet_lab_validated": False,
        "selected_oligos": selected_oligos,
        "note": "The selected multiplex panel is audited after set selection; PrimerPooler is grouped by actual tube/pool, while MFEprimer/BLAST assess binding evidence independently.",
    }
    provenance_block = answer.setdefault("provenance", {})
    if not isinstance(provenance_block, dict):
        raise ValueError("multiplex result provenance must be an object")
    active_methods = method_fidelity_for_run(module_id, "multiplex", request, answer)
    enforce_method_fidelity(active_methods, context=f"{module_id}:multiplex")
    provenance_block["scientific_authorities"] = scientific_authorities_for_module(module_id)
    provenance_block["method_fidelity"] = active_methods
    provenance_block["method_fidelity_references"] = method_fidelity_references_for_module(module_id) + method_fidelity_context_references("generic-multiplex")
    provenance_block["method_fidelity_scope"] = "active-run-methods-plus-separate-reference-authorities"
    provenance_block["method_fidelity_registry"] = method_fidelity_registry_identity()
    provenance_block["toolchain_fingerprint"] = toolchain_fingerprint(answer)
    return answer



def run_toolchain(_request: dict[str, Any]) -> dict[str, Any]:
    """Native Linux deployment preflight without starting a design.

    This reports identities only. It never installs a tool, builds a database,
    downloads anything or mutates the host.
    """
    return {
        "runtime_contract_version": CONTRACT_VERSION,
        "coordinate_contract": dict(COORDINATE_CONTRACT),
        "module_count": len(MODULE_TO_ENGINE),
        "engine_count": len(ENGINE_BINDINGS),
        "toolchain": toolchain_snapshot(),
    }

def run_nested(request: dict[str, Any]) -> dict[str, Any]:
    """Two rounds, the second reading inside the first."""
    return nested_run(request)


def run_inverse(request: dict[str, Any]) -> dict[str, Any]:
    """Primers reading outward, into sequence the caller does not have."""
    return inverse_run(request)


def run_probe(request: dict[str, Any]) -> dict[str, Any]:
    """A pair, and a third oligo between them that reports."""
    return probe_run(request)


def run_single(request: dict[str, Any]) -> dict[str, Any]:
    """One primer, reading into something rather than across it."""
    return single_run(request)


def run_mutagenic(request: dict[str, Any]) -> dict[str, Any]:
    """A pair that deliberately disagrees with the template, to change it."""
    return mutagenic_run(request)


def run_tiling(request: dict[str, Any]) -> dict[str, Any]:
    """Overlapping amplicons covering something too long for one reaction."""
    return tiling_run(request)


def run_junction(request: dict[str, Any]) -> dict[str, Any]:
    """Primers carrying the joins, for assembling fragments without ligation."""
    return junction_run(request)


def run_discriminate(request: dict[str, Any]) -> dict[str, Any]:
    """A pair that amplifies one allele and not the other."""
    return discriminate_run(request)


def run_loop_set(request: dict[str, Any]) -> dict[str, Any]:
    """Six oligos over eight regions, for amplification at one temperature."""
    return loop_set_run(request)


HANDLERS = {
    "thermo": run_thermo,
    "design": run_design,
    "run": run_pipeline,
    "presets": run_presets,
    "fetch": run_fetch,
    "consensus": run_consensus,
    "align": run_align,
    "aligners": run_aligners,
    "universal": run_universal,
    "universal_presets": run_universal_presets,
    "nested": run_nested,
    "inverse": run_inverse,
    "multiplex": run_multiplex,
    "vector_primers": run_vector_primers,
    "enzymes": run_enzymes,
    "check": run_check,
    "probe": run_probe,
    "single": run_single,
    "mutagenic": run_mutagenic,
    "tiling": run_tiling,
    "junction": run_junction,
    "discriminate": run_discriminate,
    "loop_set": run_loop_set,
    "toolchain": run_toolchain,
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in COMMANDS:
        return _fail("invalidRequest", f"expected one of: {', '.join(COMMANDS)}")

    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        return _fail("invalidRequest", f"stdin was not valid JSON: {error}")

    envelope: RequestEnvelope | None = None
    request_id = "unbound"
    try:
        envelope = parse_request(raw, argv[1])
        request = envelope.payload
        request_id = envelope.request_id
    except IpcError as error:
        # A narrow escape hatch exists only for repository debugging of old CLI
        # fixtures. Production Rust never sets it, so an old/unversioned worker
        # caller fails before a scientific handler is reached.
        if os.environ.get("PCRSTUDIO_ALLOW_LEGACY_IPC") == "1" and isinstance(raw, dict):
            request = raw
        else:
            return _fail("invalidRequest", str(error), request_id)

    try:
        answer = (
            orchestrate(argv[1], request, HANDLERS[argv[1]])
            if argv[1] in COMMAND_TO_ENGINE
            else HANDLERS[argv[1]](request)
        )
    except BackgroundTooLarge as error:
        return _fail("backgroundTooLarge", str(error), request_id)
    except AlignError as error:
        return _fail("toolMissing", str(error), request_id)
    except (
        SequenceError,
        IntakeError,
        FetchError,
        ConsensusError,
        AlignmentError,
        NestedError,
        InverseError,
        MultiplexError,
        ProbeError,
        SinglePrimerError,
        MutagenesisError,
        TilingError,
        JunctionError,
        DiscriminationError,
        LoopSetError,
        RestrictionError,
        ValidationError,
        ValueError,
    ) as error:
        return _fail("invalidRequest", str(error), request_id)
    except Exception as error:
        return _fail("toolFailed", f"{type(error).__name__}: {error}", request_id)

    wire_answer: Any = ipc_success(envelope, answer) if envelope is not None else answer
    try:
        encoded = json.dumps(wire_answer)
    except (TypeError, ValueError) as error:
        return _fail("toolFailed", f"the answer could not be encoded as JSON: {error}", request_id)

    try:
        sys.stdout.write(encoded)
        sys.stdout.write("\n")
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
