"""Evidence-only multiplex LAMP planning.

DARQ/QUASR/FLOS/assimilation-style modified oligos remain method-specific.
PCRStudio does not synthesize those modifications from a standard LAMP set.
"""
from __future__ import annotations
import hashlib,json
from typing import Any
METHODS={'darq','quasr','flos','assimilation-probe','other-reviewed'}
LAMP_MULTIPLEX_SOFTWARE_MAX_TARGETS=4

def resolve(plan:Any,*,topology:str)->dict[str,Any]|None:
    if topology!='multiplex-modified-primer-probe':
        if plan not in (None,[], ''): raise ValueError('lamp_multiplex_plan requires multiplex-modified-primer-probe topology')
        return None
    if not isinstance(plan,list) or not (1<=len(plan)<LAMP_MULTIPLEX_SOFTWARE_MAX_TARGETS):
        raise ValueError('multiplex LAMP planning requires 1–3 complete peer targets (4 total including current); software bound is not wet-lab qualification')
    normalized=[]; ids=set(); reporters=set(); channels=set()
    for row in plan:
        if not isinstance(row,dict): raise ValueError('each lamp_multiplex_plan row must be an object')
        get=lambda snake,camel: str(row.get(snake) or row.get(camel) or '').strip()
        target=get('target','target'); method=get('method','method'); reporter=get('reporter','reporter'); channel=get('channel','channel'); role=get('modified_oligo_role','modifiedOligoRole'); sha=get('set_sha256','setSha256').lower(); authority=get('authority_id','authorityId'); evidence=get('empirical_evidence_ref','empiricalEvidenceRef')
        if not target or target in ids: raise ValueError('LAMP multiplex target identities must be non-empty and unique')
        ids.add(target)
        if method not in METHODS: raise ValueError('unsupported LAMP multiplex method identity')
        if not reporter or reporter in reporters or not channel or channel in channels: raise ValueError('LAMP multiplex requires unique explicit reporter/channel identities')
        reporters.add(reporter); channels.add(channel)
        if not role or not authority or not evidence: raise ValueError('LAMP multiplex requires modified oligo role, method authority and empirical evidence reference')
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha): raise ValueError('LAMP multiplex peer set_sha256 must be a SHA-256 hex digest')
        normalized.append({'target':target,'method':method,'reporter':reporter,'channel':channel,'modified_oligo_role':role,'set_sha256':sha,'authority_id':authority,'empirical_evidence_ref':evidence})
    digest=hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'status':'external-empirical-panel-context-complete','panel':normalized,'panel_sha256':digest,'target_count':1+len(normalized),'software_planning_bound':LAMP_MULTIPLEX_SOFTWARE_MAX_TARGETS,'wet_lab_qualified_plex':None,'automatic_modified_oligo_design':False,'sequence_decision_impact':'none','signal_claim':'empirical-target-specific-signal-required'}
