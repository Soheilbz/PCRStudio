"""Content-addressed scientific authority identity attached to every design run."""
from __future__ import annotations
import json
from importlib.resources import files
from typing import Any

_RESOURCE = "data/scientific-authority-registry.generated.json"
_REGISTRY = json.loads(files("pcr_tools").joinpath(*_RESOURCE.split("/")).read_text(encoding="utf-8"))


def for_module(module_id: str | None) -> list[dict[str, Any]]:
    """Return immutable authority identities relevant to one canonical module."""
    if not module_id:
        return []
    rows = _REGISTRY.get("modules", {}).get(module_id)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"scientific authority registry has no entry for canonical module `{module_id}`")
    out=[]
    for row in rows:
        if not isinstance(row, dict) or not row.get("canonical_sha256") or not row.get("authority_id"):
            raise ValueError(f"scientific authority registry row for `{module_id}` is malformed")
        out.append(dict(row))
    return out
