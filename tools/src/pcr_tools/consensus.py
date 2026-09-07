"""Several sequences, and what to do when a primer has to fit all of them.

Somebody with ten isolates of the same gene does not want ten designs; they
want one pair that works on all ten. That is a real question and it has two
honest answers, which is why this module refuses more often than it computes.

**If the sequences are already aligned** — same length, gaps as `-` where an
alignment put them — a column-wise consensus is exactly right. Where a column
disagrees it becomes the IUPAC code for what it holds, and the design keeps
primers off those positions or, in an engine built for it, uses degeneracy.

**If they are not aligned**, this refuses. Building a consensus from unaligned
sequences by lining up their first bases is not an approximation of the right
answer; it is a different answer that happens to have the same shape, and it
would produce primers nobody could use. Aligning them needs an aligner, and
saying so is more use than a number that looks like it means something.

Note also what a consensus is not. It is a summary, and a primer against a
summary is a primer against a sequence that may exist in no isolate at all.
The engine built for this question is `consensus-pair`, which designs
degenerate primers from an alignment rather than collapsing it first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fetch import NUCLEIC_ALPHABET

#: What each combination of bases collapses to. Standard IUPAC.
IUPAC: dict[frozenset[str], str] = {
    frozenset("A"): "A",
    frozenset("C"): "C",
    frozenset("G"): "G",
    frozenset("T"): "T",
    frozenset("AG"): "R",
    frozenset("CT"): "Y",
    frozenset("GC"): "S",
    frozenset("AT"): "W",
    frozenset("GT"): "K",
    frozenset("AC"): "M",
    frozenset("CGT"): "B",
    frozenset("AGT"): "D",
    frozenset("ACT"): "H",
    frozenset("ACG"): "V",
    frozenset("ACGT"): "N",
}

#: Characters an alignment uses for a gap.
GAPS = frozenset("-.~")

# Possible concrete bases for every IUPAC symbol. U is normalised to T before
# this table is used, because an RNA alignment still represents the same
# primer-binding complement after reverse transcription.
BASES_FOR_CODE = {
    "A": frozenset("A"),
    "C": frozenset("C"),
    "G": frozenset("G"),
    "T": frozenset("T"),
    "R": frozenset("AG"),
    "Y": frozenset("CT"),
    "S": frozenset("GC"),
    "W": frozenset("AT"),
    "K": frozenset("GT"),
    "M": frozenset("AC"),
    "B": frozenset("CGT"),
    "D": frozenset("AGT"),
    "H": frozenset("ACT"),
    "V": frozenset("ACG"),
    "N": frozenset("ACGT"),
}


class ConsensusError(ValueError):
    """Sequences a consensus cannot honestly be built from."""


@dataclass
class Consensus:
    """One sequence standing for several, and how much it hid."""

    sequence: str
    #: How many sequences went into it.
    from_count: int
    #: Columns where they did not all agree.
    varied: int
    #: Columns where a gap made the base unknowable.
    gapped: int
    notes: list[str]

    @property
    def length(self) -> int:
        return len(self.sequence)

    @property
    def identity(self) -> float:
        """What share of columns every sequence agreed on, as a percentage."""
        if not self.sequence:
            return 0.0
        return round(100.0 * (self.length - self.varied) / self.length, 1)


def build(sequences: list[str], *, names: list[str] | None = None) -> Consensus:
    """Collapse aligned sequences into one, with IUPAC codes where they differ.

    Raises:
        ConsensusError: for fewer than two sequences, or sequences of unequal
            length, which means they have not been aligned.
    """
    cleaned: list[str] = []
    for index, sequence in enumerate(sequences, start=1):
        if not isinstance(sequence, str):
            raise ConsensusError(f"sequence {index} is not text")
        value = "".join(c for c in sequence.upper() if not c.isspace()).replace("U", "T")
        if not value:
            raise ConsensusError(f"sequence {index} is empty")
        invalid = sorted(set(value) - NUCLEIC_ALPHABET)
        if invalid:
            raise ConsensusError(
                f"sequence {index} contains invalid symbol(s): "
                + ", ".join(repr(symbol) for symbol in invalid)
            )
        cleaned.append(value)

    if len(cleaned) < 2:
        raise ConsensusError("A consensus needs at least two sequences.")

    lengths = {len(s) for s in cleaned}
    if len(lengths) > 1:
        shortest, longest = min(lengths), max(lengths)
        raise ConsensusError(
            f"These {len(cleaned)} sequences are {shortest} to {longest} bases long, so they "
            "have not been aligned. A consensus built by lining up their first bases would "
            "not be a summary of anything. Align them first, or design against one of them "
            "and check the others as a background."
        )

    notes: list[str] = []
    letters: list[str] = []
    varied = 0
    gapped = 0

    for column in zip(*cleaned, strict=True):
        bases = set().union(*(BASES_FOR_CODE[c] for c in column if c not in GAPS))
        has_gap = any(c in GAPS for c in column)

        if not bases:
            # Every sequence is gapped or ambiguous here; nothing can be said.
            letters.append("N")
            gapped += 1
            varied += 1
            continue

        if has_gap:
            gapped += 1
        if len(bases) > 1 or has_gap:
            varied += 1

        letters.append(IUPAC.get(frozenset(bases), "N"))

    consensus = Consensus(
        sequence="".join(letters),
        from_count=len(cleaned),
        varied=varied,
        gapped=gapped,
        notes=notes,
    )

    if names and len(names) == len(cleaned):
        notes.append("Built from " + ", ".join(names) + ".")
    if varied:
        notes.append(
            f"{varied} of {consensus.length} columns disagree, so the consensus carries "
            "ambiguity codes there. No primer will be placed over one."
        )
    if gapped:
        notes.append(
            f"{gapped} columns hold a gap in at least one sequence. Those are the positions "
            "where a consensus is least trustworthy."
        )
    notes.append(
        "A consensus is a summary. A primer against it is a primer against a sequence that "
        "may exist in none of your isolates — check the design against each of them before "
        "ordering."
    )

    return consensus


def consensus_to_dict(result: Consensus) -> dict[str, Any]:
    """The consensus as plain data."""
    return {
        "sequence": result.sequence,
        "length": result.length,
        "from_count": result.from_count,
        "varied": result.varied,
        "gapped": result.gapped,
        "identity": result.identity,
        "notes": result.notes,
    }
