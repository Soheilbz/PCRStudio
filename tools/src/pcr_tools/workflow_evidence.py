"""Bounded empirical workflow evidence shared by every PCRStudio engine.

Evidence is a flat scalar observation record. It is provenance about what was
observed after design; it is never an implicit feature vector and never mutates
the candidate ranking that produced the saved design.
"""

from __future__ import annotations

from typing import Any

MAX_WORKFLOW_EVIDENCE_FIELDS = 64
MAX_WORKFLOW_EVIDENCE_KEY_CHARS = 80
MAX_WORKFLOW_EVIDENCE_TEXT_CHARS = 8_000


class WorkflowEvidenceError(ValueError):
    """The submitted evidence record is not bounded/auditable."""


def validate_evidence_fields(value: Any) -> dict[str, str | int | float | bool | None] | None:
    """Return one canonical flat evidence map, or ``None`` when absent."""
    if value in (None, "", {}):
        return None
    if not isinstance(value, dict):
        raise WorkflowEvidenceError("workflow_evidence must be a flat object")
    if len(value) > MAX_WORKFLOW_EVIDENCE_FIELDS:
        raise WorkflowEvidenceError(
            f"workflow_evidence may contain at most {MAX_WORKFLOW_EVIDENCE_FIELDS} fields"
        )
    cleaned: dict[str, str | int | float | bool | None] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            raise WorkflowEvidenceError("workflow_evidence keys must be strings")
        key = raw_key.strip()
        if not 1 <= len(key) <= MAX_WORKFLOW_EVIDENCE_KEY_CHARS:
            raise WorkflowEvidenceError(
                f"workflow_evidence keys must contain 1-{MAX_WORKFLOW_EVIDENCE_KEY_CHARS} characters"
            )
        if isinstance(raw_value, str):
            if len(raw_value) > MAX_WORKFLOW_EVIDENCE_TEXT_CHARS:
                raise WorkflowEvidenceError(
                    f"workflow_evidence.{key} exceeds {MAX_WORKFLOW_EVIDENCE_TEXT_CHARS} characters"
                )
            cleaned[key] = raw_value.strip()
        elif raw_value is None or isinstance(raw_value, (int, float, bool)):
            cleaned[key] = raw_value
        else:
            raise WorkflowEvidenceError(f"workflow_evidence.{key} must be scalar")
    return cleaned


def evidence_block(value: Any, *, note: str | None = None) -> dict[str, Any] | None:
    """Build the canonical result block used by every current engine."""
    cleaned = validate_evidence_fields(value)
    if cleaned is None:
        return None
    return {
        "recorded": True,
        "decision_impact": "none",
        "observed": cleaned,
        "note": note
        or (
            "Empirical/run evidence is stored for reproducibility and validation; "
            "it does not mutate sequence ranking in the original design run."
        ),
    }
