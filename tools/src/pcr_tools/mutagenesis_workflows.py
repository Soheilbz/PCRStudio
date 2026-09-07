"""Distinct mutagenesis topology planners and edit normalization.

Q5, QuikChange Lightning, QuikChange Lightning Multi and NEBuilder multi-site
are deliberately separate workflows.  This module owns edit reconstruction and
route-specific evidence; it never changes topology because a primer is easier
to design elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .design import clean_template
from .thermo import analyse, folded, pair_dimer, reverse_complement
from .registries.authorities import MUTAGENESIS_AUTHORITY, record as authority_record

DNA = set("ACGT")

_QC_SINGLE = authority_record(MUTAGENESIS_AUTHORITY, "agilent-quikchange-lightning-210518")
_QC_MULTI = authority_record(MUTAGENESIS_AUTHORITY, "agilent-quikchange-lightning-multi-210513-210516")
# This is an implementation enumeration ceiling, not an Agilent maximum.  The manuals
# explicitly allow primers longer than the preferred 45 nt when needed to reach Tm.
_QUICKCHANGE_SEARCH_MAX_NT = 60


# Standard genetic code, DNA alphabet.
CODONS = {
    'F':('TTT','TTC'),'L':('TTA','TTG','CTT','CTC','CTA','CTG'),'I':('ATT','ATC','ATA'),'M':('ATG',),
    'V':('GTT','GTC','GTA','GTG'),'S':('TCT','TCC','TCA','TCG','AGT','AGC'),'P':('CCT','CCC','CCA','CCG'),
    'T':('ACT','ACC','ACA','ACG'),'A':('GCT','GCC','GCA','GCG'),'Y':('TAT','TAC'),'H':('CAT','CAC'),
    'Q':('CAA','CAG'),'N':('AAT','AAC'),'K':('AAA','AAG'),'D':('GAT','GAC'),'E':('GAA','GAG'),
    'C':('TGT','TGC'),'W':('TGG',),'R':('CGT','CGC','CGA','CGG','AGA','AGG'),'G':('GGT','GGC','GGA','GGG'),
    '*':('TAA','TAG','TGA')
}
AA3 = {'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E','GLY':'G','HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F','PRO':'P','SER':'S','THR':'T','TRP':'W','TYR':'Y','VAL':'V','STOP':'*'}


class WorkflowError(ValueError):
    pass


@dataclass(frozen=True)
class EditSpec:
    kind: str
    at: int
    to: str = ""
    replacing: int = 0
    label: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind":self.kind,"at":self.at,"to":self.to,"replacing":self.replacing,"label":self.label}


def normalize_edit(raw: dict[str, Any], template_length: int) -> EditSpec:
    if not isinstance(raw, dict): raise WorkflowError("each edit must be an object")
    kind=str(raw.get('kind') or '').strip()
    if kind not in {'substitute','insert','delete'}: raise WorkflowError("edit.kind must be substitute, insert or delete")
    at=raw.get('at')
    if isinstance(at,bool) or not isinstance(at,int): raise WorkflowError("edit.at must be a zero-based integer")
    to=str(raw.get('to') or '').upper().replace('U','T')
    replacing=int(raw.get('replacing') or 0)
    if any(b not in DNA for b in to): raise WorkflowError("ordinary edit sequence must use unambiguous A/C/G/T")
    if kind=='insert':
        if not 0 <= at <= template_length or not to or replacing: raise WorkflowError("insertion requires boundary coordinate, non-empty to, replacing=0")
    else:
        if not 0 <= at < template_length: raise WorkflowError("edit coordinate lies outside template")
        if kind=='substitute' and (not to or replacing != len(to) or replacing < 1): raise WorkflowError("substitution requires same-length non-empty replacement")
        if kind=='delete' and (to or replacing < 1): raise WorkflowError("deletion requires replacing>=1 and empty to")
        if at+replacing>template_length: raise WorkflowError("edit runs beyond template")
    return EditSpec(kind,at,to,replacing,str(raw.get('label') or '').strip() or None)


def normalize_edits(request: dict[str,Any], template_length: int) -> list[EditSpec]:
    raws=request.get('edits')
    if raws is None:
        raw=request.get('edit')
        raws=[raw] if isinstance(raw,dict) else None
    if not isinstance(raws,list) or not raws: raise WorkflowError("edit or non-empty edits[] is required")
    edits=[normalize_edit(raw,template_length) for raw in raws]
    spans=[]
    for e in edits:
        end=e.at+(e.replacing if e.kind!='insert' else 0)
        spans.append((e.at,end,e))
    for i,(a0,a1,a) in enumerate(spans):
        for b0,b1,b in spans[i+1:]:
            if a.kind=='insert' and b.kind=='insert' and a0==b0: raise WorkflowError("two insertions at the same boundary are ambiguous; combine them explicitly")
            if max(a0,b0) < min(a1,b1): raise WorkflowError("edits overlap on the reference template; supply one explicit complex edit instead")
    return sorted(edits,key=lambda e:(e.at,e.kind))


def apply_edits(template: str, edits: list[EditSpec]) -> str:
    seq=clean_template(template)
    for edit in sorted(edits,key=lambda e:e.at,reverse=True):
        if edit.kind=='insert': seq=seq[:edit.at]+edit.to+seq[edit.at:]
        else: seq=seq[:edit.at]+edit.to+seq[edit.at+edit.replacing:]
    return seq


def sequence_diff(template: str, edited: str, edits: list[EditSpec]) -> dict[str,Any]:
    return {"reference_length":len(template),"edited_length":len(edited),"delta_length":len(edited)-len(template),"edits":[e.as_dict() for e in edits],"exact_edited_construct":edited,"claim_boundary":"Predicted construct sequence; clone-level sequence confirmation is required."}


def _aa(code: str) -> str:
    token=code.strip().upper()
    if token in AA3: return AA3[token]
    if len(token)==1 and token in CODONS: return token
    raise WorkflowError(f"unknown amino-acid code {code!r}")


def amino_acid_edit(template: str, raw: dict[str,Any], *, codon_policy: str, codon_usage: dict[str,float] | None=None) -> tuple[EditSpec,dict[str,Any]]:
    seq=clean_template(template)
    residue=raw.get('residue')
    cds_start=raw.get('cds_start',raw.get('cdsStart',0))
    if isinstance(residue,bool) or not isinstance(residue,int) or residue < 1: raise WorkflowError("aminoAcidEdit.residue must be 1-based positive integer")
    if isinstance(cds_start,bool) or not isinstance(cds_start,int) or cds_start < 0: raise WorkflowError("aminoAcidEdit.cdsStart must be zero-based non-negative")
    target=_aa(str(raw.get('to') or raw.get('to_aa') or raw.get('toAa') or ''))
    at=cds_start+(residue-1)*3
    old=seq[at:at+3]
    if len(old)!=3: raise WorkflowError("requested residue lies beyond CDS/template")
    candidates=list(CODONS[target])
    requested=str(raw.get('codon') or '').upper()
    if codon_policy=='user-selected-codon':
        if requested not in candidates: raise WorkflowError("selected codon does not encode requested amino acid")
        picked=requested
    elif codon_policy=='host-codon-usage':
        if not codon_usage: raise WorkflowError("host-codon-usage policy requires explicit caller-supplied codonUsage frequencies")
        picked=max(candidates,key=lambda codon:float(codon_usage.get(codon,0.0)))
        if float(codon_usage.get(picked,0.0)) <= 0: raise WorkflowError("codonUsage contains no positive frequency for the requested amino acid")
    elif codon_policy=='minimum-nucleotide-changes':
        picked=min(candidates,key=lambda codon:(sum(a!=b for a,b in zip(old,codon,strict=True)),codon))
    else: raise WorkflowError("unsupported codon policy")
    return EditSpec('substitute',at,picked,3,f"{old}->{picked}; residue {residue}"), {"residue":residue,"from_codon":old,"to_codon":picked,"to_amino_acid":target,"codon_policy":codon_policy}


def _gc(seq: str) -> float:
    return 100.0*(seq.count('G')+seq.count('C'))/len(seq) if seq else 0.0


def quikchange_tm(primer: str, *, authority: dict[str, Any], mismatch_percent: float=0.0, effective_n: int | None=None) -> float:
    n=effective_n or len(primer)
    if n <= 0: raise WorkflowError("QuikChange Tm denominator must be positive")
    terms=authority["tm_formula_parameters"]
    return round(float(terms["intercept"]) + float(terms["gc_coefficient"])*_gc(primer) - float(terms["length_coefficient"])/n - mismatch_percent,1)


def _quikchange_structure_review(primer: str, *, dimer_threshold_kcal_mol: float | None = None) -> dict[str, Any]:
    """Public-manual secondary-structure review, not Agilent web-tool ranking."""
    report = analyse(primer, temp_c=55.0)
    measured = folded(report)
    hairpin_tm = report.hairpin.tm if measured else None
    self_dimer_dg = report.self_dimer.dg if measured else None
    return {
        "model": "Primer3 thermodynamic review at 55 C",
        "measured": measured,
        "hairpin_tm_c": hairpin_tm,
        "hairpin_review_required": bool(measured and hairpin_tm is not None and hairpin_tm >= 55.0),
        "self_dimer_dg_kcal_mol": self_dimer_dg,
        "self_dimer_pass": (None if dimer_threshold_kcal_mol is None or not measured else self_dimer_dg > dimer_threshold_kcal_mol),
        "dimer_threshold_kcal_mol": dimer_threshold_kcal_mol,
        "claim_boundary": "Manual-guideline review using Primer3 thermodynamics; not Agilent Primer Design Program/Energy Cost equivalence.",
    }


def quikchange_single(template: str, edit: EditSpec) -> dict[str,Any]:
    seq=clean_template(template); edited=apply_edits(seq,[edit])
    # Candidate window is expressed in edited coordinates. For equal-length substitution the mapping is direct;
    # for a small insertion/deletion, centre around the edit junction and use the manual's indel Tm formula.
    delta=len(edit.to)-edit.replacing
    center=edit.at + max(len(edit.to),1)//2
    found=[]
    if edit.kind=='insert' and len(edit.to)>int(_QC_SINGLE['small_insertion_software_design_max_nt']):
        raise WorkflowError("Agilent's current QuikChange primer-design help recommends the software only for small insertions up to 7 nt; larger insertions are not auto-designed in this branch.")
    if edit.kind == 'substitute' and edit.replacing > 3:
        raise WorkflowError("QuikChange Lightning manual-faithful design allows at most 3 consecutive mismatches in one mutagenic primer; split/reformulate the edit or use another validated topology.")
    for length in range(int(_QC_SINGLE["primer_length_nt_min_preferred"]), _QUICKCHANGE_SEARCH_MAX_NT + 1):
        left=(length-max(len(edit.to),1))//2
        start=max(0,center-left)
        end=start+length
        if end>len(edited): start=max(0,len(edited)-length); end=len(edited)
        primer=edited[start:end]
        if len(primer)<25: continue
        # mutation must be at least 10 bases from either ordered-primer end.
        edit_start=edit.at
        edit_end=edit.at+max(len(edit.to),1)
        if edit_start-start<int(_QC_SINGLE['mutation_min_distance_from_primer_end_nt']) or end-edit_end<int(_QC_SINGLE['mutation_min_distance_from_primer_end_nt']): continue
        effective_n=len(primer)-len(edit.to) if edit.kind=='insert' else len(primer)
        mismatch_pct=0.0 if edit.kind in {'insert','delete'} else 100.0*edit.replacing/len(primer)
        tm=quikchange_tm(primer,authority=_QC_SINGLE,mismatch_percent=mismatch_pct,effective_n=max(1,effective_n))
        if tm<float(_QC_SINGLE["tm_c_min"]): continue
        structure=_quikchange_structure_review(primer)
        found.append({
            "forward":primer,"reverse":reverse_complement(primer),"start":start,"end":end,"length":len(primer),
            "tm_formula_c":tm,"gc_percent":round(_gc(primer),1),
            "gc_ideal_met":_gc(primer) >= float(_QC_SINGLE.get("gc_percent_min_ideal",40)),
            "three_prime_gc_preference":primer[-1] in 'GC',
            "structure_review":structure,
            "manual_rule_status":"manual-faithful-candidate",
            "vendor_web_tool_equivalent":False,
        })
    if not found: return {"orderable":False,"why":"No complementary QuikChange Lightning primer pair met the reviewed >=78 C formula and >=10-nt mutation-to-end geometry within PCRStudio's 25–60 nt implementation search envelope. Agilent's 25–45 nt range is preferred, not a vendor maximum.","pairs":[],"search_primer_length_max_nt":_QUICKCHANGE_SEARCH_MAX_NT,"search_length_is_vendor_limit":False}
    found.sort(key=lambda x:(x['structure_review']['hairpin_review_required'], not x['gc_ideal_met'], x['length']>int(_QC_SINGLE['primer_length_nt_max_preferred']), not x['three_prime_gc_preference'], abs(x['length']-35), -x['tm_formula_c']))
    return {"orderable":True,"pairs":found[:5],"why":"","topology":"quikchange-complementary","amplification":"linear","dpnI_required":True,"authority":{"id":"agilent-quikchange-lightning-210518","primer_length_preferred_nt":[_QC_SINGLE["primer_length_nt_min_preferred"],_QC_SINGLE["primer_length_nt_max_preferred"]],"search_primer_length_max_nt":_QUICKCHANGE_SEARCH_MAX_NT,"search_length_is_vendor_limit":False,"tm_formula_min_c":_QC_SINGLE["tm_c_min"],"mutation_min_from_each_end_nt":_QC_SINGLE["mutation_min_distance_from_primer_end_nt"],"source":_QC_SINGLE["source_identity"],"method_fidelity":"F2-manual-rule-faithful","vendor_web_tool_equivalent":False,"manual_soft_preferences":["GC >=40% ideal","3-prime C/G preferred","hairpin Tm below 55 C preferred"]}}


def quikchange_multi(template: str, edits: list[EditSpec]) -> dict[str,Any]:
    seq=clean_template(template)
    if any(e.kind!='substitute' or e.replacing!=len(e.to) for e in edits):
        raise WorkflowError("QuikChange Lightning Multi automatic branch currently requires non-overlapping same-length substitutions; indel multi-site requests route to the PCRStudio NEBuilder multi-site routing workflow.")
    if any(e.replacing > 3 for e in edits):
        raise WorkflowError("QuikChange Lightning Multi manual-faithful design allows at most 3 consecutive mismatches per mutagenic primer.")
    candidates=[]
    for edit in edits:
        edited=apply_edits(seq,[edit]); centre=edit.at+edit.replacing//2; picked=None
        for length in range(int(_QC_MULTI["primer_length_nt_min"]), _QUICKCHANGE_SEARCH_MAX_NT + 1):
            start=centre-length//2; end=start+length
            if start<0 or end>len(seq): continue
            if edit.at-start<int(_QC_MULTI['mutation_min_distance_from_primer_end_nt']) or end-(edit.at+edit.replacing)<int(_QC_MULTI['mutation_min_distance_from_primer_end_nt']): continue
            primer=edited[start:end]
            mismatch_pct=100.0*edit.replacing/len(primer)
            tm=quikchange_tm(primer,authority=_QC_MULTI,mismatch_percent=mismatch_pct)
            if tm<float(_QC_MULTI["tm_c_min"]): continue
            structure=_quikchange_structure_review(primer,dimer_threshold_kcal_mol=-9.0)
            if structure["self_dimer_pass"] is False:
                continue
            item={
                "edit":edit.as_dict(),"sequence":primer,"start":start,"end":end,"length":len(primer),
                "tm_formula_c":tm,"gc_percent":round(_gc(primer),1),"strand":"plus",
                "gc_ideal_met":_gc(primer)>=40.0,"three_prime_gc_preference":primer[-1] in 'GC',
                "structure_review":structure,"manual_rule_status":"manual-faithful-candidate",
                "vendor_web_tool_equivalent":False,
            }
            if picked is None or (structure['hairpin_review_required'],not item['gc_ideal_met'],not item['three_prime_gc_preference'],length>int(_QC_MULTI['primer_length_nt_max_preferred']),abs(length-35),-tm)<(picked['structure_review']['hairpin_review_required'],not picked['gc_ideal_met'],not picked['three_prime_gc_preference'],picked['length']>int(_QC_MULTI['primer_length_nt_max_preferred']),abs(picked['length']-35),-picked['tm_formula_c']): picked=item
        if picked is None: return {"orderable":False,"why":f"No same-strand Lightning Multi primer survived at edit {edit.at} within PCRStudio's 25–60 nt implementation search envelope; the vendor preferred range is not treated as a hard maximum.","primers":[],"search_primer_length_max_nt":_QUICKCHANGE_SEARCH_MAX_NT,"search_length_is_vendor_limit":False}
        candidates.append(picked)
    ordered=sorted(candidates,key=lambda p:p['start'])
    for a,b in zip(ordered,ordered[1:]):
        if a['end']>b['start']:
            return {"orderable":False,"why":"Lightning Multi requires same-orientation mutagenic primers that do not overlap; the current edit spacing cannot satisfy that geometry.","primers":ordered}
    pairwise=[]
    for i,a in enumerate(ordered):
        for b in ordered[i+1:]:
            dimer=pair_dimer(a['sequence'],b['sequence'],temp_c=55.0)
            pairwise.append({"a_start":a['start'],"b_start":b['start'],"dg_kcal_mol":dimer.dg,"pass":dimer.dg>-9.0})
    if any(not row['pass'] for row in pairwise):
        return {"orderable":False,"why":"Lightning Multi manual-faithful dimer review found a predicted primer heterodimer at or below -9 kcal/mol at the 55 C review condition.","primers":ordered,"pairwise_dimer_review":pairwise}
    return {"orderable":True,"why":"","primers":ordered,"topology":"quikchange-lightning-multi","same_template_strand":True,"nonoverlap_verified":True,"pairwise_dimer_review":pairwise,"vendor_web_tool_equivalent":False,"authority":{"id":"agilent-quikchange-lightning-multi-210513-210516","primer_length_preferred_nt":[_QC_MULTI["primer_length_nt_min"],_QC_MULTI["primer_length_nt_max_preferred"]],"search_primer_length_max_nt":_QUICKCHANGE_SEARCH_MAX_NT,"search_length_is_vendor_limit":False,"tm_formula_min_c":_QC_MULTI["tm_c_min"],"mutation_min_from_each_end_nt":_QC_MULTI["mutation_min_distance_from_primer_end_nt"],"source":_QC_MULTI["source_identity"]}}


def nebuilder_multisite_route(template: str, edits: list[EditSpec]) -> dict[str,Any]:
    seq=clean_template(template); edited=apply_edits(seq,edits)
    # Partition at midpoints between edits. This is a deterministic routing plan,
    # not a claim of NEBaseChanger-equivalent proprietary/online ranking.
    positions=sorted(e.at for e in edits)
    cuts=[]
    for a,b in zip(positions,positions[1:]): cuts.append((a+b)//2)
    bounds=[0,*cuts,len(seq)]
    segments=[]
    for i,(a,b) in enumerate(zip(bounds,bounds[1:]),start=1):
        # Reconstruct fragment from the globally edited sequence by mapping only safe equal-coordinate slices
        # when length-changing edits are absent in this segment. For arbitrary indels, provide the entire final
        # construct as explicit desired sequence and route coordinates as reference hints.
        segments.append({"name":f"mutagenesis_fragment_{i}","kind":"pcr-amplified","reference_start":a,"reference_end":b,"sequence_role":"derive-from-exact-edited-construct","template_role":"original-plasmid"})
    return {"route_to_engine":"junction-primers","method":"nebuilder","protocol":"neb-nebuilder-e2621","edited_construct":edited,"segments":segments,"source_tool_characterization":"NEBaseChanger v2.8.4 documents a multi-site workflow that routes fragments to NEBuilder HiFi","vendor_tool_equivalent":False,"method_identity":"PCRStudio multi-site NEBuilder HiFi routing informed by NEBaseChanger workflow","claim_boundary":"Routing/construct plan only; Junction Primers performs the explicit overlap/primer design. This is not NEBaseChanger primer design or ranking."}


def library_edit(template: str, *, at: int, codon: str) -> dict[str,Any]:
    seq=clean_template(template); token=codon.upper()
    allowed={'NNK':32,'NNS':32}
    if token not in allowed and any(base not in 'ACGTRYSWKMBDHVN' for base in token): raise WorkflowError("custom library codon must use IUPAC DNA symbols")
    if at<0 or at+len(token)>len(seq): raise WorkflowError("library codon replacement lies outside template")
    construct=seq[:at]+token+seq[at+len(token):]
    return {"mode":token if token in allowed else "custom-codon-set","at":at,"iupac":token,"theoretical_concrete_codons":allowed.get(token),"construct_iupac":construct,"claim_boundary":"Library diversity is theoretical sequence space; synthesis abundance and clone distribution require empirical measurement."}
