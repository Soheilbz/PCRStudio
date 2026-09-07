"""Reproducible species-panel manifest helpers.

These utilities validate snapshot identity, not biological completeness. Network
resolution remains an explicit external validation step.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

_ACCESSION_VERSION = re.compile(r"^[A-Za-z]{1,6}_?[A-Za-z0-9]*\d+\.\d+$|^[A-Za-z]{1,4}\d+\.\d+$")


class SpeciesPanelError(ValueError):
    pass


def parse_accession_version_manifest(text: str) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(str(text).splitlines(), start=1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        token = value.split()[0]
        if not _ACCESSION_VERSION.fullmatch(token):
            raise SpeciesPanelError(
                f"line {lineno} must begin with a versioned accession such as NC_000001.11; got {token!r}"
            )
        if token in seen:
            raise SpeciesPanelError(f"duplicate accession.version in panel manifest: {token}")
        seen.add(token)
        rows.append(token)
    if not rows:
        raise SpeciesPanelError("species panel accession manifest is empty")
    return tuple(sorted(rows))


def manifest_sha256(accessions: tuple[str, ...] | list[str]) -> str:
    canonical = "\n".join(sorted(accessions)) + "\n"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SurveillanceDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    version_changed: tuple[tuple[str, str], ...]
    unchanged: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def surveillance_diff(
    old: tuple[str, ...] | list[str], new: tuple[str, ...] | list[str]
) -> SurveillanceDiff:
    def base(accession: str) -> str:
        return accession.rsplit(".", 1)[0]

    old_map = {base(x): x for x in old}
    new_map = {base(x): x for x in new}
    changed = tuple(
        sorted(
            (old_map[b], new_map[b])
            for b in old_map.keys() & new_map.keys()
            if old_map[b] != new_map[b]
        )
    )
    unchanged = tuple(
        sorted(old_map[b] for b in old_map.keys() & new_map.keys() if old_map[b] == new_map[b])
    )
    added = tuple(sorted(new_map[b] for b in new_map.keys() - old_map.keys()))
    removed = tuple(sorted(old_map[b] for b in old_map.keys() - new_map.keys()))
    return SurveillanceDiff(
        added=added, removed=removed, version_changed=changed, unchanged=unchanged
    )


@dataclass(frozen=True)
class SpeciesRecordMetadata:
    """One reproducible panel-record annotation.

    The record id must match the first FASTA header token used by the runtime.
    ``weight`` is optional user-declared relative population evidence; it is
    recorded and summarized but never changes sequence ranking or relaxes the
    strict all-inclusivity-records coverage gate.
    """

    record_id: str
    accession_version: str
    role: str
    topology: str
    weight: float | None = None
    group: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_record_metadata_manifest(text: str) -> tuple[SpeciesRecordMetadata, ...]:
    """Parse TSV ``record_id accession.version role topology [weight] [group]``.

    Roles are ``inclusivity`` or ``exclusivity``. Topology is ``linear``,
    ``circular`` or ``fragment``.  A fragment is scanned linearly and is
    explicitly not treated as evidence that the rest of the source molecule
    lacks a binding site.  Optional weights are relative evidence only.
    """
    rows: list[SpeciesRecordMetadata] = []
    seen_record: set[str] = set()
    seen_accession: set[str] = set()
    for lineno, raw in enumerate(str(text).splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 4 or len(parts) > 6:
            raise SpeciesPanelError(
                f"line {lineno} must contain 4-6 tab-separated fields: record_id, accession.version, role, topology, optional weight, optional group"
            )
        record_id, accession, role, topology = (part.strip() for part in parts[:4])
        if not record_id or any(ch.isspace() for ch in record_id):
            raise SpeciesPanelError(
                f"line {lineno} record_id must be a non-empty FASTA identifier without whitespace"
            )
        if not _ACCESSION_VERSION.fullmatch(accession):
            raise SpeciesPanelError(f"line {lineno} accession must be versioned; got {accession!r}")
        if role not in {"inclusivity", "exclusivity"}:
            raise SpeciesPanelError(f"line {lineno} role must be inclusivity or exclusivity")
        if topology not in {"linear", "circular", "fragment"}:
            raise SpeciesPanelError(f"line {lineno} topology must be linear, circular or fragment")
        if record_id in seen_record:
            raise SpeciesPanelError(f"duplicate species panel record_id: {record_id}")
        if accession in seen_accession:
            raise SpeciesPanelError(f"duplicate species panel accession.version: {accession}")
        weight: float | None = None
        if len(parts) >= 5 and parts[4].strip():
            try:
                weight = float(parts[4].strip())
            except ValueError as exc:
                raise SpeciesPanelError(f"line {lineno} weight must be numeric") from exc
            if not (weight > 0.0) or weight == float("inf"):
                raise SpeciesPanelError(
                    f"line {lineno} weight must be finite and greater than zero"
                )
        group = parts[5].strip() if len(parts) >= 6 and parts[5].strip() else None
        rows.append(SpeciesRecordMetadata(record_id, accession, role, topology, weight, group))
        seen_record.add(record_id)
        seen_accession.add(accession)
    if not rows:
        raise SpeciesPanelError("species panel record-metadata manifest is empty")
    return tuple(rows)


def record_metadata_sha256(
    rows: tuple[SpeciesRecordMetadata, ...] | list[SpeciesRecordMetadata],
) -> str:
    canonical = (
        "\n".join(
            "\t".join(
                [
                    row.record_id,
                    row.accession_version,
                    row.role,
                    row.topology,
                    "" if row.weight is None else format(row.weight, ".12g"),
                    row.group or "",
                ]
            )
            for row in sorted(
                rows,
                key=lambda item: (
                    item.record_id,
                    item.accession_version,
                    item.role,
                    item.topology,
                    item.group or "",
                    -1.0 if item.weight is None else item.weight,
                ),
            )
        )
        + "\n"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_record_metadata(
    rows: tuple[SpeciesRecordMetadata, ...] | list[SpeciesRecordMetadata],
    *,
    accessions: tuple[str, ...] | list[str],
    inclusivity_record_ids: tuple[str, ...] | list[str],
    exclusivity_record_ids: tuple[str, ...] | list[str],
) -> dict[str, object]:
    """Validate exact metadata↔FASTA↔accession identity and summarize evidence."""
    by_record = {row.record_id: row for row in rows}
    expected_ids = set(inclusivity_record_ids) | set(exclusivity_record_ids)
    if set(by_record) != expected_ids:
        missing = sorted(expected_ids - set(by_record))
        extra = sorted(set(by_record) - expected_ids)
        raise SpeciesPanelError(
            f"record-metadata manifest must cover every FASTA record exactly once; missing={missing}, extra={extra}"
        )
    if {row.accession_version for row in rows} != set(accessions):
        missing = sorted(set(accessions) - {row.accession_version for row in rows})
        extra = sorted({row.accession_version for row in rows} - set(accessions))
        raise SpeciesPanelError(
            f"record-metadata accessions must exactly match accession manifest; missing={missing}, extra={extra}"
        )
    inclusivity_ids = set(inclusivity_record_ids)
    for row in rows:
        expected_role = "inclusivity" if row.record_id in inclusivity_ids else "exclusivity"
        if row.role != expected_role:
            raise SpeciesPanelError(
                f"record {row.record_id!r} is {expected_role} FASTA but metadata role is {row.role}"
            )
    topology_counts = {key: 0 for key in ("linear", "circular", "fragment")}
    group_counts: dict[str, int] = {}
    weighted = [row for row in rows if row.role == "inclusivity" and row.weight is not None]
    inclusivity_rows = [row for row in rows if row.role == "inclusivity"]
    for row in rows:
        topology_counts[row.topology] += 1
        if row.group:
            group_counts[row.group] = group_counts.get(row.group, 0) + 1
    total_weight = sum(float(row.weight) for row in weighted if row.weight is not None)
    normalized_weights = (
        {
            row.record_id: float(row.weight) / total_weight
            for row in weighted
            if row.weight is not None
        }
        if total_weight > 0
        else {}
    )
    return {
        "record_count": len(rows),
        "topology_counts": topology_counts,
        "group_counts": dict(sorted(group_counts.items())),
        "population_weighting_status": (
            "complete-user-declared-relative-weights-evidence-only-not-used-for-ranking"
            if inclusivity_rows and len(weighted) == len(inclusivity_rows)
            else "partial-user-declared-relative-weights-evidence-only-not-used-for-ranking"
            if weighted
            else "not-supplied"
        ),
        "normalized_inclusivity_weights": normalized_weights,
        "fragment_record_count": topology_counts["fragment"],
        "claim_boundary": "metadata improves reproducibility/topology/population-evidence bookkeeping; it does not prove pangenome completeness or empirical sensitivity",
    }


@dataclass(frozen=True)
class AccessionAuthorityRecord:
    """One resolver snapshot row for accession/taxonomy lifecycle validation."""

    accession_version: str
    taxid: int
    status: str
    replacement_accession_version: str | None = None
    sequence_database_snapshot: str | None = None
    taxonomy_snapshot: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_accession_authority_manifest(text: str) -> tuple[AccessionAuthorityRecord, ...]:
    """Parse TSV accession.version, TaxID, lifecycle status, replacement, DB snapshot, taxonomy snapshot.

    This is an offline resolver snapshot, not a network lookup.  Supported
    lifecycle statuses are ``current``, ``suppressed`` and ``replaced``.
    Replaced records must name a versioned replacement accession; current and
    suppressed rows must leave that column empty.
    """
    rows: list[AccessionAuthorityRecord] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(str(text).splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 3 or len(parts) > 6:
            raise SpeciesPanelError(
                f"line {lineno} must contain 3-6 tab-separated fields: accession.version, TaxID, status, optional replacement accession.version, optional sequence DB snapshot, optional taxonomy snapshot"
            )
        accession = parts[0].strip()
        if not _ACCESSION_VERSION.fullmatch(accession):
            raise SpeciesPanelError(f"line {lineno} accession must be versioned; got {accession!r}")
        if accession in seen:
            raise SpeciesPanelError(
                f"duplicate accession.version in accession authority manifest: {accession}"
            )
        try:
            taxid = int(parts[1].strip())
        except ValueError as exc:
            raise SpeciesPanelError(f"line {lineno} TaxID must be a positive integer") from exc
        if taxid <= 0:
            raise SpeciesPanelError(f"line {lineno} TaxID must be a positive integer")
        status = parts[2].strip().lower()
        if status not in {"current", "suppressed", "replaced"}:
            raise SpeciesPanelError(f"line {lineno} status must be current, suppressed or replaced")
        replacement = parts[3].strip() if len(parts) >= 4 and parts[3].strip() else None
        if status == "replaced":
            if replacement is None or not _ACCESSION_VERSION.fullmatch(replacement):
                raise SpeciesPanelError(
                    f"line {lineno} replaced accession requires a versioned replacement accession"
                )
            if replacement == accession:
                raise SpeciesPanelError(
                    f"line {lineno} replacement accession must differ from the superseded accession"
                )
        elif replacement is not None:
            raise SpeciesPanelError(
                f"line {lineno} status {status} must not declare a replacement accession"
            )
        sequence_snapshot = parts[4].strip() if len(parts) >= 5 and parts[4].strip() else None
        taxonomy_snapshot = parts[5].strip() if len(parts) >= 6 and parts[5].strip() else None
        rows.append(
            AccessionAuthorityRecord(
                accession, taxid, status, replacement, sequence_snapshot, taxonomy_snapshot
            )
        )
        seen.add(accession)
    if not rows:
        raise SpeciesPanelError("species accession authority manifest is empty")
    return tuple(rows)


def accession_authority_sha256(
    rows: tuple[AccessionAuthorityRecord, ...] | list[AccessionAuthorityRecord],
) -> str:
    canonical = (
        "\n".join(
            "\t".join(
                [
                    row.accession_version,
                    str(row.taxid),
                    row.status,
                    row.replacement_accession_version or "",
                    row.sequence_database_snapshot or "",
                    row.taxonomy_snapshot or "",
                ]
            )
            for row in sorted(rows, key=lambda item: item.accession_version)
        )
        + "\n"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_accession_authority(
    rows: tuple[AccessionAuthorityRecord, ...] | list[AccessionAuthorityRecord],
    *,
    accessions: tuple[str, ...] | list[str],
    target_taxid: int,
    sequence_database_snapshot: str,
    taxonomy_snapshot: str,
) -> dict[str, object]:
    """Validate an offline accession resolver snapshot against the panel contract."""
    by_accession = {row.accession_version: row for row in rows}
    expected = set(accessions)
    if set(by_accession) != expected:
        raise SpeciesPanelError(
            f"accession authority manifest must cover the panel exactly; missing={sorted(expected - set(by_accession))}, extra={sorted(set(by_accession) - expected)}"
        )
    suppressed = sorted(row.accession_version for row in rows if row.status == "suppressed")
    replaced = {
        row.accession_version: row.replacement_accession_version
        for row in rows
        if row.status == "replaced"
    }
    # A target panel cannot silently include a suppressed/replaced record under a
    # current-snapshot claim.  The caller must update the panel and explicitly
    # review the replacement before a new design is accepted.
    if suppressed:
        raise SpeciesPanelError(
            "species panel contains suppressed accession(s): " + ", ".join(suppressed)
        )
    if replaced:
        detail = ", ".join(f"{old}->{new}" for old, new in sorted(replaced.items()))
        raise SpeciesPanelError(
            "species panel contains replaced accession(s); update/review replacements before design: "
            + detail
        )
    sequence_mismatch = sorted(
        row.accession_version
        for row in rows
        if row.sequence_database_snapshot
        and row.sequence_database_snapshot != sequence_database_snapshot
    )
    taxonomy_mismatch = sorted(
        row.accession_version
        for row in rows
        if row.taxonomy_snapshot and row.taxonomy_snapshot != taxonomy_snapshot
    )
    if sequence_mismatch:
        raise SpeciesPanelError(
            "accession authority sequence-database snapshot disagrees with the declared panel snapshot for: "
            + ", ".join(sequence_mismatch)
        )
    if taxonomy_mismatch:
        raise SpeciesPanelError(
            "accession authority taxonomy snapshot disagrees with the declared panel snapshot for: "
            + ", ".join(taxonomy_mismatch)
        )
    taxids = sorted({row.taxid for row in rows})
    return {
        "record_count": len(rows),
        "status_counts": {
            status: sum(row.status == status for row in rows)
            for status in ("current", "suppressed", "replaced")
        },
        "declared_target_taxid": target_taxid,
        "observed_taxids": taxids,
        "target_taxid_match_count": sum(row.taxid == target_taxid for row in rows),
        "all_records_match_target_taxid": all(row.taxid == target_taxid for row in rows),
        "claim_boundary": "TaxID equality is checked against the supplied offline resolver snapshot; PCRStudio does not infer taxonomic completeness, synonymy or biological species scope from accession labels.",
    }


def revalidation_policy() -> dict[str, object]:
    """Return the fail-closed lifecycle policy attached to a species-panel snapshot."""
    return {
        "silent_update_allowed": False,
        "triggers": [
            "accession-suppressed-or-replaced",
            "sequence-database-snapshot-change",
            "taxonomy-snapshot-change",
            "inclusivity-or-exclusivity-panel-content-change",
            "accession-authority-manifest-change",
        ],
        "required_action": "freeze-new-authority-snapshot-and-rerun-specificity-validation-before-renewing-the-species-specific-claim",
        "claim_boundary": "A prior finite-panel result is not automatically current after any authority/database/panel lifecycle change.",
    }
