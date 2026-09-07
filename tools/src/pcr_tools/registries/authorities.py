"""Generated unified scientific-authority loader for all PCRStudio engines."""
from __future__ import annotations
import json
from importlib.resources import files
from typing import Any

def _load(filename: str) -> dict[str, Any]:
    return json.loads(files("pcr_tools").joinpath(f"data/{filename}").read_text(encoding="utf-8"))

ASSEMBLY_AUTHORITY = _load("assembly-authority.generated.json")
CONSENSUS_AUTHORITY = _load("consensus-authority.generated.json")
DISCRIMINATING_AUTHORITY = _load("discriminating-authority.generated.json")
INVERSE_AUTHORITY = _load("inverse-authority.generated.json")
MUTAGENESIS_AUTHORITY = _load("mutagenesis-authority.generated.json")
NESTED_AUTHORITY = _load("nested-authority.generated.json")
PROBE_AUTHORITY = _load("probe-authority.generated.json")
RACE_AUTHORITY = _load("race-authority.generated.json")
SEQUENCING_AUTHORITY = _load("sequencing-authority.generated.json")
TILING_AUTHORITY = _load("tiling-authority.generated.json")
FLANKING_AUTHORITY = _load("flanking-protocol-authority.generated.json")
LAMP_AUTHORITY = _load("lamp-protocol-authority.generated.json")

def record(authority: dict[str, Any], record_id: str) -> dict[str, Any]:
    try:
        return dict(authority["records"][record_id])
    except KeyError as exc:
        raise ValueError(f"unknown authority record `{record_id}`") from exc
