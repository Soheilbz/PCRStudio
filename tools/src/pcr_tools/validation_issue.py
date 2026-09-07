"""One structured validation vocabulary shared across PCRStudio layers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal, TypedDict

Severity = Literal["info", "warning", "error"]
OwnerStep = Literal[
    "target", "design", "strategy", "constraints", "vector", "reaction",
    "specificity", "validation", "construct", "review",
]


class ValidationIssueDict(TypedDict):
    code: str
    severity: Severity
    ownerStep: OwnerStep
    fieldPath: str | None
    message: str
    source: str
    blocking: bool


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Machine-readable validation fact; prose is never a control signal."""

    code: str
    severity: Severity
    owner_step: OwnerStep
    field_path: str | None
    message: str
    source: str
    blocking: bool = True

    def to_dict(self) -> ValidationIssueDict:
        raw = asdict(self)
        return {
            "code": raw["code"],
            "severity": raw["severity"],
            "ownerStep": raw["owner_step"],
            "fieldPath": raw["field_path"],
            "message": raw["message"],
            "source": raw["source"],
            "blocking": raw["blocking"],
        }
