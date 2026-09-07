"""Several targets in one tube.

The claim this module makes is that choosing pairs for a set is not the same as
choosing the best pair for each target separately. Most of what is tested here
is that claim: cases built so the per-target best answer and the per-set best
answer differ, where a tool that did N independent searches would give the
wrong one.

The rest is the readout. Two products thirty bases apart are one band on a gel,
two peaks on a capillary, and not a question at all for sequencing — so the
readout is required, and refusing to guess it is itself behaviour worth pinning.
"""

from __future__ import annotations

import random

import pytest

import pcr_tools.multiplex as multiplex_module
from pcr_tools.multiplex import (
    CROWDED,
    MAX_SEARCH_ROUNDS,
    MAX_TARGETS,
    Candidate,
    MultiplexError,
    badness,
    choose,
    run,
    separation_needed,
    set_badness,
    split_into_tubes,
)
from pcr_tools.thermo import reverse_complement

# ── The published objective ────────────────────────────────────────────────


def test_two_random_oligos_barely_register():
    """The baseline everything else is read against."""
    generator = random.Random(11)
    scores = [
        badness(
            "".join(generator.choice("ACGT") for _ in range(20)),
            "".join(generator.choice("ACGT") for _ in range(20)),
        )
        for _ in range(40)
    ]
    assert max(scores) < 100


def test_the_same_duplex_costs_far_more_at_the_three_prime_ends():
    """What makes this a primer measure rather than a hybridisation one.

    Extension starts at the 3' end. A five-base duplex that traps both 3' ends
    makes a primer dimer; the identical duplex sitting in the middle of both
    oligos mostly does not.
    """
    anchored = badness("AAAAAAAAAAAAAAAGGCCT", "AAAAAAAAAAAAAAAAGGCC")
    internal = badness("AAAAAGGCCTAAAAAAAAAA", "AAAAAAAAAAAGGCCAAAAA")

    assert anchored > 20 * internal


def test_a_longer_complementary_stretch_costs_more_than_a_shorter_one():
    short = badness("AAAAAAAAAAAAAAAAGGCC", "AAAAAAAAAAAAAAAAGGCC")
    longer = badness("AAAAAAAAAAAAGGCCGGCC", "AAAAAAAAAAAAGGCCGGCC")
    assert longer > short


def test_the_set_includes_each_oligo_against_itself():
    """An oligo dimerising with a second copy of itself is a real failure."""
    self_pairing = "GGCCGGCCAAAAGGCCGGCC"
    assert set_badness([self_pairing]) > 0


# ── Choosing for the set rather than for each target ───────────────────────


def pair(target: str, left: str, right: str, size: int, index: int = 0) -> Candidate:
    return Candidate(target=target, left=left, right=right, product_size=size, index=index)


def test_it_gives_up_a_targets_favourite_to_keep_the_tube_quiet():
    """The whole reason a set search exists.

    Target B has one option, and it is complementary to target A's first
    choice. A tool designing each target on its own would pick A's first choice
    and ship a set that eats itself; choosing for the set takes A's second.
    """
    trap = "GGCCGGCCTTAAGGCCGGCC"
    candidates = {
        "A": [
            pair("A", "AAAAAAAAAAAAAAAAAAAA", reverse_complement(trap), 200, index=0),
            pair("A", "AAAAAAAAAAAAAAAAAAAA", "TTATTATTATTATTATTATT", 200, index=1),
        ],
        "B": [pair("B", trap, "TTTTTTTTTTTTTTTTTTTT", 400)],
    }

    placement = choose(candidates, rounds=50)
    picked = {chosen.target: chosen.index for chosen in placement.chosen}
    assert picked["A"] == 1, "it kept the pair that fights B's only option"


def test_the_most_constrained_target_is_placed_first():
    """A target with three options constrains the tube more than one with a hundred.

    Placing it last means placing it into whatever is left, which is how a set
    search ends up with no room for the target that had the least to begin with.
    """
    candidates = {
        "roomy": [pair("roomy", "A" * 20, "T" * 20, 200, i) for i in range(9)],
        "tight": [pair("tight", "C" * 20, "G" * 20, 300)],
    }
    placement = choose(candidates, rounds=10)
    assert "tight (1)" in placement.steps[0]
    assert placement.steps[0].index("tight") < placement.steps[0].index("roomy")


def test_the_same_request_gives_the_same_tube():
    """A search that answered differently each time could not be checked.

    Two people comparing notes would disagree, and no recorded result would
    ever match.
    """
    candidates = {
        name: [
            pair(name, f"ACGT{name}AAAAAAAAAAA"[:20], "T" * 20, 200 + step * 40, step)
            for step in range(6)
        ]
        for name in ("one", "two", "three")
    }
    first = choose(candidates, rounds=100, seed=3)
    second = choose(candidates, rounds=100, seed=3)
    assert [c.index for c in first.chosen] == [c.index for c in second.chosen]


def test_a_target_with_no_candidates_is_refused_by_name():
    with pytest.raises(MultiplexError, match="no candidate pairs"):
        choose({"A": [pair("A", "A" * 20, "T" * 20, 200)], "B": []})


def test_zero_targets_per_tube_is_refused_before_the_split_can_loop():
    candidates = {"A": [pair("A", "A" * 20, "T" * 20, 200)]}
    with pytest.raises(MultiplexError, match=r"per_tube.*at least 1"):
        split_into_tubes(candidates, per_tube=0)


def test_negative_rounds_and_overlarge_rounds_are_refused():
    with pytest.raises(MultiplexError, match=r"rounds.*at least 0"):
        choose({}, rounds=-1)
    with pytest.raises(MultiplexError, match=r"rounds.*at most"):
        choose({}, rounds=MAX_SEARCH_ROUNDS + 1)


def test_non_integer_controls_are_refused_instead_of_truncated():
    with pytest.raises(MultiplexError, match=r"per_tube.*integer"):
        split_into_tubes({}, per_tube=1.5)


# ── What the reader can tell apart ─────────────────────────────────────────


def test_a_readout_nobody_named_is_refused_rather_than_guessed():
    with pytest.raises(MultiplexError, match="readout"):
        separation_needed(300, "eyeballs")


# ── Tubes ──────────────────────────────────────────────────────────────────


def test_a_panel_too_big_for_one_tube_is_split_rather_than_refused():
    """What laboratories actually do with a large panel.

    Splitting is the answer, not a failure to report, and a tool that refused
    above some plex count would be refusing the normal case.
    """
    candidates = {
        f"t{index}": [pair(f"t{index}", "A" * 20, "T" * 20, 200 + index)]
        for index in range(CROWDED + 4)
    }
    tubes = split_into_tubes(candidates, rounds=5)
    assert len(tubes) == 2
    assert sum(len(tube.chosen) for tube in tubes) == CROWDED + 4


# ── End to end, on a real sequence ─────────────────────────────────────────


def test_a_multiplex_without_a_readout_is_refused():
    with pytest.raises(MultiplexError, match="readout"):
        run({"targets": [{"template": "ACGT" * 100}, {"template": "ACGT" * 100}]})


def test_non_text_readout_is_refused_as_invalid_input():
    with pytest.raises(MultiplexError, match="readout"):
        run({"readout": ["agarose"], "targets": [{}, {}]})


def test_ngs_refuses_an_unused_size_reference_profile():
    with pytest.raises(MultiplexError, match=r"omit it for NGS"):
        run(
            {
                "readout": "ngs",
                "readout_profile": "qiagen-qiaxcel-high-resolution",
                "targets": [{"template": "A" * 200}, {"template": "C" * 200}],
            }
        )


def test_per_tube_cannot_exceed_the_public_target_ceiling():
    with pytest.raises(MultiplexError, match=r"per_tube.*at most"):
        run(
            {
                "readout": "ngs",
                "per_tube": MAX_TARGETS + 1,
                "targets": [{"template": "A" * 200}, {"template": "C" * 200}],
            }
        )


def test_multiplex_refuses_targets_with_different_named_protocols(monkeypatch):
    """One physical tube cannot silently mix two vendor chemistry overlays."""
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "qpcr-sybr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )

    def fake_run_single(entry, **kwargs):
        protocol_id = (
            "neb-luna-universal-m3003" if entry.get("name") == "a" else "thermo-powerup-sybr-a2574x"
        )
        return {
            "assay": {
                "id": "qpcr-sybr",
                "name": "qPCR SYBR",
                "engine": "flanking-pair",
                "status": "experimental",
                "profile_authority": {
                    "profileId": "qpcr-sybr",
                    "source": "test",
                    "transport": "test",
                },
                "defaults": {},
                "purposes": ["general"],
                "modifiers": ["multiplex"],
                "requires": [],
                "enzyme": [],
            },
            "reaction": {"polymerase": "qpcr-dye"},
            "constraints": {},
            "provenance": {},
            "protocol": {"kind": "qpcr-sybr", "protocol_id": protocol_id, "selection": protocol_id},
            "reverse_transcription": None,
            "pairs": [
                {
                    "left": {"sequence": "A" * 20},
                    "right": {"sequence": "T" * 20},
                    "product_size": 100,
                }
            ],
            "target": {"name": entry.get("name", "")},
        }

    monkeypatch.setattr(multiplex_module, "run_single", fake_run_single)
    request = {
        "readout": "ngs",
        "targets": [
            {"name": "a", "template": "A" * 200},
            {"name": "b", "template": "C" * 200},
        ],
    }
    with pytest.raises(MultiplexError, match="same named protocol/chemistry overlay"):
        multiplex_module.run(request)


def test_multiplex_refuses_targets_with_different_rt_authority(monkeypatch):
    """RNA targets in one tube must share RT placement/authority as well as PCR chemistry."""
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "qpcr-sybr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )

    def fake_run_single(entry, **kwargs):
        rt = common if entry.get("name") == "a" else other
        return {
            "assay": {
                "id": "qpcr-sybr",
                "name": "qPCR SYBR",
                "engine": "flanking-pair",
                "status": "experimental",
                "profile_authority": {
                    "profileId": "qpcr-sybr",
                    "source": "test",
                    "transport": "test",
                },
                "defaults": {},
                "purposes": ["general"],
                "modifiers": ["multiplex"],
                "requires": [],
                "enzyme": [],
            },
            "reaction": {"polymerase": "qpcr-dye"},
            "constraints": {},
            "provenance": {},
            "protocol": {
                "kind": "qpcr-sybr",
                "protocol_id": "neb-luna-one-step-rt-qpcr-e3005",
                "selection": "Luna One-Step",
            },
            "reverse_transcription": rt,
            "pairs": [
                {
                    "left": {"sequence": "A" * 20},
                    "right": {"sequence": "T" * 20},
                    "product_size": 100,
                }
            ],
            "target": {"name": entry.get("name", "")},
        }

    monkeypatch.setattr(multiplex_module, "run_single", fake_run_single)
    common = {
        "one_step": True,
        "hold": {"celsius": 55, "seconds": 600},
        "before": "initial-denaturation-and-qpcr-cycling",
        "authority_status": "named",
        "note": "x",
    }
    other = {**common, "hold": {"celsius": 60, "seconds": 600}}
    request = {
        "readout": "ngs",
        "targets": [
            {"name": "a", "template": "A" * 200},
            {"name": "b", "template": "C" * 200},
        ],
    }
    with pytest.raises(MultiplexError, match="same reverse-transcription authority"):
        multiplex_module.run(request)


def test_multiplex_refuses_a_profile_that_does_not_declare_the_modifier(monkeypatch):
    """Direct worker callers cannot bypass the canonical profile capability gate."""
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "qpcr-sybr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )
    monkeypatch.setattr(
        multiplex_module,
        "run_single",
        lambda entry, **kwargs: {
            "assay": {
                "id": "qpcr-sybr",
                "name": "qPCR SYBR",
                "engine": "flanking-pair",
                "status": "experimental",
                "profile_authority": {
                    "profileId": "qpcr-sybr",
                    "source": "test",
                    "transport": "test",
                },
                "defaults": {},
                "purposes": ["general"],
                "modifiers": ["reverse-transcription", "variant-masking"],
                "requires": [],
                "enzyme": [],
            },
            "reaction": {"polymerase": "qpcr-dye"},
            "constraints": {},
            "provenance": {},
            "pairs": [],
        },
    )
    with pytest.raises(MultiplexError, match="does not declare the canonical `multiplex` modifier"):
        multiplex_module.run(
            {"readout": "ngs", "targets": [{"template": "A" * 200}, {"template": "C" * 200}]}
        )


def test_multiplex_refuses_unknown_outer_request_fields_before_search():
    with pytest.raises(MultiplexError, match="unknown multiplex request field"):
        run(
            {
                "readout": "ngs",
                "targets": [{"template": "ACGT" * 100}, {"template": "TGCA" * 100}],
                "perTubes": 2,
            }
        )


def test_multiplex_refuses_target_fields_the_set_optimizer_cannot_represent():
    with pytest.raises(MultiplexError, match=r"unsupported multiplex field.*tails"):
        run(
            {
                "readout": "ngs",
                "targets": [
                    {
                        "name": "a",
                        "template": "A" * 200,
                        "tails": {"left": "AAAAAA", "right": "CCCCCC"},
                    },
                    {"name": "b", "template": "C" * 200},
                ],
            }
        )


def _fake_multiplex_single(entry, **kwargs):
    constraints = dict(entry.get("constraints") or {})
    return {
        "assay": {
            "id": "standard-pcr",
            "name": "Standard PCR",
            "engine": "flanking-pair",
            "status": "stable",
            "profile_authority": {
                "profileId": "standard-pcr",
                "source": "test",
                "transport": "test",
            },
            "defaults": {},
            "purposes": ["general"],
            "modifiers": ["multiplex"],
            "requires": [],
            "enzyme": [],
        },
        "reaction": {
            "polymerase": "test",
            "mv_conc": 50.0,
            "dv_conc": 1.5,
            "dntp_conc": 0.8,
            "dna_conc": 10.0,
        },
        "constraints": constraints,
        "provenance": {"source": "test"},
        "protocol": None,
        "reverse_transcription": None,
        "pairs": [
            {
                "left": {"sequence": "A" * 20},
                "right": {"sequence": "T" * 20},
                "product_size": 100,
            }
        ],
        "target": {"name": entry.get("name", "")},
    }


def test_multiplex_preserves_target_specific_constraint_provenance(monkeypatch):
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "standard-pcr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )
    monkeypatch.setattr(multiplex_module, "run_single", _fake_multiplex_single)

    result = multiplex_module.run(
        {
            "readout": "ngs",
            "targets": [
                {
                    "name": "a",
                    "template": "A" * 200,
                    "constraints": {"product_min": 80, "product_max": 120},
                },
                {
                    "name": "b",
                    "template": "C" * 200,
                    "constraints": {"product_min": 150, "product_max": 220},
                },
            ],
        }
    )

    assert result["constraint_scope"] == "per-target"
    assert "constraints" not in result
    assert result["targets"][0]["constraints"] == {"product_min": 80, "product_max": 120}
    assert result["targets"][1]["constraints"] == {"product_min": 150, "product_max": 220}


def test_multiplex_reports_a_shared_constraint_block_only_when_identical(monkeypatch):
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "standard-pcr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )
    monkeypatch.setattr(multiplex_module, "run_single", _fake_multiplex_single)
    shared = {"product_min": 100, "product_max": 180}

    result = multiplex_module.run(
        {
            "readout": "ngs",
            "targets": [
                {"name": "a", "template": "A" * 200, "constraints": shared},
                {"name": "b", "template": "C" * 200, "constraints": shared},
            ],
        }
    )

    assert result["constraint_scope"] == "shared"
    assert result["constraints"] == shared
    assert all(target["constraints"] == shared for target in result["targets"])


def test_multiplex_order_sheet_preserves_tube_without_inventing_tm(monkeypatch):
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "standard-pcr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )
    monkeypatch.setattr(multiplex_module, "run_single", _fake_multiplex_single)

    result = multiplex_module.run(
        {
            "readout": "ngs",
            "targets": [
                {"name": "a", "template": "A" * 200},
                {"name": "b", "template": "C" * 200},
            ],
        }
    )

    line = result["order_sheet"][0]
    assert line["tube"] == "tube-1"
    assert line["pool"] == 0
    assert line["gc_percent"] == 0.0
    assert "tm" not in line


def test_multiplex_refuses_mixed_computational_provenance(monkeypatch):
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "standard-pcr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )

    def fake(entry, **kwargs):
        result = _fake_multiplex_single(entry, **kwargs)
        result["provenance"] = {"worker": "A" if entry.get("name") == "a" else "B"}
        return result

    monkeypatch.setattr(multiplex_module, "run_single", fake)
    with pytest.raises(MultiplexError, match="same computational provenance"):
        multiplex_module.run(
            {
                "readout": "ngs",
                "targets": [
                    {"name": "a", "template": "A" * 200},
                    {"name": "b", "template": "C" * 200},
                ],
            }
        )


def test_multiplex_reports_tube_partition_as_bounded_heuristic(monkeypatch):
    monkeypatch.setattr(
        multiplex_module,
        "require_named_assay",
        lambda entry, command, require_profile_authority=True: "standard-pcr",
    )
    monkeypatch.setattr(
        multiplex_module, "validate_required_context", lambda entry, module_id: None
    )
    monkeypatch.setattr(multiplex_module, "run_single", _fake_multiplex_single)

    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    result = multiplex_module.run(
        {
            "readout": "ngs",
            "per_tube": 1,
            "targets": [
                {"name": "a", "template": "A" * 200},
                {"name": "b", "template": "C" * 200},
            ],
        }
    )
    assignment = result["selection_method"]["tube_assignment"]
    assert assignment["strategy"] == "deterministic-fewest-candidates-first-chunking"
    assert assignment["global_partition_optimized"] is False
    assert assignment["tube_count"] == 2
    assert "Development mode assigned targets" in assignment["note"]
