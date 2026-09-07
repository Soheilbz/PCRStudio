"""Named-method fidelity and approximation-boundary audit."""
from __future__ import annotations
import json
from .common import ROOT, error

GRADES={
 'F0-upstream-exact','F1-exact-public-port','F2-manual-rule-faithful',
 'F3-compatible-approximate','F4-external-authority-only'
}
PRIMARY_IMPACTS={'primary-design','primary-ranking','primary-generation','candidate-elimination','lamp-geometry-and-eligibility'}

def _text(rel:str)->str:
    return (ROOT/rel).read_text(encoding='utf-8')

def audit_method_fidelity()->None:
    path=ROOT/'contracts/method-fidelity.json'
    try: data=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        error(f'method-fidelity: canonical registry parse failed: {exc}'); return
    methods=data.get('methods'); modules=data.get('modules')
    if not isinstance(methods,dict) or not isinstance(modules,dict):
        error('method-fidelity: methods/modules registries are required'); return
    for method_id,row in methods.items():
        if not isinstance(row,dict): error(f'method-fidelity: {method_id} row must be an object'); continue
        if row.get('grade') not in GRADES: error(f'method-fidelity: {method_id} has invalid grade')
        for field in ('display_name','implementation','decision_impact','claim_boundary','authority_url'):
            if not str(row.get(field) or '').strip(): error(f'method-fidelity: {method_id} missing {field}')
        if not isinstance(row.get('scientific_strict_eligible'),bool): error(f'method-fidelity: {method_id} missing strict-eligibility boolean')
        if row.get('grade')=='F3-compatible-approximate' and row.get('scientific_strict_eligible') and row.get('decision_impact') in PRIMARY_IMPACTS:
            error(f'method-fidelity: approximate method {method_id} cannot be Scientific-Strict primary decision logic')
        if row.get('grade')=='F4-external-authority-only' and str(row.get('implementation')) not in {'external-authority','external-upstream-not-yet-managed'}:
            error(f'method-fidelity: F4 method {method_id} must remain external-authority only')
    module_contract=_text('contracts/modules.toml')
    module_ids=[]
    for line in module_contract.splitlines():
        line=line.strip()
        if line.startswith('id = "'):
            value=line.split('"',2)[1]
            if value in modules or value in {'standard-pcr','long-range-pcr','colony-pcr','nested-pcr','inverse-pcr','qpcr-sybr','qpcr-probe','digital-pcr','arms-pcr','tetra-primer-arms','kasp','species-specific-pcr','lamp','rpa','universal-primers','tiled-scheme','race','sequencing-primer','gibson-assembly','restriction-cloning','site-directed-mutagenesis'}:
                module_ids.append(value)
    public=set(module_ids)
    if set(modules)!=public:
        error(f'method-fidelity: module map differs from public module set; missing={sorted(public-set(modules))}, extra={sorted(set(modules)-public)}')
    for module_id, ids in modules.items():
        if not isinstance(ids,list) or not ids: error(f'method-fidelity: {module_id} has no method declarations'); continue
        for method_id in ids:
            if method_id not in methods: error(f'method-fidelity: {module_id} references unknown {method_id}')

    # Projection must be generated from the canonical registry.
    generated=ROOT/'tools/src/pcr_tools/data/method-fidelity.generated.json'
    if not generated.exists(): error('method-fidelity: runtime projection missing')
    for rel in ('knowledge/reviews/METHOD-FIDELITY-AUDIT.json','knowledge/reviews/METHOD-FIDELITY-AUDIT.md'):
        if not (ROOT/rel).exists(): error(f'method-fidelity: generated review artifact missing: {rel}')
    public_docs = _text('README.md') + _text('release/PUBLIC-SOURCE.md') + _text('release/RELEASE-NOTES.md')
    for marker in ('## Method fidelity','Method-fidelity closure is part of the current source candidate.','A subsequent method-fidelity closure adds a canonical named-method registry'):
        if marker not in public_docs: error(f'method-fidelity: public release documentation missing marker: {marker}')

    universal=_text('tools/src/pcr_tools/universal.py')
    for forbidden in ('Cheap stand-in for the real penalty','MEASURE_BEST ='):
        if forbidden in universal: error(f'method-fidelity: Universal Primers still contains decision-affecting surrogate marker: {forbidden}')
    for required in ('MAX_EXACT_PAIR_EVALUATIONS','Universal-primer exact search refused','will not thin candidates with a surrogate score'):
        if required not in universal: error(f'method-fidelity: Universal exact/fail-closed marker missing: {required}')

    lamp=_text('tools/src/pcr_tools/loop_set.py')
    # The diagnostic helper may exist, but it may not appear in either selection key.
    for fn in ('def preliminary_key','def stage2_key'):
        block=lamp[lamp.index(fn):]
        block=block[:block.index('\n\n', 1) if '\n\n' in block[1:] else len(block)]
        if '_generic_off_target_rank' in block: error(f'method-fidelity: LAMP generic linear proxy still affects {fn}')
    if 'LAMP exact-search boundary exceeded' not in lamp or 'generic_direct_decision_impact": "diagnostic-only"' not in lamp:
        error('method-fidelity: LAMP must fail closed on truncated search and keep the generic linear screen diagnostic-only')

    discr=json.loads((ROOT/'contracts/chemistry/discriminating-protocols.json').read_text(encoding='utf-8'))
    tetra=discr.get('records',{}).get('tetra-collins-day-2001-reference',{})
    if tetra.get('additional_mismatch_position_from_3prime') != -2 or int(tetra.get('inner_primer_length_nt_min') or 0) != 26:
        error('method-fidelity: named tetra-ARMS authority must enforce -2 mismatch and >=26-nt inner primers')
    if tetra.get('execution_status')!='executable-manual-rule-faithful':
        error('method-fidelity: tetra-ARMS named public method is not marked manual-rule-faithful executable')
    disc_py=_text('tools/src/pcr_tools/discriminate.py')
    for marker in ('TETRA_SECOND_MISMATCH_AT = -2','TETRA_INNER_MIN_NT = 26','with_tetra_second_mismatch'):
        if marker not in disc_py: error(f'method-fidelity: tetra-ARMS implementation marker missing: {marker}')

    multiplex=_text('tools/src/pcr_tools/multiplex.py')
    if 'SADDLE simulated annealing' not in multiplex or '"simulated_annealing": False' not in multiplex:
        error('method-fidelity: internal multiplex optimiser must not claim SADDLE simulated annealing')
    if methods.get('saddle-optimizer',{}).get('grade')!='F4-external-authority-only':
        error('method-fidelity: exact SADDLE optimiser must remain external-authority-only until official code/authority is available')

    rpa=_text('tools/src/pcr_tools/rpa_screening.py')
    for marker in ('forward_candidates_recommended": [8, 10]','reverse_candidates_recommended": [8, 10]','pair_matrix_recommended": [64, 100]','sequence_prediction_equivalence": False'):
        if marker not in rpa: error(f'method-fidelity: RPA empirical-development marker missing: {marker}')

    mut=_text('tools/src/pcr_tools/mutagenic.py')+_text('tools/src/pcr_tools/mutagenesis_workflows.py')
    for forbidden in ('orderable-reviewed-quikchange','orderable-reviewed-lightning-multi','NEBaseChanger multi-site -> NEBuilder HiFi route'):
        if forbidden in mut: error(f'method-fidelity: stale overstated mutagenesis claim remains: {forbidden}')
    for required in ('orderable-manual-faithful-quikchange','vendor_web_tool_equivalent":False','PCRStudio multi-site NEBuilder HiFi routing informed by NEBaseChanger workflow'):
        if required not in mut: error(f'method-fidelity: mutagenesis fidelity marker missing: {required}')

    kasp=_text('tools/src/pcr_tools/discriminate.py')+_text('tools/src/pcr_tools/kasp_plus_minus.py')
    if 'vendor_kraken_equivalent":False' not in kasp and 'vendor_kraken_equivalent": False' not in kasp:
        error('method-fidelity: KASP must preserve explicit non-equivalence to proprietary Kraken')

    orchestrator=_text('tools/src/pcr_tools/orchestrator.py')
    fingerprint=_text('tools/src/pcr_tools/fingerprints.py')
    webtypes=_text('web/src/lib/api/types.ts')
    if 'provenance["method_fidelity"]' not in orchestrator or 'method_fidelity": provenance.get' not in fingerprint:
        error('method-fidelity: per-run fidelity declarations are not fingerprint-bound')
    if 'method_fidelity:' not in webtypes or 'method_fidelity_registry:' not in webtypes:
        error('method-fidelity: Web provenance transport does not retain fidelity declarations')

    # User-facing names must describe public-rule/reference boundaries rather than imply vendor-tool equivalence.
    ui_claim_text = "\n".join([
        _text('web/src/components/project/workspace.tsx'),
        _text('web/src/components/design/engine-fields/lamp-fields.tsx'),
        _text('web/src/components/design/engine-fields.tsx'),
        _text('web/src/components/design/page-plan.ts'),
    ])
    for forbidden in ('PrimerExplorer V5 compatibility', 'NEBaseChanger → NEBuilder multi-site route', 'ARMSprimer3-style'):
        if forbidden in ui_claim_text:
            error(f'method-fidelity: stale user-facing equivalence wording remains: {forbidden}')
    for required in ('PrimerExplorer V5 public-rule profile', 'PCRStudio multi-site NEBuilder routing (NEBaseChanger workflow reference)'):
        if required not in ui_claim_text:
            error(f'method-fidelity: explicit user-facing fidelity boundary missing: {required}')

    # RPA empirical-matrix evidence must survive strict Web parsing; otherwise the backend can be truthful while the UI drops the evidence.
    rpa_schema = _text('web/src/lib/api/rpa-result-schemas.ts')
    rpa_ui = _text('web/src/components/design/design-result.tsx')
    for marker in ('prepared_forward_candidates', 'prepared_reverse_candidates', 'prepared_matrix_pair_count', 'matrix_ready'):
        if marker not in rpa_schema:
            error(f'method-fidelity: RPA Web schema drops empirical-matrix field: {marker}')
    if (
        "full_empirical_assay_development.matrix_ready" not in rpa_ui
        or '"ready" : "insufficient"' not in rpa_ui
    ):
        error('method-fidelity: RPA UI does not expose empirical matrix readiness')

    # Generic multiplex must expose the official SADDLE optimiser as a separate reference and block the F3 local optimiser in Scientific-Strict.
    main_py = _text('tools/src/pcr_tools/__main__.py')
    if 'method_fidelity_context_references("generic-multiplex")' not in main_py or 'enforce_method_fidelity(active_methods' not in main_py:
        error('method-fidelity: multiplex active/reference separation or Scientific-Strict enforcement is missing')
