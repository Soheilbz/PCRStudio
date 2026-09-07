"""Final-panel orchestration regressions for multiplex design.

Multiplex candidate selection is not the validation boundary.  The selected
oligos, grouped by the tubes they will actually share, must be sent through the
common independent validator after optimization.
"""

from __future__ import annotations

import pytest

import pcr_tools.__main__ as cli
from pcr_tools.tool_runtime import ToolRuntimeError


def _wire(monkeypatch: pytest.MonkeyPatch, *, mode: str, validation_status: str):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    final_panel = {
        "engine": "multiplex",
        "tubes": [
            {
                "tube": 0,
                "sets": ["target-a", "target-c"],
                "primers": ["a-F", "a-R", "c-F", "c-R"],
            },
            {"tube": 1, "sets": ["target-b"], "primers": ["b-F", "b-R"]},
        ],
        "panel_validation_scope": "final-selected-oligos-grouped-by-tube",
        "selection_marker": "optimizer-final-panel",
    }
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        cli, "assay_identity", lambda request, command: ("standard-pcr", "flanking-pair")
    )
    monkeypatch.setattr(cli, "validate_required_context", lambda request, module_id: None)
    monkeypatch.setattr(cli, "require_engine_toolchain", lambda engine_id, module_id, request: None)
    monkeypatch.setattr(cli, "multiplex_run", lambda request: final_panel.copy())
    monkeypatch.setattr(cli, "engine_contract", lambda engine_id, module_id: {"engine": engine_id})
    monkeypatch.setattr(cli, "module_contract", lambda module_id: {"module": module_id})
    monkeypatch.setattr(cli, "resolved_parameters", lambda request, result: {"resolved": True})
    monkeypatch.setattr(cli, "toolchain_mode", lambda: mode)

    def fake_validate_result(*, command, request, result, engine_id, module_id):
        seen.update(
            command=command,
            request=request,
            result=result,
            engine_id=engine_id,
            module_id=module_id,
        )
        assert result["selection_marker"] == "optimizer-final-panel"
        assert result["panel_validation_scope"] == "final-selected-oligos-grouped-by-tube"
        assert result["tubes"] == final_panel["tubes"]
        return {
            "status": validation_status,
            "selected_oligos": 6,
            "methods": ["primerpooler", "mfeprimer", "blast"],
        }

    monkeypatch.setattr(cli, "validate_result", fake_validate_result)
    return seen


@pytest.mark.parametrize(
    "status",
    ["verification-incomplete", "validator-error", "evidence-collected-limited"],
)
def test_strict_multiplex_fails_closed_when_final_panel_validation_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, status: str
):
    _wire(monkeypatch, mode="strict", validation_status=status)
    with pytest.raises(ToolRuntimeError, match="strict final-panel validation did not complete"):
        cli.run_multiplex({"template": "ACGT" * 200})


def test_compatible_multiplex_preserves_incomplete_evidence_without_claiming_completion(
    monkeypatch: pytest.MonkeyPatch,
):
    _wire(monkeypatch, mode="compatible", validation_status="evidence-collected-limited")
    result = cli.run_multiplex({"template": "ACGT" * 200})

    assert result["verification"]["status"] == "evidence-collected-limited"
    assert result["verification"]["computational_design_complete"] is True
    assert result["verification"]["external_evidence_complete"] is False
    assert (
        "selected multiplex panel is audited after set selection" in result["verification"]["note"]
    )


def test_multiplex_wrapper_resolves_module_identity_from_target_assays(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    seen: dict[str, object] = {}
    request = {
        "targets": [
            {"assay": {"id": "standard-pcr", "engine": "flanking-pair"}},
            {"assay": {"id": "standard-pcr", "engine": "flanking-pair"}},
        ]
    }
    monkeypatch.setattr(
        cli,
        "require_engine_toolchain",
        lambda engine_id, module_id, request: seen.update(preflight=(engine_id, module_id)),
    )
    monkeypatch.setattr(
        cli, "multiplex_run", lambda request: {"tubes": [{"tube": 1}], "order_sheet": []}
    )
    monkeypatch.setattr(
        cli,
        "engine_contract",
        lambda engine_id, module_id: {"engine": engine_id, "module": module_id},
    )
    monkeypatch.setattr(cli, "module_contract", lambda module_id: {"module": module_id})
    monkeypatch.setattr(cli, "resolved_parameters", lambda request, result: {})
    monkeypatch.setattr(
        cli,
        "validate_result",
        lambda **kwargs: {
            "status": "not-applicable",
            "selected_oligos": 0,
            "interpretation_complete": True,
        },
    )
    monkeypatch.setattr(cli, "toolchain_mode", lambda: "compatible")

    result = cli.run_multiplex(request)
    assert seen["preflight"] == ("flanking-pair", "standard-pcr")
    assert result["module_contract"] == {"module": "standard-pcr"}
    assert result["runtime_contract"]["module"] == "standard-pcr"


def test_multiplex_wrapper_refuses_mixed_target_module_identity():
    request = {
        "targets": [
            {"assay": {"id": "standard-pcr", "engine": "flanking-pair"}},
            {"assay": {"id": "colony-pcr", "engine": "flanking-pair"}},
        ]
    }
    with pytest.raises(ValueError, match="same assay/module identity"):
        cli._multiplex_assay_identity(request)


def test_multiplex_wrapper_refuses_partial_target_module_identity():
    request = {
        "targets": [
            {"assay": {"id": "standard-pcr", "engine": "flanking-pair"}},
            {"name": "target-without-assay"},
        ]
    }
    with pytest.raises(ValueError, match="missing its canonical assay/module identity"):
        cli._multiplex_assay_identity(request)


def test_multiplex_resolved_parameters_refuses_invalid_constraint_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        cli,
        "resolved_parameters",
        lambda request, result: {"reaction": {}, "constraints": {}},
    )
    request = {"targets": [{"assay": {"id": "standard-pcr", "engine": "flanking-pair"}}]}
    answer = {"targets": [{"name": "a", "constraints": {}}], "constraint_scope": ""}
    with pytest.raises(ValueError, match="valid constraint_scope"):
        cli._multiplex_resolved_parameters(request, answer)


def test_multiplex_resolved_parameters_refuses_missing_worker_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        cli, "resolved_parameters", lambda request, result: {"reaction": {}, "constraints": {}}
    )
    request = {"targets": [{"assay": {"id": "standard-pcr", "engine": "flanking-pair"}}]}
    with pytest.raises(ValueError, match="shared reaction contract"):
        cli._multiplex_resolved_parameters(
            request, {"targets": [{"name": "a", "constraints": {}}], "constraint_scope": "shared"}
        )


def test_multiplex_resolved_parameters_preserve_per_target_policy_provenance(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        cli,
        "resolved_parameters",
        lambda request, result: {
            "reaction": {"temperature": {"value": 60, "source": "resolved"}},
            "constraints": {
                "product_min": {
                    "value": (result.get("constraints") or {}).get("product_min"),
                    "source": request.get("source", "unknown"),
                }
            },
        },
    )
    request = {"targets": [{"source": "a"}, {"source": "b"}]}
    answer = {
        "reaction": {"polymerase": "x"},
        "constraint_scope": "per-target",
        "targets": [
            {"name": "a", "constraints": {"product_min": 80}},
            {"name": "b", "constraints": {"product_min": 120}},
        ],
    }
    resolved = cli._multiplex_resolved_parameters(request, answer)
    assert resolved["constraint_scope"] == "per-target"
    assert resolved["constraints"] == {}
    assert [row["name"] for row in resolved["per_target_constraints"]] == ["a", "b"]
    assert resolved["per_target_constraints"][0]["constraints"]["product_min"]["source"] == "a"
    assert resolved["per_target_constraints"][1]["constraints"]["product_min"]["source"] == "b"
