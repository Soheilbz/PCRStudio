"""Reaction conditions, named after the reaction rather than after a number.

A melting temperature is not a property of a primer. It is a property of a
primer in a buffer, and the buffers people actually use disagree with each
other by more than a design decision does. Asking somebody for four salt
concentrations is asking the wrong question; asking which reaction they are
setting up is the right one.

One trap is worth stating where it cannot be missed. Primer3's `dntp_conc` is
the **sum of all four** deoxynucleotides, not the concentration of each. A
reaction at the usual 0.2 mM per base is 0.8 here. Entering 0.2 describes a
reaction nobody runs, and it shifts every melting temperature we report.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .thermo import (
    PRIMER3_LOW_LEVEL_CONTROLS,
)


@dataclass(frozen=True)
class Reaction:
    """Thermodynamic reaction inputs, in the units Primer3 expects.

    These values describe the calculation state, not automatically a complete
    physical recipe. In particular, ``dna_conc`` is Primer3's effective
    annealing-oligo input and may differ from the initial oligo concentration
    in a real reaction mix.

    Attributes:
        mv_conc: Monovalent cations (Na+, K+, NH4+) in mM.
        dv_conc: Divalent cations (Mg2+) in mM.
        dntp_conc: The **sum** of all four dNTPs in mM.
        dna_conc: Effective annealing-oligo input for Tm in nM.
    """

    mv_conc: float
    dv_conc: float
    dntp_conc: float
    dna_conc: float

    def as_conditions(self) -> dict[str, float]:
        """Return the condition names consumed by the thermodynamic layers."""
        return {
            "mv_conc": self.mv_conc,
            "dv_conc": self.dv_conc,
            "dntp_conc": self.dntp_conc,
            "dna_conc": self.dna_conc,
        }

    def validate(self) -> None:
        """Reject a tube that could not exist.

        Raises:
            ValueError: naming the two numbers that disagree.
        """
        for label, value in (
            ("monovalent", self.mv_conc),
            ("divalent", self.dv_conc),
            ("dNTP", self.dntp_conc),
            ("oligo", self.dna_conc),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{label} concentration must be a finite number")
            try:
                finite = math.isfinite(float(value))
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"{label} concentration must be finite, not {value!r}")
            if value < 0:
                raise ValueError(f"{label} concentration cannot be negative")
        # The low-level thermodynamics API can calculate an Mg-only value, but
        # the actual Primer3 picker rejects PRIMER_SALT_MONOVALENT=0. Keep the
        # public design contract aligned with the picker rather than allowing
        # a request that will fail later as an opaque OSError.
        if self.mv_conc <= 0:
            raise ValueError(
                "the flanking-pair Primer3 picker requires a positive monovalent salt concentration"
            )
        if self.dna_conc <= 0:
            raise ValueError("the oligo concentration must be above zero")
        # Primer3's documented behavior is not to reject this case: when the
        # total dNTP concentration exceeds divalent cations, it omits the
        # divalent-cation effect from the salt correction. The result layer
        # records that fallback so the calculation is not mistaken for one
        # using the configured Mg2+ value mechanistically.


@dataclass(frozen=True)
class Cycling:
    """How the block is programmed, for one polymerase.

    Starting points rather than a protocol. Every one of these is the number a
    person would write down before optimising, and the only one this can work
    out for itself is the extension time, which follows the product length.
    """

    #: Denaturation, and the first long one that gets the template apart.
    denature_c: float
    denature_seconds: int
    initial_denature_seconds: int
    #: How long to hold the annealing temperature.
    anneal_seconds: int
    #: Extension, and how fast this enzyme goes.
    extend_c: float
    extend_seconds_per_kb: int
    #: The shortest extension worth programming, however short the product.
    min_extend_seconds: int
    final_extend_seconds: int
    cycles: int
    #: Whether annealing and extension are one step at one temperature.
    #:
    #: Long-range protocols routinely drop the separate annealing step and hold
    #: a single temperature for both, because primers long enough to survive a
    #: multi-kilobase extension anneal perfectly well at the extension
    #: temperature. Reporting a three-step programme for a reaction nobody runs
    #: in three steps would be a protocol somebody follows and wonders about.
    two_step: bool = False
    #: The one temperature that combined step is held at, when it is combined.
    anneal_extend_c: float | None = None
    #: The single temperature an isothermal reaction is held at, if it is one.
    #:
    #: Recombinase amplification does not cycle: it is one temperature for
    #: twenty minutes. Everything else in this dataclass describes a thermal
    #: cycler, and filling those fields in for a reaction that never changes
    #: temperature would print a programme nobody runs.
    isothermal_c: float | None = None
    #: How long that hold lasts.
    isothermal_seconds: int | None = None
    #: The longest extension worth programming, however long the product.
    #:
    #: Long-range manuals stop scaling per kilobase somewhere above ten and
    #: print a flat time instead. A linear model with no cap keeps climbing
    #: past anything anybody runs.
    extend_seconds_max: int | None = None

    def validate(self) -> None:
        """Reject a thermal programme that cannot be represented safely.

        Profiles are trusted configuration, but assay defaults can also arrive
        through direct worker callers.  Letting a non-finite or negative value
        reach the protocol renderer produces a plausible-looking programme
        that nobody can actually set on a cycler.
        """
        for name, value in asdict(self).items():
            if value is None:
                continue
            if name == "two_step":
                if not isinstance(value, bool):
                    raise ValueError("cycling `two_step` must be boolean")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"cycling `{name}` must be a finite number")
            try:
                finite = math.isfinite(float(value))
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"cycling `{name}` must be finite, not {value!r}")

        for name, value in asdict(self).items():
            if name == "two_step" or value is None:
                continue
            if name in {
                "denature_seconds",
                "initial_denature_seconds",
                "anneal_seconds",
                "extend_seconds_per_kb",
                "min_extend_seconds",
                "final_extend_seconds",
                "cycles",
                "isothermal_seconds",
                "extend_seconds_max",
            } and not isinstance(value, int):
                raise ValueError(f"cycling `{name}` must be an integer")
            if value < 0:
                raise ValueError(f"cycling `{name}` cannot be negative")
        if self.cycles < 1:
            raise ValueError("a cycling programme needs at least one cycle")
        if (self.isothermal_c is None) != (self.isothermal_seconds is None):
            raise ValueError(
                "an isothermal programme must provide both its hold temperature and its duration"
            )
        if self.isothermal_c is not None and self.isothermal_seconds is not None:
            if self.isothermal_seconds <= 0:
                raise ValueError("an isothermal hold needs a positive duration")
            if self.two_step:
                raise ValueError("an isothermal programme cannot also be marked as two-step")
        elif self.two_step and self.anneal_extend_c is None:
            raise ValueError(
                "a two-step programme needs an explicit anneal_extend_c hold temperature"
            )
        elif not self.two_step and self.anneal_extend_c is not None:
            raise ValueError("anneal_extend_c is only valid when the programme is marked two-step")
        if (
            self.extend_seconds_max is not None
            and self.extend_seconds_max < self.min_extend_seconds
        ):
            raise ValueError(
                "the maximum extension time cannot be shorter than the minimum extension time"
            )


@dataclass(frozen=True)
class Polymerase:
    """A named set of conditions, with the sentence that explains it."""

    id: str
    name: str
    summary: str
    reaction: Reaction
    cycling: Cycling
    #: Whether this enzyme chews up a downstream primer as it extends.
    #:
    #: Taq does; the archaeal high-fidelity enzymes do not. It matters in
    #: exactly two places and in opposite directions. A single-tube nested
    #: reaction holds both primer pairs at once, so an enzyme with this
    #: activity destroys the inner primers as it extends the outer product —
    #: swapping it out has been reported to buy a hundred to a thousand fold in
    #: sensitivity. A hydrolysis-probe assay is the mirror: the activity *is*
    #: the read-out, because the signal is the polymerase chewing through the
    #: probe.
    five_prime_exonuclease: bool = True
    #: Whether this enzyme opens double-stranded DNA ahead of itself.
    #:
    #: What makes an isothermal reaction possible at all. LAMP and RPA never
    #: heat the template apart — there is no denaturation step to separate the
    #: strands, so the polymerase has to do it as it goes. *Bst* and its
    #: relatives do; Taq and the archaeal proofreading enzymes do not, and in a
    #: LAMP tube one of those produces nothing whatever the primers are.
    #:
    #: Recorded from the isothermal literature, which states it as the defining
    #: property of the enzymes those methods use: "the *Bst* DNA polymerase most
    #: used in LAMP shows a high strand displacement activity, which eliminates
    #: the DNA denaturation stage" (Soroka, Wasowicz and Rymaszewska, *Cells*
    #: 2021, doi:10.3390/cells10081931).
    strand_displacing: bool = False
    #: Whether it resects a mismatched 3' end rather than extending from it.
    #:
    #: Two assays turn on this and they want opposite things.
    #:
    #: An allele-specific design *is* a deliberate 3' mismatch, so an enzyme
    #: that proofreads removes the base the discrimination rests on and every
    #: sample reads as a heterozygote. The published workaround — a
    #: phosphorothioate 3' end — is imperfect: all six proofreading enzymes
    #: tested still digested modified primers (Gale et al., *Photochem
    #: Photobiol* 2004, doi:10.1562/2004-03-30-RA-133).
    #:
    #: A long PCR needs exactly that activity. Taq alone past about three
    #: kilobases gives "variously sized truncated molecules that appear as
    #: unattractive smears on a gel"; what fixes it is a second enzyme
    #: "in much smaller amounts" providing "a proofreading 3' → 5' exonuclease
    #: function that resects mismatched 3' ends" (Green and Sambrook, *Cold
    #: Spring Harb Protoc* 2019, doi:10.1101/pdb.prot095158; the original
    #: measurement is Cheng et al., *PNAS* 1994, doi:10.1073/pnas.91.12.5695).
    proofreading: bool = False
    #: Whether it survives being cycled to 95 degrees, over and over.
    #:
    #: Not the same as working warm. *Bst* runs happily at 65 °C and is
    #: inactivated around 80; the RPA enzymes work at body temperature. Both
    #: are useless in anything with a denaturation step, and both are the only
    #: thing that works without one.
    thermostable: bool = True
    #: Whether this is a complete chemistry validated for recombinase-
    #: polymerase amplification rather than merely a strand-displacing enzyme.
    #: Bst can displace strands but is not an RPA reaction mix.
    rpa_compatible: bool = False


#: The conditions on offer. Deliberately described as reactions people set up,
#: not as vendor buffers whose exact composition is proprietary and which we
#: would therefore be guessing at.
POLYMERASES: tuple[Polymerase, ...] = (
    Polymerase(
        id="taq-standard",
        name="Standard Taq",
        summary=(
            "The ordinary reaction: 50 mM monovalent salt, 1.5 mM magnesium, "
            "0.2 mM of each dNTP, with a 200 nM Tm oligo input."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=200.0),
        cycling=Cycling(
            denature_c=95.0,
            denature_seconds=30,
            initial_denature_seconds=180,
            anneal_seconds=30,
            extend_c=72.0,
            extend_seconds_per_kb=60,
            min_extend_seconds=30,
            final_extend_seconds=300,
            cycles=32,
        ),
    ),
    Polymerase(
        id="taq-high-magnesium",
        name="Taq, magnesium raised",
        summary=(
            "The same reaction with magnesium at 2.5 mM, which is what a "
            "stubborn amplification usually gets first; the Tm oligo input "
            "remains 200 nM."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=2.5, dntp_conc=0.8, dna_conc=200.0),
        cycling=Cycling(
            denature_c=95.0,
            denature_seconds=30,
            initial_denature_seconds=180,
            anneal_seconds=30,
            extend_c=72.0,
            extend_seconds_per_kb=60,
            min_extend_seconds=30,
            final_extend_seconds=300,
            cycles=32,
        ),
    ),
    Polymerase(
        id="race-gsp-screening",
        name="RACE GSP thermodynamic screening context",
        summary=(
            "A declared DNA-duplex calculation context for RACE gene-specific primer screening. "
            "The ionic and oligo values exist only to make Primer3 nearest-neighbour calculations "
            "reproducible; they are not a claim about the polymerase, reverse-transcription mix, "
            "adapter chemistry or cycling programme used by a particular RACE kit/SOP."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=300.0),
        cycling=Cycling(
            # Required by the generic calculation-context dataclass only. RACE bench cycling is
            # deliberately owned by the named RACE kit/SOP and is never emitted from this preset.
            denature_c=95.0, denature_seconds=30, initial_denature_seconds=180,
            anneal_seconds=30, extend_c=72.0, extend_seconds_per_kb=60,
            min_extend_seconds=60, final_extend_seconds=300, cycles=32,
        ),
    ),
    Polymerase(
        id="sanger-primer-screening",
        name="Sanger-primer thermodynamic screening context",
        summary=(
            "A declared DNA-duplex calculation context used only to rank a single sequencing primer. "
            "It does not identify the cycle-sequencing polymerase, dye terminator chemistry, buffer, "
            "instrument or facility SOP. Those remain separate named handoff/provenance records."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=200.0),
        cycling=Cycling(
            # Calculation placeholder only; never a Sanger bench programme.
            denature_c=95.0, denature_seconds=30, initial_denature_seconds=180,
            anneal_seconds=30, extend_c=72.0, extend_seconds_per_kb=60,
            min_extend_seconds=30, final_extend_seconds=300, cycles=32,
        ),
    ),
    Polymerase(
        id="long-range",
        name="Long-range PCR thermodynamic screening adapter",
        summary=(
            "Fixed cross-protocol nearest-neighbour screening context retained for sequence "
            "comparability across reviewed long-range chemistries. Its numeric reaction values "
            "are model inputs inherited from the audited Gen-1 baseline; they are not a reconstruction "
            "of NEB, Takara, QIAGEN or historical Thermo proprietary buffer composition. Named protocols "
            "own bench formulation/cycling and may narrow the primer sequence-constraint envelope; "
            "they do not alter this shared thermodynamic reaction model."
        ),
        # Preserve the audited Gen-1 numeric thermodynamic adapter exactly so
        # adding/changing a bench protocol cannot silently re-rank primer pairs.
        # These values originated from the historical K018x screening branch,
        # but are now explicitly a versioned cross-protocol calculation model,
        # not a vendor formulation claim. A future chemistry-specific ranking
        # model would require a separately versioned scientific contract.
        reaction=Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.8, dna_conc=300.0),
        cycling=Cycling(
            # 94 for 20 s is what the long-range manuals print for thin-walled
            # tubes. One buffer system says not to exceed 93; that is specific
            # to its own buffer, and three other manufacturers run 94.
            denature_c=94.0,
            denature_seconds=20,
            initial_denature_seconds=120,
            anneal_seconds=0,
            extend_c=68.0,
            extend_seconds_per_kb=60,
            min_extend_seconds=180,
            # Internal calculation placeholder only. Long-range bench cycling is
            # chemistry-specific and is returned separately by the selected named
            # protocol; pair-level cycling is deliberately suppressed here.
            extend_seconds_max=1200,
            final_extend_seconds=600,
            cycles=30,
            # 68 C is the frozen Gen-1 screening temperature used for sequence
            # thermodynamics/specificity calculations. It is not bench annealing
            # authority for every named long-range chemistry.
            two_step=True,
            anneal_extend_c=68.0,
        ),
        # Capability flag for the currently reviewed executable Gen-1
        # long-range family. The supported branches use proofreading-capable
        # long-range systems, but this screening-adapter flag is not a claim
        # about a selected vendor's proprietary formulation, enzyme ratio,
        # fidelity value or universal mechanism for every conceivable long-PCR
        # chemistry. Bench authority remains with the named protocol overlay.
        proofreading=True,
    ),
    Polymerase(
        id="qpcr-dye",
        name="qPCR thermodynamic screening context",
        summary=(
            "A declared nearest-neighbour calculation context for qPCR primer/probe screening. "
            "The 2 mM Mg2+, 0.8 mM total dNTP and 250 nM effective oligo values are model "
            "inputs, not a claim about any universal or proprietary qPCR master-mix recipe. "
            "Named chemistry overlays own bench cycling and kit/instrument provenance."
        ),
        # This preset exists because Tm is conditional on an explicitly declared
        # calculation state. It deliberately does NOT claim to reconstruct a
        # proprietary master mix. MIQE 2.0 requires reaction conditions to be
        # reported and warns that master-mix components can shift effective Tm;
        # named protocol overlays therefore remain separate from this screening model.
        reaction=Reaction(mv_conc=50.0, dv_conc=2.0, dntp_conc=0.8, dna_conc=250.0),
        cycling=Cycling(
            denature_c=95.0,
            denature_seconds=15,
            initial_denature_seconds=120,
            anneal_seconds=30,
            extend_c=60.0,
            extend_seconds_per_kb=0,
            min_extend_seconds=0,
            # No final extension: the products are 200 bases at most and the
            # instrument is reading them, not a gel.
            final_extend_seconds=0,
            cycles=40,
            two_step=True,
            anneal_extend_c=60.0,
        ),
    ),
    Polymerase(
        id="digital-pcr",
        name="Digital-PCR thermodynamic screening context",
        summary=(
            "Primer-design calculation context for partitioned endpoint PCR. "
            "The salt/oligo inputs support sequence thermodynamics only; this "
            "preset is not a platform cycling recipe. Bench cycling is emitted "
            "only by a named platform/chemistry overlay."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=3.3, dntp_conc=0.8, dna_conc=250.0),
        cycling=Cycling(
            denature_c=94.0,
            denature_seconds=30,
            # These cycling fields are retained only because the generic
            # Polymerase dataclass requires a complete numeric calculation
            # context. They are never rendered as a dPCR bench protocol unless
            # a named platform overlay supplies its own authoritative cycling.
            initial_denature_seconds=600,
            # The dPCR two-step hold is one combined annealing/extension
            # step. The platform protocol's 60 seconds is the whole hold;
            # it must not be doubled by also imposing a minimum extension.
            # A 60 °C internal screening point is used only for generic
            # thermodynamic calculations, not as a platform instruction.
            anneal_seconds=60,
            extend_c=60.0,
            extend_seconds_per_kb=0,
            min_extend_seconds=0,
            final_extend_seconds=0,
            cycles=40,
            two_step=True,
            anneal_extend_c=60.0,
        ),
    ),
    Polymerase(
        id="rpa",
        name="Recombinase amplification",
        summary=(
            "RPA Primer3 screening proxy. The 480 nM oligo and 14 mM MgOAc values "
            "match the named lyophilised Basic starting setup; the 1.8 mM total-dNTP "
            "value comes only from the separately documented Liquid Basic calculation "
            "context and is not a claim about the undisclosed lyophilised-pellet formulation."
        ),
        # TwistAmp Basic's 50 uL protocol adds 2.4 uL of each 10 uM primer,
        # i.e. 480 nM final concentration. This is a kit starting point, not a
        # universal RPA optimum, but it is a better documented default than
        # the former unsupported 300 nM value.
        # Primer3 requires a complete finite calculation context. Lyophilised
        # TwistAmp Basic does not expose a user-set dNTP concentration; 1.8 mM
        # total dNTP is documented for *Liquid Basic* and is retained here only
        # as an explicitly labelled screening proxy. It must never be rendered
        # as the selected lyophilised Basic bench formulation or validity gate.
        reaction=Reaction(mv_conc=100.0, dv_conc=14.0, dntp_conc=1.8, dna_conc=480.0),
        cycling=Cycling(
            # These are the fields a cycler needs and this reaction has none of
            # them. They are filled with the hold temperature so nothing
            # divides by zero, and `isothermal_c` is what should be read.
            denature_c=39.0,
            denature_seconds=0,
            initial_denature_seconds=0,
            anneal_seconds=0,
            extend_c=39.0,
            extend_seconds_per_kb=0,
            min_extend_seconds=0,
            final_extend_seconds=0,
            cycles=1,
            isothermal_c=39.0,
            isothermal_seconds=1200,
        ),
        # The recombinase reaction's polymerase is a large-fragment Pol I with
        # no 3'->5' proofreading and is not a Taq-like 5'->3' exonuclease.
        # TwistAmp Exo/Nfo readouts add a separate nuclease and a blocked probe;
        # marking this preset as exonuclease-positive would incorrectly make
        # it look suitable for a hydrolysis-probe contract.
        #
        # It does displace strands, and it is not thermostable. Both follow
        # from what the method is: a recombinase loads the primers onto duplex
        # DNA and the polymerase extends from there, at 37-42 °C, with nothing
        # ever heated apart (Tan et al., *Front Cell Infect Microbiol* 2022,
        # doi:10.3389/fcimb.2022.1019071). Cycling it to 95 would destroy every
        # protein in the tube.
        strand_displacing=True,
        five_prime_exonuclease=False,
        thermostable=False,
        rpa_compatible=True,
    ),
    Polymerase(
        id="bst",
        name="Strand-displacing, for loop-mediated amplification",
        summary=(
            "Isothermal: one hold at 65 degrees, in the high-magnesium buffer "
            "these reactions run in — 8 mM magnesium, 1.4 mM of each dNTP, and "
            "the inner primers at 1.6 µM."
        ),
        # Not the PCR numbers, and the difference is not a preference. A loop
        # set holds six oligos at very unequal concentrations — the inner pair
        # at eight times the outer — and the buffer carries several times the
        # magnesium and the dNTPs a PCR does, because the polymerase is opening
        # duplex DNA continuously rather than being handed separated strands.
        # The melting temperatures every window in this design is judged
        # against are computed in *this* reaction, so running it against the
        # PCR numbers would put every oligo several degrees out.
        reaction=Reaction(mv_conc=50.0, dv_conc=8.0, dntp_conc=5.6, dna_conc=1600.0),
        cycling=Cycling(
            # Nothing is cycled. The fields a cycler needs are filled with the
            # hold so nothing divides by zero; `isothermal_c` is the one to read.
            denature_c=65.0,
            denature_seconds=0,
            initial_denature_seconds=0,
            anneal_seconds=0,
            extend_c=65.0,
            extend_seconds_per_kb=0,
            min_extend_seconds=0,
            final_extend_seconds=0,
            cycles=1,
            isothermal_c=65.0,
            isothermal_seconds=3600,
        ),
        # What the method is built on, and what the catalogue was missing: a
        # LAMP page offering only PCR enzymes was offering a set of choices
        # none of which runs the assay. *Bst* and *Bsm* are the enzymes these
        # reactions use, they displace strands, and they have no 5'->3'
        # exonuclease (Dhama et al., *Pak J Biol Sci* 2014,
        # doi:10.3923/pjbs.2014.151.166).
        strand_displacing=True,
        five_prime_exonuclease=False,
        # It works warm and it does not survive cycling: inactivated around 80
        # degrees, which is below a denaturation step.
        thermostable=False,
    ),
    Polymerase(
        id="proofreading",
        name="Proofreading polymerase",
        summary=(
            "A high-fidelity reaction: 2 mM magnesium and a 500 nM Tm oligo "
            "input, which is where many proofreading protocols start."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=2.0, dntp_conc=0.8, dna_conc=500.0),
        # The archaeal high-fidelity enzymes have 3'->5' proofreading and no
        # 5'->3' activity, which is what makes this the one that can run a
        # single-tube nested reaction.
        five_prime_exonuclease=False,
        proofreading=True,
        cycling=Cycling(
            denature_c=98.0,
            denature_seconds=10,
            initial_denature_seconds=30,
            anneal_seconds=20,
            extend_c=72.0,
            extend_seconds_per_kb=30,
            min_extend_seconds=15,
            final_extend_seconds=120,
            cycles=30,
        ),
    ),
    Polymerase(
        id="q5-sdm-screening",
        name="Q5 SDM Primer3 thermodynamic screening context",
        summary=(
            "A reproducible Primer3 nearest-neighbour calculation context for the Q5/E0554 "
            "mutagenesis primer search. The ionic values are explicitly Primer3 screening "
            "inputs, not a reconstruction of Q5 Hot Start Master Mix or NEBaseChanger. "
            "Q5 annealing temperature remains a named protocol/NEBaseChanger decision."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.6, dna_conc=50.0),
        cycling=Cycling(
            # Placeholder required by the shared calculation-context dataclass only.
            # Mutagenic results never emit this as a bench programme.
            denature_c=98.0, denature_seconds=10, initial_denature_seconds=30,
            anneal_seconds=20, extend_c=72.0, extend_seconds_per_kb=30,
            min_extend_seconds=15, final_extend_seconds=120, cycles=25,
        ),
        proofreading=True,
    ),
    Polymerase(
        id="primer3-default",
        name="Primer3 defaults",
        summary=(
            "What Primer3 assumes when nobody tells it otherwise. Included for "
            "comparison with other tools — its 0.6 mM total dNTP is lower than "
            "a normal reaction, so it is not a bench condition."
        ),
        reaction=Reaction(mv_conc=50.0, dv_conc=1.5, dntp_conc=0.6, dna_conc=50.0),
        cycling=Cycling(
            denature_c=95.0,
            denature_seconds=30,
            initial_denature_seconds=180,
            anneal_seconds=30,
            extend_c=72.0,
            extend_seconds_per_kb=60,
            min_extend_seconds=30,
            final_extend_seconds=300,
            cycles=32,
        ),
    ),
)

DEFAULT_POLYMERASE = "taq-standard"

_BY_ID = {p.id: p for p in POLYMERASES}


def polymerase(preset_id: str | None) -> Polymerase:
    """One preset by id, defaulting to the ordinary reaction.

    Raises:
        ValueError: naming what was asked for and what exists.
    """
    if not preset_id:
        return _BY_ID[DEFAULT_POLYMERASE]
    if preset_id not in _BY_ID:
        known = ", ".join(sorted(_BY_ID))
        raise ValueError(f"unknown polymerase preset `{preset_id}`. Known: {known}")
    return _BY_ID[preset_id]


def polymerases_to_dict() -> list[dict[str, Any]]:
    """The presets, for a form to render without knowing what is in them.

    The four activities travel with each entry because an assay decides which
    enzymes it can offer from *these* rather than from a list of enzyme names
    kept beside it. A per-assay list would be twenty-one places to be wrong,
    and would go stale the day a twelfth enzyme arrived; a property is a fact
    about the enzyme and is stated once, here.
    """
    return [
        {
            "id": p.id,
            "name": p.name,
            "summary": p.summary,
            "reaction": p.reaction.as_conditions(),
            "thermodynamics": thermodynamic_model(p),
            "cycling": asdict(p.cycling),
            "does": {
                "strand_displacing": p.strand_displacing,
                "five_prime_exonuclease": p.five_prime_exonuclease,
                "proofreading": p.proofreading,
                "thermostable": p.thermostable,
                "rpa_compatible": p.rpa_compatible,
            },
        }
        for p in POLYMERASES
    ]


#: The versioned Gen-1 thermodynamic model. Reaction concentrations remain
#: explicit inputs, but model *identity* is not inferred from one concentration:
#: Primer3's recommended SantaLucia salt correction stays selected until a
#: separately reviewed profile explicitly names another model.
TM_MODEL = {
    "name": "SantaLucia 1998 nearest-neighbour with SantaLucia 1998 salt correction",
    "tm_formula": "SantaLucia 1998",
    "salt_correction": "SantaLucia 1998",
    "primer3_tm_formula": 1,
    "primer3_salt_corrections": 1,
    "oligo_concentration_parameter": "PRIMER_DNA_CONC",
    "oligo_concentration_role": "empirical_annealing_oligo_for_tm",
    "oligo_concentration_note": (
        "The reported nM value is the effective annealing-oligo concentration "
        "used for thermodynamic calculations, not necessarily the initial "
        "concentration of oligos in the reaction mix."
    ),
    "salt_correction_policy": "explicit-versioned-model; no Mg-threshold auto-switch",
    # Primer3 documents the Owczarzy correction as a Tm correction; it cannot
    # provide the thermodynamic parameters needed for bound-fraction output.
    "bound_fraction_supported": False,
    "primer3_low_level_controls": dict(PRIMER3_LOW_LEVEL_CONTROLS),
}


def thermodynamic_model(
    preset: Polymerase | None = None,
    reaction: Reaction | None = None,
) -> dict[str, Any]:
    """Describe the shared calculation and its assay-specific meaning.

    PCR-like reactions use the model for candidate generation and reporting.
    RPA still needs a finite Primer3-compatible guard for the shared search,
    but recombinase loading is not PCR annealing; exposing that distinction in
    the result prevents a calculated Tm from being mistaken for an RPA kinetic
    prediction.
    """
    from .thermo import salt_correction_for_conditions

    model = dict(TM_MODEL)
    effective_reaction = reaction or (preset.reaction if preset is not None else None)
    if effective_reaction is not None:
        salt_correction_for_conditions(effective_reaction.as_conditions())
        if effective_reaction.dntp_conc > effective_reaction.dv_conc:
            model.update(
                {
                    "divalent_cation_effect": "not-considered-by-primer3",
                    "divalent_cation_note": (
                        "PRIMER_DNTP_CONC exceeds PRIMER_SALT_DIVALENT; Primer3 omits "
                        "the divalent-cation term from its salt correction."
                    ),
                }
            )
    if preset is not None and preset.rpa_compatible:
        model.update(
            {
                "role": "screening-proxy",
                "interpretation": (
                    "Primer3 DNA-duplex Tm is used only as a finite sequence "
                    "screen; it is not a mechanistic RPA binding or yield model."
                ),
            }
        )
    else:
        model.update(
            {
                "role": "design-and-report",
                "interpretation": (
                    "PCR-like DNA-duplex estimate conditional on the supplied "
                    "reaction concentrations; validate against the actual kit."
                ),
            }
        )
    return model


@dataclass(frozen=True)
class Purpose:
    """What the product is for, and what that changes about it.

    A pair for a Sanger read and a pair for a colony check are both standard
    PCR, and they are not the same design: one has to be long enough to be
    worth a read and short enough to be one, the other has to be quick and
    unambiguous on a gel. Neither is a different assay, so neither is a
    different module -- but leaving somebody to work out the product size from
    first principles is leaving them to guess.

    Only the constraints that genuinely differ are listed. Anything absent
    stays at the module's own default, which is what makes these a starting
    point rather than a second set of defaults.
    """

    id: str
    name: str
    summary: str
    #: Constraint overrides, in `Constraints` field names.
    constraints: dict[str, float]


#: The downstream uses the current assay catalogue can express. An assay may
#: add its own physical constraints; a purpose only adds a generic rule when
#: the rule is supported across the relevant workflows.
PURPOSES: tuple[Purpose, ...] = (
    Purpose(
        id="general",
        name="General amplification",
        summary="No particular downstream use. A clean, easy product of ordinary length.",
        constraints={"product_min": 200, "product_max": 1000},
    ),
    Purpose(
        id="sanger",
        name="Sanger sequencing",
        summary=(
            "One read covers roughly 700 to 900 reliable bases and the first few dozen are "
            "poor, so the product is long enough to be worth reading and short enough to be "
            "read in one go."
        ),
        constraints={"product_min": 400, "product_max": 900},
    ),
    Purpose(
        id="sequencing",
        name="Amplicon sequencing",
        summary=(
            "A product intended for a sequencing library or tiled scheme. "
            "Amplicon size, overlap and adapter rules belong to the selected assay."
        ),
        constraints={},
    ),
    Purpose(
        id="screen",
        name="Screening on a gel",
        summary=(
            "Present or absent, decided by eye. Short so it runs quickly and sits well clear "
            "of primer dimer, and with no long homopolymer to slur the band."
        ),
        constraints={"product_min": 150, "product_max": 500, "max_poly_x": 3},
    ),
    Purpose(
        id="cloning",
        name="Amplifying an insert to clone",
        summary=(
            "The product is retained in a construct, but cloning alone does not define a universal "
            "amplicon-size window, pair-ΔTm ceiling or GC clamp. Those belong to the selected "
            "assay/polymerase/vector workflow; this purpose therefore adds no hard sequence gate."
        ),
        constraints={},
    ),
    Purpose(
        id="genotyping-band",
        name="Sizing a variant by band length",
        summary=(
            "An insertion or deletion read off a gel, so both alleles have to run far enough "
            "apart to tell apart. Short products make a given difference easier to see."
        ),
        constraints={"product_min": 120, "product_max": 400},
    ),
)

DEFAULT_PURPOSE = "general"

_PURPOSES_BY_ID = {p.id: p for p in PURPOSES}


def purpose(purpose_id: str | None) -> Purpose:
    """One purpose by id, defaulting to no particular downstream use.

    Raises:
        ValueError: naming what was asked for and what exists.
    """
    if not purpose_id:
        return _PURPOSES_BY_ID[DEFAULT_PURPOSE]
    if purpose_id not in _PURPOSES_BY_ID:
        known = ", ".join(sorted(_PURPOSES_BY_ID))
        raise ValueError(f"unknown purpose `{purpose_id}`. Known: {known}")
    return _PURPOSES_BY_ID[purpose_id]


def purposes_to_dict() -> list[dict[str, Any]]:
    """The purposes, for a form to render without knowing what is in them."""
    return [
        {"id": p.id, "name": p.name, "summary": p.summary, "constraints": p.constraints}
        for p in PURPOSES
    ]


#: How each constraint should be worded in a form.
#:
#: Published rather than restated in the interface, because the two engines do
#: not take the same settings and a form that hard-codes one engine's fields
#: silently drops the other's. The key is the field name the worker expects, so
#: what the form sends is what the engine reads.
FIELD_WORDING: dict[str, tuple[str, str]] = {
    "product_min": ("Product, shortest (bp)", ""),
    "product_max": ("Product, longest (bp)", ""),
    "length_min": ("Primer length, shortest", ""),
    "length_opt": ("Primer length, ideal", ""),
    "length_max": (
        "Primer length, longest",
        "Primer3 will not go above 36 -- an array size built into it, not a "
        "thermodynamic limit. Its manual says 35; the binary accepts 36 and "
        "refuses 37, which is what the validator here follows.",
    ),
    "tm_min": ("Tm, lowest (°C)", ""),
    "tm_opt": ("Tm, ideal (°C)", ""),
    "tm_max": ("Tm, highest (°C)", ""),
    "tm_pair_max_difference": (
        "Tm pair-difference reference (°C)",
        "A profile/ranking reference for keeping paired primers thermally similar. "
        "It is not a chemistry-independent proof that a pair can or cannot share a bench annealing step.",
    ),
    "tm_spread_max": (
        "Tm, most the mixture may spread (°C)",
        "A degenerate primer is many oligos; the annealing temperature has to suit all of them.",
    ),
    "gc_min": ("GC, lowest (%)", ""),
    "gc_max": ("GC, highest (%)", ""),
    "max_poly_x": (
        "Longest run of one base",
        "Homopolymers slip during synthesis and during extension.",
    ),
    "min_three_prime_distance": (
        "Primers to differ by (bases)",
        "How far apart two candidates' 3-prime ends must be to count as different designs.",
    ),
    "max_degeneracy": (
        "Most molecules in the mixture",
        "Profile-selected mixture budget. Every variable position increases the number of concrete "
        "members; the acceptable ceiling is assay/formulation dependent, not universally 64.",
    ),
    "conserved_end": (
        "Bases at the 3-prime end kept unambiguous",
        "A profile-selected strategy to reduce terminal mismatch risk. Degeneracy itself is not a mismatch; "
        "the exact conserved length is method- and family-dependent.",
    ),
    "min_coverage": (
        "Share of each column to account for",
        "One covers every base seen. Below one, a variant too rare to be worth its degeneracy is "
        "left out — and the coverage actually achieved is measured on the finished primer.",
    ),
}


def fields_for(defaults: dict[str, Any]) -> list[dict[str, Any]]:
    """One engine's settings, worded, in the order they were declared."""
    described = []
    for name, value in defaults.items():
        label, hint = FIELD_WORDING.get(name, (name.replace("_", " ").capitalize(), ""))
        described.append({"name": name, "label": label, "hint": hint, "default": value})
    return described
