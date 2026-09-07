"""Olivar 1.3.3 adapter for variant-aware tiled amplicon design.

Olivar is an independent PRIMARY backend, not a scoring supplement to
PrimalScheme3. PCRStudio invokes only an explicitly provisioned executable or
wrapper fingerprinted as the ``olivar`` tool. It never guesses a Conda
environment or invokes an emulation/compatibility shell.

The adapter normalises Olivar's BED export into PCRStudio's canonical
0-based, half-open coordinate contract. Olivar's internal coordinates are
1-based closed; only the BED export is consumed for ordered primer geometry.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .primalscheme_adapter import (
    PrimalSchemeImportError,
    _find_bed,
    _normalise_result,
    _prepare_input,
    _write_text,
)
from .tool_runtime import ToolRuntimeError, resolve, run_tool


class OlivarImportError(PrimalSchemeImportError):
    """Olivar input/output could not be represented without guessing."""


def available() -> bool:
    return resolve("olivar").available


def _authority_inputs(request: dict[str, Any]) -> tuple[int, bool, bool]:
    seed = int(request.get("olivarSeed") if request.get("olivarSeed") is not None else 10)
    if seed < 0 or seed > 2_147_483_647:
        raise OlivarImportError("olivarSeed must be an integer between 0 and 2147483647")
    degenerate = bool(request.get("olivarDegenerateMode", False))
    check_variants = bool(request.get("olivarCheckVariants", True))
    return seed, degenerate, check_variants


def _find_olvr(workspace: Path) -> Path:
    files = sorted(workspace.rglob("*.olvr"))
    if len(files) != 1:
        raise OlivarImportError(
            f"Olivar build must produce exactly one .olvr model for a single-target request; found {len(files)}"
        )
    return files[0]


def run(request: dict[str, Any]) -> dict[str, Any]:
    if not available():
        raise OlivarImportError(
            "Olivar 1.3.3 is unavailable. Provision the pinned external-managed executable/wrapper and its SHA-256 fingerprint; PCRStudio does not guess a Conda environment or executable path."
        )
    operation = str(request.get("tilingOperation") or "")
    if operation != "scheme-create":
        raise OlivarImportError(
            "PCRStudio's Olivar 1.3.3 backend currently executes scheme-create only; repair/replace lifecycle belongs to PrimalScheme3/ARTIC until a lossless Olivar lifecycle contract is qualified."
        )
    if bool(request.get("circular")):
        raise OlivarImportError(
            "Olivar circular-target BED normalisation is not yet qualified; circular tiling remains fail-closed."
        )
    if request.get("existingBed") or request.get("schemeConfig") or request.get("regionBed") or request.get("primerName"):
        raise OlivarImportError(
            "Olivar scheme-create does not accept PrimalScheme lifecycle BED/config/region replacement inputs."
        )
    if request.get("tilingTargets") not in (None, [], ""):
        raise OlivarImportError(
            "multi-target Olivar normalisation is not yet lossless in PCRStudio's single-reference result contract; use one target per request until the multi-chrom result schema is selected."
        )

    chosen, msa_payload, reference_sequence, alignment_meta = _prepare_input(request)
    limits = chosen.limits
    seed, degenerate, check_variants = _authority_inputs(request)
    min_base_frequency = float(request.get("tilingMinBaseFrequency") or 0.01)
    if not 0.0 <= min_base_frequency <= 1.0:
        raise OlivarImportError("tilingMinBaseFrequency must be between 0 and 1")

    with tempfile.TemporaryDirectory(prefix="pcrstudio-olivar-") as workspace_name:
        workspace = Path(workspace_name)
        source = _write_text(workspace / "input.msa.fasta", msa_payload)
        build_output = workspace / "olivar-build"
        scheme_output = workspace / "olivar-scheme"
        module_id = str((request.get("assay") or {}).get("id") or "tiled-scheme")
        tool_runs: list[dict[str, Any]] = []

        build_args = [
            "build",
            "-m",
            source.name,
            "-o",
            build_output.name,
            "--min-var",
            f"{min_base_frequency:g}",
            "-p",
            "1",
        ]
        if degenerate:
            build_args.append("--deg")
        try:
            _completed, build_run = run_tool(
                "olivar",
                build_args,
                role="PRIMARY",
                operation_id="build_reference",
                engine_id="tiling-scheme",
                module_id=module_id,
                cwd=workspace,
                timeout_seconds=600,
            )
        except ToolRuntimeError as error:
            raise OlivarImportError(str(error)) from error
        tool_runs.append(build_run)
        model = _find_olvr(workspace)

        tiling_args = [
            "tiling",
            str(model.relative_to(workspace)),
            "-o",
            scheme_output.name,
            "--max-amp-len",
            str(int(limits.product_max)),
            "--min-amp-len",
            str(int(limits.product_min)),
            "--seed",
            str(seed),
            "-p",
            "1",
        ]
        if check_variants:
            tiling_args.append("--check-var")
        if degenerate:
            tiling_args.append("--deg")
        try:
            _completed, tiling_run = run_tool(
                "olivar",
                tiling_args,
                role="PRIMARY",
                operation_id="scheme_create",
                engine_id="tiling-scheme",
                module_id=module_id,
                cwd=workspace,
                timeout_seconds=900,
            )
        except ToolRuntimeError as error:
            raise OlivarImportError(str(error)) from error
        tool_runs.append(tiling_run)
        bed = _find_bed(workspace)

        result = _normalise_result(
            request=request,
            chosen=chosen,
            msa_payload=msa_payload,
            reference_sequence=reference_sequence,
            alignment_meta=alignment_meta,
            bed=bed,
            workspace=workspace,
            operation="scheme-create",
            tool_runs=tool_runs,
            backend_id="olivar",
            backend_version="1.3.3",
            backend_label="Olivar",
            inspect_primary_interactions=False,
            backend_notes=[
                "Olivar internal 1-based closed coordinates are never imported directly; PCRStudio consumes only the BED export under the shared 0-based half-open contract.",
                "Olivar risk/SADDLE optimisation is backend-specific evidence and is not averaged with PrimalScheme3 or PrimerPooler scores.",
            ],
        )
        result["olivar"] = {
            "seed": seed,
            "degenerate_mode": degenerate,
            "check_variants": check_variants,
            "minimum_variant_frequency": min_base_frequency,
            "execution_scope": "external-managed-explicit-wrapper",
            "coordinate_boundary": "Olivar internal 1-based closed; imported BED 0-based half-open",
        }
        return result
