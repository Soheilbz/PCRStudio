from __future__ import annotations

from types import SimpleNamespace

from pcr_tools import external_validation as ev


def test_flanking_primerpooler_is_optional_not_release_gating() -> None:
    assert "primerpooler" in ev._requested_validators("flanking-pair")
    assert "primerpooler" not in ev._required_validators("flanking-pair")
    assert {"mfeprimer", "ncbi_blast_plus"} <= ev._required_validators("flanking-pair")


def test_nested_primerpooler_is_optional_not_release_gating() -> None:
    assert "primerpooler" in ev._requested_validators("nested")
    assert "primerpooler" not in ev._required_validators("nested")


def test_tiling_primerpooler_remains_required_validator() -> None:
    assert "primerpooler" in ev._requested_validators("tiling-scheme")
    assert "primerpooler" in ev._required_validators("tiling-scheme")


def test_optional_unavailable_check_does_not_make_required_set_incomplete(monkeypatch) -> None:
    # This test exercises the role partition directly. The full envelope is
    # covered by orchestration tests; this guard prevents OPTIONAL from drifting
    # back into the release-gating set.
    required = ev._required_validators("flanking-pair")
    checks = [
        {"tool_id": "mfeprimer", "status": "evidence-collected"},
        {"tool_id": "ncbi_blast_plus", "status": "evidence-collected"},
        {"tool_id": "primerpooler", "status": "unchecked"},
    ]
    unchecked = [c for c in checks if c["status"] == "unchecked" and c["tool_id"] in required]
    assert unchecked == []


def test_mfeprimer_keeps_database_contract_after_relative_database_invocation(
    monkeypatch,
    tmp_path,
) -> None:
    """The path loop must not overwrite the database evidence contract."""
    monkeypatch.setattr(
        ev,
        "tool_status",
        lambda tool_id: {"available": True, "configured_version": "4.5.1"},
    )
    database_path = str(tmp_path / "real-test.fasta")
    monkeypatch.setattr(
        ev,
        "configured_database_contract",
        lambda prefix: {
            "paths": [database_path],
            "sha256": "a" * 64,
            "scope": "approved-reference",
            "claim_capability": "production-specificity-evidence",
            "manifest": str(tmp_path / "real-test.manifest.json"),
            "manifest_sha256": "b" * 64,
            "manifest_error": None,
            "manifest_contract_consistent": True,
            "database_id": "real-test",
            "sequence_release": "RefSeq-test",
            "taxonomy_release": "accession-scoped",
            "filtering": "single-record",
            "deduplication": "unique-accession",
            "content_hash_matches": True,
            "index_artifacts_declared": 1,
            "index_artifacts_match": True,
        },
    )

    def fake_run_tool(tool_id, args, **kwargs):
        return SimpleNamespace(stdout='{"PrimerList": [], "AmpList": []}', stderr=""), {
            "tool_id": tool_id,
            "operation_id": kwargs["operation_id"],
        }

    monkeypatch.setattr(ev, "run_tool", fake_run_tool)
    oligos = [
        {
            "name": "F",
            "kind": "primer",
            "ordered_sequence": "ACGTACGTACGTACGTACGT",
            "annealing_sequence": "ACGTACGTACGTACGTACGT",
            "tail_sequence": "",
        },
        {
            "name": "R",
            "kind": "primer",
            "ordered_sequence": "TGCATGCATGCATGCATGCA",
            "annealing_sequence": "TGCATGCATGCATGCATGCA",
            "tail_sequence": "",
        },
    ]
    evidence = ev._mfeprimer(
        oligos,
        engine_id="flanking-pair",
        module_id="standard-pcr",
        result={"reaction": {}, "constraints": {}},
    )

    assert evidence["status"] == "evidence-collected"
    assert evidence["evidence"]["database_scope"] == "approved-reference"
    assert evidence["evidence"]["database_count"] == 1
    assert "database_paths" not in evidence["evidence"]
    assert database_path not in str(evidence)
