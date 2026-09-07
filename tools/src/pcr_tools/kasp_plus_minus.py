"""KASP-compatible presence/absence / indel junction candidate planning.

This is an open, auditable PCRStudio topology.  It does not reproduce LGC's
proprietary Kraken design.  Candidate primers are required to contain the
allele-specific junction near their 3' end and to lack an exact match in the
competing allele; empirical endpoint-cluster validation remains mandatory.
"""
from __future__ import annotations

from typing import Any

from . import kasp
from .design import Constraints
from .thermo import analyse, pair_dimer, reverse_complement
from .variants import NormalizedVariant, allele_sequences


def _specific_candidates(sequence: str, competing: str, end: int, limits: Constraints, conditions: dict[str, float]) -> list[dict[str, Any]]:
    found=[]
    for length in range(limits.length_min, limits.length_max + 1):
        start=end-length+1
        if start < 0 or end >= len(sequence):
            continue
        oligo=sequence[start:end+1]
        measured=analyse(oligo, **conditions)
        if not limits.tm_min <= measured.tm <= limits.tm_max or not limits.gc_min <= measured.gc_percent <= limits.gc_max:
            continue
        if oligo in competing:
            continue
        tail10=oligo[-min(10,len(oligo)):]
        found.append({
            "sequence":oligo,"at":start,"length":length,"tm":measured.tm,"gc_percent":measured.gc_percent,
            "three_prime_unique_10mer": tail10 not in competing,
            "competing_exact_match": False,
        })
    found.sort(key=lambda x:(not x["three_prime_unique_10mer"],abs(x["tm"]-limits.tm_opt),x["length"]))
    return found


def _common_reverse(ref_seq: str, alt_seq: str, junction_ref_end: int, limits: Constraints, conditions: dict[str,float], left_starts: tuple[int,int]) -> dict[str,Any] | None:
    # Common reverse must be an exact sequence in the shared downstream flank.
    downstream_start=max(junction_ref_end, 0)
    for right_end in range(min(len(ref_seq), downstream_start + limits.product_min), min(len(ref_seq), downstream_start + limits.product_max + 60)):
        for length in range(limits.length_min, limits.length_max+1):
            start=right_end-length+1
            if start < downstream_start or start < 0:
                continue
            plus=ref_seq[start:right_end+1]
            if not plus or plus not in alt_seq:
                continue
            oligo=reverse_complement(plus)
            measured=analyse(oligo, **conditions)
            if not limits.tm_min <= measured.tm <= limits.tm_max or not limits.gc_min <= measured.gc_percent <= limits.gc_max:
                continue
            ref_match=ref_seq.find(plus, downstream_start)
            alt_match=alt_seq.find(plus, max(0, downstream_start-20))
            if ref_match < 0 or alt_match < 0:
                continue
            ref_product=ref_match+len(plus)-left_starts[0]
            alt_product=alt_match+len(plus)-left_starts[1]
            if all(limits.product_min <= size <= limits.product_max for size in (ref_product,alt_product)):
                return {"sequence":oligo,"at_ref":ref_match,"at_alt":alt_match,"length":length,"tm":measured.tm,"gc_percent":measured.gc_percent,"product_sizes":{"REF":ref_product,"ALT":alt_product}}
    return None


def design_plus_minus(template: str, variant: NormalizedVariant, limits: Constraints, conditions: dict[str,float]) -> dict[str,Any]:
    ref_seq, alt_seq=allele_sequences(template, variant)
    # The presence/absence junction is immediately after each allele's changed core.
    ref_end = variant.at + len(variant.ref) if variant.ref else variant.at
    alt_end = variant.at + len(variant.alt) if variant.alt else variant.at
    ref_specific_end = min(len(ref_seq)-1, ref_end if not variant.ref else ref_end-1)
    alt_specific_end = min(len(alt_seq)-1, alt_end if not variant.alt else alt_end-1)
    ref_candidates=_specific_candidates(ref_seq,alt_seq,ref_specific_end,limits,conditions)
    alt_candidates=_specific_candidates(alt_seq,ref_seq,alt_specific_end,limits,conditions)
    if not ref_candidates or not alt_candidates:
        return {"orderable":False,"why":"No pair of allele-junction primers survived thermodynamic and competing-allele exact-match screening.","primers":[],"partners":[]}
    # Search a small deterministic frontier rather than coupling to proprietary ranking.
    best=None
    for r in ref_candidates[:12]:
        for a in alt_candidates[:12]:
            common=_common_reverse(ref_seq,alt_seq,variant.at+len(variant.ref),limits,conditions,(r["at"],a["at"]))
            if common is None: continue
            score=abs(r["tm"]-a["tm"])+abs(r["tm"]-common["tm"])+abs(a["tm"]-common["tm"])
            if best is None or score<best[0]: best=(score,r,a,common)
    if best is None:
        return {"orderable":False,"why":"Allele-junction primers were found, but no shared downstream common reverse primer satisfied the declared product/Tm window on both alleles.","primers":[],"partners":[]}
    _, r,a,common=best
    primers=[]
    for index,(label,p) in enumerate((("REF",r),("ALT",a))):
        primers.append({
            "name":f"{label}-specific","allele":label,"strand":"plus","sequence":p["sequence"],"ordered_sequence":kasp.attach(p["sequence"],index),
            "at":p["at"],"length":p["length"],"tm":p["tm"],"gc_percent":p["gc_percent"],"cassette":kasp.describe(index,p["sequence"],p["tm"]),
            "note":"Junction-aware KASP-compatible candidate; exact competing-allele match is absent. Empirical cluster validation is required.",
        })
    dimer_values = [
        pair_dimer(common["sequence"], specific["sequence"], **conditions).dg
        for specific in (r, a)
    ]
    partner={"for_alleles":["REF","ALT"],"sequence":common["sequence"],"at":common["at_ref"],"strand":"minus","tm":common["tm"],"gc_percent":common["gc_percent"],"length":common["length"],"product_size":max(common["product_sizes"].values()),"product_sizes":common["product_sizes"],"cross_dimer_dg":min(dimer_values),"cross_dimer_dg_basis":"worst (most negative) exact thermodynamic result across common-vs-REF and common-vs-ALT primer pairs","tm_difference":max(abs(common["tm"]-r["tm"]),abs(common["tm"]-a["tm"])),"note":"One exact shared downstream common primer used on both reconstructed allele sequences."}
    return {
        "orderable":True,"why":"","primers":primers,"partners":[partner],
        "junction_model":{"ref_junction":ref_end,"alt_junction":alt_end,"ref_length":len(ref_seq),"alt_length":len(alt_seq),"model":"explicit reconstructed REF/ALT junctions","vendor_kraken_equivalent":False},
        "call_model":{"states":["presence","absence","mixed/heterozygous-when-biologically-applicable","no-template","no-call","weak","ambiguous-cluster","failed-assay"],"claim_boundary":"A predicted design is not a genotype/presence call until endpoint controls and cluster evidence are reviewed."},
    }
