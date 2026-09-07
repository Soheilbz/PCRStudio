from __future__ import annotations

import pytest

from pcr_tools.method_fidelity import (
    MethodFidelityError,
    active_for_run,
    context_references,
    enforce_scientific_strict,
)
from pcr_tools.rpa_screening import screening_cohort


def _ids(rows):
    return {row["method_id"] for row in rows}


def test_generic_multiplex_separates_saddle_component_local_optimizer_and_reference(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "strict")
    active = active_for_run("standard-pcr", "multiplex", {}, {})
    assert {"primer3", "saddle-badness", "pcrstudio-multiplex-local-optimizer"} <= _ids(active)
    refs = context_references("generic-multiplex")
    assert "saddle-optimizer" in _ids(refs)
    with pytest.raises(MethodFidelityError, match="pcrstudio-multiplex-local-optimizer"):
        enforce_scientific_strict(active, context="standard-pcr:multiplex")


@pytest.mark.parametrize("module_id,blocked", [("arms-pcr", "arms-pcr-generalized-policy"), ("kasp", "kasp-compatible-policy")])
def test_generalized_named_method_lookalikes_are_not_scientific_strict_primary(monkeypatch, module_id, blocked):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "strict")
    active = active_for_run(module_id, "design", {}, {})
    assert blocked in _ids(active)
    with pytest.raises(MethodFidelityError, match=blocked):
        enforce_scientific_strict(active, context=f"{module_id}:design")


def test_tetra_arms_public_method_branch_is_scientific_strict_eligible(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "strict")
    active = active_for_run("tetra-primer-arms", "design", {}, {})
    assert "tetra-arms-ye-2001" in _ids(active)
    enforce_scientific_strict(active, context="tetra-primer-arms:design")


def _rpa_ranked(count: int):
    rows = []
    for i in range(count):
        rows.append(
            {
                "candidate": i,
                "score": 100.0 - i,
                "left": {"sequence": f"ACGTACGTACGTACGTACG{i % 10}"},
                "right": {"sequence": f"TGCATGCATGCATGCATGC{i % 10}"},
                "left_at": {"start": i * 10},
                "right_at": {"start": 300 + i * 11},
                "amplicon": "A" * 150,
            }
        )
    return rows


def test_rpa_empirical_matrix_gate_requires_eight_by_eight_when_requested():
    with pytest.raises(ValueError, match="8-forward by 8-reverse"):
        screening_cohort(_rpa_ranked(7), maximum=10, require_matrix_ready=True)
    cohort = screening_cohort(_rpa_ranked(8), maximum=10, require_matrix_ready=True)
    empirical = cohort["full_empirical_assay_development"]
    assert empirical["matrix_ready"] is True
    assert empirical["prepared_matrix_pair_count"] == 64
    assert len(empirical["prepared_forward_candidates"]) == 8
    assert len(empirical["prepared_reverse_candidates"]) == 8
