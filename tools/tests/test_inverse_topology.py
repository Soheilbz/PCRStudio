from __future__ import annotations

import pytest

from pcr_tools.inverse_topology import (
    InverseTopologyError,
    exact_topology,
    public_topology,
    screen_enzyme_cohort,
)


def test_full_reference_topology_is_exact_and_does_not_expose_circle_sequence():
    anchor = "ACGTTGCA" * 8
    reference = "TTTAAGCTT" + anchor + "AAGCTTGGG"
    result = exact_topology(reference, anchor, "HindIII", circular=False)
    assert result["status"] == "exact"
    assert result["fragment_length"] >= len(anchor)
    assert result["source_segments"]
    assert "_circle_sequence" not in public_topology(result)


def test_ambiguous_anchor_fails_closed():
    anchor = "ACGTTGCA" * 4
    reference = "AAGCTT" + anchor + "AAGCTT" + anchor + "AAGCTT"
    with pytest.raises(InverseTopologyError, match="ambiguous"):
        exact_topology(reference, anchor, "HindIII")


def test_enzyme_cohort_preserves_explicit_order_without_a_cross_enzyme_score():
    anchor = "ACGTTGCA" * 8
    reference = "TTTAAGCTT" + anchor + "AAGCTTGGG"
    rows = screen_enzyme_cohort(reference, anchor, ["HindIII", "not-an-enzyme"])
    assert [row["enzyme"] for row in rows] == ["HindIII", "not-an-enzyme"]
    assert "score" not in rows[0]
    assert rows[1]["designable"] is False
