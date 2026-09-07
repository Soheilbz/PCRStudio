from __future__ import annotations

import pytest

from pcr_tools.mgb_authority import MgbAuthorityError, apply_import, candidates, exchange_manifest


def _candidates():
    return candidates("ACCTATGCTAGCTACGATCGTACGATCGATGCTAGCATCGATCGTACGATC", start=4, end=48)


def test_export_is_hash_bound_and_contains_no_internal_tm():
    cands = _candidates()
    export = exchange_manifest(cands, authority_id="thermofisher-primer-express-mgb")
    assert len(export["candidate_set_sha256"]) == 64
    assert export["decision_impact"] == "external-authority-required"
    assert all("tm" not in row and "tm_c" not in row for row in export["candidates"])


def test_import_requires_the_exact_candidate_set_hash_and_provenance():
    cands = _candidates()
    export = exchange_manifest(cands, authority_id="thermofisher-primer-express-mgb")
    payload = {
        "schema": "pcrstudio.mgb-authority-result.v1",
        "authority_id": "thermofisher-primer-express-mgb",
        "candidate_set_sha256": export["candidate_set_sha256"],
        "tool": "Primer Express",
        "version": "externally-recorded",
        "calculated_at": "2026-09-05T00:00:00Z",
        "candidates": [{"candidate_id": cands[0]["candidate_id"], "tm_c": 69.0}],
    }
    resolved = apply_import(cands, payload, authority_id="thermofisher-primer-express-mgb")
    assert resolved["ranked_candidates"][0]["tm_source"] == "external-mgb-authority"
    payload["candidate_set_sha256"] = "0" * 64
    with pytest.raises(MgbAuthorityError, match="candidate_set_sha256"):
        apply_import(cands, payload, authority_id="thermofisher-primer-express-mgb")
