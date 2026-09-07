"""Independent interaction evidence must respect physical reaction groups."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pcr_tools import external_validation as validation


def _oligo(name: str, sequence: str, *, tube: int | None = None, pool: int | None = None):
    return {
        "name": name,
        "kind": "primer",
        "ordered_sequence": sequence,
        "annealing_sequence": sequence,
        "tail_sequence": "",
        "tube": tube,
        "pool": pool,
    }


def test_primerpooler_runs_once_per_actual_tube_and_never_crosses_tubes(monkeypatch: pytest.MonkeyPatch):
    oligos = [
        _oligo("a-F", "ACGTACGTACGTACGTACGT", tube=0),
        _oligo("a-R", "TGCATGCATGCATGCATGCA", tube=0),
        _oligo("c-F", "AACCAACCAACCAACCAACC", tube=0),
        _oligo("b-F", "AGCTAGCTAGCTAGCTAGCT", tube=1),
        _oligo("b-R", "TCGATCGATCGATCGATCGA", tube=1),
        _oligo("d-F", "GATCGATCGATCGATCGATC", tube=1),
    ]
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        validation,
        "tool_status",
        lambda tool_id: {"available": True, "configured_version": "1.89"},
    )

    def fake_run_tool(tool_id, args, **kwargs):
        fasta = args[-1]
        text = open(fasta, encoding="utf-8").read()
        calls.append({"tool": tool_id, "args": list(args), "fasta": text})
        return SimpleNamespace(stdout="no problematic interactions\n", stderr="", returncode=0), {
            "tool_id": tool_id,
            "operation_id": kwargs["operation_id"],
        }

    monkeypatch.setattr(validation, "run_tool", fake_run_tool)
    result = {
        "reaction": {
            "mv_conc": 50.0,
            "dv_conc": 2.0,
            "dntp_conc": 0.8,
            "dna_conc": 50.0,
            "anneal_extend_c": 60.0,
        },
    }
    evidence = validation._primerpooler(
        oligos, engine_id="flanking-pair", module_id="standard-pcr", result=result
    )

    assert evidence["status"] == "evidence-collected"
    assert evidence["evidence"]["grouping"] == "tube-or-pool"
    # Two calls are the physical tube audits.  The third is the explicitly
    # evidence-only pool proposal, which is allowed to consider the complete
    # selected primer set and is never accepted as a tube assignment.
    assert len(calls) == 3
    physical_calls = calls[:2]
    contents = [str(call["fasta"]) for call in physical_calls]
    assert any(">a-F" in text and ">c-F" in text and ">b-F" not in text for text in contents)
    assert any(">b-F" in text and ">d-F" in text and ">a-F" not in text for text in contents)
    assert all(str(call["args"][0]).startswith("--dg=333.15,2.0,50.0,0.8") for call in physical_calls)
    assert all("--counts" in call["args"] for call in physical_calls)
    assert "--pools=?,1," in str(calls[2]["args"])


def test_explicit_tube_takes_precedence_over_pool_for_physical_grouping(monkeypatch: pytest.MonkeyPatch):
    oligos = [
        _oligo("a", "ACGTACGTACGTACGTACGT", tube=0, pool=4),
        _oligo("b", "TGCATGCATGCATGCATGCA", tube=0, pool=5),
        _oligo("c", "AGCTAGCTAGCTAGCTAGCT", tube=0, pool=6),
    ]
    monkeypatch.setattr(
        validation,
        "tool_status",
        lambda tool_id: {"available": True, "configured_version": "1.89"},
    )
    calls = 0

    def fake_run_tool(tool_id, args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(stdout="ok\n", stderr="", returncode=0), {"tool_id": tool_id}

    monkeypatch.setattr(validation, "run_tool", fake_run_tool)
    evidence = validation._primerpooler(
        oligos,
        engine_id="flanking-pair",
        module_id="standard-pcr",
        result={"reaction": {}},
    )
    assert calls == 1
    assert [group["group"] for group in evidence["evidence"]["groups"]] == ["tube:0"]


def _lamp_hit(role: str, start: int, end: int, orientation: str, expected: str):
    return {
        "lamp_set_index": 1,
        "lamp_region_role": role,
        "subject": "subject-1",
        "start": start,
        "end": end,
        "orientation": orientation,
        "expected_orientation": expected,
        "mismatches": 0,
        "full_length": True,
        "critical_terminal_exact": True,
    }


def test_blast_lamp_topology_detects_reverse_complement_locus():
    # Physical coordinates are the mirror of a valid 220-nt reference locus.
    hits = [
        _lamp_hit("F3", 192, 210, "reverse", "forward"),
        _lamp_hit("F2", 167, 185, "reverse", "forward"),
        _lamp_hit("F1c", 120, 140, "forward", "reverse"),
        _lamp_hit("B1c", 95, 115, "reverse", "forward"),
        _lamp_hit("B2", 52, 70, "forward", "reverse"),
        _lamp_hit("B3", 27, 45, "forward", "reverse"),
    ]
    out = validation._blast_lamp_topology(
        hits,
        {
            "parameter_set": {
                "f2_b2_span": [120, 180],
                "loop_span": [40, 60],
                "outer_gap": [0, 20],
                "middle_gap": [0, 100],
            }
        },
    )
    assert out["exact_compatible_locus_count_lower_bound"] == 1
    assert out["compatible_loci"][0]["locus_orientation"] == "reverse"


def test_lamp_blast_queries_split_composite_oligos_and_exclude_synthetic_linker():
    oligos = [
        {
            "name": "F3",
            "annealing_sequence": "AACCGGTTAACCGGTTAA",
            "lamp_role": "F3",
            "lamp_set_index": 1,
        },
        {
            "name": "FIP",
            "annealing_sequence": "ACGTACGTACGTACGTAC",
            "lamp_target_tail_sequence": "TTGCAATTGCAATTGCAA",
            "lamp_linker_sequence": "TTTT",
            "lamp_role": "FIP",
            "lamp_set_index": 1,
        },
        {
            "name": "BIP",
            "annealing_sequence": "TGCATGCATGCATGCATG",
            "lamp_target_tail_sequence": "GGCCAAGGCCAAGGCCAA",
            "lamp_linker_sequence": "TTTT",
            "lamp_role": "BIP",
            "lamp_set_index": 1,
        },
        {
            "name": "B3",
            "annealing_sequence": "CCGGAATTCCGGAATTCC",
            "lamp_role": "B3",
            "lamp_set_index": 1,
        },
        {
            "name": "LF",
            "annealing_sequence": "ATGCCGATGCCGATGCCG",
            "lamp_role": "LF",
            "lamp_set_index": 1,
        },
        {
            "name": "LB",
            "annealing_sequence": "CGTTAACGTTAACGTTAA",
            "lamp_role": "LB",
            "lamp_set_index": 1,
        },
    ]
    queries = validation._lamp_blast_region_queries(oligos)
    by_role = {q["lamp_region_role"]: q["annealing_sequence"] for q in queries}
    assert set(by_role) == {"F3", "F2", "F1c", "B1c", "B2", "B3", "LF", "LB"}
    assert by_role["F2"] == oligos[1]["annealing_sequence"]
    assert by_role["F1c"] == oligos[1]["lamp_target_tail_sequence"]
    assert by_role["B2"] == oligos[2]["annealing_sequence"]
    assert by_role["B1c"] == oligos[2]["lamp_target_tail_sequence"]
    assert by_role["LF"] == oligos[4]["annealing_sequence"]
    assert by_role["LB"] == oligos[5]["annealing_sequence"]
    kinds = {q["lamp_region_role"]: q["kind"] for q in queries}
    assert kinds["LF"] == kinds["LB"] == "lamp-loop-region"
    assert all(kinds[role] == "lamp-region" for role in {"F3", "F2", "F1c", "B1c", "B2", "B3"})
    assert all("TTTT" not in seq for seq in by_role.values())


def test_loop_set_runtime_contract_declares_conditional_mafft_and_mfe_structure_ops():
    from pcr_tools.runtime_contract import ENGINE_BINDINGS

    bindings = {b["tool_id"]: b for b in ENGINE_BINDINGS["loop-set"]}
    assert bindings["mafft"]["role"] == "CONDITIONAL_PRIMARY"
    assert bindings["mafft"]["operations"] == ["align_panel"]
    assert set(bindings["mfeprimer"]["operations"]) == {
        "validate_role_specificity",
        "validate_dimer",
        "validate_hairpin",
    }


def test_loop_set_mfeprimer_ordered_oligo_qc_executes_dimer_and_hairpin(monkeypatch: pytest.MonkeyPatch, tmp_path):
    calls: list[str] = []

    def fake_run_tool(tool_id, args, **kwargs):
        calls.append(kwargs["operation_id"])
        return SimpleNamespace(stdout="ok\n", stderr="", returncode=0), {
            "tool_id": tool_id,
            "operation_id": kwargs["operation_id"],
        }

    monkeypatch.setattr(validation, "run_tool", fake_run_tool)
    oligos = [
        {
            "name": "FIP",
            "ordered_sequence": "TTGCAATTGCAATTGCAATTTTACGTACGTACGTACGTAC",
            "annealing_sequence": "ACGTACGTACGTACGTAC",
            "tail_sequence": "TTGCAATTGCAATTGCAATTTT",
        },
        {
            "name": "BIP",
            "ordered_sequence": "GGCCAAGGCCAAGGCCAATTTTTGCATGCATGCATGCATG",
            "annealing_sequence": "TGCATGCATGCATGCATG",
            "tail_sequence": "GGCCAAGGCCAAGGCCAATTTT",
        },
    ]
    records, warnings = validation._mfeprimer_oligo_qc(
        oligos,
        workspace=tmp_path,
        engine_id="loop-set",
        module_id="lamp",
        reaction={"mv_conc": 50.0, "dv_conc": 2.0, "dntp_conc": 0.8, "dna_conc": 50.0},
    )
    assert warnings == []
    assert calls == ["validate_dimer", "validate_hairpin"]
    assert [record["operation"] for record in records] == ["dimer", "hairpin"]


def test_loop_set_mfeprimer_qc_never_crosses_alternative_lamp_sets(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    calls: list[dict[str, object]] = []

    def fake_run_tool(tool_id, args, **kwargs):
        fasta_path = args[args.index("-i") + 1]
        calls.append(
            {
                "operation_id": kwargs["operation_id"],
                "fasta": open(fasta_path, encoding="utf-8").read(),
            }
        )
        return SimpleNamespace(stdout="ok\n", stderr="", returncode=0), {
            "tool_id": tool_id,
            "operation_id": kwargs["operation_id"],
        }

    monkeypatch.setattr(validation, "run_tool", fake_run_tool)
    oligos = [
        {
            "name": "S1-FIP",
            "ordered_sequence": "ACGTACGTACGTACGTACGT",
            "annealing_sequence": "ACGTACGTACGTACGTACGT",
            "tail_sequence": "",
            "lamp_set_index": 1,
        },
        {
            "name": "S1-BIP",
            "ordered_sequence": "TGCATGCATGCATGCATGCA",
            "annealing_sequence": "TGCATGCATGCATGCATGCA",
            "tail_sequence": "",
            "lamp_set_index": 1,
        },
        {
            "name": "S2-FIP",
            "ordered_sequence": "AACCAACCAACCAACCAACC",
            "annealing_sequence": "AACCAACCAACCAACCAACC",
            "tail_sequence": "",
            "lamp_set_index": 2,
        },
        {
            "name": "S2-BIP",
            "ordered_sequence": "GGTTGGTTGGTTGGTTGGTT",
            "annealing_sequence": "GGTTGGTTGGTTGGTTGGTT",
            "tail_sequence": "",
            "lamp_set_index": 2,
        },
    ]
    records, warnings = validation._mfeprimer_oligo_qc(
        oligos,
        workspace=tmp_path,
        engine_id="loop-set",
        module_id="lamp",
        reaction={"mv_conc": 50.0, "dv_conc": 2.0, "dntp_conc": 0.8, "dna_conc": 50.0},
    )

    assert warnings == []
    assert len(calls) == 4
    assert {record["lamp_set_index"] for record in records} == {1, 2}
    assert {record["physical_group"] for record in records} == {"lamp-set-1", "lamp-set-2"}
    set1_fastas = [str(call["fasta"]) for call in calls if "S1-FIP" in str(call["fasta"])]
    set2_fastas = [str(call["fasta"]) for call in calls if "S2-FIP" in str(call["fasta"])]
    assert len(set1_fastas) == 2 and all("S2-FIP" not in text for text in set1_fastas)
    assert len(set2_fastas) == 2 and all("S1-FIP" not in text for text in set2_fastas)


def test_blast_lamp_topology_surfaces_upstream_hit_truncation_without_clean_claim():
    hits = [
        _lamp_hit("F3", 10, 28, "forward", "forward"),
        _lamp_hit("F2", 35, 53, "forward", "forward"),
        _lamp_hit("F1c", 80, 100, "reverse", "reverse"),
        _lamp_hit("B1c", 105, 125, "forward", "forward"),
        _lamp_hit("B2", 150, 168, "reverse", "reverse"),
        _lamp_hit("B3", 175, 193, "reverse", "reverse"),
    ]
    out = validation._blast_lamp_topology(
        hits,
        {
            "parameter_set": {
                "f2_b2_span": [120, 180],
                "loop_span": [40, 60],
                "outer_gap": [0, 20],
                "middle_gap": [0, 100],
            }
        },
        hit_collection_potentially_capped=True,
    )
    assert out["exact_compatible_locus_count_lower_bound"] == 1
    assert out["blast_hit_collection_potentially_capped"] is True
    assert out["complete_within_collected_hits"] is True
    assert out["interpretation_complete"] is False


def test_blast_lamp_topology_indexes_out_geometrically_impossible_decoys():
    # Large numbers of per-role BLAST hits should not spend the six-region
    # combination budget unless they survive the actual positional geometry.
    hits = [
        _lamp_hit("F3", 10, 28, "forward", "forward"),
        _lamp_hit("F2", 35, 53, "forward", "forward"),
        _lamp_hit("F1c", 80, 100, "reverse", "reverse"),
        _lamp_hit("B1c", 105, 125, "forward", "forward"),
        _lamp_hit("B2", 150, 168, "reverse", "reverse"),
        _lamp_hit("B3", 175, 193, "reverse", "reverse"),
    ]
    for offset in range(1000, 2000, 10):
        hits.extend([
            _lamp_hit("F1c", offset, offset + 20, "reverse", "reverse"),
            _lamp_hit("B1c", offset + 300, offset + 320, "forward", "forward"),
            _lamp_hit("B2", offset + 600, offset + 618, "reverse", "reverse"),
        ])
    out = validation._blast_lamp_topology(
        hits,
        {
            "parameter_set": {
                "f2_b2_span": [120, 180],
                "loop_span": [40, 60],
                "outer_gap": [0, 20],
                "middle_gap": [0, 100],
            }
        },
    )
    assert out["exact_compatible_locus_count_lower_bound"] == 1
    assert out["combination_evaluations"] == 1
    assert out["combination_capped"] is False
