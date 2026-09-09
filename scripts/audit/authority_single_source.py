"""Guard the current source tree against parallel protocol authorities.

The generated Rust/Web files are projections, not alternative registries.  A
small number of compatibility aliases may remain at an input migration
boundary, but current executable option lists must come from the reviewed
authority consumed by the rest of the stack.
"""
from __future__ import annotations

import json
import re

from .common import *  # noqa: F403


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")  # noqa: F405


def _json(relative: str) -> dict:
    return json.loads(_text(relative))


def audit_active_authority_single_sources() -> None:
    """Reject active hand-written copies of current protocol vocabularies."""

    expected_bindings = {
        "tools/src/pcr_tools/registries/flanking_protocols.py": (
            "STANDARD_PCR_PROTOCOLS",
            "QPCR_PROTOCOLS",
            "RPA_PROTOCOLS",
            "LONG_RANGE_PROTOCOLS",
            "DIGITAL_PROTOCOLS",
        ),
        "tools/src/pcr_tools/junction.py": ("ASSEMBLY_PROTOCOLS",),
        "tools/src/pcr_tools/mutagenic.py": (
            "EDITS",
            "POST_AMPLIFICATION_PROTOCOLS",
            "MUTAGENESIS_TOPOLOGIES",
        ),
        "tools/src/pcr_tools/probe.py": ("PROBE_PROTOCOLS",),
        "tools/src/pcr_tools/kasp.py": ("PROTOCOLS",),
        "crates/pcr-core/src/engines/discriminating_pair.rs": ("KASP_PROTOCOLS",),
    }
    for relative, names in expected_bindings.items():
        text = _text(relative)
        for name in names:
            assignments = list(
                re.finditer(
                    rf"^\s*(?:(?:pub\s+)?const\s+{re.escape(name)}\b[^=]*=|{re.escape(name)}\s*=)",
                    text,
                    flags=re.MULTILINE,
                )
            )
            if len(assignments) != 1:
                error(  # noqa: F405
                    f"{relative}: current authority binding {name} must have exactly one definition; found {len(assignments)}"
                )

    source_expectations = {
        "tools/src/pcr_tools/registries/flanking_protocols.py": (
            'STANDARD_PCR_PROTOCOLS = tuple(_GROUPS["standard_pcr"])',
            'DIGITAL_PROTOCOLS = tuple(_GROUPS["digital"])',
        ),
        "tools/src/pcr_tools/junction.py": (
            'ASSEMBLY_PROTOCOLS = tuple(ASSEMBLY_AUTHORITY["groups"]["protocols"])',
        ),
        "tools/src/pcr_tools/mutagenic.py": (
            'EDITS = tuple(MUTAGENESIS_AUTHORITY["groups"]["edit_kinds"])',
            'POST_AMPLIFICATION_PROTOCOLS = tuple(MUTAGENESIS_AUTHORITY["groups"]["protocols"])',
            'MUTAGENESIS_TOPOLOGIES = tuple(MUTAGENESIS_AUTHORITY["groups"]["topology_families"])',
        ),
        "tools/src/pcr_tools/probe.py": (
            'PROBE_PROTOCOLS = (',
            '*PROBE_AUTHORITY["groups"]["probe_protocols"],',
        ),
        "tools/src/pcr_tools/kasp.py": (
            'PROTOCOLS = tuple(DISCRIMINATING_AUTHORITY["groups"]["kasp_protocols"])',
        ),
        "crates/pcr-core/src/engines/discriminating_pair.rs": (
            "const KASP_PROTOCOLS: &[&str] = DISCRIMINATING_KASP_PROTOCOLS;",
        ),
    }
    for relative, markers in source_expectations.items():
        text = _text(relative)
        for marker in markers:
            if marker not in text:
                error(f"{relative}: current authority is not bound to the canonical projection: {marker}")  # noqa: F405

    if 'value="lgc-standard"' in _text("web/src/components/design/engine-fields/advanced-fields.tsx"):
        error("Web KASP controls expose the historical lgc-standard branch as a new-design option")  # noqa: F405

    # Compatibility aliases are migration inputs only. They must not leak into
    # the current option vocabulary or become a second protocol definition.
    probe = _text("tools/src/pcr_tools/probe.py")
    probe_block = probe.split("PROBE_PROTOCOLS = (", 1)[1].split(")", 1)[0]
    if '"taqman-mgb"' in probe_block:
        error("tools/src/pcr_tools/probe.py: historical taqman-mgb alias leaked into current protocol options")  # noqa: F405

    canonical = {
        "contracts/chemistry/discriminating-protocols.json": "kasp_protocols",
    }
    for relative, group in canonical.items():
        payload = _json(relative)  # noqa: F405
        groups = payload.get("groups", {})
        values = groups.get(group, []) if isinstance(groups, dict) else []
        if not values or len(values) != len(set(values)):
            error(f"{relative}: {group} is missing or contains duplicate current/migration IDs")  # noqa: F405
        records = payload.get("records", {})
        if not isinstance(records, dict) or not set(values) - {"not-selected"} <= set(records):
            error(f"{relative}: {group} has IDs without authority records")  # noqa: F405
