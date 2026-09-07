"""A pair, and a third oligo that sits between them and reports.

A hydrolysis-probe assay reads fluorescence rather than a band or a dye, so
what is measured is not "was there a product" but "was there *this* product".
The probe is what makes that difference: it binds inside the amplicon, and only
a polymerase copying through that exact stretch releases its signal.

Three things follow, and together they are why this is its own engine.

The probe has to bind before the primers do. It is not extended and it is not
copied — it is destroyed — so it has to already be sitting there when the
polymerase arrives. That means it melts several degrees above the primers, not
alongside them, which is the opposite of every other relationship this project
manages.

Its 5' base may not be a G. The fluorophore is attached there, and a guanine
beside it quenches the reporter. It is a rule about chemistry rather than about
hybridisation, so no thermodynamic measure would ever find it — it comes from
the probe vendors' own design guidelines rather than from anything this project
can compute. What can be checked is whether practice agrees, and it does: the
CDC N1, CDC N2 and E_Sarbeco probes all begin with an adenine.

And the probe's melting temperature has to be computed in the same reaction as
the primers'. That sounds obvious and is exactly what is easy to get wrong:
Primer3 takes the salts for the internal oligo as *separate* parameters, so
sending the reaction to the primers and not to the probe silently computes the
two numbers in two different buffers. Measured here: 66.1 against 74.9 for the
same oligo, 8.8 degrees apart -- larger than the separation the assay depends
on, so it would report a probe melting a degree *below* its own primers as one
melting seven above.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from itertools import groupby
from typing import Any
import hashlib
import json

import primer3

from . import rt, screen
from .accessibility import fold_oligos
from .design import CandidatePair, Constraints, clean_template, pair_at, design as design_pairs
from .intake import target_to_dict
from .presets import thermodynamic_model
from .provenance import provenance
from .registries.authorities import PROBE_AUTHORITY, record as authority_record
from .workflow_evidence import evidence_block
from .mgb_authority import MgbAuthorityError, apply_import as apply_mgb_import, candidates as mgb_candidates, exchange_manifest as mgb_exchange
from .probe_closure import ProbeClosureError, combined_signal, multiplex_interactions, optical_authority
from .scientific_integrity import enforce_constraint_overrides, strict as scientific_strict
from .settings import excluded_from, how_many_from, label, prepare
from .thermo import DEFAULT_CONDITIONS, analyse, report_to_dict


class ProbeError(ValueError):
    """A probe assay that could not be asked for."""


def _max_consecutive_base(sequence: str, base: str) -> int:
    """Return the longest run of one base in a candidate oligo."""
    return max(
        (sum(1 for _ in group) for value, group in groupby(sequence.upper()) if value == base),
        default=0,
    )


#: Low-level/unbound pair-and-probe search heuristic.  It exists so the
#: geometry engine can be tested and benchmarked independently of a commercial
#: chemistry; it is NOT a named-assay validity rule or a bench protocol.  The
#: routed `qpcr-probe` module cannot execute from this offset.
UNBOUND_ENGINE_PROBE_TM_OFFSET_C = 7.0
MGB_PROBE_MIN_NT = 13
MGB_PROBE_MAX_NT = 25
QPCR_MULTIPLEX_SOFTWARE_MAX_TARGETS = 12
QPCR_MULTIPLEX_MAX_PEERS = QPCR_MULTIPLEX_SOFTWARE_MAX_TARGETS - 1
PROFILE_CONSTRAINT_FIELDS = frozenset(Constraints.__dataclass_fields__)
PROFILE_PROBE_RULES = frozenset({"max_consecutive_g"})
PROFILE_PRIMER_RULES = frozenset({"max_gc_last5"})

#: What the probe's 5' base may not be.
#:
#: A guanine beside the fluorophore quenches it. Not a hybridisation rule and
#: not something any thermodynamic measure would find — it is stated by the
#: probe vendors' design guidelines, and the three most-run probe assays in the
#: world all obey it.
FORBIDDEN_FIRST_BASE = "G"

#: The same rule in Primer3's own vocabulary, so it never picks one.
#:
#: `h` is the ambiguity code for "not G". Giving Primer3 the rule beats
#: discarding its answers afterwards: filtering after the fact threw away five
#: of twelve returned probes on the first target tried, and those five had
#: displaced better ones from the list before we ever saw it.
FIVE_PRIME_PATTERN = "hnnnn"

# Named qPCR-probe chemistry is owned by the canonical current authority.  The
# low-level geometry engine below remains usable without a named chemistry for
# research/benchmarking, but routed qPCR Probe execution never invents one.
PROBE_PROTOCOL_ALIASES = {
    "taqman-mgb": "taqman-mgb-reference",  # historical request compatibility
}
PROBE_PROTOCOLS = (
    "not-selected",
    "thermofisher-taqman-conventional",
    "idt-primetime-conventional",
    "taqman-mgb-reference",
    "taqman-mgb",
)


def probe_protocol(named: str | None) -> dict[str, Any] | None:
    """Resolve one chemistry profile from the canonical qPCR-probe authority."""
    selected = str(named or "not-selected")
    selected = PROBE_PROTOCOL_ALIASES.get(selected, selected)
    if selected == "not-selected":
        return None
    if selected not in PROBE_AUTHORITY.get("records", {}):
        raise ProbeError("probe_protocol must be one of: " + ", ".join(PROBE_PROTOCOLS) + ".")
    rec = authority_record(PROBE_AUTHORITY, selected)
    if rec.get("kind") != "hydrolysis-probe-design-profile":
        raise ProbeError(f"`{selected}` is not a hydrolysis-probe design profile.")
    rec["protocol_id"] = selected
    return rec


def _probe_modifications(request: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    """Validate optical/manufacturing fields against the selected chemistry.

    Reporter/quencher identity is manufacturing/readout metadata.  It is not
    allowed to change sequence ranking; the chemistry profile owns only the
    allowed vocabulary and the sequence-design rules.
    """
    reporter = request.get("probe_reporter")
    quencher = request.get("probe_quencher")
    internal = request.get("probe_internal_quencher")
    allowed_reporters = list(protocol.get("reporter_options") or [])
    allowed_quenchers = list(protocol.get("quencher_options") or [])
    if reporter and reporter not in allowed_reporters:
        raise ProbeError(
            f"reporter `{reporter}` is not reviewed for {protocol['protocol_id']}; "
            f"allowed: {', '.join(allowed_reporters) or 'none specified'}"
        )
    if quencher and quencher not in allowed_quenchers:
        raise ProbeError(
            f"quencher `{quencher}` is not reviewed for {protocol['protocol_id']}; "
            f"allowed: {', '.join(allowed_quenchers) or 'none specified'}"
        )
    chemistry = str(protocol.get("chemistry") or "")
    if chemistry != "double-quenched-hydrolysis" and internal:
        raise ProbeError(
            "probe_internal_quencher is only valid for a reviewed double-quenched hydrolysis profile."
        )
    if chemistry == "double-quenched-hydrolysis" and quencher == "ZEN+Iowa Black FQ":
        internal = internal or "ZEN"
        quencher = "Iowa Black FQ"
    return {
        "chemistry": chemistry,
        "reporter": reporter,
        "internal_quencher": internal,
        "quencher": quencher,
        "instrument_profile": request.get("probe_instrument_profile"),
        "decision_impact": "none-on-sequence-ranking",
        "note": (
            "Reporter, quencher and instrument metadata are validated against the selected chemistry "
            "and recorded for ordering/optics; they do not silently alter sequence ranking."
        ),
    }


@dataclass(frozen=True)
class Probe:
    """The third oligo, and where it sits."""

    sequence: str
    at: int
    length: int
    tm: float
    gc_percent: float
    #: How far it is from the forward primer, which must not be zero.
    after_left: int
    #: How much clear of the primers it melts.
    above: float


@dataclass(frozen=True)
class Assay:
    """One pair with its probe."""

    pair: CandidatePair
    probe: Probe
    product_size: int


def design(
    template: str,
    *,
    target_start: int | None = None,
    target_length: int | None = None,
    constraints: Constraints | None = None,
    probe_constraints: Constraints | None = None,
    conditions: dict[str, float] | None = None,
    how_many: int = 5,
    excluded: list[tuple[int, int]] | None = None,
) -> tuple[list[Assay], str]:
    """Pairs with a probe between them, best first.

    Args:
        probe_constraints: What the probe must satisfy, which is not what the
            primers must satisfy: it melts higher, it is usually longer, and it
            may not begin with a guanine.

    Returns:
        The assays, and Primer3's own account of what it rejected.

    Raises:
        ProbeError: for a probe window that could not work with the primers'.
        SequenceError: if the template is not unambiguous DNA.
    """
    sequence = clean_template(template)
    limits = constraints or Constraints()
    limits.validate()

    probe_limits = probe_constraints or Constraints(
        length_min=18,
        length_opt=24,
        length_max=30,
        tm_min=round(limits.tm_min + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
        tm_opt=round(limits.tm_opt + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
        tm_max=round(limits.tm_max + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
        gc_min=30.0,
        gc_max=80.0,
        # A probe is not extended, so a 3'-end rule about extension has nothing
        # to act on.
        gc_clamp=0,
        max_end_gc=5,
        product_min=limits.product_min,
        product_max=limits.product_max,
    )
    probe_limits.validate()

    if probe_limits.tm_min <= limits.tm_max:
        raise ProbeError(
            f"The probe is allowed down to {probe_limits.tm_min} °C and the primers "
            f"up to {limits.tm_max} °C, so a design could come back with a probe "
            "cooler than its own primers. The probe has to be bound before the "
            "polymerase arrives, which means it melts above them rather than "
            "alongside them."
        )

    reaction = {**DEFAULT_CONDITIONS, **(conditions or {})}

    sequence_args: dict[str, Any] = {
        "SEQUENCE_ID": "template",
        "SEQUENCE_TEMPLATE": sequence,
    }
    if target_start is not None and target_length is not None:
        sequence_args["SEQUENCE_TARGET"] = [target_start, target_length]
    if excluded:
        regions = [list(one) for one in excluded]
        sequence_args["SEQUENCE_EXCLUDED_REGION"] = regions
        # Both keys, and the second is the one that matters here.
        #
        # Primer3's `SEQUENCE_EXCLUDED_REGION` applies to primers only: the
        # internal oligo has its own list and ignores that one. Measured — a
        # probe told to avoid a 200-base stretch sat at exactly the same base
        # as before, so the request had been accepted and dropped.
        #
        # It is the probe this usually exists for. A probe over a variant fails
        # on half the samples and works on the other half, which reads as
        # biology rather than as a design fault.
        sequence_args["SEQUENCE_INTERNAL_EXCLUDED_REGION"] = regions

    settings = limits.to_primer3(reaction, how_many * 4)
    settings.update(
        {
            "PRIMER_PICK_INTERNAL_OLIGO": 1,
            "PRIMER_INTERNAL_MUST_MATCH_FIVE_PRIME": FIVE_PRIME_PATTERN,
            "PRIMER_INTERNAL_MIN_SIZE": probe_limits.length_min,
            "PRIMER_INTERNAL_OPT_SIZE": probe_limits.length_opt,
            "PRIMER_INTERNAL_MAX_SIZE": probe_limits.length_max,
            "PRIMER_INTERNAL_MIN_TM": probe_limits.tm_min,
            "PRIMER_INTERNAL_OPT_TM": probe_limits.tm_opt,
            "PRIMER_INTERNAL_MAX_TM": probe_limits.tm_max,
            "PRIMER_INTERNAL_MIN_GC": probe_limits.gc_min,
            "PRIMER_INTERNAL_MAX_GC": probe_limits.gc_max,
            # The reaction, said a second time for the probe.
            #
            # Primer3 keeps the internal oligo's buffer separate from the
            # primers', and its defaults are not this reaction. Leaving them
            # alone computes the probe's melting temperature in one buffer and
            # the primers' in another: measured on a probe off NM_000546.6,
            # 66.1 against 74.9 -- 8.8 degrees, which is larger than the
            # separation the whole assay depends on. It would report a probe
            # melting a degree *below* its own primers as one melting seven
            # above.
            "PRIMER_INTERNAL_SALT_MONOVALENT": reaction["mv_conc"],
            "PRIMER_INTERNAL_SALT_DIVALENT": reaction["dv_conc"],
            "PRIMER_INTERNAL_DNTP_CONC": reaction["dntp_conc"],
            "PRIMER_INTERNAL_DNA_CONC": reaction["dna_conc"],
        }
    )

    answer = primer3.design_primers(seq_args=sequence_args, global_args=settings)

    refused = str(answer.get("PRIMER_ERROR", "")).strip()
    if refused:
        raise ProbeError(f"Primer3 refused this request: {refused}")

    found: list[Assay] = []
    rejected_for_g = 0
    for index in range(int(answer.get("PRIMER_PAIR_NUM_RETURNED", 0))):
        probe_sequence = answer.get(f"PRIMER_INTERNAL_{index}_SEQUENCE")
        if not probe_sequence:
            continue
        if probe_sequence[0].upper() == FORBIDDEN_FIRST_BASE:
            # Should never fire: Primer3 was given the rule above. Kept as a
            # check on that setting rather than as the mechanism, because a
            # quenched reporter is silent rather than wrong -- the assay comes
            # back negative and looks like absent template.
            rejected_for_g += 1
            continue

        pair = pair_at(answer, index, sequence, reaction)
        probe_at, probe_length = answer[f"PRIMER_INTERNAL_{index}"]
        measured = analyse(probe_sequence, **reaction)
        warmest_primer = max(pair.left.tm, pair.right.tm)

        found.append(
            Assay(
                pair=pair,
                probe=Probe(
                    sequence=probe_sequence,
                    at=probe_at,
                    length=probe_length,
                    tm=measured.tm,
                    gc_percent=measured.gc_percent,
                    after_left=probe_at - (pair.left_at.start + pair.left_at.length),
                    above=round(measured.tm - warmest_primer, 1),
                ),
                product_size=pair.product_size,
            )
        )
        if len(found) >= how_many:
            break

    explain = str(answer.get("PRIMER_INTERNAL_EXPLAIN", ""))
    if rejected_for_g:  # pragma: no cover - the setting above prevents this
        explain += (
            f" {rejected_for_g} got past PRIMER_INTERNAL_MUST_MATCH_FIVE_PRIME"
            " beginning with a guanine and were dropped here."
        )

    return found, explain.strip()


def assay_to_dict(assay: Assay, **conditions: float) -> dict[str, Any]:
    """One probe assay as plain data."""
    probe = assay.probe
    return {
        "left": report_to_dict(analyse(assay.pair.left.sequence, **conditions)),
        "right": report_to_dict(analyse(assay.pair.right.sequence, **conditions)),
        "probe": {
            **report_to_dict(analyse(probe.sequence, **conditions)),
            "at": probe.at,
            "after_left": probe.after_left,
            "above_primers": probe.above,
            "first_base": probe.sequence[0],
            "note": (
                f"Melts {probe.above} °C above the warmer primer, so it is already "
                "bound when the polymerase arrives — which is the whole mechanism: "
                "the probe is destroyed rather than extended, and only a polymerase "
                f"copying through this exact stretch releases the signal. It begins "
                f"with {probe.sequence[0]} rather than a guanine, which would quench "
                "the reporter it sits next to."
            ),
        },
        "product_size": assay.product_size,
        "measured_in": {
            "note": (
                "The probe's melting temperature is computed in the same reaction "
                "as the primers'. Primer3 takes the two as separate settings, and "
                "leaving the probe at its defaults puts them nearly nine degrees "
                "apart on one oligo — which would turn a working assay into one "
                "whose probe melts below its own primers."
            )
        },
    }


#: The most assays one request may ask for.
MOST_ASSAYS = 10


def check_enzyme(preset: Any) -> None:
    """Whether this polymerase could report anything.

    The signal comes from the polymerase chewing through the probe with its
    5'->3' exonuclease. An enzyme without one copies the template perfectly and
    displaces the probe intact, so the reaction amplifies and reports nothing.

    The same field decides the nested engine's single-tube refusal, in the
    opposite direction: there the exonuclease destroys the design, here its
    absence does. Worth stating in both places because the failure is silent
    either way -- no signal reads exactly like no template.

    Raises:
        ProbeError: naming the enzyme and what it lacks.
    """
    if not getattr(preset, "five_prime_exonuclease", True):
        raise ProbeError(
            f"{getattr(preset, 'name', 'This enzyme')} has no 5'->3' exonuclease, "
            "and that is what cleaves the probe. The reaction would amplify "
            "normally and report nothing, which on a plate reads as no template "
            "rather than as the wrong enzyme. A hydrolysis probe needs a Taq-based "
            "polymerase; a proofreading enzyme is for the assays that read a band."
        )


def _mgb_run(
    request: dict[str, Any], *, chosen: Any, limits: Constraints, reaction: dict[str, float], how_many: int,
    protocol: dict[str, Any], optical: dict[str, Any] | None,
) -> dict[str, Any]:
    """MGB candidate exchange without ever calculating ordinary-DNA probe Tm."""
    mode = str(request.get("probe_mgb_authority_mode") or "").strip()
    if mode not in {"export-candidates", "import-results"}:
        raise ProbeError("MGB qPCR requires probeMgbAuthorityMode: export-candidates or import-results")
    pair_result = design_pairs(
        chosen.target.sequence, target_start=request.get("target_start"), target_length=request.get("target_length"),
        excluded=excluded_from(request), constraints=limits, conditions=reaction, how_many=max(1, min(how_many, 10)),
        masked=chosen.target.soft_masked,
    )
    if not pair_result.pairs:
        return {
            "engine":"pair-and-probe","assay":chosen.assay_to_dict(),"target":target_to_dict(chosen.target),
            "protocol":protocol,"mgb_authority":{"status":"no-primer-pair"},"assays":[],"order_sheet":[],
            "orderability":{"orderable":False,"status":"no-primer-pair"},
            "why_nothing":"No primer pair was available from the unchanged qPCR primer envelope.",
        }
    pair=pair_result.pairs[0]
    start=pair.left_at.start+pair.left_at.length
    end=pair.right_at.start-pair.right_at.length+1
    if end-start < MGB_PROBE_MIN_NT:
        raise ProbeError(f"top primer pair leaves no valid internal interval for a {MGB_PROBE_MIN_NT}-{MGB_PROBE_MAX_NT} nt MGB probe")
    try:
        cands=mgb_candidates(chosen.target.sequence,start=start,end=end,minimum=MGB_PROBE_MIN_NT,maximum=MGB_PROBE_MAX_NT)
    except MgbAuthorityError as exc:
        raise ProbeError(str(exc)) from exc
    authority_id=str(protocol.get("authority_exchange_id") or "thermofisher-primer-express-mgb")
    exchange=mgb_exchange(cands,authority_id=authority_id)
    base={
        "engine":"pair-and-probe","provenance":provenance(reaction),"assay":chosen.assay_to_dict(),
        "target":target_to_dict(chosen.target),"reaction":{"polymerase":chosen.preset.id,"polymerase_name":chosen.preset.name,**reaction,"model":thermodynamic_model(chosen.preset,chosen.reaction)},
        "protocol":protocol,"optical_configuration":optical,"mgb_authority":{"exchange":exchange},
        "workflow_evidence":evidence_block(request.get("workflow_evidence"),note="Observed qPCR evidence never changes the original MGB candidate ranking."),
        "background":None,"considered":pair_result.considered,"order_sheet":[],
    }
    if mode=="export-candidates":
        base.update({"assays":[],"orderability":{"orderable":False,"status":"awaiting-external-mgb-authority"},"why_nothing":"MGB candidates were exported; import MGB-aware Tm values from the declared authority to rank/order them."})
        return base
    try:
        resolution=apply_mgb_import(cands,request.get("probe_mgb_authority_payload"),authority_id=authority_id)
    except MgbAuthorityError as exc:
        raise ProbeError(str(exc)) from exc
    selected=resolution["ranked_candidates"][0]
    seq=selected["sequence"]
    gc=round(100.0*(seq.count("G")+seq.count("C"))/len(seq),1)
    assay={
        "left":report_to_dict(pair.left),"right":report_to_dict(pair.right),
        "probe":{"sequence":seq,"length":len(seq),"gc_percent":gc,"tm":selected["tm"],"at":selected["template_start"],"strand":selected["strand"],"tm_source":"external-mgb-authority","candidate_id":selected["candidate_id"]},
        "product_size":pair.product_size,"mgb_authority":resolution,
    }
    name=label(chosen.target.name)
    order=[
        {"name":f"{name}_1F","sequence":pair.left.sequence,"annealing_sequence":pair.left.sequence,"tail_sequence":"","kind":"primer","length":pair.left.length,"gc_percent":pair.left.gc_percent,"tm":pair.left.tm},
        {"name":f"{name}_1R","sequence":pair.right.sequence,"annealing_sequence":pair.right.sequence,"tail_sequence":"","kind":"primer","length":pair.right.length,"gc_percent":pair.right.gc_percent,"tm":pair.right.tm},
        {"name":f"{name}_1P","sequence":seq,"annealing_sequence":seq,"tail_sequence":"","kind":"probe","length":len(seq),"gc_percent":gc,"tm":selected["tm"],"tm_source":"external-mgb-authority","modifications":{"five_prime_reporter":(optical or {}).get("reporter"),"three_prime_quencher":(optical or {}).get("quencher"),"chemistry":"mgb-nfq"}},
    ]
    base["mgb_authority"]["resolution"]=resolution
    base.update({"assays":[assay],"orderability":{"orderable":True,"status":"external-authority-resolved"},"order_sheet":order,"why_nothing":""})
    return base


def run(request: dict[str, Any]) -> dict[str, Any]:
    """One probe assay design, end to end, in the shape the interface reads.

    The probe carries its own constraints, layered separately from the primers.
    The routed `qpcr-probe` module requires a named executable chemistry in
    every policy mode because MGB and non-MGB probes do not share one universal
    Tm relationship.  The low-level geometry engine retains a clearly non-
    authoritative unbound search heuristic for engine tests/research only.

    Raises:
        IntakeError: the input is not a usable template.
        ProbeError: a probe that could not sit where it must.
        ValueError: a constraint, preset or reaction that cannot hold.
    """
    chosen = prepare(request)
    how_many = how_many_from(request, MOST_ASSAYS)
    check_enzyme(chosen.preset)
    selected_protocol = probe_protocol(request.get("probe_protocol"))
    if selected_protocol is not None and chosen.assay_id != "qpcr-probe":
        raise ProbeError(
            "named qPCR-probe chemistry belongs to the canonical `qpcr-probe` assay and cannot be "
            "made executable by omitting assay identity in development mode."
        )
    if chosen.assay_id == "qpcr-probe" and selected_protocol is None:
        raise ProbeError(
            "qPCR Probe requires an explicit named executable probe chemistry. "
            "The unbound-engine primer-to-probe Tm heuristic is not a release protocol."
        )
    if selected_protocol is not None and selected_protocol.get("execution_status") != "executable":
        if not (selected_protocol.get("chemistry") == "mgb-nfq" and selected_protocol.get("execution_status") == "external-authority-required"):
            raise ProbeError(
                f"probe protocol `{selected_protocol['protocol_id']}` is {selected_protocol.get('execution_status')} and is not executable."
            )
    optical = _probe_modifications(request, selected_protocol) if selected_protocol is not None else None

    # A named protocol is a scientific identity, not a label painted over an
    # arbitrary set of user values. Strict execution may tighten its bounded
    # envelope, but it cannot widen the vendor/profile limits and continue to
    # report the same protocol identity.
    explicit_primer_constraints = request.get("constraints") or {}
    effective_limits = chosen.limits
    if selected_protocol is not None and selected_protocol.get("primer_constraints"):
        protocol_primer_profile = dict(selected_protocol["primer_constraints"])
        unknown = sorted(
            set(protocol_primer_profile) - PROFILE_CONSTRAINT_FIELDS - PROFILE_PRIMER_RULES
        )
        if unknown:
            raise ProbeError(
                "the selected qPCR protocol declares unsupported primer rule(s): "
                + ", ".join(unknown)
            )
        protocol_primer_baseline = {
            **asdict(chosen.limits),
            **{
                key: value
                for key, value in protocol_primer_profile.items()
                if key in PROFILE_CONSTRAINT_FIELDS
            },
        }
        enforce_constraint_overrides(
            explicit_primer_constraints,
            protocol_primer_baseline,
            context=f"named qPCR probe protocol {selected_protocol['selection']} primer envelope",
        )
        effective_limits = replace(
            chosen.limits,
            **{
                field: value
                for field, value in protocol_primer_profile.items()
                if field not in explicit_primer_constraints
                and field in PROFILE_CONSTRAINT_FIELDS
            },
        )
        max_gc_last5 = protocol_primer_profile.get("max_gc_last5")
        if max_gc_last5 is not None:
            effective_limits = replace(
                effective_limits,
                max_end_gc=min(effective_limits.max_end_gc, int(max_gc_last5)),
            )

    supplied = request.get("probe") or {}
    strange = sorted(set(supplied) - set(Constraints.__dataclass_fields__))
    if strange:
        raise ValueError(f"unknown constraint(s) for the probe: {', '.join(strange)}")

    probe_defaults = _derived_from(effective_limits)
    if selected_protocol is not None:
        profile_probe = dict(selected_protocol.get("probe_constraints") or {})
        unknown = sorted(set(profile_probe) - PROFILE_CONSTRAINT_FIELDS - PROFILE_PROBE_RULES)
        if unknown:
            raise ProbeError(
                "the selected qPCR protocol declares unsupported probe rule(s): "
                + ", ".join(unknown)
            )
        probe_rules = {
            key: value for key, value in profile_probe.items() if key in PROFILE_PROBE_RULES
        }
        profile_probe = {
            key: value for key, value in profile_probe.items() if key in PROFILE_CONSTRAINT_FIELDS
        }
        delta = selected_protocol.get("probe_tm_delta_min_c")
        if delta is not None:
            # IDT's reviewed relationship is relative to the primer window, not
            # a Thermo-Fisher-style fixed 68–70 C window. The lower bound must
            # be above the warmest allowed primer, otherwise a nominal +6 C
            # overlay can still produce a probe that is only alongside a
            # 65 C primer. Build the executable window from the actual hard
            # primer ceiling rather than from tm_min alone.
            delta = float(delta)
            probe_floor = float(effective_limits.tm_max) + delta
            profile_probe.update(
                {
                    "tm_min": round(probe_floor, 1),
                    "tm_opt": round(max(float(effective_limits.tm_opt) + delta, probe_floor), 1),
                    "tm_max": round(max(float(effective_limits.tm_max) + delta, probe_floor), 1),
                }
            )
        probe_defaults.update(profile_probe)
        enforce_constraint_overrides(
            supplied,
            probe_defaults,
            context=f"named qPCR probe protocol {selected_protocol['selection']} probe envelope",
        )
    # `Constraints` also carries pair-product bounds, even though Primer3
    # applies the product range only to the primer pair. Keep the automatic
    # probe record internally valid when the vendor's 50-bp lower assay window
    # meets a 25-nt probe ceiling; an explicit user value remains a hard error
    # if it cannot hold its declared oligo geometry.
    if "product_min" not in supplied:
        probe_defaults["product_min"] = max(
            probe_defaults["product_min"], 2 * probe_defaults["length_max"] + 1
        )
    probe_limits = (
        Constraints(
            **{
                **probe_defaults,
                **supplied,
            }
        )
        if supplied or selected_protocol is not None
        else None
    )

    reaction = chosen.reaction.as_conditions()
    panel_for_multiplex = request.get("probe_multiplex_panel")
    if panel_for_multiplex:
        if not isinstance(panel_for_multiplex, list) or len(panel_for_multiplex) > QPCR_MULTIPLEX_MAX_PEERS:
            raise ProbeError("qPCR Probe multiplex planning accepts 1–11 peer assays (12 total including the current assay); this is a software bound, not a wet-lab qualification claim")
        if scientific_strict():
            missing=[]
            for index,row in enumerate(panel_for_multiplex):
                if not isinstance(row,dict):
                    missing.append(f"peer-{index+1}:typed-row")
                    continue
                peer_label=str(row.get("target") or f"peer-{index+1}")
                for camel,snake in (("forwardPrimer","forward_primer"),("reversePrimer","reverse_primer"),("probeSequence","probe_sequence")):
                    if not str(row.get(camel) or row.get(snake) or "").strip():
                        missing.append(f"{peer_label}:{camel}")
            if missing:
                raise ProbeError("Scientific-Strict qPCR multiplex requires peer forward/reverse/probe sequences for complete cross-assay interaction evidence; missing " + ", ".join(missing[:24]))
            if not request.get("probe_optical_authority_payload"):
                raise ProbeError("Scientific-Strict qPCR multiplex requires a versioned pcrstudio.qpcr-optical-profile.v1 authority; instrument name alone is not spectral validation")
    try:
        optical_validation = optical_authority(
            request.get("probe_optical_authority_payload"),
            panel=request.get("probe_multiplex_panel"),
            reporter=(optical or {}).get("reporter"),
        )
    except ProbeClosureError as exc:
        raise ProbeError(str(exc)) from exc
    if selected_protocol is not None and selected_protocol.get("chemistry") == "mgb-nfq":
        result = _mgb_run(request, chosen=chosen, limits=effective_limits, reaction=reaction, how_many=how_many, protocol=selected_protocol, optical=optical)
        result["optical_authority"] = optical_validation
        panel=request.get("probe_multiplex_panel")
        if result.get("assays"):
            one=result["assays"][0]
            try:
                result["multiplex_interactions"] = multiplex_interactions(panel,{"forward":one["left"]["sequence"],"reverse":one["right"]["sequence"],"probe":one["probe"]["sequence"]},mv_conc=float(reaction.get("mv_conc",50.0)),dv_conc=float(reaction.get("dv_conc",1.5)),dntp_conc=float(reaction.get("dntp_conc",0.6)),dna_conc=float(reaction.get("dna_conc",50.0)))
            except ProbeClosureError as exc:
                raise ProbeError(str(exc)) from exc
        return result
    found, explain = design(
        chosen.target.sequence,
        target_start=request.get("target_start"),
        target_length=request.get("target_length"),
        constraints=effective_limits,
        probe_constraints=probe_limits,
        conditions=reaction,
        how_many=how_many,
        excluded=excluded_from(request),
    )
    max_consecutive_g = (
        int(probe_rules["max_consecutive_g"])
        if selected_protocol is not None and "max_consecutive_g" in probe_rules
        else None
    )
    if max_consecutive_g is not None:
        found = [
            assay
            for assay in found
            if _max_consecutive_base(assay.probe.sequence, "G") <= max_consecutive_g
        ]

    junctions_raw=request.get("probe_transcript_junctions") or []
    variants_raw=request.get("probe_variant_positions") or []
    junctions=[]
    variants=[]
    try:
        junctions=sorted({int(x) for x in junctions_raw}) if isinstance(junctions_raw,list) else []
        variants=sorted({int(x) for x in variants_raw}) if isinstance(variants_raw,list) else []
    except (TypeError,ValueError) as exc:
        raise ProbeError("probe transcript junctions and variant positions must be integer arrays in 0-based template coordinates") from exc
    mode=str(request.get("probe_transcript_mode") or "not-specified")
    filtered=[]
    for assay in found:
        ps,pe=assay.probe.at,assay.probe.at+assay.probe.length
        product_start=assay.pair.left_at.start
        product_end=assay.pair.right_at.start+1
        if any(ps <= v < pe for v in variants):
            continue
        if mode=="exon-junction" and junctions and not any(ps < j < pe for j in junctions):
            continue
        if mode=="exon-spanning" and junctions and not any(product_start < j < product_end for j in junctions):
            continue
        filtered.append(assay)
    if mode in {"exon-junction","exon-spanning"} and not junctions:
        raise ProbeError(f"probeTranscriptMode={mode} requires explicit probeTranscriptJunctions")
    found=filtered
    assays = [assay_to_dict(assay, **reaction) for assay in found]
    name = label(chosen.target.name)

    # Independent whole-probe fold evidence. Primer3 remains the candidate
    # authority; ViennaRNA is an OPTIONAL orthogonal structure view and never
    # silently rejects a probe on a different thermodynamic model.
    probe_sequences = {f"probe_{index}": assay.probe.sequence for index, assay in enumerate(found, start=1)}
    fold_temperature = (
        chosen.preset.cycling.anneal_extend_c
        or chosen.preset.cycling.isothermal_c
        or chosen.preset.cycling.extend_c
        or 60.0
    )
    probe_folds = fold_oligos(probe_sequences, celsius=float(fold_temperature))
    independent_probe_structure = {
        "checked": probe_folds.checked,
        "model": probe_folds.model,
        "celsius": probe_folds.celsius,
        "note": probe_folds.note,
        "decision_impact": "advisory-independent-structure-evidence",
        "folds": {
            key: {
                "length": value.length,
                "dg": value.dg,
                "duplex_dg": value.duplex_dg,
                "fraction": value.fraction,
                "structure": value.structure,
            }
            for key, value in probe_folds.folds.items()
        },
    }

    # ── Where else these three oligos could sit ─────────────────────────────
    #
    # This page showed a specificity step and this engine had nowhere to put
    # the answer, so a pasted genome was dropped on the way in and the result
    # said nothing about it. A probe assay is exactly the design where that
    # matters most: a second site does not show up as a stray band on a gel,
    # it shows up as a curve that looks real.
    contigs, template_only, fold_at = screen.contigs_for(
        request, template=chosen.target.sequence, name=chosen.target.name
    )
    for entry, assay in zip(assays, found, strict=True):
        entry["off_targets"] = screen.oligos(
            {"left": assay.pair.left.sequence, "right": assay.pair.right.sequence},
            contigs,
            reaction=chosen.reaction,
            fold_at=fold_at,
            max_product=screen.product_ceiling(effective_limits.product_max),
            intended_sizes=[assay.product_size],
            intended_products=[assay.pair.amplicon],
            temperature_c=(
                chosen.preset.cycling.anneal_extend_c
                or chosen.preset.cycling.isothermal_c
                or chosen.preset.cycling.extend_c
            ),
            # The probe is blocked at its 3' end. Its second sites are worth
            # knowing — that is where background fluorescence comes from — but
            # it can never start a product, so it takes no part in making one.
            non_extending={"probe": assay.probe.sequence},
        )
        entry["specificity_layers"] = {
            "amplicon": {
                "source": "extending primer-pair scan",
                "note": "Potential PCR products are evaluated independently of fluorescence."
            },
            "probe_binding": {
                "source": "non-extending probe binding scan",
                "note": "Probe second sites are reported as binding evidence; the blocked probe cannot initiate a product."
            },
            "combined_signal": combined_signal(entry["off_targets"], assay.probe.sequence, contigs),
        }

    workflow = evidence_block(
        request.get("workflow_evidence"),
        note=(
            "MIQE/run evidence is retained for validation and reporting only; it never changes the saved primer/probe ranking."
        ),
    )

    # The unbound geometry engine remains useful for research/benchmarking in
    # development mode, but without a canonical named executable chemistry it
    # is never supplier-ready. Candidate sequences remain visible in `assays`;
    # supplier actions are withheld until chemistry authority exists.
    orderable = (
        chosen.assay_id == "qpcr-probe"
        and selected_protocol is not None
        and selected_protocol.get("execution_status") == "executable"
    )
    orderability = {
        "orderable": orderable,
        "status": "orderable" if orderable else "research-only-unbound-probe-engine",
        "note": (
            "A canonical executable probe chemistry is bound to this assay."
            if orderable
            else "Pair-and-probe candidates are research/diagnostic evidence only. No canonical executable hydrolysis-probe chemistry is bound, so do not order from this result."
        ),
    }

    candidate_order_sheet = [
            entry
            for index, one in enumerate(assays, start=1)
            for entry in (
                {
                    "name": f"{name}_{index}F",
                    "sequence": one["left"]["sequence"],
                    "annealing_sequence": one["left"]["sequence"],
                    "tail_sequence": "",
                    "kind": "primer",
                    "length": one["left"]["length"],
                    "gc_percent": one["left"]["gc_percent"],
                    "tm": one["left"]["tm"],
                },
                {
                    "name": f"{name}_{index}R",
                    "sequence": one["right"]["sequence"],
                    "annealing_sequence": one["right"]["sequence"],
                    "tail_sequence": "",
                    "kind": "primer",
                    "length": one["right"]["length"],
                    "gc_percent": one["right"]["gc_percent"],
                    "tm": one["right"]["tm"],
                },
                {
                    "name": f"{name}_{index}P",
                    "sequence": one["probe"]["sequence"],
                    "annealing_sequence": one["probe"]["sequence"],
                    "tail_sequence": "",
                    "kind": "probe",
                    "length": one["probe"]["length"],
                    "gc_percent": one["probe"]["gc_percent"],
                    "tm": one["probe"]["tm"],
                    "modifications": {
                        "five_prime_reporter": (optical or {}).get("reporter"),
                        "internal_quencher": (optical or {}).get("internal_quencher"),
                        "three_prime_quencher": (optical or {}).get("quencher"),
                        "chemistry": (optical or {}).get("chemistry"),
                    },
                    "note": "Manufacturing/readout labels are validated against the selected probe chemistry.",
                },
            )
        ]

    return {
        "engine": "pair-and-probe",
        # A property of the run rather than of a design: the same hold, at the
        # same temperature, whichever candidate you pick. `None` says the
        # question was never put — this assay's page does not ask it.
        "reverse_transcription": rt.block(polymerase=chosen.preset.name)
        if rt.wanted(request)
        else None,
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
            "primers": {
                field: getattr(effective_limits, field)
                for field in Constraints.__dataclass_fields__
            },
            "probe": _probe_window(effective_limits, probe_limits),
        },
        # How far the scan looked, said once rather than implied twenty times.
        "background": screen.summary(contigs, template_only),
        "independent_probe_structure": independent_probe_structure,
        "optical_configuration": optical,
        "transcript_mode": {"mode": request.get("probe_transcript_mode") or "not-specified", "junctions": junctions, "probe_variant_positions": variants, "coordinate_system": "0-based template"},
        "optical_authority": optical_validation,
        "multiplex_interactions": (
            multiplex_interactions(
                request.get("probe_multiplex_panel"),
                {"forward": found[0].pair.left.sequence, "reverse": found[0].pair.right.sequence, "probe": found[0].probe.sequence},
                mv_conc=float(reaction.get("mv_conc",50.0)), dv_conc=float(reaction.get("dv_conc",1.5)),
                dntp_conc=float(reaction.get("dntp_conc",0.6)), dna_conc=float(reaction.get("dna_conc",50.0)),
            ) if found else None
        ),
        "multiplex_panel": {
            "submitted": bool(request.get("probe_multiplex_panel")),
            "panel": request.get("probe_multiplex_panel"),
            "target_count": 1 + len(request.get("probe_multiplex_panel") or []),
            "software_planning_bound": QPCR_MULTIPLEX_SOFTWARE_MAX_TARGETS,
            "wet_lab_qualified_plex": None,
            "peer_sequence_completeness": all(
                isinstance(row, dict) and all(str(row.get(camel) or row.get(snake) or "").strip() for camel, snake in (("forwardPrimer","forward_primer"),("reversePrimer","reverse_primer"),("probeSequence","probe_sequence")))
                for row in (request.get("probe_multiplex_panel") or [])
            ),
            "panel_sha256": hashlib.sha256(
                json.dumps(request.get("probe_multiplex_panel"), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            ).hexdigest(),
            "chemistry_modification_identity_validation": "validated-by-typed-request-authority",
            "channel_identity_validation": "unique-explicit-identities-only",
            "instrument_spectral_compatibility": optical_validation.get("status"),
            "cross_assay_oligo_interactions": "reported-in-multiplex_interactions",
            "decision_impact": "diagnostic-only",
            "note": "Reporter/quencher identity and explicit channel uniqueness are validated before execution. Instrument spectral compatibility is not inferred without a reviewed instrument-channel authority. Cross-assay primer/probe interaction is not claimed without the peer oligo sequences and never silently changes independent assay ranking."
        } if request.get("probe_multiplex_panel") else None,
        "workflow_evidence": workflow,
        "assays": assays,
        "considered": explain,
        "why_nothing": (
            ""
            if assays
            else (
                "No pair came back from the low-level unbound pair-and-probe search. "
                f"That research heuristic places the probe window about {UNBOUND_ENGINE_PROBE_TM_OFFSET_C} °C "
                "above the primer window and forbids a 5-prime guanine. It is not a named-chemistry "
                "validity rule and must not be used as a release protocol."
            )
        ),
        "orderability": orderability,
        "order_sheet": candidate_order_sheet if orderable else [],
        **({"protocol": selected_protocol} if selected_protocol is not None else {}),
    }


def _derived_from(limits: Constraints) -> dict[str, Any]:
    """The probe window this project would pick, as plain fields.

    Kept beside the default in `design` rather than repeating its numbers: a
    caller who supplies only `tm_opt` for the probe should get the rest of the
    window from here, not from `Constraints`' primer-shaped defaults.
    """
    return {
        "length_min": 18,
        "length_opt": 24,
        "length_max": 30,
        "tm_min": round(limits.tm_min + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
        "tm_opt": round(limits.tm_opt + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
        "tm_max": round(limits.tm_max + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
        "gc_min": 30.0,
        "gc_max": 80.0,
        "gc_clamp": 0,
        "max_end_gc": 5,
        "product_min": limits.product_min,
        "product_max": limits.product_max,
    }


def _probe_window(limits: Constraints, supplied: Constraints | None) -> dict[str, Any]:
    """What the probe was actually held to, and where it came from."""
    used = supplied or Constraints(**_derived_from(limits))
    return {
        **{field: getattr(used, field) for field in Constraints.__dataclass_fields__},
        "from": "explicit low-level probe constraints" if supplied else "unbound low-level engine heuristic",
        "note": (
            f"For unbound engine research only, the default probe search window is shifted "
            f"{UNBOUND_ENGINE_PROBE_TM_OFFSET_C} °C above the primer window and measured in the same "
            "reaction. This is not named-chemistry authority or a bench protocol. The 5-prime "
            "base may not be guanine because it can quench an adjacent reporter."
        ),
    }
