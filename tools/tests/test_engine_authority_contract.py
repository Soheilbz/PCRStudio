"""Current source contracts for engine authority projections and fail-closed boundaries.

Authored for the user's Linux test run. This module deliberately avoids
external scientific tools so it checks authority/projection drift separately
from native tool qualification.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_engine_json_projections_equal_canonical_sources():
    mapping = {
        "contracts/chemistry/qpcr-probe-protocols.json": "tools/src/pcr_tools/data/probe-authority.generated.json",
        "contracts/chemistry/race-protocols.json": "tools/src/pcr_tools/data/race-authority.generated.json",
        "contracts/chemistry/single-differential-corpus.json": "tools/src/pcr_tools/data/single-differential-corpus.generated.json",
    }
    for canonical, projection in mapping.items():
        assert load(canonical) == load(projection), (canonical, projection)
    matrix = load("knowledge/runtime/engine-capability-matrix.generated.json")
    assert matrix == load("tools/src/pcr_tools/data/engine-capability-matrix.generated.json")
    assert matrix == load("web/src/lib/engine-capability-matrix.generated.json")
    assert matrix["engine_count"] == 11


def test_qpcr_vendor_rules_are_not_internal_search_defaults():
    records = load("contracts/chemistry/qpcr-probe-protocols.json")["records"]
    idt = records["idt-primetime-conventional"]
    assert idt["probe_constraints"] == {"length_max": 28}
    assert idt["probe_tm_delta_min_c"] == 6.0
    assert (
        idt["internal_search_defaults"]["decision_authority"]
        == "PCRStudio-search-envelope-not-vendor-rule"
    )
    assert records["taqman-mgb-reference"]["execution_status"] == "external-authority-required"


def test_firstchoice_and_current_smarter_have_distinct_versioned_boundaries():
    records = load("contracts/chemistry/race-protocols.json")["records"]
    first = records["firstchoice-rlm-race"]
    assert first["execution_status"] == "executable"
    assert first["source_revision"] == "Rev A"
    assert first["partners"]["5prime:primary"]["sequence"] == "GCTGATGGCGATGAATGAACACTG"
    assert records["smarter-race-source-limited"]["execution_status"] == "source-limited"
    assert records["smarter-race-current"]["execution_status"] == "executable-if-complete"
    assert records["smarter-race-current"]["requires"]["partner_sequence"] is True
    assert records["smarter-race-current"]["requires"]["sop_revision"] is True
    assert records["smarter-race-current"]["requires"]["sop_sha256"] is True
    assert records["custom"]["source_kind"] == "caller-supplied-sop"
    assert "source_url" not in records["custom"]


def test_tiling_and_inverse_fail_closed_boundaries_remain_explicit():
    inverse = load("contracts/chemistry/inverse-pcr-protocols.json")["records"]
    tiling = load("contracts/chemistry/tiling-protocols.json")["records"]
    assert inverse["one-sided-internal-cut-reference"]["execution_status"] == "reference-only"
    assert tiling["olivar-1.3.3"]["execution_status"] == "executable-if-installed"
    assert tiling["artic-primer-bed-v3"]["coordinate_system"] == "0-based half-open"
