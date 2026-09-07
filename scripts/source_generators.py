#!/usr/bin/env python3
"""Canonical ordered registry of source-derived release generators.

Both preparation and source qualification consume this list. Keeping generator
ownership in one place prevents the release preparer from silently omitting an
artifact that qualification later expects to be current.
"""
from __future__ import annotations

# Order is intentional: later authorities may consume projections emitted by
# earlier ones. Names are stable qualification gate identifiers.
SOURCE_GENERATORS: tuple[tuple[str, str], ...] = (
    ("foundation-contract-generator-check", "generate-foundation-contracts.py"),
    ("domain-vocabulary-generator-check", "generate-domain-vocabulary.py"),
    ("method-fidelity-generator-check", "generate-method-fidelity.py"),
    ("multiplex-capabilities-generator-check", "generate-multiplex-capabilities.py"),
    ("engine-authority-generator-check", "generate-engine-authorities.py"),
    ("engine-contract-generator-check", "generate-engine-contracts.py"),
    ("runtime-artifact-generator-check", "generate-runtime-artifacts.py"),
    ("operations-policy-generator-check", "generate-operations-policy.py"),
    ("flanking-protocol-authority-generator-check", "generate-flanking-protocol-authority.py"),
    ("lamp-protocol-authority-generator-check", "generate-lamp-protocol-authority.py"),
    ("scientific-authority-registry-generator-check", "generate-scientific-authority-registry.py"),
    ("expert-audit-artifact-generator-check", "generate-expert-audit-artifacts.py"),
    ("flanking-evidence-ledger-generator-check", "generate-flanking-evidence-ledger.py"),
    ("http-contract-generator-check", "generate-http-contract.py"),
    # Dependency/source changes must reach the SBOM before static consistency is
    # rendered, otherwise preparation can manufacture a stale static audit.
    ("sbom-generator-check", "generate-sbom.py"),
)

CURRENT_STATIC_GENERATOR = (
    "current-static-consistency-generator-check",
    "generate-current-static-audit.py",
)
