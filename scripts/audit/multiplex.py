"""Multiplex source-closure audit.

This gate is deliberately modality-aware: endpoint PCR, spectral qPCR,
digital-PCR, tiled pools and isothermal empirical/planning branches do not
inherit one generic set of scientific claims.
"""
from __future__ import annotations
import json
from .common import ROOT, error, sha256

EXPECTED_GENERIC={"standard-pcr","colony-pcr","species-specific-pcr"}
EXPECTED_SPECIALIZED={"qpcr-probe","digital-pcr","tiled-scheme","rpa","lamp"}


def _text(rel:str)->str:
    path=ROOT/rel
    if not path.exists():
        error(f"multiplex: missing required source {rel}")
        return ""
    return path.read_text(encoding="utf-8")


def audit_multiplex_closure()->None:
    path=ROOT/'contracts/multiplex-capabilities.json'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        error(f'multiplex: canonical capability registry parse failed: {exc}')
        return
    modules=data.get('modules')
    policy=data.get('policy')
    if not isinstance(modules,dict) or not isinstance(policy,dict):
        error('multiplex: modules/policy registries are required')
        return
    for marker in (
        'software_bound_is_not_wet_lab_validation',
        'no_generic_multiplex_semantics_across_modalities',
        'scientific_strict_requires_exact_or_upstream_primary_selection',
        'empirical_signal_thresholds_are_evidence_not_sequence_predictions',
        'panel_identity_is_content_addressed',
    ):
        if policy.get(marker) is not True:
            error(f'multiplex: canonical policy must enable {marker}')
    if set(modules)!=(EXPECTED_GENERIC|EXPECTED_SPECIALIZED):
        error(f"multiplex: module registry mismatch; got={sorted(modules)}")
    for module_id,row in modules.items():
        if not isinstance(row,dict):
            error(f'multiplex: {module_id} capability row must be an object'); continue
        if row.get('wet_lab_qualified_plex') is not None:
            error(f'multiplex: {module_id} may not claim wet-lab-qualified plex before native/bench qualification')
        for field in ('engine','kind','status','primary_selection','pooling','required_evidence'):
            if field not in row or row.get(field) in ('',None,[]):
                error(f'multiplex: {module_id} missing {field}')
    for module_id in EXPECTED_GENERIC:
        if not str(modules[module_id].get('kind') or '').startswith('endpoint-multitarget'):
            error(f'multiplex: {module_id} must remain endpoint-multitarget generic multiplex')
        if modules[module_id].get('software_target_bound')!=32:
            error(f'multiplex: {module_id} software target bound drifted from 32')

    optical_profiles=data.get('qpcr_optical_profiles')
    expected_optical={'thermofisher-quantstudio5-96well-man0017162-b0':6,'thermofisher-quantstudio7pro-man0018045-p':6,'bio-rad-cfx96-bulletin-5589b':5,'bio-rad-cfx-opus96-bulletin-7279':5,'qiagen-rotor-gene-q-six-channel':6,'agilent-ariamx-six-module':6}
    if not isinstance(optical_profiles,dict) or not expected_optical.keys() <= optical_profiles.keys():
        error('multiplex: reviewed qPCR optical profile library is incomplete')
    else:
        for profile_id,max_targets in expected_optical.items():
            profile=optical_profiles[profile_id]
            if profile.get('schema')!='pcrstudio.qpcr-optical-profile.v1' or profile.get('max_targets')!=max_targets:
                error(f'multiplex: qPCR optical profile identity/capacity drifted: {profile_id}')
            channels=profile.get('channels')
            if not isinstance(channels,list) or len(channels)!=max_targets or any(not row.get('channel') or not row.get('reporters') for row in channels if isinstance(row,dict)):
                error(f'multiplex: qPCR optical profile channel map incomplete: {profile_id}')
            if 'calibration' not in str(profile.get('authority_scope') or '').lower():
                error(f'multiplex: qPCR optical profile must keep run calibration outside static compatibility authority: {profile_id}')

    platform_authorities=data.get('platform_authorities')
    expected_platforms={
        'bio-rad-qx200':(2,2,{'channel'}),
        'bio-rad-qx-one':(4,8,{'channel','amplitude','probe-mix'}),
        'bio-rad-qx-continuum':(4,4,{'channel'}),
        'bio-rad-qx600':(6,12,{'channel','amplitude','probe-mix'}),
        'bio-rad-qx700':(7,7,{'channel'}),
        'qiacuity-one-2plex':(2,4,{'channel','amplitude'}),
        'qiacuity-one-5plex':(8,12,{'channel','amplitude','hybrid'}),
        'qiacuity-four':(8,12,{'channel','amplitude','hybrid'}),
        'qiacuity-eight':(8,12,{'channel','amplitude','hybrid'}),
        'thermo-absolute-q':(5,5,{'channel'}),
        'roche-digital-lightcycler':(6,6,{'channel'}),
    }
    if not isinstance(platform_authorities,dict):
        error('multiplex: dPCR platform authority registry is missing')
    else:
        for platform_id,(channels,total,modes) in expected_platforms.items():
            row=platform_authorities.get(platform_id)
            if not isinstance(row,dict):
                error(f'multiplex: reviewed dPCR platform authority missing: {platform_id}'); continue
            if row.get('detection_channels')!=channels or row.get('multiplex_target_bound')!=total or set(row.get('modes') or [])!=modes:
                error(f'multiplex: dPCR platform authority/capacity drifted: {platform_id}')
            if not row.get('authority_url') or row.get('reviewed_date')!='2026-09-06':
                error(f'multiplex: dPCR platform authority provenance incomplete: {platform_id}')

    # All generated projections must be exact semantic copies of the canonical payload.
    canonical=json.dumps(data,sort_keys=True,separators=(',',':'))
    for rel in (
        'tools/src/pcr_tools/data/multiplex-capabilities.generated.json',
        'crates/pcr-core/generated/multiplex-capabilities.generated.json',
        'web/src/lib/multiplex-capabilities.generated.json',
        'knowledge/runtime/multiplex-capabilities.generated.json',
    ):
        try:
            projected=json.loads((ROOT/rel).read_text(encoding='utf-8'))
        except Exception as exc:
            error(f'multiplex: projection missing/invalid {rel}: {exc}'); continue
        projected=dict(projected); projected.pop('_projection',None)
        if json.dumps(projected,sort_keys=True,separators=(',',':')) != canonical:
            error(f'multiplex: generated capability projection drift: {rel}')

    generic=_text('tools/src/pcr_tools/multiplex.py')
    for marker in (
        'def choose_exact(', 'MAX_EXACT_STATES', 'optimizer_mode', 'cross_product_specificity',
        'SADDLE simulated annealing',
    ):
        if marker not in generic:
            error(f'multiplex: generic endpoint implementation missing marker: {marker}')
    if 'scientific-strict' not in generic.lower() or 'exact' not in generic.lower():
        error('multiplex: generic endpoint Scientific-Strict exact-selection boundary is missing')
    if 'explicit' not in generic.lower() or 'tube' not in generic.lower():
        error('multiplex: generic multiplex must require explicit tube identity instead of hidden auto-partitioning')
    for marker in ('primer_concentration_nm','empirical_evidence_ref','formulation_sha256','no-sequence-ranking-impact'):
        if marker not in generic:
            error(f'multiplex: generic empirical formulation lifecycle missing marker: {marker}')
    pooler=_text('tools/src/pcr_tools/external_validation.py')
    for marker in ('--seedless','--pools=?,1,','accepted_into_design','assign_pools','evidence-only-until-explicitly-accepted'):
        if marker not in pooler:
            error(f'multiplex: upstream PrimerPooler proposal boundary missing: {marker}')

    scientific=_text('scripts/audit/scientific.py')
    for module_id in EXPECTED_GENERIC:
        if module_id not in scientific:
            error(f'multiplex: scientific audit no longer names generic multiplex module {module_id}')

    probe_rust=_text('crates/pcr-core/src/engines/pair_and_probe.rs')
    probe_py=_text('tools/src/pcr_tools/probe_closure.py')+_text('tools/src/pcr_tools/probe.py')
    probe_web=_text('web/src/components/design/probe-multiplex-editor.tsx')+_text('web/src/lib/projects/engine-request-extensions.ts')
    for marker in ('forward_primer','reverse_primer','probe_sequence'):
        if marker not in probe_rust:
            error(f'multiplex: qPCR Probe Rust panel drops peer oligo field {marker}')
    for marker in ('forwardPrimer','reversePrimer','probeSequence'):
        if marker not in probe_web:
            error(f'multiplex: qPCR Probe Web panel drops peer oligo field {marker}')
    for marker in ('pcrstudio.qpcr-optical-profile.v1','threshold":"none-universal','diagnostic-only'):
        if marker not in probe_py:
            error(f'multiplex: qPCR Probe authority/interaction boundary missing: {marker}')
    probe_fields=_text('web/src/components/design/probe-fields.tsx')
    if 'qpcr_optical_profiles' not in probe_fields or 'Built-in profiles reproduce reviewed manufacturer channel/reporter maps' not in probe_fields:
        error('multiplex: qPCR reviewed optical-profile selector/claim boundary is missing from Web UI')

    dpcr_rust=_text('crates/pcr-core/src/engines/digital_multiplex.rs')+_text('crates/pcr-core/src/engines/digital_multiplex_authority.generated.rs')
    dpcr_py=_text('tools/src/pcr_tools/registries/flanking_protocols.py')
    dpcr_ui=_text('web/src/components/design/engine-fields/digital-pcr-fields.tsx')
    for marker in ('channel','amplitude','hybrid','probe-mix'):
        if marker not in dpcr_rust or marker not in dpcr_py:
            error(f'multiplex: dPCR mode missing across Rust/Python: {marker}')
    for marker in ('DIGITAL_MULTIPLEX_SOFTWARE_MAX_TARGETS','QIACUITY_CHANNEL_TARGET_MAX','QX600_CHANNEL_TARGET_MAX','QX600_MULTIPLEX_MAX','threshold_rain_cluster_inference'):
        if marker not in dpcr_py:
            error(f'multiplex: dPCR named-bound/evidence marker missing: {marker}')
    if 'wet_lab_qualified_plex' not in dpcr_py or 'panel_sha256' not in dpcr_py:
        error('multiplex: dPCR result must expose panel identity and non-qualification boundary')
    if 'digitalMultiplex' not in dpcr_ui and 'digital multiplex' not in dpcr_ui.lower():
        error('multiplex: dPCR multiplex planning UI is missing')

    rpa=_text('tools/src/pcr_tools/rpa_screening.py')+_text('tools/src/pcr_tools/pipeline.py')
    for marker in ('forward_candidates_recommended": [8, 10]','reverse_candidates_recommended": [8, 10]','matrix_ready','empirical'):
        if marker not in rpa:
            error(f'multiplex: RPA empirical-development boundary missing: {marker}')
    rpa_panel=_text('tools/src/pcr_tools/rpa_multiplex.py')
    for marker in ('extend_order_sheet','rpa-multiplex-1','whole-panel independent interaction review'):
        if marker not in rpa_panel:
            error(f'multiplex: RPA peer assay whole-panel validation handoff missing: {marker}')

    lamp=_text('tools/src/pcr_tools/loop_set.py')
    if '_generic_off_target_rank' in lamp:
        # Helper may remain diagnostic, but selection keys are guarded by method-fidelity audit.
        pass
    if 'multiplex-modified-primer-probe' not in _text('tools/src/pcr_tools/data/lamp-protocol-authority.generated.json'):
        error('multiplex: LAMP specialized multiplex topology is absent from canonical authority')

    tiling=_text('tools/src/pcr_tools/tiling.py')+_text('tools/src/pcr_tools/tiling_backend.py')+_text('tools/src/pcr_tools/external_validation.py')
    for marker in ('primalscheme','olivar','primerpooler'):
        if marker not in tiling.lower():
            error(f'multiplex: tiled-scheme upstream/validation marker missing: {marker}')

    for rel in ('knowledge/reviews/MULTIPLEX-MATURITY-AUDIT.md','release/current/CURRENT-MULTIPLEX-CLOSURE.md'):
        if not (ROOT/rel).exists():
            error(f'multiplex: closure/review artifact missing: {rel}')
