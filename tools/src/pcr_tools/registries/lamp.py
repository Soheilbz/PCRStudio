"""Canonical Loop Set/LAMP protocol registry.

The scientific catalogue and all closed vocabularies are authored once in
``contracts/chemistry/lamp-protocols.json`` and projected by
``scripts/generate-lamp-protocol-authority.py``.  This module is deliberately
thin so Python cannot silently diverge from Rust/Web/UI vocabulary.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

_AUTHORITY_PATH = Path(__file__).resolve().parents[1] / "data" / "lamp-protocol-authority.generated.json"
_AUTHORITY: dict[str, Any] = json.loads(_AUTHORITY_PATH.read_text(encoding="utf-8"))
_GROUPS: dict[str, list[str]] = _AUTHORITY["groups"]

# deepcopy preserves the historical expectation that callers may inspect a
# normal mutable mapping without ever mutating the generated authority file.
LAMP_PROTOCOL_REGISTRY: dict[str, dict[str, Any]] = deepcopy(_AUTHORITY["protocols"])
LAMP_PROTOCOLS = tuple(_GROUPS["protocols"])
LAMP_READOUTS = tuple(_GROUPS["readouts"])
LAMP_READOUT_CHEMISTRIES = tuple(_GROUPS["readout_chemistries"])
LAMP_SAMPLE_MATRICES = tuple(_GROUPS["sample_matrices"])
LAMP_SAMPLE_PREPARATIONS = tuple(_GROUPS["sample_preparations"])
LAMP_FORMULATIONS = tuple(_GROUPS["formulations"])
LAMP_CONFIRMATION_MODES = tuple(_GROUPS["confirmation_modes"])
LAMP_DETECTION_TOPOLOGIES = tuple(_GROUPS["detection_topologies"])
LAMP_DESIGN_INTENTS = tuple(_GROUPS["design_intents"])
LAMP_LOOP_POLICIES = tuple(_GROUPS["loop_policies"])
LAMP_DESIGN_STAGES = tuple(_GROUPS["design_stages"])
LAMP_PARAMETER_SETS = tuple(_GROUPS["parameter_sets"])
LAMP_GEOMETRY_PROFILES = tuple(_GROUPS["geometry_profiles"])
LAMP_INNER_LINKERS = tuple(_GROUPS["inner_linkers"])
LAMP_INSTRUMENT_PROFILES = tuple(_GROUPS["instrument_profiles"])
LAMP_CARRYOVER_STRATEGIES = tuple(_GROUPS["carryover_strategies"])
LAMP_RECONSTITUTION_OPTIONS = tuple(_GROUPS["reconstitution_options"])
LAMP_SPECIFICITY_ADDITIVES = tuple(_GROUPS["specificity_additives"])
LAMP_ACCELERATION_ADDITIVES = tuple(_GROUPS["acceleration_additives"])
LAMP_PRIMER_KINETICS_PROFILES = tuple(_GROUPS["primer_kinetics_profiles"])
LAMP_PREINCUBATION_STRATEGIES = tuple(_GROUPS["preincubation_strategies"])
LAMP_SAMPLE_BUFFER_TYPES = tuple(_GROUPS["sample_buffer_types"])
LAMP_MUTATION_ANCHORS = tuple(_GROUPS["mutation_anchors"])
LAMP_FIXED_PRIMER_ROLES = tuple(_GROUPS["fixed_primer_roles"])

_READOUT_CHEMISTRY_BRANCH: dict[str, str] = dict(_AUTHORITY["compatibility"]["readout_chemistry_branch"])
LAMP_AUTOMATIC_JUDGMENT: dict[str, Any] = deepcopy(_AUTHORITY["automatic_judgment"])
LAMP_SCREENING_COHORT: dict[str, Any] = deepcopy(_AUTHORITY["screening_cohort"])
LAMP_CATALOGUE_SNAPSHOT: dict[str, Any] = deepcopy(_AUTHORITY["catalogue_snapshot"])
