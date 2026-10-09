"""Pure platform contract helpers; no scientific runtime or business authority."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any


def _check_json(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite values are not valid contract JSON.")
        return
    if isinstance(value, list):
        for item in value:
            _check_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _check_json(item)
        return
    raise ValueError("Contract values must be JSON with string object keys.")


def canonical_json(value: Any) -> str:
    _check_json(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True, slots=True)
class FrozenInput:
    """String storage makes nested caller mutation unable to change a snapshot."""

    document: str
    sha256: str

    def __post_init__(self) -> None:
        if hashlib.sha256(self.document.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("Snapshot digest does not match its document.")
        if not isinstance(json.loads(self.document), dict):
            raise ValueError("An execution snapshot must be a JSON object.")

    @classmethod
    def create(cls, request: dict[str, Any]) -> FrozenInput:
        if not isinstance(request, dict):
            raise ValueError("An execution request must be a JSON object.")
        document = canonical_json(request)
        return cls(document, hashlib.sha256(document.encode("utf-8")).hexdigest())

    def decoded(self) -> dict[str, Any]:
        # A fresh decoded value never mutates the sealed representation.
        return json.loads(self.document)  # type: ignore[no-any-return]


def check_local_schema(schema: dict[str, Any]) -> None:
    """Never let a capability schema retrieve attacker-controlled remote refs."""

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef") and (
                    not isinstance(item, str) or not item.startswith("#")
                ):
                    raise ValueError("Capability schema references must be local.")
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(schema)
