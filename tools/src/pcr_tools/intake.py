"""Turning whatever somebody pasted into one thing the rest of the code trusts.

A person hands us a sequence in one of about a dozen shapes: raw bases, FASTA,
a block copied out of a GenBank flat file with its coordinates still attached,
something a word processor has been through, RNA, or a protein sequence pasted
by mistake. Each of those has a failure mode that is silent — the sequence is
accepted, it is subtly wrong, and nobody finds out until the gel.

So nothing here guesses quietly. Every inference becomes a `Note`, the notes
travel with the sequence, and the interface shows them back before a primer is
designed. The rule is that a person can always see what we decided on their
behalf while there is still time to disagree.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

#: The bases a template may be written in once we are done with it. Lowercase
#: is kept on purpose: it is how a repeat-masked genome marks its repeats, and
#: Primer3 reads it through PRIMER_LOWERCASE_MASKING.
DNA = frozenset("ACGT")

#: Everything IUPAC allows. These are not refused outright — a template with a
#: handful of them is ordinary — but they are counted and located, because one
#: of them under a primer's 3' end is the end of that primer.
AMBIGUOUS = frozenset("RYSWKMBDHVN")

#: Letters that appear in proteins and never in nucleic acid. If a sequence
#: contains these, it is not DNA and saying so is more use than a complaint
#: about unknown bases.
PROTEIN_ONLY = frozenset("EFILPQXZJO")


class IntakeError(ValueError):
    """Input that cannot become a template, with a reason a person can act on."""


@dataclass(frozen=True)
class Note:
    """One thing we decided, or noticed, on the way in.

    `kind` is for the interface to branch on; `message` is for the person.
    """

    kind: str
    message: str


@dataclass
class Target:
    """One template, and the full account of how it got that way."""

    #: The sequence, case preserved. Lowercase means soft-masked.
    sequence: str
    #: What to call it. From a FASTA header where there was one.
    name: str
    #: What the caller actually sent, before anything was stripped.
    raw_length: int
    #: Whether the lowercase in this sequence is repeat masking.
    soft_masked: bool
    #: Whether the submitted alphabet contained uracil before it was normalised.
    #:
    #: This is kept separately from the note because downstream chemistry must
    #: act on it. Once U has become T, looking at `sequence` can no longer tell
    #: an RNA request from a DNA request.
    rna_input: bool = False
    #: Where the ambiguity codes are, zero-based. Truncated for display by the
    #: caller, never here — the count is what matters and it is `len()`.
    ambiguous_at: list[int] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.sequence)

    @property
    def upper(self) -> str:
        """The sequence with masking flattened, for anything that cannot read case."""
        return self.sequence.upper()


def _note(notes: list[Note], kind: str, message: str) -> None:
    notes.append(Note(kind=kind, message=message))


def _strip_fasta(text: str, notes: list[Note]) -> tuple[str, str]:
    """Pull the first record out of FASTA, and say so if there were more."""
    if not text.lstrip().startswith(">"):
        return text, ""

    records = [block for block in text.lstrip().split(">") if block.strip()]
    header, _, body = records[0].partition("\n")
    name = header.strip()

    if len(records) > 1:
        _note(
            notes,
            "multipleRecords",
            f"The input held {len(records)} FASTA records. Only the first, "
            f"{name or 'unnamed'}, was used.",
        )
    return body, name


#: A GenBank ORIGIN block is coordinate-prefixed lines of ten-base groups. The
#: coordinates are the trap: strip non-letters naively and they weld themselves
#: into the sequence.
_ORIGIN_LINE = re.compile(r"^\s*\d+\s+(?:[A-Za-z]{1,10}\s*)+$")


def _strip_genbank(text: str, notes: list[Note]) -> str:
    """Extract a GenBank ORIGIN block, or remove coordinates from a fragment."""
    lines = text.splitlines()

    # A complete flat file has metadata and feature annotations before ORIGIN.
    # Reading every alphabetic character from it would weld LOCUS/FEATURES to
    # the sequence and can even introduce protein-only letters. The terminator
    # is the record boundary; anything after it is not part of this template.
    origin = next(
        (index for index, line in enumerate(lines) if line.strip().upper() == "ORIGIN"),
        None,
    )
    if origin is not None:
        sequence_lines: list[str] = []
        for line in lines[origin + 1 :]:
            if line.strip() == "//":
                break
            # A GenBank coordinate is a numeric prefix followed by whitespace;
            # do not rescue a malformed `1ACGT` line by silently deleting its
            # leading digit and changing the submitted molecule.
            sequence_lines.append(re.sub(r"^\s*\d+\s+", "", line))
        _note(
            notes,
            "genbankLayout",
            "The input looked like a GenBank record, so only its ORIGIN "
            "sequence block was used and its line coordinates were removed.",
        )
        return "\n".join(sequence_lines)

    numbered = [line for line in lines if _ORIGIN_LINE.match(line)]
    if len(numbered) < 2 or len(numbered) < len([line for line in lines if line.strip()]) // 2:
        return text

    _note(
        notes,
        "genbankLayout",
        "The input looked like a GenBank ORIGIN block, so the line coordinates "
        "were removed rather than read as bases.",
    )
    return "\n".join(re.sub(r"^\s*\d+\s+", "", line) for line in lines)


def _normalise(text: str) -> str:
    """Undo what word processors and non-UTF-8 locales do to a pasted sequence."""
    # NFKC turns full-width and other compatibility forms into plain ASCII, and
    # a no-break space into a space we can then drop.
    return unicodedata.normalize("NFKC", text).replace(" ", " ")


def resolve(
    text: str,
    *,
    name: str = "",
    lowercase_masking: bool | None = None,
) -> Target:
    """Turn pasted text into a template, and account for every change made.

    Raises:
        IntakeError: when the input is empty, is not nucleic acid, or is so
            short that no primer could sit on it.
    """
    if not isinstance(text, str) or not text.strip():
        raise IntakeError("No sequence was given.")

    notes: list[Note] = []
    raw_length = len(text)

    body, fasta_name = _strip_fasta(_normalise(text), notes)
    body = _strip_genbank(body, notes)

    # Whitespace and GenBank coordinate digits are formatting. Punctuation is
    # not: silently dropping a gap, slash or stop marker changes coordinates
    # and can create a sequence that was never pasted. Refuse it before the
    # alphabet check so the caller can repair the source rather than trust a
    # shortened template.
    invalid_symbols = sorted(
        {character for character in body if not character.isspace() and not character.isalpha()}
    )
    if invalid_symbols:
        raise IntakeError(
            "The input contains formatting symbols "
            + ", ".join(repr(symbol) for symbol in invalid_symbols)
            + ". Remove alignment gaps or punctuation and provide a DNA/RNA sequence."
        )

    # Whitespace goes. By this point, digits are valid only if they were
    # recognised and removed as GenBank line coordinates above; a digit left
    # in raw/FASTA input must have been rejected rather than silently changing
    # the molecule and every downstream coordinate.
    letters = "".join(c for c in body if c.isalpha())
    if not letters:
        raise IntakeError("The input contained no letters, so there is no sequence in it.")

    upper = letters.upper()

    protein = sorted(set(upper) & PROTEIN_ONLY)
    if protein:
        raise IntakeError(
            f"This looks like a protein sequence: it contains "
            f"{', '.join(protein)}, which nucleic acid does not. "
            "Primers are designed against DNA."
        )

    rna_input = "U" in upper
    if rna_input:
        letters = "".join(("T" if c == "U" else "t" if c == "u" else c) for c in letters)
        upper = letters.upper()
        _note(
            notes,
            "rnaConverted",
            "The input was RNA. U was read as T, which is what a primer will "
            "anneal to once it is reverse-transcribed.",
        )

    unknown = sorted(set(upper) - DNA - AMBIGUOUS)
    if unknown:
        raise IntakeError(
            f"The sequence contains {', '.join(unknown)}, which is neither a base "
            "nor an IUPAC ambiguity code."
        )

    lower_count = sum(1 for c in letters if c.islower())
    if lowercase_masking is not None and not isinstance(lowercase_masking, bool):
        raise IntakeError("`lowercase_masking` must be true or false when supplied.")

    # Case is data only when the caller says it is data. A percentage threshold
    # cannot distinguish a deliberately masked repeat from ordinary lower-case
    # formatting, so Generation-1 never infers this interpretation from case
    # density or policy mode.
    if lower_count and lowercase_masking is True:
        soft_masked = True
        _note(
            notes,
            "softMasked",
            f"{lower_count} of {len(letters)} bases are lowercase. The caller "
            "explicitly marked lowercase as soft-masked sequence, so primer 3' "
            "ends will avoid those bases under the Primer3 masking policy.",
        )
    elif lower_count and lowercase_masking is False:
        soft_masked = False
        letters = letters.upper()
        _note(
            notes,
            "caseFlattened",
            f"{lower_count} lowercase base(s) were explicitly declared formatting, "
            "not soft masking, so case was normalised before design.",
        )
    else:
        if lower_count:
            raise IntakeError(
                "PCRStudio does not infer whether lowercase sequence bases are soft masking or formatting. "
                "Set `lowercase_masking=true` to preserve lowercase as masked sequence, or false to normalise case."
            )
        soft_masked = False

    ambiguous_at = [i for i, c in enumerate(letters.upper()) if c in AMBIGUOUS]
    if ambiguous_at:
        _note(
            notes,
            "ambiguity",
            f"{len(ambiguous_at)} ambiguity code(s) in the template. No primer "
            "will be allowed to overlap one.",
        )

    if raw_length != len(letters):
        _note(
            notes,
            "trimmed",
            f"{raw_length} characters in, {len(letters)} bases out.",
        )

    return Target(
        sequence=letters,
        name=name or fasta_name or "template",
        raw_length=raw_length,
        soft_masked=soft_masked,
        rna_input=rna_input,
        ambiguous_at=ambiguous_at,
        notes=notes,
    )


def target_to_dict(target: Target, *, ambiguity_shown: int = 12) -> dict[str, Any]:
    """The confirmation panel's data: what we understood, not the sequence itself.

    The sequence is deliberately absent. This is the thing shown back to a
    person before they commit, and a wall of bases is not information.
    """
    return {
        "name": target.name,
        "length": target.length,
        "raw_length": target.raw_length,
        "gc_percent": round(100.0 * sum(c in "GCgc" for c in target.sequence) / target.length, 1)
        if target.length
        else 0.0,
        "soft_masked": target.soft_masked,
        "rna_input": target.rna_input,
        "ambiguous_count": len(target.ambiguous_at),
        # One-based, because every genome browser a bench scientist has ever
        # used counts from one.
        "ambiguous_at": [i + 1 for i in target.ambiguous_at[:ambiguity_shown]],
        "notes": [{"kind": n.kind, "message": n.message} for n in target.notes],
    }
