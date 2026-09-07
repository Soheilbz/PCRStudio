"""Dependency-light Generation 1 foundation characterization and property tests.

These tests deliberately do not import Primer3. They protect the architecture
contract even on a release-builder that lacks the native scientific toolchain;
the full thermodynamic suite remains a separate native qualification gate.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from pcr_tools.contract_loader import (
    ENGINES,
    FOUNDATION,
    MODULE_TO_ENGINE,
    MODULES,
    TOOL_PAYLOAD,
    TOOLS,
)
from pcr_tools.coordinates import Boundary, CircularPosition, HalfOpenInterval
from pcr_tools.ipc import IpcError, parse_request, success
from pcr_tools.numeric_recipe import Quantity, dilution_volume, resolve
from pcr_tools.validation_issue import ValidationIssue


def _valid_envelope(module: str = "lamp") -> dict[str, object]:
    row = MODULES[module]
    return {
        "protocolVersion": str(FOUNDATION["ipc_protocol_version"]),
        "requestSchema": int(FOUNDATION["request_schema_version"]),
        "resultSchema": int(FOUNDATION["result_schema_version"]),
        "requestId": "property-1",
        "command": row["command"],
        "engine": row["engine"],
        "module": module,
        "payload": {"assay": {"id": module, "engine": row["engine"]}},
    }


def test_generated_foundation_cardinality_and_bindings() -> None:
    assert len(MODULES) == 21
    assert len(ENGINES) == 11
    assert len(TOOLS) == len(TOOL_PAYLOAD["tools"])
    assert set(TOOLS) == set(TOOL_PAYLOAD["tools"])
    assert all(spec.tool_id == tool_id for tool_id, spec in TOOLS.items())
    assert {row["engine"] for row in MODULES.values()} == set(ENGINES)
    for module, row in MODULES.items():
        assert MODULE_TO_ENGINE[module] == row["engine"]
        assert ENGINES[row["engine"]]["command"] == row["command"]


def test_ipc_envelope_round_trip_and_fail_closed_identity() -> None:
    raw = _valid_envelope("lamp")
    envelope = parse_request(raw, "loop_set")
    wrapped = success(envelope, {"ok": "science"})
    assert wrapped["requestId"] == raw["requestId"]
    assert wrapped["payload"] == {"ok": "science"}

    for key, wrong in (
        ("protocolVersion", "stale"),
        ("requestSchema", 999),
        ("resultSchema", 999),
        ("engine", "flanking-pair"),
        ("module", "standard-pcr"),
    ):
        broken = dict(raw)
        broken[key] = wrong
        with pytest.raises(IpcError):
            parse_request(broken, "loop_set")


def test_half_open_coordinate_length_and_circular_normalization_properties() -> None:
    rng = random.Random(0xC001D00D)
    for _ in range(2_000):
        start = rng.randrange(0, 100_000)
        length = rng.randrange(0, 20_000)
        interval = HalfOpenInterval(Boundary(start), Boundary(start + length))
        assert interval.length == length

        reference = rng.randrange(1, 50_000)
        raw = rng.randrange(-(10**8), 10**8)
        position = CircularPosition(raw, reference)
        assert 0 <= position.value < reference
        assert position.value == raw % reference


def test_numeric_dilution_and_bounded_override_properties() -> None:
    rng = random.Random(0xB10C0DE)
    for _ in range(2_000):
        reaction = rng.uniform(1.0, 100.0)
        final_x = rng.uniform(0.001, 2.0)
        stock_x = rng.uniform(final_x, 500.0)
        got = dilution_volume(
            Quantity(reaction, "uL"), Quantity(final_x, "x"), Quantity(stock_x, "x")
        )
        assert got.unit == "uL"
        assert got.value == pytest.approx(reaction * final_x / stock_x)
        assert 0 <= got.value <= reaction

    resolution = resolve(
        baseline={"mg_mM": 8.0},
        ranges={"mg_mM": [6.0, 10.0]},
        overrides={"mg_mM": 9.0},
        subject="test",
    )
    assert resolution.values["mg_mM"] == 9.0
    assert resolution.origins["mg_mM"] == "user-override-within-source-bound"
    with pytest.raises(ValueError):
        resolve(ranges={"mg_mM": [6.0, 10.0]}, overrides={"mg_mM": 11.0}, subject="test")


def test_validation_issue_serialization_is_stable() -> None:
    issue = ValidationIssue(
        code="REQUIRED_CONTEXT_MISSING",
        severity="error",
        owner_step="reaction",
        field_path="lampInstrumentProfile",
        message="required",
        source="module-contract",
        blocking=True,
    )
    payload = issue.to_dict()
    assert payload == {
        "code": "REQUIRED_CONTEXT_MISSING",
        "severity": "error",
        "ownerStep": "reaction",
        "fieldPath": "lampInstrumentProfile",
        "message": "required",
        "source": "module-contract",
        "blocking": True,
    }


def test_generated_contract_files_are_byte_identical_across_consumers() -> None:
    root = Path(__file__).resolve().parents[2]
    names = (
        "foundation.generated.json",
        "module-contracts.generated.json",
        "engine-contracts.generated.json",
        "tool-contracts.generated.json",
    )
    bases = (
        root / "knowledge/runtime",
        root / "tools/src/pcr_tools/data",
        root / "web/src/lib/contracts",
        root / "crates/pcr-contracts/generated",
        root / "crates/pcr-core/generated",
    )
    for name in names:
        content = [(base / name).read_bytes() for base in bases]
        assert all(blob == content[0] for blob in content[1:]), name
        json.loads(content[0])


def test_cross_language_differential_corpus_matches_python_contracts() -> None:
    root = Path(__file__).resolve().parents[2]
    corpus = json.loads(
        (root / "contracts/differential-context.generated.json").read_text(encoding="utf-8")
    )
    assert len(corpus["cases"]) == 21
    for case in corpus["cases"]:
        module = case["module"]
        row = MODULES[module]
        assert row["engine"] == case["expectedEngine"]
        assert row["command"] == case["expectedCommand"]
        assert row["resource_weight"] == case["resourceWeight"]
        assert row["required_context"] == case["requiredContext"]
        assert row["conditional_required_context"] == case["conditionalRequiredContext"]
        assert row["wire_required_context"] == case["wireRequiredContext"]
        assert row["wire_conditional_required_context"] == case["wireConditionalRequiredContext"]
        assert row["wire_required_any_of"] == case["wireRequiredAnyOf"]
        assert row["field_owners"] == case["fieldOwners"]
        assert case["wrongEngine"] != case["expectedEngine"]


def test_reverse_complement_is_an_involution_for_iupac_oligos() -> None:
    from pcr_tools.degenerate import EXPANSION, reverse_complement

    rng = random.Random(0x5EEDC0DE)
    alphabet = tuple(EXPANSION)
    for _ in range(5_000):
        sequence = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 80)))
        assert reverse_complement(reverse_complement(sequence)) == sequence


def test_numeric_resolution_is_invariant_to_irrelevant_overlay_order() -> None:
    overlays = [
        {"id": "dna-only", "when": {"substrate": "dna"}, "set": {"mg_mM": 8.0}},
        {"id": "rna-only", "when": {"substrate": "rna"}, "set": {"rt_units": 50.0}},
    ]
    first = resolve(baseline={"salt_mM": 50.0}, overlays=overlays, scenario={"substrate": "dna"})
    second = resolve(
        baseline={"salt_mM": 50.0}, overlays=list(reversed(overlays)), scenario={"substrate": "dna"}
    )
    assert first.values == second.values
    assert first.origins == second.origins
    assert {row["id"] for row in first.applied_overlays} == {
        row["id"] for row in second.applied_overlays
    }


def test_tightening_numeric_range_never_makes_an_out_of_range_override_valid() -> None:
    rng = random.Random(0xC0FFEE)
    for _ in range(2_000):
        lo = rng.uniform(-100.0, 100.0)
        hi = lo + rng.uniform(0.001, 100.0)
        inner_lo = rng.uniform(lo, hi)
        inner_hi = rng.uniform(inner_lo, hi)
        candidate = hi + rng.uniform(0.001, 50.0)
        with pytest.raises(ValueError):
            resolve(ranges={"x": [lo, hi]}, overrides={"x": candidate}, subject="outer")
        with pytest.raises(ValueError):
            resolve(ranges={"x": [inner_lo, inner_hi]}, overrides={"x": candidate}, subject="inner")


def test_tool_adapter_rejects_unknown_registry_identity() -> None:
    from pcr_tools.tool_runtime import ToolRuntimeError, tool_adapter

    with pytest.raises(ToolRuntimeError, match="unknown tool contract"):
        tool_adapter(
            "not-a-real-tool",
            role="VALIDATOR",
            operation_id="contract-test",
            engine_id="flanking-pair",
            module_id="standard-pcr",
        )


def test_tool_adapter_capabilities_are_registry_backed() -> None:
    from pcr_tools.tool_runtime import tool_adapter

    adapter = tool_adapter(
        "primer3_core",
        role="PRIMARY",
        operation_id="primer-design",
        engine_id="flanking-pair",
        module_id="standard-pcr",
    )
    capabilities = adapter.capabilities()
    assert capabilities["tool_id"] == "primer3_core"
    assert capabilities["configured_version"]
    assert capabilities["operation_id"] == "primer-design"


def test_egress_policy_is_https_only_and_cannot_expand_at_runtime(monkeypatch):
    from pcr_tools.egress import (
        EgressPolicyError,
        allowed_hosts,
        validate_https_url,
        validate_redirect,
    )

    monkeypatch.delenv("PCRSTUDIO_EGRESS_ALLOWLIST", raising=False)
    assert allowed_hosts() == frozenset({"eutils.ncbi.nlm.nih.gov"})
    assert (
        validate_https_url("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi")
        == "eutils.ncbi.nlm.nih.gov"
    )
    for url in (
        "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        "https://example.org/",
        "https://eutils.ncbi.nlm.nih.gov:8443/",
        "https://user:secret@eutils.ncbi.nlm.nih.gov/",
    ):
        with pytest.raises(EgressPolicyError):
            validate_https_url(url)

    # Redirects remain on the exact source host even if a future release grows
    # the compiled allowlist. The current release has one reviewed host.
    assert (
        validate_redirect(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?retmode=text",
        )
        == "eutils.ncbi.nlm.nih.gov"
    )

    monkeypatch.setenv("PCRSTUDIO_EGRESS_ALLOWLIST", "example.org")
    with pytest.raises(EgressPolicyError):
        allowed_hosts()


def test_autosave_conflict_merge_does_not_duplicate_large_draft_over_server_action() -> None:
    """The browser already owns the merge base; do not transmit two draft copies.

    A legal maximum-size sequence can make ``settings + baseSettings`` exceed
    Next's Server Action body ceiling. Conflict reconciliation therefore returns
    the remote snapshot and performs the three-way merge in the browser before
    an optimistic-concurrency retry.
    """
    root = Path(__file__).resolve().parents[2]
    actions = (root / "web/src/lib/projects/actions.ts").read_text(encoding="utf-8")
    autosave = (root / "web/src/components/project/use-draft-autosave.ts").read_text(
        encoding="utf-8"
    )

    assert "baseSettings: Record<string, unknown>" not in actions
    assert "remoteUpdatedAt?: string" in actions
    assert "remoteSettings?: Record<string, unknown>" in actions
    assert "threeWayMerge(serverBaseDraft.current, draft, remote)" in autosave
    assert "MAX_ACTION_BYTES" in autosave
