"""PrimalScheme3 3.3.0 adapter for the generation-1 tiled-scheme engine.

The adapter owns the complete executable lifecycle PCRStudio exposes in Gen-1:

* ``scheme-create`` for a new tiled scheme,
* ``panel-create`` for bounded region/panel designs,
* ``repair-mode`` for adding primers against a newer aligned population, and
* ``scheme-replace`` for replacing one named primer-pair in an existing scheme.

MAFFT is the canonical alignment authority when multiple unaligned sequences
are supplied.  A reviewed alignment can instead be preserved explicitly with
``tilingAlignmentMode=prealigned``.  All imported BED coordinates are normalised
under PCRStudio's 0-based, half-open contract; ambiguous upstream outputs fail
closed rather than being silently reinterpreted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from .align import AlignError, aligned_to_dict
from .align import align as align_sequences
from .design import Constraints
from .intake import target_to_dict
from .presets import thermodynamic_model
from .provenance import provenance
from .scientific_integrity import strict as strict_science
from .settings import label, prepare
from .thermo import analyse
from .tool_runtime import ToolRuntimeError, resolve, run_tool, toolchain_mode

_PAIR_TOKEN = re.compile(r"(?i)(?:^|[_-])(LEFT|RIGHT)(?:[_-]?\d+)?$")
_ALLOWED_ALIGNMENT = frozenset("ACGTURYSWKMBDHVN-")
_LIFECYCLE = frozenset({"scheme-create", "panel-create", "repair-mode", "scheme-replace"})

_IUPAC_BASES: dict[str, frozenset[str]] = {
    "A": frozenset("A"),
    "C": frozenset("C"),
    "G": frozenset("G"),
    "T": frozenset("T"),
    "U": frozenset("T"),
    "R": frozenset("AG"),
    "Y": frozenset("CT"),
    "S": frozenset("CG"),
    "W": frozenset("AT"),
    "K": frozenset("GT"),
    "M": frozenset("AC"),
    "B": frozenset("CGT"),
    "D": frozenset("AGT"),
    "H": frozenset("ACT"),
    "V": frozenset("ACG"),
    "N": frozenset("ACGT"),
}
_IUPAC_COMPLEMENT = {
    "A": "T",
    "C": "G",
    "G": "C",
    "T": "A",
    "U": "A",
    "R": "Y",
    "Y": "R",
    "S": "S",
    "W": "W",
    "K": "M",
    "M": "K",
    "B": "V",
    "D": "H",
    "H": "D",
    "V": "B",
    "N": "N",
    "-": "-",
}


def _oriented_alignment_segment(aligned_sequence: str, columns: list[int], strand: str) -> str:
    segment = "".join(aligned_sequence[column].upper() for column in columns)
    if strand == "+":
        return segment
    return "".join(_IUPAC_COMPLEMENT.get(base, "N") for base in reversed(segment))


def _alignment_variant_risk(*, msa_payload: str, primers: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure observed primer-site conservation in the exact MSA used for tiling.

    This is deliberately *not* an amplification-success model.  It reports whether
    each ordered primer sequence is reproduced exactly, is only ambiguity-compatible,
    or has a definite mismatch/gap in each aligned input sequence.  The terminal-five
    summary is evidence for review because 3′ mismatches can matter strongly, but no
    universal dropout threshold is manufactured from it.
    """

    records = _fasta_records(msa_payload)
    if not records:
        return {
            "status": "not-evaluated",
            "reason": "No alignment records were available.",
            "alignment_depth": 0,
            "primers": [],
        }
    widths = {len(sequence) for _, sequence in records}
    if len(widths) != 1:
        raise PrimalSchemeImportError(
            "variant-risk analysis requires one rectangular MSA; aligned rows have different widths"
        )
    reference_aligned = records[0][1].upper()
    reference_columns = [index for index, base in enumerate(reference_aligned) if base != "-"]
    reference_length = len(reference_columns)

    reports: list[dict[str, Any]] = []
    for primer in primers:
        start = int(primer["start"])
        end = int(primer["end"])
        sequence = str(primer["sequence"]).upper().replace("U", "T")
        strand = str(primer["strand"])
        if start < 0 or end > reference_length or end <= start:
            raise PrimalSchemeImportError(
                f"primer {primer['name']!r} lies outside the ungapped alignment-reference coordinate domain"
            )
        columns = reference_columns[start:end]
        if len(columns) != len(sequence):
            raise PrimalSchemeImportError(
                f"primer {primer['name']!r} BED span ({len(columns)} nt) does not equal its sequence length ({len(sequence)} nt); variant-risk mapping would be ambiguous"
            )

        exact = 0
        ambiguity_compatible = 0
        definite_nonmatch = 0
        gap_sequences = 0
        terminal_non_exact = 0
        worst_examples: list[dict[str, Any]] = []
        terminal_start = max(0, len(sequence) - 5)

        for record_name, aligned_sequence in records:
            oriented = _oriented_alignment_segment(aligned_sequence, columns, strand)
            has_gap = "-" in oriented
            definite_positions: list[int] = []
            ambiguous_positions: list[int] = []
            for offset, (primer_base, observed) in enumerate(zip(sequence, oriented, strict=True)):
                if observed == "-":
                    definite_positions.append(offset)
                    continue
                allowed = _IUPAC_BASES.get(observed)
                if allowed is None or primer_base not in allowed:
                    definite_positions.append(offset)
                elif observed != primer_base:
                    ambiguous_positions.append(offset)

            non_exact_positions = sorted(set(definite_positions + ambiguous_positions))
            if not non_exact_positions:
                exact += 1
            elif definite_positions:
                definite_nonmatch += 1
            else:
                ambiguity_compatible += 1
            if has_gap:
                gap_sequences += 1
            if any(position >= terminal_start for position in non_exact_positions):
                terminal_non_exact += 1
            if non_exact_positions and len(worst_examples) < 8:
                worst_examples.append(
                    {
                        "record": record_name,
                        "definite_mismatch_or_gap_positions_0based": definite_positions,
                        "ambiguity_compatible_positions_0based": ambiguous_positions,
                    }
                )

        depth = len(records)
        reports.append(
            {
                "name": str(primer["name"]),
                "role": str(primer["role"]),
                "strand": strand,
                "start": start,
                "end": end,
                "alignment_depth": depth,
                "exact_match_sequences": exact,
                "ambiguity_compatible_sequences": ambiguity_compatible,
                "definite_nonmatch_sequences": definite_nonmatch,
                "gap_sequences": gap_sequences,
                "terminal_5nt_non_exact_sequences": terminal_non_exact,
                "exact_match_fraction": round(exact / max(depth, 1), 6),
                "definite_nonmatch_fraction": round(definite_nonmatch / max(depth, 1), 6),
                "terminal_5nt_non_exact_fraction": round(terminal_non_exact / max(depth, 1), 6),
                "examples": worst_examples,
            }
        )

    affected = [report for report in reports if report["exact_match_sequences"] < len(records)]
    definite = [report for report in reports if report["definite_nonmatch_sequences"] > 0]
    return {
        "status": "observed-alignment-conservation-evidence",
        "semantics": "MSA-site conservation evidence; not an amplification/dropout guarantee",
        "alignment_depth": len(records),
        "terminal_window_nt": 5,
        "primers_with_any_non_exact_observation": len(affected),
        "primers_with_definite_mismatch_or_gap": len(definite),
        "max_definite_nonmatch_fraction": max(
            (report["definite_nonmatch_fraction"] for report in reports), default=0.0
        ),
        "max_terminal_5nt_non_exact_fraction": max(
            (report["terminal_5nt_non_exact_fraction"] for report in reports), default=0.0
        ),
        "primers": reports,
        "interpretation": (
            "Review any non-exact or terminal observations against the intended population and assay. "
            "PCRStudio does not turn these fractions into a universal wet-lab dropout threshold."
        ),
    }


class PrimalSchemeImportError(ValueError):
    """Upstream scheme input/output could not be represented without guessing."""


def available() -> bool:
    return resolve("primalscheme3").available


def should_attempt(request: dict[str, Any]) -> bool:
    policy = os.environ.get("PCRSTUDIO_TILING_BACKEND", "primalscheme3").strip().lower()
    if policy not in {"primalscheme3", "internal-development"}:
        policy = "primalscheme3"
    if policy == "internal-development":
        if strict_science():
            raise PrimalSchemeImportError(
                "the internal tiled walker is a development-only backend; strict scientific execution requires PrimalScheme3 3.3.0"
            )
        return False
    return True


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _split_name(name: str) -> tuple[str, str] | None:
    match = _PAIR_TOKEN.search(name)
    if not match:
        return None
    role = match.group(1).upper()
    stem = name[: match.start()].rstrip("_-") or name
    return stem, role


def _parse_bed(path: Path) -> list[dict[str, Any]]:
    primers: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith(("#", "track", "browser")):
            continue
        fields = line.split("\t")
        if len(fields) < 6:
            fields = line.split()
        if len(fields) < 6:
            raise PrimalSchemeImportError(
                f"{path.name}:{line_number} has fewer than six BED fields"
            )
        try:
            start = int(fields[1])
            end = int(fields[2])
        except ValueError as error:
            raise PrimalSchemeImportError(
                f"{path.name}:{line_number} has non-integer coordinates"
            ) from error
        if start < 0 or end <= start:
            raise PrimalSchemeImportError(
                f"{path.name}:{line_number} is not a valid zero-based half-open interval"
            )
        name = fields[3]
        try:
            pool_raw = int(fields[4])
        except ValueError:
            pool_raw = 1
        strand = fields[5]
        if strand not in {"+", "-"}:
            raise PrimalSchemeImportError(
                f"{path.name}:{line_number} has invalid strand {strand!r}"
            )
        sequence = "".join(fields[6].split()).upper() if len(fields) >= 7 else ""
        if not sequence:
            raise PrimalSchemeImportError(
                f"{path.name}:{line_number} has no primer sequence; PCRStudio will not reconstruct it by guessing strand semantics"
            )
        split = _split_name(name)
        if split is None:
            role = "LEFT" if strand == "+" else "RIGHT"
            stem = re.sub(r"(?i)[_-]?[FR]$", "", name) or name
        else:
            stem, role = split
        primers.append(
            {
                "chrom": fields[0],
                "name": name,
                "stem": stem,
                "role": role,
                "start": start,
                "end": end,
                "pool_raw": pool_raw,
                "strand": strand,
                "sequence": sequence,
            }
        )
    return primers


def _parse_region_bed(raw: str, *, reference_length: int) -> list[tuple[int, int]]:
    """Parse and merge requested BED regions under PCRStudio coordinate rules.

    Region BED is input authority for ``panel-create`` coverage.  Unlike primer
    BED it needs only the first three BED columns.  Coordinates are never
    silently clipped because doing so would make the reported coverage scope
    differ from what the user supplied.
    """
    intervals: list[tuple[int, int]] = []
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(("#", "track", "browser")):
            continue
        fields = line.split("\t")
        if len(fields) < 3:
            fields = line.split()
        if len(fields) < 3:
            raise PrimalSchemeImportError(
                f"region BED line {line_number} has fewer than three fields"
            )
        try:
            start = int(fields[1])
            end = int(fields[2])
        except ValueError as error:
            raise PrimalSchemeImportError(
                f"region BED line {line_number} has non-integer coordinates"
            ) from error
        if start < 0 or end <= start:
            raise PrimalSchemeImportError(
                f"region BED line {line_number} is not a valid zero-based half-open interval"
            )
        if end > reference_length:
            raise PrimalSchemeImportError(
                f"region BED line {line_number} ends at {end}, past the {reference_length}-base reference"
            )
        intervals.append((start, end))
    if not intervals:
        raise PrimalSchemeImportError("region BED contains no usable intervals")

    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            prior_start, prior_end = merged[-1]
            merged[-1] = (prior_start, max(prior_end, end))
    return merged


def _gaps_within(
    intervals: list[tuple[int, int]], covered: set[int], *, why: str
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for region_start, region_end in intervals:
        at = region_start
        while at < region_end:
            if at in covered:
                at += 1
                continue
            first = at
            while at < region_end and at not in covered:
                at += 1
            gaps.append({"from": first, "to": at, "bases": at - first, "why": why})
    return gaps


def _find_bed(workspace: Path, *, exclude: Path | None = None) -> Path:
    exact = sorted(
        path for path in workspace.rglob("primer.bed") if exclude is None or path != exclude
    )
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise PrimalSchemeImportError(
            "PrimalScheme3 produced multiple primer.bed files; configure one scheme per request"
        )
    preferred = sorted(
        path for path in workspace.rglob("*.primer.bed") if exclude is None or path != exclude
    )
    candidates = preferred or sorted(
        path for path in workspace.rglob("*.bed") if exclude is None or path != exclude
    )
    if not candidates:
        raise PrimalSchemeImportError("PrimalScheme3 completed but produced no BED file")
    if len(preferred) > 1:
        raise PrimalSchemeImportError(
            "PrimalScheme3 produced multiple primer BED files; configure one scheme per request"
        )
    if not preferred and len(candidates) > 1:
        raise PrimalSchemeImportError(
            "PrimalScheme3 produced multiple BED files without a canonical primer.bed; PCRStudio will not choose one by filesystem order"
        )
    return candidates[0]


def _find_config(workspace: Path) -> Path | None:
    preferred = sorted(workspace.rglob("config.json"))
    if len(preferred) == 1:
        return preferred[0]
    if len(preferred) > 1:
        # Prefer a config below the generated output directory, but never use
        # filesystem ordering as a hidden scientific choice.
        generated = [
            path for path in preferred if "scheme" in {part.lower() for part in path.parts}
        ]
        if len(generated) == 1:
            return generated[0]
        return None
    return None


def _normalise_pools(primers: list[dict[str, Any]]) -> dict[int, int]:
    values = sorted({int(one["pool_raw"]) for one in primers})
    return {value: index for index, value in enumerate(values)}


def _fasta_records(raw: str) -> list[tuple[str, str]]:
    text = raw.strip().replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith(">"):
        sequence = "".join(character for character in text if not character.isspace()).upper()
        sequence = sequence.replace("U", "T")
        invalid = sorted(set(sequence) - (_ALLOWED_ALIGNMENT - {"-"}))
        if invalid:
            raise PrimalSchemeImportError(
                "tiling input contains invalid nucleotide symbol(s): " + ", ".join(invalid)
            )
        return [("reference", sequence)]

    records: list[tuple[str, str]] = []
    name = ""
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if name:
                records.append((name, "".join(chunks).upper().replace("U", "T")))
            name = line[1:].strip().split()[0] or f"sequence_{len(records) + 1}"
            chunks = []
        else:
            chunks.append("".join(line.split()))
    if name:
        records.append((name, "".join(chunks).upper().replace("U", "T")))
    if not records:
        raise PrimalSchemeImportError("the tiling FASTA contains no records")
    if len({name for name, _ in records}) != len(records):
        raise PrimalSchemeImportError("every tiling FASTA record needs a unique identifier")
    for name, sequence in records:
        invalid = sorted(set(sequence) - _ALLOWED_ALIGNMENT)
        if invalid:
            raise PrimalSchemeImportError(
                f"{name} contains invalid alignment symbol(s): " + ", ".join(invalid)
            )
        if not sequence.replace("-", ""):
            raise PrimalSchemeImportError(f"{name} contains no nucleotide bases")
    return records


def _prepare_input(request: dict[str, Any]) -> tuple[Any, str, str, dict[str, Any]]:
    """Resolve assay/reaction settings while preserving the full MSA payload."""
    records = _fasta_records(str(request.get("template") or ""))
    alignment_mode = str(request.get("tilingAlignmentMode") or "auto")
    if alignment_mode not in {"auto", "prealigned"}:
        raise PrimalSchemeImportError("tilingAlignmentMode must be `auto` or `prealigned`")

    alignment_meta: dict[str, Any]
    if len(records) > 1:
        if alignment_mode == "auto":
            if any("-" in sequence for _, sequence in records):
                raise PrimalSchemeImportError(
                    "auto tiling alignment received gap characters. Remove the existing gaps or select prealigned so PCRStudio does not realign a reviewed MSA."
                )
            fasta = "\n".join(f">{name}\n{sequence}" for name, sequence in records)
            try:
                aligned = align_sequences(
                    fasta,
                    engine_id="tiling-scheme",
                    module_id="tiled-scheme",
                )
            except AlignError as error:
                raise PrimalSchemeImportError(str(error)) from error
            described = aligned_to_dict(aligned)
            msa_payload = str(described["fasta"]) + "\n"
            alignment_meta = {
                "mode": "auto",
                "authority": described["tool"],
                "tool_version": described["tool_version"],
                "tool_role": described["tool_role"],
                "depth": described["depth"],
                "width": described["width"],
                "warnings": described["warnings"],
                "sha256": _sha256_text(msa_payload),
            }
            aligned_records = _fasta_records(msa_payload)
        else:
            widths = {len(sequence) for _, sequence in records}
            if len(widths) != 1:
                raise PrimalSchemeImportError(
                    "prealigned tiling input must have the same aligned width on every FASTA row"
                )
            msa_payload = "\n".join(f">{name}\n{sequence}" for name, sequence in records) + "\n"
            aligned_records = records
            alignment_meta = {
                "mode": "prealigned",
                "authority": "user-reviewed-alignment",
                "tool_version": None,
                "tool_role": "INPUT",
                "depth": len(records),
                "width": next(iter(widths)),
                "warnings": [],
                "sha256": _sha256_text(msa_payload),
            }
    else:
        name, sequence = records[0]
        msa_payload = f">{name}\n{sequence}\n"
        aligned_records = records
        alignment_meta = {
            "mode": "single-reference",
            "authority": "not-applicable",
            "tool_version": None,
            "tool_role": "INPUT",
            "depth": 1,
            "width": len(sequence),
            "warnings": [],
            "sha256": _sha256_text(msa_payload),
        }

    reference_name, reference_aligned = aligned_records[0]
    reference_sequence = reference_aligned.replace("-", "")
    settings_request = dict(request)
    settings_request["template"] = reference_sequence
    settings_request["name"] = str(request.get("name") or reference_name)
    # Lifecycle transport fields are not part of the generic settings contract.
    for field in (
        "tilingOperation",
        "tilingAlignmentMode",
        "existingBed",
        "schemeConfig",
        "regionBed",
        "panelMode",
        "primerName",
        "tilingBackend",
        "olivarSeed",
        "olivarDegenerateMode",
        "olivarCheckVariants",
        "tilingTargets",
    ):
        settings_request.pop(field, None)
    chosen = prepare(settings_request)
    return chosen, msa_payload, reference_sequence, alignment_meta


def _write_text(path: Path, value: str) -> Path:
    path.write_text(value.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")
    return path


def _artifact(path: Path, *, kind: str) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "kind": kind,
        "name": path.name,
        "sha256": _sha256_text(content),
        "content": content,
    }


def _inspect_interactions(
    bed: Path, *, module_id: str, workspace: Path
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        completed, tool_run = run_tool(
            "primalscheme3",
            ["interactions", "--threshold", "-26", str(bed)],
            role="PRIMARY",
            operation_id="inspect_interactions",
            engine_id="tiling-scheme",
            module_id=module_id,
            cwd=workspace,
            timeout_seconds=180,
        )
    except ToolRuntimeError as error:
        if toolchain_mode() == "strict":
            raise PrimalSchemeImportError(str(error)) from error
        return None, {
            "status": "unavailable",
            "warning": str(error),
            "threshold": -26.0,
        }
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return tool_run, {
        "status": "evidence-collected",
        "threshold": -26.0,
        "summary_lines": lines[-100:],
        "interpretation": "PrimalScheme3 interaction report; PrimerPooler remains the independent pool validator.",
    }


def _collect_visualisations(
    *,
    bed: Path,
    msa: Path,
    reference_sequence: str,
    reference_id: str,
    module_id: str,
    workspace: Path,
) -> dict[str, Any]:
    """Collect current PrimalScheme3 native visualisations as diagnostic artifacts."""
    ref = _write_text(workspace / "reference.fasta", f">{reference_id}\n{reference_sequence}\n")
    specs = [
        (
            "visualise_bedfile",
            [
                "visualise-bedfile",
                str(bed),
                str(ref),
                "--ref-id",
                reference_id,
                "--output",
                str(workspace / "bedfile.html"),
            ],
            workspace / "bedfile.html",
            "bed-layout-html",
        ),
        (
            "visualise_primer_mismatches",
            [
                "visualise-primer-mismatches",
                str(msa),
                str(bed),
                "--output",
                str(workspace / "primer-mismatches.html"),
                "--no-include-seqs",
                "--no-offline-plots",
            ],
            workspace / "primer-mismatches.html",
            "primer-mismatch-html",
        ),
    ]
    artifacts = []
    runs = []
    warnings = []
    for operation_id, args, out, kind in specs:
        try:
            _completed, run = run_tool(
                "primalscheme3",
                args,
                role="OPTIONAL",
                operation_id=operation_id,
                engine_id="tiling-scheme",
                module_id=module_id,
                cwd=workspace,
                timeout_seconds=180,
            )
            runs.append(run)
            if out.exists():
                artifacts.append(_artifact(out, kind=kind))
            else:
                warnings.append(f"{operation_id} completed without the expected artifact")
        except ToolRuntimeError as exc:
            warnings.append(str(exc))
    return {
        "status": "evidence-collected" if artifacts else "unavailable",
        "artifacts": artifacts,
        "tool_runs": runs,
        "warnings": warnings,
        "decision_impact": "diagnostic-only",
        "note": "Native visualisations expose scheme layout and primer mismatch evidence; they never alter candidate ranking or orderability.",
    }


def _normalise_result(
    *,
    request: dict[str, Any],
    chosen: Any,
    msa_payload: str,
    reference_sequence: str,
    alignment_meta: dict[str, Any],
    bed: Path,
    workspace: Path,
    operation: str,
    tool_runs: list[dict[str, Any]],
    backend_id: str = "primalscheme3",
    backend_version: str = "3.3.0",
    backend_label: str = "PrimalScheme3",
    inspect_primary_interactions: bool = True,
    backend_notes: list[str] | None = None,
) -> dict[str, Any]:
    reaction = chosen.reaction.as_conditions()
    limits = chosen.limits
    primers = _parse_bed(bed)
    if not primers:
        raise PrimalSchemeImportError(f"{backend_label} BED contained no primers")
    variant_risk = _alignment_variant_risk(msa_payload=msa_payload, primers=primers)
    pool_map = _normalise_pools(primers)
    reference_length = len(reference_sequence)
    circular = bool(request.get("circular", False))

    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for primer in primers:
        stem = str(primer["stem"])
        role = str(primer["role"])
        if role in grouped[stem]:
            raise PrimalSchemeImportError(
                f"{backend_label} amplicon {stem!r} contains multiple {role} primers; alternative-primer BED import is not yet losslessly representable"
            )
        grouped[stem][role] = primer

    tiles: list[dict[str, Any]] = []
    order_sheet: list[dict[str, Any]] = []
    for index, stem in enumerate(
        sorted(grouped, key=lambda key: min(value["start"] for value in grouped[key].values()))
    ):
        pair = grouped[stem]
        left = pair.get("LEFT")
        right = pair.get("RIGHT")
        if left is None or right is None:
            raise PrimalSchemeImportError(
                f"{backend_label} amplicon {stem!r} does not have both LEFT and RIGHT primers"
            )
        left_start, left_end = int(left["start"]), int(left["end"])
        right_start, right_end = int(right["start"]), int(right["end"])
        crosses_join = bool(circular and left_start > right_end)
        if crosses_join:
            start, end = left_start, right_end
            size = (reference_length - start) + end
        else:
            start = min(left_start, right_start)
            end = max(left_end, right_end)
            size = end - start
        pool = pool_map[int(left["pool_raw"])]
        if pool_map[int(right["pool_raw"])] != pool:
            raise PrimalSchemeImportError(
                f"{backend_label} assigned the two primers of {stem!r} to different pools"
            )
        tile = {
            "index": index,
            "name": stem,
            "pool": pool,
            "start": start,
            "end": end,
            "size": size,
            "crosses_the_join": crosses_join,
            "left": left["sequence"],
            "right": right["sequence"],
            "left_start": int(left["start"]),
            "left_end": int(left["end"]),
            "right_start": int(right["start"]),
            "right_end": int(right["end"]),
        }
        tiles.append(tile)
        for suffix, primer in (("F", left), ("R", right)):
            measured = analyse(primer["sequence"], **reaction)
            order_sheet.append(
                {
                    "name": str(primer["name"]) or f"{label(chosen.target.name)}_{index}{suffix}",
                    "sequence": primer["sequence"],
                    "annealing_sequence": primer["sequence"],
                    "tail_sequence": "",
                    "kind": "primer",
                    "length": len(primer["sequence"]),
                    "gc_percent": measured.gc_percent,
                    "tm": measured.tm,
                    "pool": pool,
                }
            )

    covered: set[int] = set()
    for tile in tiles:
        if tile.get("crosses_the_join"):
            covered.update(range(max(0, int(tile["start"])), reference_length))
            covered.update(range(0, min(reference_length, int(tile["end"]))))
        else:
            covered.update(
                range(max(0, int(tile["start"])), min(reference_length, int(tile["end"])))
            )

    requested_regions: list[tuple[int, int]] = []
    if operation == "panel-create" and request.get("regionBed"):
        requested_regions = _parse_region_bed(
            str(request["regionBed"]), reference_length=reference_length
        )

    if requested_regions:
        requested_bases: set[int] = set()
        for start, end in requested_regions:
            requested_bases.update(range(start, end))
        covered_in_scope = covered & requested_bases
        coverage_bases = len(covered_in_scope)
        coverage_of = len(requested_bases)
        coverage_scope = "requested-regions"
        gaps = _gaps_within(
            requested_regions,
            covered,
            why=f"No imported {backend_label} amplicon covers this requested panel interval.",
        )
    else:
        coverage_bases = len(covered)
        coverage_of = reference_length
        coverage_scope = "whole-reference"
        gaps = _gaps_within(
            [(0, reference_length)],
            covered,
            why=f"No imported {backend_label} amplicon covers this interval.",
        )

    pools: dict[str, list[int]] = defaultdict(list)
    for tile in tiles:
        pools[str(tile["pool"])].append(tile["index"])

    interaction_run = None
    interaction_evidence: dict[str, Any] | None = None
    if inspect_primary_interactions:
        interaction_run, interaction_evidence = _inspect_interactions(
            bed,
            module_id=str((request.get("assay") or {}).get("id") or "tiled-scheme"),
            workspace=workspace,
        )
        if interaction_run is not None:
            tool_runs.append(interaction_run)
    else:
        interaction_evidence = {
            "status": "backend-specific",
            "interpretation": f"{backend_label} interaction/risk evidence is retained in backend artifacts; independent PrimerPooler/MFEprimer/BLAST validation remains separate.",
        }

    config = _find_config(workspace)
    artifacts: dict[str, Any] = {"primer_bed": _artifact(bed, kind="primer-bed")}
    output_license: dict[str, Any] | None = None
    if backend_id == "primalscheme3":
        license_notice = (
            "PrimalScheme states that generated primer schemes are licensed under "
            "CC BY-SA 4.0. Attribution and share-alike obligations apply to the "
            "generated scheme; licensing of the input reference remains separate. "
            "Upstream: https://primalscheme.com/faqs/\n"
        )
        notice_path = _write_text(workspace / "PRIMALSCHEME-OUTPUT-LICENSE.txt", license_notice)
        artifacts["output_license_notice"] = _artifact(notice_path, kind="license-notice")
        output_license = {
            "spdx": "CC-BY-SA-4.0",
            "applies_to": "generated PrimalScheme primer scheme/output",
            "attribution_required": True,
            "share_alike": True,
            "upstream": "https://primalscheme.com/faqs/",
            "input_license_separate": True,
        }
    if config is not None:
        artifacts["config_json"] = _artifact(config, kind="primalscheme-config")

    scheme_orderable = bool(tiles) and not gaps
    orderability = {
        "orderable": scheme_orderable,
        "status": "orderable" if scheme_orderable else "not-orderable-incomplete-coverage",
        "note": (
            "The declared coverage scope has no uncovered interval."
            if scheme_orderable
            else "The imported scheme is diagnostic only because at least one interval in the declared coverage scope is uncovered (or no complete amplicon was imported). Complete the scheme before ordering."
        ),
    }

    return {
        "engine": "tiling-scheme",
        "provenance": provenance(reaction),
        "assay": chosen.assay_to_dict(),
        "target": target_to_dict(chosen.target),
        "reaction": {
            "polymerase": chosen.preset.id,
            "polymerase_name": chosen.preset.name,
            **reaction,
            "model": thermodynamic_model(chosen.preset, chosen.reaction),
        },
        "constraints": {
            field: getattr(limits, field) for field in Constraints.__dataclass_fields__
        },
        "reference_id": chosen.target.name or "unnamed-reference",
        "coordinate_system": "0-based, half-open; circular origin-spanning tiles use start>end with crosses_the_join=true",
        "scheme_format": "pcrstudio-tiling-v2",
        "lifecycle": {
            "operation": operation,
            "circular": circular,
            "alignment": alignment_meta,
            "tool_runs": tool_runs,
            "interaction_evidence": interaction_evidence,
            "input_artifacts": {
                key: {
                    "sha256": _sha256_text(str(request[key])),
                    "characters": len(str(request[key])),
                }
                for key in ("existingBed", "schemeConfig", "regionBed")
                if request.get(key)
            },
        },
        "scheme_artifacts": artifacts,
        "output_license": output_license,
        "tiles": tiles,
        "pools": dict(sorted(pools.items(), key=lambda item: int(item[0]))),
        "gaps": gaps,
        "variant_risk": variant_risk,
        "coverage": {
            "bases": coverage_bases,
            "of": coverage_of,
            "percent": round(100.0 * coverage_bases / max(coverage_of, 1), 1),
            "scope": coverage_scope,
            "reference_bases": reference_length,
            "reference_covered_bases": len(covered),
            "requested_regions": [
                {"start": start, "end": end, "bases": end - start}
                for start, end in requested_regions
            ],
        },
        "interactions": [],
        "how_it_was_laid_out": [
            f"{backend_label} {backend_version} executed `{operation}` and PCRStudio imported the resulting BED under the shared zero-based half-open contract.",
            "MAFFT is the alignment authority for multi-sequence auto mode unless the selected backend explicitly records a different alignment step; reviewed pre-aligned input is preserved only when explicitly selected.",
            "PCRStudio maps every imported primer back onto the exact design MSA and reports exact, ambiguity-compatible, definite-mismatch/gap and terminal-5-nt conservation evidence without converting it into a universal dropout threshold.",
            f"{backend_label} backend evidence and independent PrimerPooler/MFEprimer/BLAST evidence are recorded separately rather than merged into one opaque score.",
            *(backend_notes or []),
        ],
        "note": f"Pool assignment is imported from {backend_label} and independently audited when the configured validators are available.",
        "why_nothing": (
            ""
            if scheme_orderable
            else (
                f"{backend_label} returned no complete amplicons."
                if not tiles
                else f"The scheme leaves {len(gaps)} uncovered interval(s) inside the declared coverage scope; partial coverage is diagnostic and not releasable for ordering."
            )
        ),
        "orderability": orderability,
        "order_sheet": order_sheet if scheme_orderable else [],
        "primary_backend": {
            "id": backend_id,
            "configured_version": backend_version,
            "operation": operation,
            "bed_file": bed.name,
            "tool_runs": tool_runs,
        },
    }


def run(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("tails") not in (None, {}, ""):
        raise PrimalSchemeImportError(
            "Generation-1 tiled-scheme has no 5-prime-tail input. Tail-aware PrimalScheme3 "
            "pool assignment/revalidation is not qualified; remove the historical field and regenerate."
        )
    if request.get("excluded"):
        raise PrimalSchemeImportError(
            "The PrimalScheme3 3.3.0 PRIMARY adapter has no qualified excluded-region "
            "input. PCRStudio will not silently ignore `excluded` or mask the MSA and "
            "pretend that is equivalent. Remove the excluded-region request or use a "
            "future explicitly validated masking branch."
        )
    if not available():
        raise PrimalSchemeImportError(
            "PrimalScheme3 3.3.0 is unavailable; provision the pinned project-local Linux scientific tool before using the canonical tiled-scheme backend"
        )
    assay = request.get("assay") or {}
    assay_id = str(assay.get("id") or "") if isinstance(assay, dict) else ""
    raw_operation = request.get("tilingOperation")
    if assay_id == "tiled-scheme" and raw_operation in (None, ""):
        raise PrimalSchemeImportError(
            "tiled-scheme requires explicit `tilingOperation`; lifecycle identity is not inferred from omission."
        )
    operation = str(raw_operation or "scheme-create")
    if operation not in _LIFECYCLE:
        raise PrimalSchemeImportError(
            f"unknown tiling lifecycle operation {operation!r}; use {', '.join(sorted(_LIFECYCLE))}"
        )
    circular = bool(request.get("circular"))
    if circular and operation != "scheme-create":
        raise PrimalSchemeImportError(
            "circular=true is executable only for PrimalScheme3 scheme-create; panel/repair/replace do not expose an equivalent upstream circular switch and remain fail-closed"
        )

    if assay_id == "tiled-scheme" and request.get("tilingAlignmentMode") in (None, ""):
        raise PrimalSchemeImportError(
            "tiled-scheme requires explicit `tilingAlignmentMode`: auto or prealigned; alignment authority is scientific input."
        )
    if operation != "panel-create" and (
        request.get("regionBed") is not None or request.get("panelMode") is not None
    ):
        raise PrimalSchemeImportError("regionBed/panelMode are only valid for panel-create.")
    if operation == "panel-create" and request.get("panelMode") in (None, ""):
        raise PrimalSchemeImportError(
            "panel-create requires explicit `panelMode`: region-only, entropy or equal."
        )
    if (
        operation not in {"repair-mode", "scheme-replace"}
        and request.get("schemeConfig") is not None
    ):
        raise PrimalSchemeImportError(
            "schemeConfig is only valid for repair-mode or scheme-replace."
        )
    if operation == "scheme-create" and request.get("existingBed") is not None:
        raise PrimalSchemeImportError(
            "existingBed is not a scheme-create input in PCRStudio Gen-1; hidden stale state is refused rather than changing the operation."
        )
    if operation != "scheme-replace" and request.get("primerName") is not None:
        raise PrimalSchemeImportError("primerName is only valid for scheme-replace.")

    chosen, msa_payload, reference_sequence, alignment_meta = _prepare_input(request)
    limits = chosen.limits
    if request.get("slide") is not None:
        raise PrimalSchemeImportError(
            "`slide` belongs to the internal development tiler and is not a PrimalScheme3 3.3.0 input; the canonical backend never ignores it in any policy mode."
        )
    if operation == "scheme-create":
        if request.get("overlap") is None or request.get("pools") is None:
            raise PrimalSchemeImportError(
                "scheme-create requires explicit `overlap` and `pools`; PCRStudio does not apply hidden tiling-geometry defaults."
            )
        overlap = int(request["overlap"])
        pools_requested = int(request["pools"])
    elif operation == "panel-create":
        if request.get("overlap") is not None:
            raise PrimalSchemeImportError(
                "PrimalScheme3 panel-create has no min-overlap option; `overlap` would be a dead input and is refused."
            )
        if request.get("pools") is None:
            raise PrimalSchemeImportError("panel-create requires explicit `pools`.")
        overlap = None
        pools_requested = int(request["pools"])
    else:
        if request.get("overlap") is not None or request.get("pools") is not None:
            raise PrimalSchemeImportError(
                f"{operation} inherits lifecycle geometry from the reviewed BED/config; `overlap`/`pools` are not executable inputs for this operation."
            )
        overlap = None
        pools_requested = None
    if pools_requested is not None and pools_requested < 1:
        raise PrimalSchemeImportError(
            "PrimalScheme3 requires `--n-pools` to be at least 1; PCRStudio does not impose an additional biological upper bound."
        )
    target_amplicon = max(
        100,
        min(2000, round((limits.product_min + limits.product_max) / 2)),
    )
    min_base_frequency = float(request.get("tilingMinBaseFrequency") or 0.0)
    if not 0.0 <= min_base_frequency <= 1.0:
        raise PrimalSchemeImportError("tilingMinBaseFrequency must be between 0 and 1")
    backtrack = bool(request.get("tilingBacktrack", False))
    high_gc = bool(request.get("tilingHighGc", False))

    with tempfile.TemporaryDirectory(prefix="pcrstudio-primalscheme-") as workspace_name:
        workspace = Path(workspace_name)
        source = _write_text(workspace / "input.msa.fasta", msa_payload)
        output = workspace / "scheme"
        module_id = str((request.get("assay") or {}).get("id") or "tiled-scheme")
        tool_runs: list[dict[str, Any]] = []

        existing_bed: Path | None = None
        if request.get("existingBed"):
            existing_bed = _write_text(workspace / "input.primer.bed", str(request["existingBed"]))
            # Fail early on malformed imports before handing them to upstream.
            _parse_bed(existing_bed)
        config: Path | None = None
        if request.get("schemeConfig"):
            try:
                parsed_config = json.loads(str(request["schemeConfig"]))
            except json.JSONDecodeError as error:
                raise PrimalSchemeImportError(f"schemeConfig is not valid JSON: {error}") from error
            if not isinstance(parsed_config, dict):
                raise PrimalSchemeImportError("schemeConfig must be a JSON object")
            config = _write_text(
                workspace / "config.json",
                json.dumps(parsed_config, indent=2, sort_keys=True) + "\n",
            )
        region_bed: Path | None = None
        if request.get("regionBed"):
            region_bed = _write_text(workspace / "regions.bed", str(request["regionBed"]))

        args: list[str]
        operation_id: str
        if operation == "scheme-create":
            args = [
                "scheme-create",
                "--msa",
                str(source),
                "--output",
                str(output),
                "--amplicon-size",
                str(target_amplicon),
                "--min-overlap",
                str(overlap),
                "--n-pools",
                str(pools_requested),
                "--mapping",
                "first",
                "--force",
                "--no-use-matchdb",
                "--online-plots",
                "--min-base-freq",
                f"{min_base_frequency:g}",
                "--backtrack" if backtrack else "--no-backtrack",
                "--high-gc" if high_gc else "--no-high-gc",
                "--circular" if circular else "--no-circular",
            ]
            if existing_bed is not None:
                args.extend(["--input-bedfile", str(existing_bed)])
            operation_id = "scheme_create"
        elif operation == "panel-create":
            panel_mode = str(request.get("panelMode") or "region-only")
            if panel_mode not in {"region-only", "entropy", "equal"}:
                raise PrimalSchemeImportError("panelMode must be region-only, entropy or equal")
            args = [
                "panel-create",
                "--msa",
                str(source),
                "--output",
                str(output),
                "--mode",
                panel_mode,
                "--amplicon-size",
                str(target_amplicon),
                "--n-pools",
                str(pools_requested),
                "--mapping",
                "first",
                "--force",
                "--no-use-matchdb",
                "--online-plots",
                "--min-base-freq",
                f"{min_base_frequency:g}",
                "--high-gc" if high_gc else "--no-high-gc",
            ]
            if region_bed is not None:
                args.extend(["--region-bedfile", str(region_bed)])
            if existing_bed is not None:
                args.extend(["--input-bedfile", str(existing_bed)])
            operation_id = "panel_create"
        elif operation == "repair-mode":
            if existing_bed is None or config is None:
                raise PrimalSchemeImportError(
                    "repair-mode requires existingBed and schemeConfig from the scheme being repaired"
                )
            args = [
                "repair-mode",
                "--bedfile",
                str(existing_bed),
                "--msa",
                str(source),
                "--config",
                str(config),
                "--output",
                str(output),
                "--force",
            ]
            operation_id = "repair_mode"
        else:
            if existing_bed is None or config is None:
                raise PrimalSchemeImportError(
                    "scheme-replace requires existingBed and schemeConfig from the original scheme"
                )
            primer_name = str(request.get("primerName") or "").strip()
            if not primer_name:
                raise PrimalSchemeImportError("scheme-replace requires primerName")
            args = [
                "scheme-replace",
                primer_name,
                str(existing_bed),
                str(source),
                "--amplicon-size",
                str(target_amplicon),
                "--config",
                str(config),
            ]
            operation_id = "scheme_replace"

        try:
            _completed, tool_run = run_tool(
                "primalscheme3",
                args,
                role="PRIMARY",
                operation_id=operation_id,
                engine_id="tiling-scheme",
                module_id=module_id,
                cwd=workspace,
                timeout_seconds=300,
            )
        except ToolRuntimeError as error:
            raise PrimalSchemeImportError(str(error)) from error
        tool_runs.append(tool_run)

        if operation == "scheme-replace":
            # Upstream has no output argument. Prefer a newly-created BED when
            # present, otherwise consume the input BED that the command is
            # documented to update.  No path escapes the request workspace.
            other_beds = [path for path in sorted(workspace.rglob("*.bed")) if path != existing_bed]
            bed = other_beds[0] if len(other_beds) == 1 else existing_bed
            if bed is None:
                raise PrimalSchemeImportError("scheme-replace produced no importable BED")
            if len(other_beds) > 1:
                raise PrimalSchemeImportError(
                    "scheme-replace produced multiple BED files; PCRStudio will not choose one by filesystem order"
                )
        else:
            bed = _find_bed(workspace, exclude=existing_bed if operation == "repair-mode" else None)

        result = _normalise_result(
            request=request,
            chosen=chosen,
            msa_payload=msa_payload,
            reference_sequence=reference_sequence,
            alignment_meta=alignment_meta,
            bed=bed,
            workspace=workspace,
            operation=operation,
            tool_runs=tool_runs,
        )
        if isinstance(result.get("lifecycle"), dict):
            visual = _collect_visualisations(
                bed=bed,
                msa=source,
                reference_sequence=reference_sequence,
                reference_id=str(
                    getattr(getattr(chosen, "target", None), "name", None) or "reference"
                ),
                module_id=module_id,
                workspace=workspace,
            )
            result["native_visualisations"] = visual
            if visual.get("tool_runs"):
                result["lifecycle"].setdefault("tool_runs", []).extend(visual["tool_runs"])
        else:
            # A replacement normalizer used by an integration test or adapter
            # can return a reduced record; do not run visualisation tools until
            # the canonical lifecycle envelope exists.
            result["native_visualisations"] = {"status": "not-collected", "tool_runs": []}
        return result
