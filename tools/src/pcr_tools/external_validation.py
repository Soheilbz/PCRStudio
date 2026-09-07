"""Independent generation-1 validation adapters.

The design engines keep their assay-specific search logic.  This module adds a
single, versioned validation boundary around the oligos they selected.  It does
*not* silently turn a database hit into an off-target rejection: without a
known target accession/taxonomy that inference is unsafe.  Instead it records
machine-readable evidence, and marks claims that still need target-aware
interpretation as incomplete.

All subprocesses are shell-free native Linux process calls through
:mod:`tool_runtime`; executable/database identities remain explicit and fingerprinted.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import tempfile
from bisect import bisect_left, bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .pydna_validation import validate as validate_with_pydna
from .runtime_contract import ENGINE_BINDINGS
from .scientific_integrity import strict as scientific_strict
from .tool_runtime import (
    ToolRuntimeError,
    configured_database_contract,
    run_tool,
    tool_status,
)

VALIDATION_CONTRACT_VERSION = "1.2.0"
_MODES = {"off", "auto", "strict"}
_DNA = re.compile(r"^[ACGTRYSWKMBDHVN]+$", re.IGNORECASE)


def _project_temp_root() -> Path | None:
    """Return PCRStudio's repository-local scratch root when discoverable.

    Validator adapters create query/output workspaces themselves, so these are
    project scratch files rather than opaque compiler/toolchain temporaries.
    Keep them under `.local/tmp` when running from a source checkout; installed
    deployments without repository markers retain the platform temporary-dir
    fallback.
    """
    try:
        current = Path.cwd().resolve()
    except OSError:
        return None
    for directory in (current, *current.parents):
        if (directory / "Cargo.toml").is_file() and (directory / "tools" / "pyproject.toml").is_file():
            root = directory / ".local" / "tmp"
            root.mkdir(parents=True, exist_ok=True)
            return root
    return None


def _mode() -> str:
    """Resolve validator mode without allowing strict science to be downgraded."""
    if scientific_strict():
        return "strict"
    value = os.environ.get("PCRSTUDIO_EXTERNAL_VALIDATION", "strict").strip().lower()
    return value if value in _MODES else "strict"


def _clean_sequence(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    sequence = "".join(value.split()).upper().replace("U", "T")
    if not sequence or not _DNA.fullmatch(sequence):
        return None
    return sequence


def selected_oligos(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return ordered molecules plus the template-annealing sequence.

    ``sequence`` in an order sheet is supplier-ready and may contain a 5' tail.
    Specificity searches must use only the segment that can bind the original
    template in the first amplification round, while interaction/structure
    checks must use the complete ordered molecule.  Engines that add tails or
    composite segments therefore emit ``annealing_sequence`` explicitly.

    Every Generation-1 result must declare ``annealing_sequence`` explicitly.
    A missing field is a contract error, not a backwards-compatibility cue: a
    composite/tail-bearing ordered molecule searched in full can create a
    scientifically different specificity question.
    """
    raw = result.get("order_sheet") or []
    if not isinstance(raw, list):
        return []
    answer: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(raw, start=1):
        if isinstance(entry, str) or not isinstance(entry, dict):
            continue
        ordered = _clean_sequence(entry.get("sequence"))
        if not ordered:
            continue
        raw_annealing = entry.get("annealing_sequence")
        annealing = _clean_sequence(raw_annealing)
        if not annealing:
            raise ValueError(
                f"order_sheet entry {entry.get('name') or index!r} lacks an explicit valid annealing_sequence; specificity will not guess it from the ordered oligo"
            )
        if not ordered.endswith(annealing) and entry.get("tail_sequence"):
            # 5' extensions are the only supported non-template additions in
            # this boundary. Refuse an inconsistent explicit contract rather
            # than silently searching the wrong molecule.
            raise ValueError(
                f"order_sheet entry {entry.get('name') or index!r} declares an annealing sequence "
                "that is not the 3' suffix of the ordered oligo"
            )
        tail = _clean_sequence(entry.get("tail_sequence")) if entry.get("tail_sequence") else ""
        if tail and ordered != tail + annealing:
            raise ValueError(
                f"order_sheet entry {entry.get('name') or index!r} has inconsistent tail/annealing fields"
            )
        name = str(entry.get("name") or f"oligo_{index}").strip() or f"oligo_{index}"
        kind = str(entry.get("kind") or "primer").strip().lower() or "primer"
        key = (name, ordered, annealing)
        if key in seen:
            continue
        seen.add(key)
        selected = {
            "name": name,
            "kind": kind,
            "ordered_sequence": ordered,
            "annealing_sequence": annealing,
            "tail_sequence": tail,
            "pool": entry.get("pool"),
            "tube": entry.get("tube"),
            "note": entry.get("note"),
        }
        # LAMP-specific decomposition belongs only on LAMP order-sheet rows.
        # Adding empty LAMP keys to every Generation-1 oligo changes the shared
        # validator boundary for unrelated engines and produces noisy persisted
        # diffs without carrying any scientific information.
        if any(
            key in entry
            for key in (
                "lamp_role",
                "lamp_set_index",
                "lamp_target_tail_sequence",
                "lamp_linker_sequence",
            )
        ):
            selected.update(
                {
                    "lamp_role": entry.get("lamp_role"),
                    "lamp_set_index": entry.get("lamp_set_index"),
                    "lamp_target_tail_sequence": _clean_sequence(
                        entry.get("lamp_target_tail_sequence")
                    )
                    or "",
                    "lamp_linker_sequence": _clean_sequence(
                        entry.get("lamp_linker_sequence")
                    )
                    or "",
                }
            )
        answer.append(selected)
    return answer


def _sequence_for(oligo: dict[str, Any], molecule: str) -> str:
    if molecule == "ordered":
        return str(oligo["ordered_sequence"])
    if molecule == "annealing":
        return str(oligo["annealing_sequence"])
    raise ValueError(f"unknown oligo molecule selector: {molecule}")

def _safe_id(name: str, index: int) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_.-")
    return token[:80] or f"oligo_{index}"


def _write_fasta(
    path: Path,
    oligos: list[dict[str, Any]],
    *,
    molecule: str,
    kinds: set[str] | None = None,
) -> dict[str, str]:
    identifiers: dict[str, str] = {}
    # Callers commonly hand this helper a path inside a per-operation workspace
    # that has not yet been materialised.  Creating only that leaf's parents is
    # safe and keeps the process-boundary input deterministic.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        written = 0
        for source_index, oligo in enumerate(oligos, start=1):
            if kinds is not None and str(oligo.get("kind")) not in kinds:
                continue
            written += 1
            base = _safe_id(str(oligo["name"]), source_index)
            identifier = base
            suffix = 2
            while identifier in identifiers:
                identifier = f"{base}_{suffix}"
                suffix += 1
            identifiers[identifier] = str(oligo["name"])
            handle.write(f">{identifier}\n{_sequence_for(oligo, molecule)}\n")
    return identifiers

def _reaction(result: dict[str, Any]) -> dict[str, float]:
    raw = result.get("reaction") or {}
    if not isinstance(raw, dict):
        raw = {}
    answer: dict[str, float] = {}
    for key in ("mv_conc", "dv_conc", "dntp_conc", "dna_conc"):
        try:
            answer[key] = float(raw.get(key, 0.0))
        except (TypeError, ValueError):
            answer[key] = 0.0
    return answer




def _declared_operations(engine_id: str, tool_id: str) -> tuple[str, ...]:
    """Return canonical operation ids declared for one engine/tool binding."""
    for binding in ENGINE_BINDINGS.get(engine_id, ()):
        if str(binding.get("tool_id")) == tool_id:
            return tuple(str(value) for value in binding.get("operations", ()))
    return ()


def _one_declared_operation(
    engine_id: str,
    tool_id: str,
    *,
    exclude: set[str] | None = None,
) -> str:
    """Resolve one semantic operation and fail closed on an ambiguous contract."""
    excluded = exclude or set()
    operations = [op for op in _declared_operations(engine_id, tool_id) if op not in excluded]
    if len(operations) != 1:
        raise ValueError(
            f"{engine_id}/{tool_id} must declare exactly one applicable operation; got {operations}"
        )
    return operations[0]

def _public_database_contract(database: dict[str, Any], *, database_hash: str | None) -> dict[str, Any]:
    """Path-free database provenance safe to persist in a design result.

    Full filesystem paths and raw manifests are deployment diagnostics. The raw
    manifest can contain the operator's source-FASTA path, so returning it in a
    client-visible result leaks host layout without improving reproducibility.
    Stable ids/releases/hashes and contract verdicts carry the scientific
    provenance needed by the design record.
    """
    return {
        "database_hash": database_hash,
        "database_scope": database.get("scope"),
        "database_claim_capability": database.get("claim_capability"),
        "database_manifest_sha256": database.get("manifest_sha256"),
        "database_id": database.get("database_id"),
        "sequence_release": database.get("sequence_release"),
        "taxonomy_release": database.get("taxonomy_release"),
        "filtering": database.get("filtering"),
        "deduplication": database.get("deduplication"),
        "mfeprimer_index_k": database.get("mfeprimer_index_k"),
        "mfeprimer_query_k_policy": database.get("mfeprimer_query_k_policy"),
        "manifest_contract_consistent": database.get("manifest_contract_consistent"),
        "content_hash_matches": database.get("content_hash_matches"),
        "index_artifacts_declared": database.get("index_artifacts_declared"),
        "index_artifacts_match": database.get("index_artifacts_match"),
    }


def _base_evidence(tool_id: str, *, status: str, purpose: str) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "configured_version": tool_status(tool_id)["configured_version"],
        "status": status,
        "purpose": purpose,
        "decision_impact": "advisory-unless-target-aware",
        "interpretation_contract": "target-aware-evidence-v1",
        # Tool execution/evidence collection is not the same claim as a
        # target-aware pass/fail interpretation. Adapters must opt in only
        # when they can distinguish intended from unintended evidence under a
        # reproducible identity contract.
        "interpretation_complete": False,
        "evidence": {},
        "tool_run": None,
        "warnings": [],
    }


def _mfeprimer_oligo_qc(
    oligos: list[dict[str, Any]],
    *,
    workspace: Path,
    engine_id: str,
    module_id: str,
    reaction: dict[str, float],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Independent dimer/hairpin runs on physically co-reacting ordered molecules.

    Specificity and intramolecular/intermolecular structure intentionally use
    different molecule views.  A non-template 5' tail must not be searched
    against the original genome, but it absolutely can form a dimer or hairpin
    in the tube and therefore belongs in these two checks.

    LAMP result rows are alternative complete primer sets, not one combined
    reaction.  When ``lamp_set_index`` is present, each set is therefore checked
    independently so MFEprimer cannot report cross-set dimers between oligos
    that would never be mixed experimentally.
    """
    groups: list[tuple[str, int | None, list[dict[str, Any]]]]
    if engine_id == "loop-set":
        by_set: dict[int, list[dict[str, Any]]] = {}
        unassigned: list[dict[str, Any]] = []
        for oligo in oligos:
            set_index = int(oligo.get("lamp_set_index") or 0)
            if set_index > 0:
                by_set.setdefault(set_index, []).append(oligo)
            else:
                unassigned.append(oligo)
        if by_set:
            groups = [
                (f"lamp-set-{set_index}", set_index, by_set[set_index])
                for set_index in sorted(by_set)
            ]
            # Fail-honest fallback for malformed/mixed historical payloads.
            # These rows are kept isolated from every indexed LAMP set rather
            # than being allowed to create cross-set dimer evidence.
            if unassigned:
                groups.append(("lamp-unassigned", None, unassigned))
        else:
            groups = [("all-oligos", None, oligos)]
    else:
        groups = [("all-oligos", None, oligos)]

    common = [
        "--mono", str(reaction["mv_conc"]),
        "--diva", str(reaction["dv_conc"]),
        "--dntp", str(reaction["dntp_conc"]),
        "--oligo", str(reaction["dna_conc"]),
        "-j",
    ]
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    declared = set(_declared_operations(engine_id, "mfeprimer"))
    for group_name, lamp_set_index, group_oligos in groups:
        fasta = workspace / f"ordered-oligos-{group_name}.fa"
        identifiers = _write_fasta(fasta, group_oligos, molecule="ordered")
        if not identifiers:
            continue
        for operation, command in (("dimer", "dimer"), ("hairpin", "hairpin")):
            operation_id = f"validate_{operation}"
            if operation_id not in declared:
                continue
            output = workspace / f"mfeprimer-{operation}-{group_name}"
            try:
                completed, run = run_tool(
                    "mfeprimer",
                    [command, "-i", str(fasta), "-o", str(output), *common],
                    role="VALIDATOR",
                    operation_id=operation_id,
                    engine_id=engine_id,
                    module_id=module_id,
                    cwd=workspace,
                    timeout_seconds=180,
                )
            except ToolRuntimeError as error:
                warnings.append(
                    f"MFEprimer {operation} check failed for {group_name}: {error}"
                )
                continue
            record: dict[str, Any] = {
                "operation": operation,
                "molecule": "ordered_sequence",
                "physical_group": group_name,
                "query_count": len(identifiers),
                "tool_run": run,
                "stdout_excerpt": [
                    line.strip()
                    for line in completed.stdout.splitlines()
                    if line.strip()
                ][-12:],
            }
            if lamp_set_index is not None:
                record["lamp_set_index"] = lamp_set_index
            records.append(record)
    return records, warnings

def _mfeprimer(
    oligos: list[dict[str, Any]],
    *,
    engine_id: str,
    module_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    evidence = _base_evidence(
        "mfeprimer",
        status="unchecked",
        purpose="independent binding/product and oligo-structure validation",
    )
    status = tool_status("mfeprimer")
    if not status["available"]:
        evidence["warnings"].append(
            "MFEprimer 4.5.1 is not configured as a native executable on this host."
        )
        return evidence

    database = configured_database_contract("PCRSTUDIO_MFEPRIMER_DATABASES")
    databases = list(database["paths"])
    database_hash = database["sha256"]
    if not databases:
        evidence["warnings"].append(
            "No versioned MFEprimer database is configured; database specificity was not claimed."
        )
        return evidence
    if not database_hash:
        evidence["warnings"].append(
            "PCRSTUDIO_MFEPRIMER_DATABASES_SHA256 is missing; the database is not reproducibly identified."
        )
        if _mode() == "strict":
            return evidence
    if database["scope"] not in {"production", "approved-reference"}:
        evidence["warnings"].append(
            f"MFEprimer database scope is {database['scope']!r}; evidence is suitable for smoke/development checks, not a production specificity claim."
        )
    if database.get("manifest_error"):
        evidence["warnings"].append(f"MFEprimer database manifest could not be parsed: {database['manifest_error']}")
    if database.get("manifest") and not database.get("manifest_contract_consistent"):
        evidence["warnings"].append("MFEprimer database manifest scope/hash does not match the configured database contract.")
        if _mode() == "strict":
            return evidence
    if database.get("content_hash_matches") is False:
        evidence["warnings"].append("MFEprimer configured FASTA content does not match its declared SHA-256.")
        if _mode() == "strict":
            return evidence
    if database.get("index_artifacts_match") is not True:
        evidence["warnings"].append(
            "MFEprimer database index artifacts are missing or do not match the manifest SHA-256 fingerprints; production specificity cannot be claimed."
        )
        if _mode() == "strict":
            return evidence

    mfe_index_k = database.get("mfeprimer_index_k")
    if mfe_index_k is None:
        evidence["warnings"].append(
            "MFEprimer index k is not recorded in the database manifest. Query -k remains omitted so v4.5.1 can auto-detect it from the index header, but the release record cannot report which seed length was chosen during indexing."
        )
    evidence["evidence"]["index_seed_contract"] = {
        "index_k": mfe_index_k,
        "query_k": "omitted-auto-detect-from-index-header",
        "query_policy": database.get("mfeprimer_query_k_policy")
        or "MFEprimer 4.5.1 query -k omitted; runtime reads k from each index header and errors on an explicit mismatch.",
        "decision_impact": "specificity-search-index-provenance",
    }

    reaction = _reaction(result)
    with tempfile.TemporaryDirectory(prefix="pcrstudio-mfe-", dir=str(_project_temp_root()) if _project_temp_root() else None) as workspace_name:
        workspace = Path(workspace_name)
        fasta = workspace / "oligos.fa"
        prefix = workspace / "mfeprimer-result"
        identifiers = _write_fasta(fasta, oligos, molecule="annealing", kinds={"primer"})
        if not identifiers:
            evidence["status"] = "not-applicable"
            evidence["evidence"] = {"reason": "no amplification-primer annealing sequences"}
            return evidence
        args: list[str] = ["spec", "-i", str(fasta.resolve())]
        for database_path in databases:
            args.extend(["-d", str(Path(database_path).resolve())])
        args.extend(["-o", str(prefix.resolve()), "-j", "--bind-amp-only", "-b"])
        # MFEprimer uses concentrations in mM/nM as documented by the tool.
        args.extend(["--mono", str(reaction["mv_conc"])])
        args.extend(["--diva", str(reaction["dv_conc"])])
        args.extend(["--dntp", str(reaction["dntp_conc"])])
        args.extend(["--oligo", str(reaction["dna_conc"])])

        constraints = result.get("constraints") or {}
        if isinstance(constraints, dict):
            flat = constraints.get("primers") if isinstance(constraints.get("primers"), dict) else constraints
            if isinstance(flat, dict):
                if isinstance(flat.get("product_min"), (int, float)):
                    args.extend(["--minSize", str(int(flat["product_min"]))])
                if isinstance(flat.get("product_max"), (int, float)):
                    args.extend(["--maxSize", str(int(flat["product_max"]))])

        try:
            completed, run = run_tool(
                "mfeprimer",
                args,
                role="VALIDATOR",
                operation_id=_one_declared_operation(
                    engine_id,
                    "mfeprimer",
                    exclude={"validate_dimer", "validate_hairpin"},
                ),
                engine_id=engine_id,
                module_id=module_id,
                timeout_seconds=180,
            )
        except ToolRuntimeError as error:
            evidence["status"] = "error"
            evidence["warnings"].append(str(error))
            return evidence

        evidence["tool_run"] = run
        evidence["status"] = "evidence-collected"
        evidence["evidence"] = {
            **_public_database_contract(database, database_hash=database_hash),
            # Persist only path-free database identity. Exact host filesystem
            # locations remain deployment diagnostics; hashes/releases and
            # readiness verdicts carry the reproducibility contract.
            "database_count": len(databases),
            "query_count": len(identifiers),
            "query_ids": identifiers,
            "molecule": "annealing_sequence",
            "parser_contract": "mfeprimer-4.5.1-json-or-tsv-v1",
        }

        # Prefer JSON when the installed build emitted it.  Do not depend on a
        # single filename: MFEprimer's output layout changed in 4.5.0.
        parsed: Any | None = None
        json_sources = [completed.stdout]
        if prefix.is_file():
            json_sources.append(prefix.read_text(encoding="utf-8", errors="replace"))
        json_sources.extend(
            p.read_text(encoding="utf-8", errors="replace") for p in workspace.glob("*.json")
        )
        for text in json_sources:
            text = text.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
                break
            except json.JSONDecodeError:
                continue
        if parsed is not None:
            if isinstance(parsed, list):
                evidence["evidence"]["records"] = len(parsed)
            elif isinstance(parsed, dict):
                evidence["evidence"]["json_keys"] = sorted(str(k) for k in parsed)[:50]
            evidence["evidence"]["format"] = "json"
        else:
            tsv_files = sorted(workspace.glob("*.tsv"))
            rows = 0
            columns: list[str] = []
            for path in tsv_files:
                try:
                    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
                        reader = csv.reader(handle, delimiter="\t")
                        first = next(reader, None)
                        if first and not columns:
                            columns = [str(value) for value in first]
                        rows += sum(1 for _ in reader)
                except OSError:
                    continue
            evidence["evidence"].update(
                {"format": "tsv", "tsv_files": [p.name for p in tsv_files], "rows": rows, "columns": columns}
            )

        structure_runs, structure_warnings = _mfeprimer_oligo_qc(
            oligos,
            workspace=workspace,
            engine_id=engine_id,
            module_id=module_id,
            reaction=reaction,
        )
        evidence["evidence"]["ordered_molecule_qc"] = structure_runs
        evidence["warnings"].extend(structure_warnings)

    evidence["warnings"].append(
        "MFEprimer evidence is independent validation. A database hit is not automatically an off-target unless the intended target/background identity makes that interpretation unambiguous."
    )
    return evidence



def _lamp_blast_region_queries(oligos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split LAMP composite primers into target-derived six-region queries.

    FIP/BIP full ordered molecules are not genomic query sequences. Their
    annealing halves provide F2/B2 and their explicit target-derived tails
    provide F1c/B1c; synthetic junction linkers are excluded.
    """
    grouped: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for oligo in oligos:
        try:
            set_index = int(oligo.get("lamp_set_index") or 0)
        except (TypeError, ValueError):
            set_index = 0
        role = str(oligo.get("lamp_role") or "").upper()
        if set_index > 0 and role:
            grouped[set_index][role] = oligo

    queries: list[dict[str, Any]] = []
    for set_index, by_role in sorted(grouped.items()):
        required = {"F3", "FIP", "BIP", "B3"}
        if not required.issubset(by_role):
            continue
        fip_tail = str(by_role["FIP"].get("lamp_target_tail_sequence") or "")
        bip_tail = str(by_role["BIP"].get("lamp_target_tail_sequence") or "")
        records = [
            ("F3", by_role["F3"]["annealing_sequence"], "forward", "3", "lamp-region"),
            ("F2", by_role["FIP"]["annealing_sequence"], "forward", "3", "lamp-region"),
            ("F1c", fip_tail, "reverse", "5", "lamp-region"),
            ("B1c", bip_tail, "forward", "5", "lamp-region"),
            ("B2", by_role["BIP"]["annealing_sequence"], "reverse", "3", "lamp-region"),
            ("B3", by_role["B3"]["annealing_sequence"], "reverse", "3", "lamp-region"),
        ]
        # LF/LB are optional and are not part of the required six-region core
        # topology. They are still real ordered oligos, so include them as
        # independent BLAST binding queries rather than silently omitting their
        # off-target evidence. Their hits deliberately do not enter the
        # six-region assembler below.
        if "LF" in by_role:
            records.append(("LF", by_role["LF"]["annealing_sequence"], "reverse", "3", "lamp-loop-region"))
        if "LB" in by_role:
            records.append(("LB", by_role["LB"]["annealing_sequence"], "forward", "3", "lamp-loop-region"))
        for role, sequence, expected_orientation, critical_end, kind in records:
            clean = _clean_sequence(sequence)
            if not clean:
                continue
            queries.append({
                "name": f"lamp_set_{set_index}_{role}",
                "kind": kind,
                "ordered_sequence": clean,
                "annealing_sequence": clean,
                "tail_sequence": "",
                "lamp_set_index": set_index,
                "lamp_region_role": role,
                "expected_orientation": expected_orientation,
                "critical_end": critical_end,
            })
    return queries


def _write_blast_queries(
    path: Path, queries: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, query in enumerate(queries, start=1):
            base = _safe_id(str(query["name"]), index)
            identifier = base
            suffix = 2
            while identifier in metadata:
                identifier = f"{base}_{suffix}"
                suffix += 1
            metadata[identifier] = query
            handle.write(f">{identifier}\n{query['annealing_sequence']}\n")
    return metadata


def _blast_lamp_topology(
    hits: list[dict[str, Any]], result: dict[str, Any], *, hit_collection_potentially_capped: bool = False
) -> dict[str, Any]:
    """Assemble BLAST region hits into LAMP-compatible six-region loci.

    Both whole-locus orientations are interpreted. A reverse-complement copy
    has every region hit on the opposite strand and appears in mirrored physical
    coordinate order; negating coordinates creates a canonical reference-order
    axis without requiring subject lengths from BLAST.

    Region lists are position-indexed with bisection before combination. This is
    not merely an optimization: on a genome database, spending the combination
    budget on geometrically impossible hits can turn a bounded validator into a
    coordinate-order artefact. The indexed assembler applies the same six-region
    geometry before the combination cap is consumed.

    This remains evidence, not a clean/off-target verdict. ``blastn-short`` is
    indexed and practical at genome scale but is not claimed to be a
    mismatch-complete enumeration of every <=2-mismatch oligo window. In
    addition, BLAST's per-query target cap is surfaced explicitly when reached.
    """
    parameter_set = result.get("parameter_set") or {}

    def span(name: str, default: tuple[int, int]) -> tuple[int, int]:
        raw = parameter_set.get(name)
        if isinstance(raw, list) and len(raw) == 2:
            try:
                return int(raw[0]), int(raw[1])
            except (TypeError, ValueError):
                pass
        return default

    def opposite(orientation: str) -> str:
        return "reverse" if orientation == "forward" else "forward"

    def by_start(values: list[dict[str, Any]], low: int, high: int) -> list[dict[str, Any]]:
        if low > high or not values:
            return []
        keys = [int(hit["canonical_start"]) for hit in values]
        return values[bisect_left(keys, low):bisect_right(keys, high)]

    def by_end(values: list[dict[str, Any]], low: int, high: int) -> list[dict[str, Any]]:
        if low > high or not values:
            return []
        ordered = sorted(values, key=lambda hit: (int(hit["canonical_end"]), int(hit["canonical_start"])))
        keys = [int(hit["canonical_end"]) for hit in ordered]
        return ordered[bisect_left(keys, low):bisect_right(keys, high)]

    f2_b2 = span("f2_b2_span", (120, 180))
    loop_span = span("loop_span", (40, 60))
    outer_gap = span("outer_gap", (0, 20))
    middle_gap = span("middle_gap", (0, 100))

    grouped: dict[tuple[int, str, str], dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for hit in hits:
        if int(hit.get("mismatches", 10**6)) > 2 or not hit.get("full_length"):
            continue
        actual = str(hit.get("orientation"))
        expected = str(hit.get("expected_orientation"))
        if actual == expected:
            locus_orientation = "forward"
            canonical_start = int(hit["start"])
            canonical_end = int(hit["end"])
        elif actual == opposite(expected):
            locus_orientation = "reverse"
            # Translation is irrelevant because every geometry constraint uses
            # differences. Negation reverses the subject coordinate axis.
            canonical_start = -int(hit["end"])
            canonical_end = -int(hit["start"])
        else:
            continue
        normalized = dict(hit)
        normalized["canonical_start"] = canonical_start
        normalized["canonical_end"] = canonical_end
        normalized["locus_orientation"] = locus_orientation
        key = (int(hit["lamp_set_index"]), str(hit["subject"]), locus_orientation)
        grouped[key][str(hit["lamp_region_role"])].append(normalized)

    loci: list[dict[str, Any]] = []
    exact_count = 0
    terminal_intact_count = 0
    evaluated = 0
    cap = 100_000
    capped = False
    orientations_seen: set[str] = set()
    subjects_with_complete_roles: set[str] = set()

    for (set_index, subject, locus_orientation), roles in sorted(grouped.items()):
        required_roles = ("F3", "F2", "F1c", "B1c", "B2", "B3")
        if any(not roles.get(role) for role in required_roles):
            continue
        orientations_seen.add(locus_orientation)
        subjects_with_complete_roles.add(subject)
        for role in roles:
            roles[role].sort(key=lambda h: (int(h["canonical_start"]), int(h["canonical_end"])))

        # Geometry-first indexed assembly. Each stage narrows by the exact LAMP
        # coordinate envelope before another role is crossed into the candidate.
        for f2 in roles["F2"]:
            f2_start = int(f2["canonical_start"])
            f1_candidates = by_start(
                roles["F1c"], f2_start + loop_span[0], f2_start + loop_span[1]
            )
            for f1c in f1_candidates:
                f1_end = int(f1c["canonical_end"])
                b1_candidates = by_start(
                    roles["B1c"], f1_end + middle_gap[0], f1_end + middle_gap[1]
                )
                for b1c in b1_candidates:
                    b1_end = int(b1c["canonical_end"])
                    b2_candidates = by_end(
                        roles["B2"], b1_end + loop_span[0], b1_end + loop_span[1]
                    )
                    for b2 in b2_candidates:
                        b2_end = int(b2["canonical_end"])
                        if not f2_b2[0] <= b2_end - f2_start <= f2_b2[1]:
                            continue
                        f3_candidates = by_end(
                            roles["F3"], f2_start - outer_gap[1], f2_start - outer_gap[0]
                        )
                        b3_candidates = by_start(
                            roles["B3"], b2_end + outer_gap[0], b2_end + outer_gap[1]
                        )
                        for f3 in f3_candidates:
                            for b3 in b3_candidates:
                                evaluated += 1
                                if evaluated > cap:
                                    capped = True
                                    break
                                six = (f3, f2, f1c, b1c, b2, b3)
                                exact = all(int(h["mismatches"]) == 0 for h in six)
                                terminal = all(bool(h["critical_terminal_exact"]) for h in six)
                                exact_count += int(exact)
                                terminal_intact_count += int(terminal)
                                if len(loci) < 20:
                                    loci.append({
                                        "set_index": set_index,
                                        "subject": subject,
                                        "locus_orientation": locus_orientation,
                                        "start": min(int(h["start"]) for h in six),
                                        "end": max(int(h["end"]) for h in six),
                                        "exact": exact,
                                        "critical_terminals_exact": terminal,
                                        "total_mismatches": sum(int(h["mismatches"]) for h in six),
                                        "regions": [
                                            {
                                                "role": h["lamp_region_role"],
                                                "start": int(h["start"]),
                                                "end": int(h["end"]),
                                                "orientation": h["orientation"],
                                                "mismatches": int(h["mismatches"]),
                                                "critical_terminal_exact": bool(h["critical_terminal_exact"]),
                                            }
                                            for h in six
                                        ],
                                    })
                            if capped:
                                break
                        if capped:
                            break
                    if capped:
                        break
                if capped:
                    break
            if capped:
                break
        if capped:
            break

    complete_within_collected_hits = not capped
    interpretation_complete = complete_within_collected_hits and not hit_collection_potentially_capped
    return {
        "checked": True,
        "search_exhaustiveness": "indexed-BLAST-heuristic-not-mismatch-complete",
        "max_mismatches_interpreted_per_region": 2,
        "locus_orientations_considered": ["forward", "reverse"],
        "locus_orientations_with_complete_role_presence": sorted(orientations_seen),
        "subjects_with_complete_role_presence": len(subjects_with_complete_roles),
        "combination_evaluations": evaluated,
        "combination_capped": capped,
        "blast_hit_collection_potentially_capped": hit_collection_potentially_capped,
        "complete_within_collected_hits": complete_within_collected_hits,
        "interpretation_complete": interpretation_complete,
        "exact_compatible_locus_count_lower_bound": exact_count,
        "terminal_intact_compatible_locus_count_lower_bound": terminal_intact_count,
        "compatible_loci": loci,
        "interpretation": (
            "Six-region LAMP-compatible database loci on either whole-locus orientation. "
            "Intended target identity is not inferred, so these are compatible-locus evidence "
            "rather than automatic off-target verdicts. Absence of a reported locus is not a "
            "clean proof when BLAST hit collection or topology assembly was bounded."
        ),
    }

def _blast(
    oligos: list[dict[str, Any]],
    *,
    engine_id: str,
    module_id: str,
    result: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    evidence = _base_evidence(
        "ncbi_blast_plus", status="unchecked", purpose="expanded short-oligo binding search"
    )
    status = tool_status("ncbi_blast_plus")
    if not status["available"]:
        evidence["warnings"].append(
            "NCBI BLAST+ 2.17.0 is not configured as a native executable on this host."
        )
        return evidence

    database = configured_database_contract("PCRSTUDIO_BLAST_DATABASE")
    raw_db = database["paths"][0] if database["paths"] else ""
    db_hash = database["sha256"]
    if not raw_db:
        evidence["warnings"].append("No BLAST database is configured; expanded specificity was not run.")
        return evidence
    if not db_hash:
        evidence["warnings"].append(
            "PCRSTUDIO_BLAST_DATABASE_SHA256 is missing; the BLAST database snapshot is not reproducibly identified."
        )
        if _mode() == "strict":
            return evidence
    if database["scope"] not in {"production", "approved-reference"}:
        evidence["warnings"].append(
            f"BLAST database scope is {database['scope']!r}; evidence is suitable for smoke/development checks, not a production specificity claim."
        )
    if database.get("manifest_error"):
        evidence["warnings"].append(f"BLAST database manifest could not be parsed: {database['manifest_error']}")
    if database.get("manifest") and not database.get("manifest_contract_consistent"):
        evidence["warnings"].append("BLAST database manifest scope/hash does not match the configured database contract.")
        if _mode() == "strict":
            return evidence
    if database.get("content_hash_matches") is False:
        evidence["warnings"].append("BLAST source FASTA content does not match its declared SHA-256.")
        if _mode() == "strict":
            return evidence
    if database.get("index_artifacts_match") is not True:
        evidence["warnings"].append(
            "BLAST index artifacts are missing or do not match the manifest SHA-256 fingerprints; production specificity cannot be claimed."
        )
        if _mode() == "strict":
            return evidence

    execution = request.get("executionContext") if isinstance(request.get("executionContext"), dict) else {}
    try:
        resource_units = max(1, min(int(execution.get("resourceUnits", 1)), 32))
    except (TypeError, ValueError):
        resource_units = 1
    configured_threads = os.environ.get("PCRSTUDIO_BLAST_THREADS")
    try:
        requested_threads = resource_units if not configured_threads else int(configured_threads)
    except ValueError:
        requested_threads = resource_units
    # The scheduler resource budget is an upper bound. A worker may use fewer
    # BLAST threads by deployment policy, never more than the server reserved.
    threads = max(1, min(requested_threads, resource_units, 32))

    with tempfile.TemporaryDirectory(prefix="pcrstudio-blast-", dir=str(_project_temp_root()) if _project_temp_root() else None) as workspace_name:
        workspace = Path(workspace_name)
        fasta = workspace / "oligos.fa"
        blast_queries = (
            _lamp_blast_region_queries(oligos) if engine_id == "loop-set" else oligos
        )
        query_metadata = _write_blast_queries(fasta, blast_queries)
        identifiers = {identifier: str(meta["name"]) for identifier, meta in query_metadata.items()}
        outfmt = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore qlen qseq sseq"
        args = [
            "-task",
            "blastn-short",
            "-query",
            str(fasta),
            "-db",
            raw_db,
            "-dust",
            "no",
            "-outfmt",
            outfmt,
            "-evalue",
            "1000",
            "-num_threads",
            str(threads),
            "-max_target_seqs",
            "5000",
        ]
        try:
            completed, run = run_tool(
                "ncbi_blast_plus",
                args,
                role="VALIDATOR",
                operation_id=_one_declared_operation(engine_id, "ncbi_blast_plus"),
                engine_id=engine_id,
                module_id=module_id,
                cwd=workspace,
                timeout_seconds=300,
            )
        except ToolRuntimeError as error:
            evidence["status"] = "error"
            evidence["warnings"].append(str(error))
            return evidence

        per_query: dict[str, dict[str, int]] = defaultdict(lambda: {"hits": 0, "full_length_hits": 0})
        lamp_hits: list[dict[str, Any]] = []
        malformed = 0
        for line in completed.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) != 15:
                malformed += 1
                continue
            query = fields[0]
            meta = query_metadata.get(query)
            if not meta:
                malformed += 1
                continue
            try:
                aligned_length = int(fields[3])
                mismatches = int(fields[4])
                gapopen = int(fields[5])
                qstart, qend = int(fields[6]), int(fields[7])
                sstart, send = int(fields[8]), int(fields[9])
                qlen = int(fields[12])
            except ValueError:
                malformed += 1
                continue
            per_query[query]["hits"] += 1
            full_length = aligned_length == qlen and qstart == 1 and qend == qlen and gapopen == 0
            if full_length:
                per_query[query]["full_length_hits"] += 1
            if engine_id == "loop-set" and meta.get("kind") == "lamp-region":
                qseq, sseq = fields[13].upper(), fields[14].upper()
                critical_end = str(meta.get("critical_end") or "3")
                terminal_index = -1 if critical_end == "3" else 0
                critical_terminal_exact = (
                    full_length
                    and len(qseq) == len(sseq)
                    and qseq[terminal_index] in "ACGT"
                    and sseq[terminal_index] in "ACGT"
                    and qseq[terminal_index] == sseq[terminal_index]
                )
                lamp_hits.append({
                    "query_id": query,
                    "lamp_set_index": int(meta["lamp_set_index"]),
                    "lamp_region_role": str(meta["lamp_region_role"]),
                    "subject": fields[1],
                    "start": min(sstart, send) - 1,
                    "end": max(sstart, send),
                    "orientation": "forward" if sstart <= send else "reverse",
                    "expected_orientation": str(meta["expected_orientation"]),
                    "mismatches": mismatches,
                    "full_length": full_length,
                    "critical_terminal_exact": critical_terminal_exact,
                    "pident": float(fields[2]),
                    "evalue": float(fields[10]),
                    "bitscore": float(fields[11]),
                })

        blast_target_cap = 5000
        hit_collection_potentially_capped = any(
            counts["hits"] >= blast_target_cap for counts in per_query.values()
        )
        evidence["status"] = "evidence-collected"
        evidence["tool_run"] = run
        evidence["evidence"] = {
            **_public_database_contract(database, database_hash=db_hash),
            "database_count": 1,
            "query_count": len(identifiers),
            "query_ids": identifiers,
            "molecule": "annealing_sequence",
            "hit_counts": dict(sorted(per_query.items())),
            "malformed_lines": malformed,
            "capped_at_targets_per_query": blast_target_cap,
            "hit_collection_potentially_capped": hit_collection_potentially_capped,
            "interpretation": "binding-hit-evidence-not-product-specificity",
        }
        if engine_id == "loop-set":
            evidence["evidence"]["lamp_region_query_contract"] = {
                "queries": len(query_metadata),
                "composite_split": "FIP=>F1c+F2; BIP=>B1c+B2; synthetic linker excluded",
                "optional_loop_queries": "LF/LB are queried independently when present and do not enter required six-region topology assembly",
                "critical_terminal_policy": "F3/F2/B2/B3/LF/LB 3-prime; F1c/B1c 5-prime",
            }
            evidence["evidence"]["lamp_six_region_topology"] = _blast_lamp_topology(
                lamp_hits, result,
                hit_collection_potentially_capped=hit_collection_potentially_capped,
            )
        evidence["warnings"].append(
            "BLAST short-oligo hits are binding evidence, not a PCR-product verdict. PCRStudio does not silently reject a primer from BLAST alone without target-aware pairing/identity context."
        )
    return evidence


def _primerpooler(
    oligos: list[dict[str, Any]],
    *,
    engine_id: str,
    module_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Audit the oligos that actually share a reaction.

    A multiplex result can contain several tubes and a tiled scheme several
    pools.  Cross-tube interactions are physically irrelevant, so the validator
    partitions on explicit ``tube`` first, then ``pool``.  Results without a
    grouping contract are audited as one set.
    """
    evidence = _base_evidence(
        "primerpooler", status="unchecked", purpose="independent multi-oligo interaction audit"
    )
    if len(oligos) < 3:
        evidence["status"] = "not-applicable"
        evidence["evidence"] = {"reason": "fewer than three ordered oligos"}
        return evidence
    status = tool_status("primerpooler")
    if not status["available"]:
        evidence["warnings"].append(
            "PrimerPooler 1.89 is not configured as a native Linux executable; the internal interaction audit remains visible but is not an independent validation."
        )
        return evidence

    reaction = _reaction(result)
    grouped: dict[str, list[dict[str, Any]]] = {}
    explicit_grouping = any(oligo.get("tube") is not None or oligo.get("pool") is not None for oligo in oligos)
    for oligo in oligos:
        if oligo.get("tube") is not None:
            key = f"tube:{oligo['tube']}"
        elif oligo.get("pool") is not None:
            key = f"pool:{oligo['pool']}"
        else:
            key = "all-selected-oligos"
        grouped.setdefault(key, []).append(oligo)

    group_results: list[dict[str, Any]] = []
    tool_runs: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="pcrstudio-pooler-", dir=str(_project_temp_root()) if _project_temp_root() else None) as workspace_name:
        workspace = Path(workspace_name)
        reaction_block = result.get("reaction") or {}
        raw_temperature = reaction_block.get("anneal_extend_c")
        temperature_role = "named-protocol-anneal-extend"
        if raw_temperature is None:
            raw_temperature = reaction_block.get("isothermal_c")
            temperature_role = "named-protocol-isothermal"

        temperature_c: float | None = None
        if raw_temperature is not None:
            try:
                measured = float(raw_temperature)
            except (TypeError, ValueError):
                measured = float("nan")
            if math.isfinite(measured):
                temperature_c = measured

        # PrimerPooler can operate either in deltaG mode, which requires an
        # explicit temperature/ionic context, or in its sequence-score mode.
        # Do not manufacture a 60 C (or borrow the tool's 45 C default) when
        # PCRStudio has no named protocol temperature. In that case the
        # independent validator uses score mode and says so explicitly.
        if temperature_c is not None:
            temperature_k = temperature_c + 273.15
            interaction_option = f"--dg={temperature_k:.2f},{reaction['dv_conc']},{reaction['mv_conc']},{reaction['dntp_conc']}"
            interaction_metric = "deltaG"
        else:
            temperature_k = None
            interaction_option = None
            interaction_metric = "primerpooler-score"
            evidence["warnings"].append(
                "No named annealing/isothermal temperature was available for PrimerPooler deltaG. "
                "The independent interaction audit therefore used PrimerPooler's score mode; no "
                "PCRStudio-invented temperature was substituted."
            )

        for group_index, (group_name, members) in enumerate(sorted(grouped.items()), start=1):
            if len(members) < 2:
                group_results.append(
                    {
                        "group": group_name,
                        "query_count": len(members),
                        "status": "not-applicable",
                        "reason": "fewer than two oligos share this reaction group",
                    }
                )
                continue
            fasta = workspace / f"oligos-{group_index}.fa"
            _write_fasta(fasta, members, molecule="ordered")
            args = ([interaction_option] if interaction_option else []) + ["--counts", str(fasta)]
            try:
                completed, run = run_tool(
                    "primerpooler",
                    args,
                    role="VALIDATOR",
                    operation_id={
                        "flanking-pair": "validate_multiplex_interactions",
                        "nested": "validate_cross_round_interactions",
                        "tiling-scheme": "audit_selected_pool_interactions",
                    }.get(engine_id)
                    or _one_declared_operation(engine_id, "primerpooler"),
                    engine_id=engine_id,
                    module_id=module_id,
                    cwd=workspace,
                    timeout_seconds=180,
                )
            except ToolRuntimeError as error:
                evidence["status"] = "error"
                evidence["warnings"].append(f"{group_name}: {error}")
                continue
            tool_runs.append(run)
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            group_results.append(
                {
                    "group": group_name,
                    "query_count": len(members),
                    "status": "evidence-collected",
                    "summary_lines": lines[-25:],
                }
            )

    pool_proposal: dict[str, Any] | None = None
    # PrimerPooler is not a primer-design algorithm, but its upstream 1.89
    # minimisation/pooling implementation is an authoritative optional pool
    # proposal once the final primer pairs are known.  Keep it evidence-only:
    # Scientific-Strict never silently rewrites PCRStudio's physical tube/pool
    # identities from this stochastic optimiser.  --seedless makes the proposal
    # reproducible for differential qualification and review.
    proposal_members = [row for row in oligos if str(row.get("kind")) == "primer"]
    proposal_pair_bases: dict[str, set[str]] = {}
    for row in proposal_members:
        name = str(row.get("name") or "")
        if name.endswith(("F", "R")) and len(name) > 1:
            proposal_pair_bases.setdefault(name[:-1], set()).add(name[-1])
    proposal_pair_count = sum(1 for roles in proposal_pair_bases.values() if {"F", "R"}.issubset(roles))
    if engine_id in {"flanking-pair", "tiling-scheme"} and proposal_pair_count >= 2:
        proposal_input = workspace / "primerpooler-proposal.fa"
        identifiers = _write_fasta(proposal_input, proposal_members, molecule="ordered", kinds={"primer"})
        prefix = workspace / "primerpooler-proposed-pool-"
        proposal_args: list[str] = ["--seedless"]
        if interaction_option:
            proposal_args.append(interaction_option)
        selection = result.get("selection_method") if isinstance(result.get("selection_method"), dict) else {}
        requested_max = selection.get("per_tube") if selection.get("tube_split_explicit") else None
        if isinstance(requested_max, int) and requested_max > 0 and requested_max < proposal_pair_count:
            proposal_args.append(f"--max-count={requested_max}")
        proposal_args.extend([f"--pools=?,1,{prefix}", str(proposal_input)])
        try:
            completed, proposal_run = run_tool(
                "primerpooler",
                proposal_args,
                role="VALIDATOR" if engine_id == "tiling-scheme" else "OPTIONAL",
                operation_id="assign_pools",
                engine_id=engine_id,
                module_id=module_id,
                cwd=workspace,
                timeout_seconds=180,
            )
            tool_runs.append(proposal_run)
            pools: list[dict[str, Any]] = []
            for pool_index, pool_file in enumerate(sorted(workspace.glob(prefix.name + "*")), start=1):
                if not pool_file.is_file():
                    continue
                try:
                    lines = pool_file.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                names: list[str] = []
                for line in lines:
                    if line.startswith(">"):
                        identifier = line[1:].strip().split()[0]
                        names.append(identifiers.get(identifier, identifier))
                if names:
                    pools.append({"pool": pool_index, "oligos": names, "source_file": pool_file.name})
            pool_proposal = {
                "status": "proposal-collected" if pools else "proposal-output-unparsed",
                "source_tool": "PrimerPooler 1.89 upstream pooling/minimisation",
                "operation": "assign_pools",
                "reproducibility": "--seedless; one-minute upstream minimisation window",
                "pair_count": proposal_pair_count,
                "pool_count": len(pools) if pools else None,
                "pools": pools,
                "accepted_into_design": False,
                "decision_impact": "evidence-only-until-explicitly-accepted",
                "stdout_tail": [line.strip() for line in completed.stdout.splitlines() if line.strip()][-25:],
                "note": (
                    "This is PrimerPooler's own upstream pool proposal for the selected primer pairs. "
                    "PCRStudio does not silently replace the panel's explicit physical tube/pool identities; "
                    "review and accept a proposal before using it as a formulation change."
                ),
            }
            if not pools:
                evidence["warnings"].append(
                    "PrimerPooler completed a pool proposal but no generated pool FASTA files were parsed; stdout is retained for qualification review."
                )
        except ToolRuntimeError as error:
            evidence["warnings"].append(f"PrimerPooler pool proposal unavailable: {error}")
            pool_proposal = {
                "status": "proposal-error",
                "source_tool": "PrimerPooler 1.89 upstream pooling/minimisation",
                "accepted_into_design": False,
                "decision_impact": "none",
                "note": str(error),
            }

    if evidence["status"] != "error":
        evidence["status"] = "evidence-collected" if any(
            group.get("status") == "evidence-collected" for group in group_results
        ) else "not-applicable"
    evidence["tool_run"] = tool_runs[0] if len(tool_runs) == 1 else None
    evidence["tool_runs"] = tool_runs
    evidence["evidence"] = {
        "query_count": len(oligos),
        "molecule": "ordered_sequence",
        "grouping": "tube-or-pool" if explicit_grouping else "single-set",
        "groups": group_results,
        "interaction_metric": interaction_metric,
        "dg_conditions": (
            {
                "temperature_c": round(temperature_c, 3),
                "temperature_kelvin": round(temperature_k, 2),
                "temperature_role": temperature_role,
                "magnesium_mM": reaction["dv_conc"],
                "monovalent_mM": reaction["mv_conc"],
                "dntp_mM": reaction["dntp_conc"],
            }
            if temperature_c is not None and temperature_k is not None
            else None
        ),
        "parser_contract": "primerpooler-1.89-counts-grouped-v4-with-upstream-pool-proposal",
        "pool_proposal": pool_proposal,
        "interpretation": (
            "Interactions are audited only among oligos that actually share a tube/pool when grouping metadata is present. "
            "DeltaG mode is used only when PCRStudio has an explicit protocol temperature; otherwise score mode is retained as diagnostic evidence."
        ),
    }
    return evidence


_EXTERNAL_VALIDATION_ADAPTERS = frozenset({"mfeprimer", "ncbi_blast_plus", "primerpooler", "pydna"})


def _requested_validators(engine_id: str) -> set[str]:
    """Return tools owned by this independent validation boundary.

    Atlas ``OPTIONAL`` means an engine may use a capability; it does not mean
    that every optional tool belongs in the common post-selection validator.
    ViennaRNA and pydna, for example, are consumed by engine-specific paths or
    provenance.  Only tools with an adapter and an interpretation contract in
    this module are requested here.
    """
    return {
        str(binding["tool_id"])
        for binding in ENGINE_BINDINGS.get(engine_id, ())
        if str(binding.get("tool_id")) in _EXTERNAL_VALIDATION_ADAPTERS
        and binding.get("role") in {"VALIDATOR", "OPTIONAL"}
    }




def _required_validators(engine_id: str) -> set[str]:
    """Return independent validators that are release-gating for this engine.

    OPTIONAL checks may enrich a result when available, but an unavailable or
    failing OPTIONAL adapter must not be promoted into a strict prerequisite.
    """
    return {
        str(binding["tool_id"])
        for binding in ENGINE_BINDINGS.get(engine_id, ())
        if str(binding.get("tool_id")) in _EXTERNAL_VALIDATION_ADAPTERS
        and binding.get("role") == "VALIDATOR"
    }

def validate_result(
    *, command: str, request: dict[str, Any], result: dict[str, Any], engine_id: str, module_id: str
) -> dict[str, Any]:
    """Collect independent evidence and return a common validation envelope."""
    mode = _mode()
    oligos = selected_oligos(result)
    wanted = _requested_validators(engine_id)
    required = _required_validators(engine_id)
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    if mode == "off":
        return {
            "contract_version": VALIDATION_CONTRACT_VERSION,
            "mode": mode,
            "status": "disabled",
            "selected_oligos": len(oligos),
            "molecule_contract": {
                "specificity": "annealing_sequence",
                "interaction": "ordered_sequence",
                "tail_position": "5-prime-only",
            },
            "checks": [],
            "warnings": ["Independent external validation is disabled by deployment policy."],
        }

    if not oligos:
        return {
            "contract_version": VALIDATION_CONTRACT_VERSION,
            "mode": mode,
            "status": "verification-incomplete",
            "selected_oligos": 0,
            "molecule_contract": {
                "specificity": "annealing_sequence",
                "interaction": "ordered_sequence",
                "tail_position": "5-prime-only",
            },
            "checks": [],
            "warnings": ["No supplier-ready oligo sequences were present in the result to validate."],
        }

    # These tools are independent validators and each owns its own temporary
    # workspace. Running them concurrently prevents a healthy BLAST search from
    # consuming the time budget left behind by an unrelated MFEprimer/interaction
    # audit. The returned list is sorted afterwards so response ordering remains
    # deterministic regardless of which process finishes first.
    jobs: list[tuple[str, Any]] = []
    if "mfeprimer" in wanted:
        jobs.append((
            "mfeprimer",
            lambda: _mfeprimer(oligos, engine_id=engine_id, module_id=module_id, result=result),
        ))
    if "ncbi_blast_plus" in wanted:
        jobs.append((
            "ncbi_blast_plus",
            lambda: _blast(
                oligos, engine_id=engine_id, module_id=module_id, result=result, request=request
            ),
        ))
    if "primerpooler" in wanted and (engine_id in {"nested", "tiling-scheme"} or len(oligos) >= 4):
        jobs.append((
            "primerpooler",
            lambda: _primerpooler(oligos, engine_id=engine_id, module_id=module_id, result=result),
        ))

    if "pydna" in wanted:
        jobs.append((
            "pydna",
            lambda: validate_with_pydna(request, result, engine_id),
        ))

    if jobs:
        with ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="pcrstudio-validator") as executor:
            future_to_id = {executor.submit(call): tool_id for tool_id, call in jobs}
            for future in as_completed(future_to_id):
                tool_id = future_to_id[future]
                try:
                    checks.append(future.result())
                except Exception as error:  # fail closed at the adapter boundary
                    evidence = _base_evidence(
                        tool_id, status="error", purpose="independent validation"
                    )
                    evidence["warnings"].append(
                        f"{tool_id} validator raised an unexpected adapter error: {error}"
                    )
                    checks.append(evidence)
        checks.sort(key=lambda check: str(check.get("tool_id") or ""))

    collected = sum(1 for check in checks if check.get("status") == "evidence-collected")
    errors = [
        check for check in checks
        if check.get("status") == "error" and check.get("tool_id") in required
    ]
    unchecked = [
        check for check in checks
        if check.get("status") == "unchecked" and check.get("tool_id") in required
    ]
    limited_database_evidence = any(
        isinstance(check.get("evidence"), dict)
        and check["evidence"].get("database_scope")
        and (
            check["evidence"].get("database_scope") not in {"production", "approved-reference"}
            or check["evidence"].get("manifest_contract_consistent") is not True
            or check["evidence"].get("content_hash_matches") is not True
            or check["evidence"].get("index_artifacts_match") is not True
        )
        for check in checks
    )
    uninterpreted_required = [
        check for check in checks
        if check.get("tool_id") in required
        and check.get("status") == "evidence-collected"
        and check.get("interpretation_complete") is not True
    ]

    for check in checks:
        warnings.extend(str(message) for message in check.get("warnings", []) if message)

    # Independent evidence is intentionally not called a PASS unless it has a
    # target-aware interpretation contract.  A reproducible smoke corpus is
    # also explicitly weaker than an approved production/background snapshot.
    if errors:
        status = "validator-error"
    elif unchecked:
        status = "verification-incomplete"
    elif checks and collected and limited_database_evidence:
        status = "evidence-collected-limited"
    elif uninterpreted_required:
        # The required tools ran against reproducible data, but their adapter
        # does not yet own enough target/background identity to convert raw
        # hits into an assay-specific verdict. Preserve the design and the raw
        # evidence without upgrading it to external verification.
        status = "evidence-collected-uninterpreted"
    elif checks and collected:
        status = "evidence-collected"
    else:
        status = "not-applicable"

    if mode == "strict" and status in {"verification-incomplete", "validator-error", "evidence-collected-limited"}:
        warnings.insert(
            0,
            "Strict validation policy is active: this result must not be presented as externally verified until the missing validator/database requirement is resolved.",
        )
    elif mode == "strict" and status == "evidence-collected-uninterpreted":
        warnings.insert(
            0,
            "Strict validation collected the required external evidence, but the current adapters do not have a target-aware interpretation contract for those hits. The computational design may be shown with this evidence-incomplete boundary; it must not be labelled externally verified.",
        )

    return {
        "contract_version": VALIDATION_CONTRACT_VERSION,
        "mode": mode,
        "status": status,
        "selected_oligos": len(oligos),
        "molecule_contract": {
            "specificity": "annealing_sequence",
            "interaction": "ordered_sequence",
            "tail_position": "5-prime-only",
        },
        "checks": checks,
        "warnings": warnings,
        "interpretation_complete": (
            status in {"evidence-collected", "not-applicable"}
            and not uninterpreted_required
        ),
        "uninterpreted_required_tools": [
            str(check.get("tool_id")) for check in uninterpreted_required
        ],
        "selection_policy": {
            "hard_filters": "engine assay constraints + Primer3/engine thermodynamics + supplied background/inclusivity checks",
            "ranking": "engine-specific deterministic ranking with stable tie-breaking",
            "external_evidence": "independent evidence; not silently converted into an off-target verdict without target-aware context",
        },
    }
