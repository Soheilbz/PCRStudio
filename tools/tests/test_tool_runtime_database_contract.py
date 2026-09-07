"""Specificity-database provenance must identify source and generated indexes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pcr_tools.tool_runtime import configured_database_contract


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, corrupt_index: bool = False):
    fasta = tmp_path / "ref.fasta"
    fasta.write_text(">ref\nACGTACGTACGT\n", encoding="utf-8")
    index = tmp_path / "ref.nsq"
    index.write_bytes(b"blast-index-v1")
    fasta_sha = _sha(fasta)
    index_sha = _sha(index)
    manifest = tmp_path / "ref.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "database_id": "ref",
                "scope": "production",
                "sequence_release": "test-release",
                "filtering": "none",
                "deduplication": "none",
                "indexed_fasta": fasta.name,
                "fasta_sha256": fasta_sha,
                "index_artifacts": [
                    {"name": index.name, "bytes": index.stat().st_size, "sha256": index_sha}
                ],
            }
        ),
        encoding="utf-8",
    )
    if corrupt_index:
        index.write_bytes(b"corrupted-index")

    prefix = "PCRSTUDIO_TEST_DATABASE"
    monkeypatch.setenv(prefix, str(fasta))
    monkeypatch.setenv(f"{prefix}_SHA256", fasta_sha)
    monkeypatch.setenv(f"{prefix}_SCOPE", "production")
    monkeypatch.setenv(f"{prefix}_MANIFEST", str(manifest))
    return configured_database_contract(prefix)


def test_database_contract_verifies_every_declared_index_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    contract = _configured(tmp_path, monkeypatch)
    assert contract["manifest_contract_consistent"] is True
    assert contract["content_hash_matches"] is True
    assert contract["index_artifacts_declared"] == 1
    assert contract["index_artifacts_match"] is True
    assert contract["index_artifacts"][0]["status"] == "verified"


def test_database_contract_detects_stale_or_corrupted_index_even_when_fasta_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    contract = _configured(tmp_path, monkeypatch, corrupt_index=True)
    assert contract["manifest_contract_consistent"] is True
    assert contract["content_hash_matches"] is True
    assert contract["index_artifacts_match"] is False
    assert contract["index_artifacts"][0]["status"] == "missing-or-mismatched"


def test_index_manifest_cannot_escape_its_database_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fasta = tmp_path / "ref.fasta"
    fasta.write_text(">ref\nACGT\n", encoding="utf-8")
    outside = tmp_path.parent / "outside.idx"
    outside.write_bytes(b"outside")
    manifest = tmp_path / "ref.manifest.json"
    digest = _sha(fasta)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "database_id": "ref",
                "scope": "approved-reference",
                "sequence_release": "test-release",
                "filtering": "none",
                "deduplication": "none",
                "indexed_fasta": fasta.name,
                "fasta_sha256": digest,
                "index_artifacts": [{"name": "../outside.idx", "sha256": _sha(outside)}],
            }
        ),
        encoding="utf-8",
    )
    prefix = "PCRSTUDIO_TEST_DATABASE_TRAVERSAL"
    monkeypatch.setenv(prefix, str(fasta))
    monkeypatch.setenv(f"{prefix}_SHA256", digest)
    monkeypatch.setenv(f"{prefix}_SCOPE", "approved-reference")
    monkeypatch.setenv(f"{prefix}_MANIFEST", str(manifest))
    contract = configured_database_contract(prefix)
    assert contract["index_artifacts_match"] is False


def test_blast_prefix_recomputes_reviewed_fasta_from_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fasta = tmp_path / "ref.fasta"
    fasta.write_text(">ref\nACGTACGT\n", encoding="utf-8")
    index = tmp_path / "ref.nsq"
    index.write_bytes(b"index")
    digest = _sha(fasta)
    manifest = tmp_path / "ref.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "database_id": "ref",
                "scope": "approved-reference",
                "sequence_release": "test-release",
                "filtering": "reviewed",
                "deduplication": "reviewed",
                "indexed_fasta": fasta.name,
                "fasta_sha256": digest,
                "index_artifacts": [{"name": index.name, "sha256": _sha(index)}],
            }
        ),
        encoding="utf-8",
    )
    prefix = "PCRSTUDIO_TEST_BLAST_PREFIX"
    monkeypatch.setenv(prefix, str(tmp_path / "ref"))
    monkeypatch.setenv(f"{prefix}_SHA256", digest)
    monkeypatch.setenv(f"{prefix}_SCOPE", "approved-reference")
    monkeypatch.setenv(f"{prefix}_MANIFEST", str(manifest))
    contract = configured_database_contract(prefix)
    assert contract["manifest_contract_consistent"] is True
    assert contract["content_hash_matches"] is True
    assert contract["index_artifacts_match"] is True
