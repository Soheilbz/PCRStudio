"""Regression contract for the pinned PrimalScheme3 3.3.0 lifecycle adapter.

These tests mock external execution.  They verify PCRStudio's command/coordinate
contract without requiring PrimalScheme, MAFFT, or any scientific executable on
the test host.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pcr_tools import primalscheme_adapter as adapter

VALID_BED = "ref\t10\t30\tamplicon_1_LEFT\t1\t+\tACGTACGTACGTACGTACGT\nref\t90\t110\tamplicon_1_RIGHT\t1\t-\tTGCATGCATGCATGCATGCA\n"
VALID_CONFIG = '{"scheme": "reviewed"}'


def test_primer_bed_parser_accepts_lf_and_crlf_under_zero_based_half_open_contract(tmp_path: Path):
    path = tmp_path / "input.bed"
    path.write_text(VALID_BED.replace("\n", "\r\n"), encoding="utf-8")
    rows = adapter._parse_bed(path)

    assert [(row["start"], row["end"], row["role"]) for row in rows] == [
        (10, 30, "LEFT"),
        (90, 110, "RIGHT"),
    ]


@pytest.mark.parametrize(
    "line, message",
    [
        ("ref\t10\t30\tname\t1\t+", "no primer sequence"),
        ("ref\t-1\t30\tname\t1\t+\tACGT", "zero-based half-open"),
        ("ref\t30\t30\tname\t1\t+\tACGT", "zero-based half-open"),
        ("ref\t10\t30\tname\t1\t?\tACGT", "invalid strand"),
        ("ref\tstart\t30\tname\t1\t+\tACGT", "non-integer"),
    ],
)
def test_primer_bed_parser_fails_closed_on_ambiguous_or_lossy_import(
    tmp_path: Path, line: str, message: str
):
    path = tmp_path / "bad.bed"
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(adapter.PrimalSchemeImportError, match=message):
        adapter._parse_bed(path)


def test_region_bed_merges_overlaps_and_preserves_requested_denominator():
    regions = adapter._parse_region_bed(
        "ref\t10\t30\ta\r\nref\t25\t50\tb\r\nref\t70\t80\tc\r\n",
        reference_length=100,
    )
    assert regions == [(10, 50), (70, 80)]
    covered = set(range(10, 20)) | set(range(24, 50)) | set(range(70, 75))
    gaps = adapter._gaps_within(regions, covered, why="uncovered requested region")
    assert [(gap["from"], gap["to"]) for gap in gaps] == [(20, 24), (75, 80)]


def test_region_bed_refuses_coordinates_past_reference():
    with pytest.raises(adapter.PrimalSchemeImportError, match="past the 100-base reference"):
        adapter._parse_region_bed("ref\t90\t101\n", reference_length=100)


def test_fasta_input_requires_unique_ids_and_equal_width_when_reviewed():
    with pytest.raises(adapter.PrimalSchemeImportError, match="unique identifier"):
        adapter._fasta_records(">same\nACGT\n>same\nACGT\n")

    records = adapter._fasta_records(">a\nACGT--\n>b\nAC-TTT\n")
    assert len(records) == 2
    assert len({len(sequence) for _, sequence in records}) == 1


def _lifecycle(monkeypatch: pytest.MonkeyPatch, operation: str, **extra):
    captured: dict[str, object] = {}
    chosen = SimpleNamespace(limits=SimpleNamespace(product_min=300, product_max=500))

    monkeypatch.setattr(adapter, "available", lambda: True)
    monkeypatch.setattr(
        adapter,
        "_prepare_input",
        lambda request: (
            chosen,
            ">ref\n" + "A" * 500 + "\n",
            "A" * 500,
            {"mode": "prealigned", "authority": "test"},
        ),
    )

    def fake_run_tool(tool_id, args, **kwargs):
        captured["tool_id"] = tool_id
        captured["args"] = list(args)
        captured["kwargs"] = kwargs
        workspace = Path(kwargs["cwd"])
        if operation != "scheme-replace":
            output = workspace / "scheme"
            output.mkdir(parents=True, exist_ok=True)
            (output / "result.primer.bed").write_text(VALID_BED, encoding="utf-8")
        return SimpleNamespace(stdout="", stderr="", returncode=0), {
            "tool_id": tool_id,
            "operation_id": kwargs["operation_id"],
        }

    monkeypatch.setattr(adapter, "run_tool", fake_run_tool)
    monkeypatch.setattr(
        adapter,
        "_normalise_result",
        lambda **kwargs: {
            "operation": kwargs["operation"],
            "bed_name": kwargs["bed"].name,
            "command": captured["args"],
        },
    )

    request = {
        "template": "A" * 500,
        "tilingOperation": operation,
        "tilingAlignmentMode": "prealigned",
        "assay": {"id": "tiled-scheme"},
        **extra,
    }
    result = adapter.run(request)
    return result, captured


def test_scheme_create_contract_is_explicit_and_uses_output(monkeypatch):
    result, captured = _lifecycle(monkeypatch, "scheme-create", overlap=20, pools=4)
    assert result["operation"] == "scheme-create"
    args = captured["args"]
    assert args[0] == "scheme-create"
    assert "--output" in args


def test_panel_create_contract_is_explicit(monkeypatch):
    result, captured = _lifecycle(
        monkeypatch,
        "panel-create",
        panelMode="region-only",
        pools=4,
        regionBed="ref\t10\t30\n",
    )
    assert result["operation"] == "panel-create"
    assert captured["args"][0] == "panel-create"


def test_repair_mode_requires_reviewed_bed_and_config(monkeypatch):
    result, captured = _lifecycle(
        monkeypatch,
        "repair-mode",
        existingBed=VALID_BED,
        schemeConfig=VALID_CONFIG,
    )
    assert result["operation"] == "repair-mode"
    assert captured["args"][0] == "repair-mode"


def test_scheme_replace_uses_the_pinned_upstream_operation(monkeypatch):
    result, captured = _lifecycle(
        monkeypatch,
        "scheme-replace",
        existingBed=VALID_BED,
        schemeConfig=VALID_CONFIG,
        primerName="amplicon_1_LEFT",
    )
    assert result["operation"] == "scheme-replace"
    assert captured["args"][0] == "scheme-replace"
    assert "--output" not in captured["args"]


def test_scheme_lifecycle_preserves_output_as_a_generated_artifact(monkeypatch):
    _result, captured = _lifecycle(monkeypatch, "scheme-create", overlap=20, pools=4)
    assert "--output" in captured["args"]
