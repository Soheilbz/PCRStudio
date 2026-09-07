#!/usr/bin/env python3
"""Dependency-free PCRStudio static source audit.

Generation 1 foundation keeps this file as the stable command while concern-specific
checks live under scripts/audit/.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

from audit.common import ERRORS, WARNINGS
from audit.foundation import (
    audit_current_surface_hygiene, audit_fork_roundtrip_surface,
    audit_generated_runtime_artifacts, audit_module_engine_parity,
    audit_python_json_toml, audit_required_context_surface,
    audit_regression_guards, audit_uncompiled_duplicate_sources,
)
from audit.lamp import audit_lamp_evidence_ledger, audit_lamp_protocol_contract, audit_lamp_web_contract
from audit.flanking import audit_flanking_protocol_contract
from audit.scientific import (
    audit_scientific_integrity, audit_scientific_authority_provenance, audit_capability_truth, audit_tool_deployment_contract,
    audit_toolchain_contract_parity, audit_worker_scientific_environment_contract,
)
from audit.engine_closure import audit_engine_contract_integrity
from audit.release import (
    audit_expert_release_artifacts, audit_expected_files, audit_hygiene,
    audit_markdown_links, audit_assay_page_architecture, audit_source_release_hardening,
    audit_current_release_identity, audit_current_identity_uniformity, audit_dependency_maintenance_exceptions, audit_capability_maturity, audit_maintainability_budgets,
)
from audit.application import audit_application_foundation
from audit.architecture import audit_architecture_integrity
from audit.engine_maturity import audit_engine_maturity
from audit.method_fidelity import audit_method_fidelity
from audit.multiplex import audit_multiplex_closure
from audit.operations import audit_operations_policy


def main() -> int:
    checks = (
        audit_generated_runtime_artifacts, audit_current_surface_hygiene,
        audit_uncompiled_duplicate_sources, audit_regression_guards,
        audit_fork_roundtrip_surface, audit_required_context_surface,
        audit_python_json_toml, audit_module_engine_parity,
        audit_lamp_web_contract, audit_lamp_protocol_contract,
        audit_flanking_protocol_contract, audit_lamp_evidence_ledger,
        audit_toolchain_contract_parity, audit_scientific_integrity, audit_scientific_authority_provenance, audit_capability_truth,
        audit_engine_contract_integrity,
        audit_tool_deployment_contract, audit_assay_page_architecture,
        audit_worker_scientific_environment_contract, audit_expert_release_artifacts,
        audit_hygiene, audit_markdown_links, audit_expected_files, audit_current_release_identity, audit_current_identity_uniformity, audit_dependency_maintenance_exceptions, audit_capability_maturity, audit_maintainability_budgets, audit_source_release_hardening,
        audit_application_foundation, audit_architecture_integrity, audit_engine_maturity, audit_method_fidelity, audit_multiplex_closure, audit_operations_policy,
    )
    for check in checks:
        check()
    print(f"PCRStudio static source audit: {len(ERRORS)} error(s), {len(WARNINGS)} warning(s)")
    for item in ERRORS:
        print(f"ERROR: {item}")
    for item in WARNINGS:
        print(f"WARNING: {item}")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
