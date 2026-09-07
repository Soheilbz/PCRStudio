"""Our probe rules against the probe assays the world actually ran.

The three assays here were run several billion times between 2020 and 2023,
which makes them the closest thing a hydrolysis-probe design has to a ground
truth. None of their targets is in the corpus, so this cannot ask "would we
have found these oligos" — it asks the sharper question instead: **would our
shipped rules have thrown them out?**

That is the question worth asking of a rule. A window nobody published inside
is a window that is wrong, however well-argued, and a rule that rejects the CDC
N1 assay is a rule that would have rejected the assay a hundred countries used.

Everything below is measured in one reaction rather than in each assay's own,
and that is deliberate. Each protocol runs its own primer and probe
concentrations, so their published temperatures are not comparable with each
other or with ours — which is the same trap the engine's own docstring is about,
one level up. Putting all three through one reaction is what makes the
comparison mean anything; it does mean the numbers here are not the numbers in
the papers, and that is said out loud rather than hidden.

Sources for the oligos, all primary and public:

  CDC 2019-nCoV_N1 and _N2 — CDC 2019-Novel Coronavirus Real-Time RT-PCR
  Diagnostic Panel, Instructions for Use; sequences also in Lu et al., Emerg
  Infect Dis 26(8):1654-1665, 2020.

  E_Sarbeco — Corman et al., Euro Surveill 25(3):2000045, 2020, Table 1;
  carried into the WHO protocol.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pcr_tools.design import Constraints
from pcr_tools.presets import polymerase
from pcr_tools.probe import FORBIDDEN_FIRST_BASE, UNBOUND_ENGINE_PROBE_TM_OFFSET_C
from pcr_tools.thermo import analyse

#: One reaction for all of them, so the three are comparable with each other.
#:
#: The qPCR preset rather than a bespoke one: it is what our own probe assays
#: are designed in, and holding theirs to a different reaction than ours would
#: be measuring two things and calling it a comparison.
CONDITIONS = polymerase("qpcr-dye").reaction.as_conditions()


@dataclass(frozen=True)
class Published:
    """One assay somebody published, and where it came from."""

    name: str
    forward: str
    reverse: str
    probe: str
    source: str


PUBLISHED = (
    Published(
        name="CDC 2019-nCoV_N1",
        forward="GACCCCAAAATCAGCGAAAT",
        reverse="TCTGGTTACTGCCAGTTGAATCTG",
        probe="ACCCCGCATTACGTTTGGTGGACC",
        source="CDC Real-Time RT-PCR Diagnostic Panel, Instructions for Use",
    ),
    Published(
        name="CDC 2019-nCoV_N2",
        forward="TTACAAACATTGGCCGCAAA",
        reverse="GCGCGACATTCCGAAGAA",
        probe="ACAATTTGCCCCCAGCGCTTCAG",
        source="CDC Real-Time RT-PCR Diagnostic Panel, Instructions for Use",
    ),
    Published(
        name="E_Sarbeco",
        forward="ACAGGTACGTTAATAGTTAATAGCGT",
        reverse="ATATTGCAGCAGTACGCACACA",
        probe="ACACTAGCCATCCTTACTGCGCTTCG",
        source="Corman et al., Euro Surveill 25(3):2000045, 2020, Table 1",
    ),
)


def separation(assay: Published) -> float:
    """How far the probe melts above the warmer of the two primers."""
    warmest = max(
        analyse(assay.forward, **CONDITIONS).tm,
        analyse(assay.reverse, **CONDITIONS).tm,
    )
    return round(analyse(assay.probe, **CONDITIONS).tm - warmest, 2)


# ── The rule the whole assay rests on ──────────────────────────────────────


@pytest.mark.parametrize("assay", PUBLISHED, ids=lambda a: a.name)
def test_every_published_probe_melts_clear_of_its_own_primers(assay: Published):
    """The mechanism, confirmed against practice rather than against a manual.

    The probe is destroyed rather than extended, so it has to be bound before
    the polymerase sets off. Measured in one reaction, all three sit between
    +5.6 and +7.5 °C above their warmer primer.
    """
    assert separation(assay) >= 5.0, assay


def test_the_published_separations_bracket_the_one_we_design_to():
    """Our offset has to be a number somebody published inside, not near.

    Measured in this reaction the three sit at +5.60, +6.70 and +7.50. Our
    `UNBOUND_ENGINE_PROBE_TM_OFFSET_C` shifts the probe's window rather than fixing the gap, so
    what matters is that it lands inside the range practice uses — a design
    aiming above all three would be asking for probes more tightly bound than
    any assay anyone actually ran.
    """
    gaps = sorted(separation(assay) for assay in PUBLISHED)
    assert gaps[0] <= UNBOUND_ENGINE_PROBE_TM_OFFSET_C <= gaps[-1], (
        f"published separations run {gaps[0]} to {gaps[-1]} °C and we design to "
        f"{UNBOUND_ENGINE_PROBE_TM_OFFSET_C}, which is outside what anybody published"
    )


# ── The rule no thermodynamic measure would find ───────────────────────────


@pytest.mark.parametrize("assay", PUBLISHED, ids=lambda a: a.name)
def test_no_published_probe_begins_with_a_guanine(assay: Published):
    """Three for three, which is the evidence the rule is real.

    A G under the fluorophore quenches it. The rule comes from IDT's and
    Applied Biosystems' design guidelines rather than from any measurement this
    project can make — so what is checked here is that practice agrees with it.
    """
    assert assay.probe[0].upper() != FORBIDDEN_FIRST_BASE, assay


# ── Would our shipped windows have refused them? ───────────────────────────


def unbound_engine_windows() -> tuple[Constraints, Constraints]:
    """A research benchmark for the unbound pair-and-probe geometry engine.

    The routed `qpcr-probe` module executes only through named conventional
    hydrolysis-probe authorities. These unbound windows remain benchmark-only
    geometry searches and are not protocol or vendor numeric authority.
    """
    import tomllib
    from pathlib import Path

    path = Path(__file__).parents[2] / "crates" / "pcr-core" / "profiles.toml"
    catalogue = tomllib.loads(path.read_text(encoding="utf-8"))["profile"]
    entry = next(one for one in catalogue if one["id"] == "qpcr-probe")

    primers = Constraints(**entry["defaults"]["constraints"])
    probe = Constraints(
        **{
            **entry["defaults"]["constraints"],
            "tm_min": round(primers.tm_min + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
            "tm_opt": round(primers.tm_opt + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
            "tm_max": round(primers.tm_max + UNBOUND_ENGINE_PROBE_TM_OFFSET_C, 1),
            "length_min": 18,
            "length_opt": 24,
            "length_max": 30,
            "gc_min": 30.0,
            "gc_max": 80.0,
        }
    )
    return primers, probe


@pytest.mark.parametrize("assay", PUBLISHED, ids=lambda a: a.name)
def test_the_unbound_engine_benchmark_window_would_not_throw_these_assays_out(assay: Published):
    """The test that makes the window falsifiable.

    A window nobody published inside is wrong however well it was argued. This
    holds the three published examples to the low-level research heuristic
    and requires them to pass. It is benchmark evidence, not release protocol authority.
    """
    primers, probe = unbound_engine_windows()
    refused: list[str] = []

    for role, oligo, window in (
        ("forward", assay.forward, primers),
        ("reverse", assay.reverse, primers),
        ("probe", assay.probe, probe),
    ):
        measured = analyse(oligo, **CONDITIONS)
        if not window.tm_min <= measured.tm <= window.tm_max:
            refused.append(
                f"{role} melts at {measured.tm} °C, outside {window.tm_min}–{window.tm_max}"
            )
        if not window.length_min <= measured.length <= window.length_max:
            refused.append(
                f"{role} is {measured.length} bases, outside {window.length_min}–"
                f"{window.length_max}"
            )
        if not window.gc_min <= measured.gc_percent <= window.gc_max:
            refused.append(
                f"{role} is {measured.gc_percent}% GC, outside {window.gc_min}–{window.gc_max}"
            )

    assert not refused, (
        f"our shipped qpcr-probe window rejects {assay.name}, which is "
        f"{assay.source}: " + "; ".join(refused)
    )


def report() -> None:
    """Print the comparison, for the record rather than for the suite."""
    primers, probe = unbound_engine_windows()
    print(f"\nmeasured in one reaction: {CONDITIONS}")
    print(
        f"our windows: primers {primers.tm_min}–{primers.tm_max} °C, "
        f"probe {probe.tm_min}–{probe.tm_max} °C\n"
    )
    print(f"{'assay':20} {'F':>6} {'R':>6} {'probe':>6} {'above':>7}  5'")
    for assay in PUBLISHED:
        print(
            f"{assay.name:20} "
            f"{analyse(assay.forward, **CONDITIONS).tm:6.1f} "
            f"{analyse(assay.reverse, **CONDITIONS).tm:6.1f} "
            f"{analyse(assay.probe, **CONDITIONS).tm:6.1f} "
            f"{separation(assay):+7.2f}  {assay.probe[0]}"
        )


if __name__ == "__main__":
    report()
