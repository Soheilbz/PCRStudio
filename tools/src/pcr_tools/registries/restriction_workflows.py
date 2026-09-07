"""Source-conditioned bench workflows for restriction cloning.

The catalogue is deliberately small and exact. It describes only public,
reviewed family/workflow protocols. Enzyme-specific facts (optimal temperature,
methylation sensitivity, heat inactivation, double-digest activity, star
activity, end geometry) stay unresolved unless the exact-enzyme registry owns
them. Bench workflow evidence never changes primer ranking.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "1.0.0"
DECISION_IMPACT = "none-on-primer-ranking"

DIGEST_PROTOCOLS: dict[str, dict[str, Any]] = {
    "neb-cutsmart-standard": {
        "vendor": "New England Biolabs",
        "name": "NEB rCutSmart standard restriction digest",
        "source_url": "https://www.neb.com/en/protocols/2013/12/16/restriction-endonuclease-digestion",
        "source_scope": "general NEB restriction digest starting conditions; exact enzyme conditions remain enzyme-specific",
        "values": {
            "reaction_volume_ul": 50.0,
            "dna_ug": 1.0,
            "buffer_x": 1.0,
            "enzyme_units_per_ug_starting": 10.0,
            "digest_time_min": 60.0,
        },
        "ranges": {"enzyme_units_per_ug": [5.0, 10.0]},
        "unresolved": [
            "exact-enzyme incubation temperature",
            "exact-enzyme methylation sensitivity",
            "exact-enzyme heat-inactivation conditions",
            "exact double-digest activity/compatibility",
            "exact-enzyme star-activity caveats",
        ],
    },
    "neb-cutsmart-timesaver": {
        "vendor": "New England Biolabs",
        "name": "NEB rCutSmart Time-Saver-qualified digest",
        "source_url": "https://www.neb.com/en/tools-and-resources/usage-guidelines/optimizing-restriction-endonuclease-reactions",
        "source_scope": "family timing only; executable use requires exact selected enzymes to be Time-Saver qualified",
        "values": {
            "reaction_volume_ul": 50.0,
            "dna_ug": 1.0,
            "buffer_x": 1.0,
            "enzyme_units_per_ug_starting": 10.0,
        },
        "ranges": {
            "enzyme_units_per_ug": [5.0, 10.0],
            "digest_time_min": [5.0, 15.0],
        },
        "unresolved": [
            "Time-Saver eligibility of each exact selected enzyme",
            "exact-enzyme incubation temperature",
            "exact-enzyme methylation sensitivity",
            "exact-enzyme heat-inactivation conditions",
            "exact double-digest activity/compatibility",
        ],
    },
    "thermo-fastdigest-universal": {
        "vendor": "Thermo Fisher Scientific",
        "name": "Thermo Scientific FastDigest universal-buffer workflow",
        "source_url": "https://documents.thermofisher.com/TFS-Assets/BID/Reference-Materials/fastdigest-restriction-enzymes-labaid.pdf",
        "source_scope": "FastDigest family protocol; enzyme-specific inactivation/methylation remains product-specific",
        "values": {
            "plasmid_reaction_volume_ul": 20.0,
            "plasmid_dna_ug_max": 1.0,
            "buffer_x": 1.0,
            "fastdigest_enzyme_ul_per_1ug": 1.0,
            "family_incubation_temperature_c": 37.0,
        },
        "ranges": {"digest_time_min": [5.0, 15.0]},
        "unresolved": [
            "exact-enzyme incubation time within the family range",
            "exact-enzyme heat-inactivation conditions",
            "exact-enzyme methylation sensitivity",
            "exact-enzyme end geometry",
        ],
    },
}

DEPHOSPHORYLATION_PROTOCOLS: dict[str, dict[str, Any]] = {
    "none": {
        "vendor": None,
        "name": "No dephosphorylation",
        "source_url": None,
        "source_scope": "explicitly records that this optional step is not planned",
        "values": {},
        "ranges": {},
        "unresolved": [],
    },
    "neb-quick-cip-m0525": {
        "vendor": "New England Biolabs",
        "name": "Quick CIP M0525 dephosphorylation",
        "source_url": "https://www.neb.com/en-us/protocols/protocol-for-dephosphorylation-of-5-ends-of-dna-using-quick-cip-neb-m0525",
        "source_scope": "published Quick CIP reaction example",
        "values": {
            "reaction_volume_ul": 20.0,
            "dna_ends_pmol": 1.0,
            "cutsmart_buffer_x": 1.0,
            "quick_cip_ul": 1.0,
            "incubation_temperature_c": 37.0,
            "incubation_time_min": 10.0,
            "heat_inactivation_temperature_c": 80.0,
            "heat_inactivation_time_min": 2.0,
        },
        "ranges": {},
        "unresolved": [
            "whether the simultaneously used restriction enzyme is heat-inactivatable; purify first when it is not",
        ],
    },
}

LIGATION_PROTOCOLS: dict[str, dict[str, Any]] = {
    "neb-t4-dna-ligase-m0202": {
        "vendor": "New England Biolabs",
        "name": "T4 DNA Ligase M0202 cloning ligation",
        "source_url": "https://www.neb.com/en/protocols/dna-ligation-with-t4-dna-ligase-m0202",
        "source_scope": "published cloning example; 1:3 vector:insert is a starting example, not a universal optimum",
        "values": {
            "reaction_volume_ul": 20.0,
            "ligase_buffer_x": 1.0,
            "ligase_units": 400.0,
            "example_vector_ng": 50.0,
            "example_vector_pmol": 0.020,
            "example_insert_pmol": 0.060,
            "example_vector_insert_molar_ratio": "1:3",
            "heat_inactivation_temperature_c": 65.0,
            "heat_inactivation_time_min": 10.0,
        },
        "ranges": {},
        "branches": {
            "sticky_end": [
                {"temperature_c": 16.0, "time": "overnight"},
                {"temperature_c": 25.0, "time_min": 10.0},
            ],
            "blunt_or_single_base_overhang": [
                {"temperature_c": 16.0, "time": "overnight"},
                {"temperature_c": 25.0, "time_min": 120.0},
            ],
        },
        "unresolved": [
            "ligation incubation branch until exact insert/vector end geometry is established",
            "experiment-specific vector:insert molar-ratio optimization",
        ],
    },
    "neb-quick-ligation-m2200": {
        "vendor": "New England Biolabs",
        "name": "Quick Ligation Kit M2200",
        "source_url": "https://www.neb.com/en-us/protocols/quick-ligation-protocol",
        "source_scope": "published Quick Ligation example; protocol specifically says not to heat-inactivate Quick Ligase",
        "values": {
            "reaction_volume_ul": 20.0,
            "quick_ligation_buffer_x": 1.0,
            "example_vector_ng": 50.0,
            "example_vector_insert_molar_ratio": "1:3",
            "incubation_temperature_c": 25.0,
            "incubation_time_min": 5.0,
            "heat_inactivate": False,
        },
        "ranges": {},
        "unresolved": ["experiment-specific vector:insert molar-ratio optimization"],
    },
}


def _copy_record(table: dict[str, dict[str, Any]], protocol_id: str, kind: str) -> dict[str, Any]:
    record = table.get(protocol_id)
    if record is None:
        raise ValueError(f"Unknown restriction-cloning {kind} protocol {protocol_id!r}.")
    out = deepcopy(record)
    out["id"] = protocol_id
    out["kind"] = kind
    out["schema_version"] = SCHEMA_VERSION
    out["decision_impact"] = DECISION_IMPACT
    return out


def resolve_restriction_workflow(
    *,
    digest_protocol: str | None,
    dephosphorylation_protocol: str | None,
    ligation_protocol: str | None,
) -> dict[str, Any]:
    if not digest_protocol:
        raise ValueError("restriction-cloning requires restriction_digest_protocol")
    if not dephosphorylation_protocol:
        raise ValueError(
            "restriction-cloning requires explicit restriction_dephosphorylation_protocol; use 'none' when omitted at the bench"
        )
    if not ligation_protocol:
        raise ValueError("restriction-cloning requires restriction_ligation_protocol")
    return {
        "schema_version": SCHEMA_VERSION,
        "decision_impact": DECISION_IMPACT,
        "digest": _copy_record(DIGEST_PROTOCOLS, digest_protocol, "digest"),
        "dephosphorylation": _copy_record(
            DEPHOSPHORYLATION_PROTOCOLS, dephosphorylation_protocol, "dephosphorylation"
        ),
        "ligation": _copy_record(LIGATION_PROTOCOLS, ligation_protocol, "ligation"),
        "controls": {
            "required_measured_controls": [
                "vector-only/background control appropriate to the cloning workflow",
                "post-transformation clone verification appropriate to the construct",
            ],
            "note": "Bench controls are measured evidence and do not mutate the primer design result.",
        },
    }


def generated_catalogue() -> dict[str, Any]:
    def table(src: dict[str, dict[str, Any]], kind: str) -> dict[str, Any]:
        return {key: _copy_record(src, key, kind) for key in sorted(src)}

    return {
        "schema_version": SCHEMA_VERSION,
        "decision_impact": DECISION_IMPACT,
        "digest": table(DIGEST_PROTOCOLS, "digest"),
        "dephosphorylation": table(DEPHOSPHORYLATION_PROTOCOLS, "dephosphorylation"),
        "ligation": table(LIGATION_PROTOCOLS, "ligation"),
    }
