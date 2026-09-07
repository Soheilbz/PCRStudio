from __future__ import annotations

from pcr_tools.tiling_evidence import (
    parse_depth_tsv,
    repair_handoff,
    scheme_diff,
    version_transition,
)


def test_depth_import_flags_dropouts_without_claiming_cause():
    evidence = parse_depth_tsv("amplicon\tdepth\nA1\t120\nA2\t4\n", dropout_threshold=20)
    assert evidence["summary"]["dropout_count"] == 1
    handoff = repair_handoff(
        evidence, operation="scheme-create", existing_bed="chr\t0\t100\tA2_LEFT\n"
    )
    assert handoff["recommended_operation"] == "repair-mode"
    assert handoff["causal_claim"] == "none"


def test_scheme_diff_recommends_minor_change_but_never_auto_publishes():
    old = "ref\t0\t20\tP1\t1\t+\n"
    new = "ref\t1\t21\tP1\t1\t+\nref\t40\t60\tP2\t1\t-\n"
    diff = scheme_diff(old, new)
    transition = version_transition("1.2.3", diff)
    assert diff["changed"] == ["P1"]
    assert diff["added"] == ["P2"]
    assert transition["recommended"] == "1.3.0"
    assert transition["auto_publish"] is False
