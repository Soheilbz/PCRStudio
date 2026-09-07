"""What produced a result, so it can be repeated or disbelieved on evidence.

A design is a claim about a molecule somebody is about to spend money on. The
claim is only checkable if the thing that made it can be identified: which
version of Primer3, computed under which thermodynamic model, by which build of
this worker. Without that, a result from last year is a set of numbers nobody
can reproduce and nobody can fault.

Cheap to collect and easy to forget, which is why it happens here rather than
being remembered at each call site.
"""

from __future__ import annotations

import platform
from collections.abc import Mapping
from typing import Any

from .presets import TM_MODEL
from .runtime_contract import (
    CONTRACT_VERSION,
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PARAMETER_MAP_VERSION,
    TOOLS,
)
from .specificity import METHOD_ID, METHOD_VERSION
from .thermo import salt_correction_for_conditions
from .tool_runtime import tool_status


def _version(module: str) -> str:
    """The installed version of one package, or why it is not there."""
    try:
        from importlib.metadata import version

        return version(module)
    except Exception:
        return "unknown"


def _libprimer3_version() -> str:
    """Return the bundled Primer3 engine version, not only the Python package."""
    try:
        from primer3.thermoanalysis import get_libprimer3_version

        return str(get_libprimer3_version())
    except Exception:
        return "unknown"


def provenance(conditions: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Everything needed to run this again and get the same answer."""
    versions = {
        "pcrstudio_tools": _version("pcrstudio-tools"),
        "primer3_py": _version("primer3-py"),
        "libprimer3": _libprimer3_version(),
        # ViennaRNA is intentionally a separate optional process. Reporting its
        # installed distribution when present makes an accessibility result
        # reproducible without importing it into the Primer3 package.
        "viennarna": _version("ViennaRNA"),
    }
    primer3_package_status = tool_status("primer3_py")
    primer3_core_status = tool_status("primer3_core")
    model = dict(TM_MODEL)
    if conditions is not None:
        method, primer3_value = salt_correction_for_conditions(dict(conditions))
        if method == "owczarzy":
            model.update(
                {
                    "name": "SantaLucia 1998 nearest-neighbour with Owczarzy 2008 salt correction",
                    "salt_correction": "Owczarzy 2008",
                    "primer3_salt_corrections": primer3_value,
                }
            )
        if float(conditions.get("dntp_conc", 0.0)) > float(conditions.get("dv_conc", 0.0)):
            model.update(
                {
                    "divalent_cation_effect": "not-considered-by-primer3",
                    "divalent_cation_note": (
                        "PRIMER_DNTP_CONC exceeds PRIMER_SALT_DIVALENT; Primer3 omits "
                        "the divalent-cation term from its salt correction."
                    ),
                }
            )

    return {
        "worker": versions["pcrstudio_tools"],
        "runtime_contract_version": CONTRACT_VERSION,
        "parameter_map_version": PARAMETER_MAP_VERSION,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "toolchain_manifest": {
            tool_id: {"configured_version": spec.version, "execution_scope": spec.execution_scope}
            for tool_id, spec in TOOLS.items()
        },
        "primer3_py": versions["primer3_py"],
        "primer3_artifact": {
            "primer3_py_record_sha256": primer3_package_status.get("artifact_sha256"),
            "libprimer3_carrier_record_sha256": primer3_core_status.get("artifact_sha256"),
            "libprimer3_version_matches_contract": primer3_core_status.get(
                "version_matches_contract"
            ),
            "artifact_identity": primer3_core_status.get("artifact_identity"),
        },
        "tool_versions": versions,
        "python": platform.python_version(),
        "model": model,
        "methods": {
            "specificity": {
                "id": METHOD_ID,
                "version": METHOD_VERSION,
            },
            "accessibility": {
                "worker": "pcr_accessibility",
                "model": "ViennaRNA, Mathews 2004 DNA parameters",
                "optional": True,
                "parameters": {
                    **{
                        "dangles": 2,
                        "noGU": 0,
                        "no_closingGU": 0,
                        "noLonelyPairs": 0,
                        "tetra_loop": 1,
                        "special_hp": 1,
                        "salt_m": 1.021,
                        "circ": 0,
                    },
                    "window": 150,
                    "max_base_pair_span": 150,
                },
            },
        },
        "platform": f"{platform.system()} {platform.machine()}",
        "note": (
            "Primer3 is bundled with primer3-py rather than installed separately; both the "
            "primer3-py package version and bundled libprimer3 engine version are recorded."
        ),
    }
