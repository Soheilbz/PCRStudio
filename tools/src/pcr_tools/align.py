"""Build the Generation-1 multiple-sequence alignment with pinned MAFFT.

A degenerate-primer search depends on alignment columns, so silently changing
aligners changes scientific input rather than merely changing implementation.
Current Generation-1 therefore has two explicit authorities only:

* ``alignment_mode=auto`` -> the pinned MAFFT 7.526 toolchain artifact;
* ``alignment_mode=prealigned`` -> a user-reviewed alignment that bypasses this module.

MUSCLE/FAMSA remain useful research references, but they are not automatic
substitutes in the executable current runtime. If MAFFT is unavailable or its
version cannot be verified against the Generation-1 pin, alignment fails closed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fetch import NUCLEIC_ALPHABET, Record, parse_fasta
from .tool_runtime import ToolRuntimeError, resolve, run_tool, tool_status

#: How long an alignment may take before it is abandoned.
TIMEOUT_SECONDS = 120

#: More than this and the wait stops being interactive; a run that size wants a
#: job rather than a request.
MAX_SEQUENCES = 500
MAX_TOTAL_BASES = 5_000_000


class AlignError(RuntimeError):
    """No aligner, or an aligner that failed, with what to do about it."""


@dataclass(frozen=True)
class Aligned:
    """The alignment, and which program produced it."""

    records: list[Record]
    tool: str
    tool_version: str
    tool_role: str
    warnings: tuple[str, ...] = ()

    @property
    def width(self) -> int:
        return len(self.records[0].sequence) if self.records else 0

    @property
    def depth(self) -> int:
        return len(self.records)


def _binary() -> str | None:
    """Resolve the one current automatic-alignment authority: MAFFT."""
    resolved = resolve("mafft")
    return str(resolved.path) if resolved.path else None


def available() -> dict[str, Any]:
    """Whether the pinned Generation-1 automatic aligner is installed."""
    mafft = _binary()
    options = [{"id": "mafft", "name": "MAFFT", "path": mafft}] if mafft else []
    return {
        "available": bool(options),
        "aligners": options,
        "reason": (
            ""
            if options
            else "MAFFT 7.526 is unavailable. Configure the canonical MAFFT toolchain artifact; PCRStudio does not auto-substitute another aligner."
        ),
    }


def _with_mafft(
    path: str,
    fasta: str,
    *,
    engine_id: str,
    module_id: str,
) -> list[Record]:
    # `--auto` picks the strategy from the size of the problem, which is what
    # anybody running MAFFT by hand would do. Execution still goes through the
    # centralized tool runtime so artifact identity, version/hash evidence and
    # command provenance are enforced consistently with every other external
    # scientific tool.
    try:
        completed, _run_record = run_tool(
            "mafft",
            ["--auto", "--quiet", "-"],
            role="PRIMARY",
            operation_id="align_panel",
            engine_id=engine_id,
            module_id=module_id,
            stdin=fasta,
            cwd=Path(os.path.dirname(path)),
            timeout_seconds=TIMEOUT_SECONDS,
        )
    except ToolRuntimeError as error:
        raise AlignError(str(error)) from error
    return parse_fasta(completed.stdout)


def align(
    fasta: str,
    *,
    engine_id: str = "consensus-pair",
    module_id: str = "universal-primers",
) -> Aligned:
    """Align the sequences in some FASTA, with whatever aligner is here.

    Raises:
        AlignError: when there is nothing to align it with, or the aligner
            failed, or the input is larger than this will attempt.
    """
    records = parse_fasta(fasta)
    if len(records) < 2:
        raise AlignError(
            f"An alignment needs at least two sequences; this input holds {len(records)}."
        )
    input_ids = [record.id for record in records]
    if len(set(input_ids)) != len(input_ids):
        duplicates = sorted(
            {identifier for identifier in input_ids if input_ids.count(identifier) > 1}
        )
        raise AlignError(
            "The alignment input contains duplicate record identifier(s): "
            + ", ".join(repr(identifier) for identifier in duplicates)
            + ". Give every sequence a unique name so the aligned rows cannot be confused."
        )
    for record in records:
        invalid = sorted(set(record.sequence) - NUCLEIC_ALPHABET)
        if invalid:
            raise AlignError(
                f"{record.id} contains invalid symbol(s): "
                + ", ".join(repr(symbol) for symbol in invalid)
                + ". Remove them before alignment."
            )
    if len(records) > MAX_SEQUENCES:
        raise AlignError(
            f"{len(records)} sequences were given and this aligns up to {MAX_SEQUENCES}."
        )
    total = sum(record.length for record in records)
    if total > MAX_TOTAL_BASES:
        raise AlignError(f"{total:,} bases in all, and this aligns up to {MAX_TOTAL_BASES:,}.")

    options = available()
    if not options["available"]:
        raise AlignError(options["reason"])

    chosen = options["aligners"][0]
    if chosen["id"] != "mafft":
        raise AlignError(
            "Current Generation-1 automatic alignment requires MAFFT 7.526; another aligner cannot be substituted implicitly."
        )

    status = tool_status("mafft")
    if status.get("version_matches_contract") is not True:
        observed = status.get("observed_version")
        raise AlignError(
            f"MAFFT resolved to {observed!r}; current Generation-1 automatic alignment requires the pinned 7.526 version."
        )

    normalised = "\n".join(f">{r.id}\n{r.sequence}" for r in records)
    aligned = _with_mafft(
        chosen["path"],
        normalised,
        engine_id=engine_id,
        module_id=module_id,
    )
    role = "PRIMARY"
    warnings: list[str] = []

    if not aligned:
        raise AlignError(f"{chosen['name']} returned nothing.")

    returned_ids = [record.id for record in aligned]
    if len(set(returned_ids)) != len(returned_ids) or set(returned_ids) != set(input_ids):
        missing = sorted(set(input_ids) - set(returned_ids))
        unexpected = sorted(set(returned_ids) - set(input_ids))
        duplicate = sorted(
            {identifier for identifier in returned_ids if returned_ids.count(identifier) > 1}
        )
        details = []
        if missing:
            details.append("missing " + ", ".join(repr(identifier) for identifier in missing))
        if unexpected:
            details.append("unexpected " + ", ".join(repr(identifier) for identifier in unexpected))
        if duplicate:
            details.append("duplicated " + ", ".join(repr(identifier) for identifier in duplicate))
        raise AlignError(
            f"{chosen['name']} returned rows that do not match the input records ("
            + "; ".join(details)
            + "). The alignment was discarded so a consensus cannot use the wrong sequences."
        )

    input_by_id = {record.id: record.sequence.replace("U", "T") for record in records}
    for record in aligned:
        invalid = sorted(set(record.sequence) - NUCLEIC_ALPHABET)
        if invalid:
            raise AlignError(
                f"{chosen['name']} returned invalid symbol(s) in {record.id}: "
                + ", ".join(repr(symbol) for symbol in invalid)
                + ". The alignment was discarded."
            )
        ungapped = (
            record.sequence.replace("-", "").replace(".", "").replace("~", "").replace("U", "T")
        )
        if ungapped != input_by_id[record.id]:
            raise AlignError(
                f"{chosen['name']} changed the bases in record {record.id!r}; only alignment "
                "gaps may be added. The alignment was discarded."
            )

    widths = {len(record.sequence) for record in aligned}
    if len(widths) > 1:
        raise AlignError(
            f"{chosen['name']} returned rows of different lengths, which is not an alignment."
        )

    # Aligners are free to reorder; the order somebody gave them in is the
    # order they will read the result in.
    order = {record.id: index for index, record in enumerate(records)}
    aligned.sort(key=lambda record: order.get(record.id, len(order)))

    return Aligned(
        records=aligned,
        tool=chosen["name"],
        tool_version=_version(chosen),
        tool_role=role,
        warnings=tuple(warnings),
    )


def _version(chosen: dict[str, str]) -> str:
    """Record the verified MAFFT version string."""
    status = tool_status("mafft")
    observed = str(status.get("observed_version") or "").strip()
    return observed or "MAFFT 7.526"


def aligned_to_dict(result: Aligned) -> dict[str, Any]:
    """The alignment as plain data, with the FASTA a person can paste anywhere."""
    return {
        "tool": result.tool,
        "tool_version": result.tool_version,
        "tool_role": result.tool_role,
        "warnings": list(result.warnings),
        "depth": result.depth,
        "width": result.width,
        "records": [{"id": record.id, "sequence": record.sequence} for record in result.records],
        "fasta": "\n".join(f">{r.id}\n{r.sequence}" for r in result.records),
    }
