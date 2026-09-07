from __future__ import annotations

from pathlib import Path

from pcr_tools import tool_runtime


def test_olivar_external_managed_requires_explicit_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PCRSTUDIO_OLIVAR", raising=False)
    resolved = tool_runtime.resolve("olivar")
    assert resolved.available is False
    assert resolved.source.startswith("explicit-env-required:")


def test_olivar_external_managed_resolves_explicit_wrapper(monkeypatch, tmp_path: Path) -> None:
    wrapper = tmp_path / "pcrstudio-olivar"
    wrapper.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="ascii")
    wrapper.chmod(0o755)
    monkeypatch.setenv("PCRSTUDIO_OLIVAR", str(wrapper))
    resolved = tool_runtime.resolve("olivar")
    assert resolved.available is True
    assert resolved.path == wrapper.resolve()
    assert resolved.source == "env:PCRSTUDIO_OLIVAR"


def test_tiling_strict_preflight_requires_only_selected_primary(monkeypatch) -> None:
    monkeypatch.setenv("PCRSTUDIO_TOOLCHAIN_MODE", "strict")
    seen: list[str] = []

    def status(tool_id: str):
        seen.append(tool_id)
        return {
            "available": True,
            "version_matches_contract": True,
            "expected_artifact_sha256": "0" * 64,
            "artifact_hash_matches": True,
        }

    monkeypatch.setattr(tool_runtime, "tool_status", status)
    monkeypatch.setattr(tool_runtime, "configured_database_contract", lambda _prefix: {
        "paths": ["db"], "sha256": "0" * 64, "scope": "production",
        "manifest": "manifest", "manifest_contract_consistent": True,
        "content_hash_matches": True, "index_artifacts_match": True,
    })
    tool_runtime.require_engine_toolchain(
        "tiling-scheme", "tiled-scheme", {"tilingBackend": "olivar"}
    )
    assert "olivar" in seen
    assert "primalscheme3" not in seen
