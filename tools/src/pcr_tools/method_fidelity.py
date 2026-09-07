"""Canonical method-fidelity declarations and Scientific-Strict enforcement."""
from __future__ import annotations
import json
from importlib.resources import files
from typing import Any

_RESOURCE = "data/method-fidelity.generated.json"
_REGISTRY = json.loads(files("pcr_tools").joinpath(*_RESOURCE.split("/")).read_text(encoding="utf-8"))

class MethodFidelityError(ValueError):
    """A named-method claim would exceed the declared fidelity authority."""

def _row(method_id: str, *, use_role: str) -> dict[str, Any]:
    raw = _REGISTRY.get("methods", {}).get(method_id)
    if not isinstance(raw, dict):
        raise MethodFidelityError(f"method fidelity registry missing `{method_id}`")
    return {"method_id": method_id, "use_role": use_role, **raw}

def _roles_for_module(module_id: str | None) -> dict[str, list[str]]:
    if not module_id:
        return {}
    roles = _REGISTRY.get("module_method_roles", {}).get(module_id)
    if not isinstance(roles, dict):
        raise MethodFidelityError(f"method fidelity registry has no role map for `{module_id}`")
    return {str(role): [str(v) for v in values] for role, values in roles.items() if isinstance(values, list)}

def declarations_for_module(module_id: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for role, ids in _roles_for_module(module_id).items():
        out.extend(_row(method_id, use_role=role) for method_id in ids)
    return out

def references_for_module(module_id: str | None) -> list[dict[str, Any]]:
    roles = _roles_for_module(module_id)
    return [_row(method_id, use_role="reference") for method_id in roles.get("references", [])]

def active_for_run(module_id: str | None, command: str, request: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    roles = _roles_for_module(module_id)
    ids: list[tuple[str, str]] = [(m, "active") for m in roles.get("active", [])]
    ids += [(m, "diagnostic") for m in roles.get("diagnostic", [])]
    ids += [(m, "required-followup") for m in roles.get("required_followup", [])]

    # Branch-specific named methods are recorded only when that branch was actually selected.
    if module_id == "qpcr-probe" and result.get("mgb_authority"):
        ids.append(("mgb-tm", "active-external-authority"))
    if module_id == "site-directed-mutagenesis":
        topology = str(result.get("topology") or request.get("mutagenesis_topology") or request.get("topology") or "")
        protocol = str((result.get("protocol") or {}).get("selection") or request.get("post_amplification_protocol") or "")
        if "q5" in topology or "Q5" in protocol:
            ids.append(("q5-manual", "active"))
        elif "quikchange" in topology.lower() or "QuikChange" in protocol:
            ids.append(("quikchange-lightning-manual", "active"))
        elif "nebuilder" in topology.lower() or "NEBuilder" in protocol:
            ids.append(("pcrstudio-nebuilder-multisite-route", "active-routing"))
    if module_id == "tiled-scheme":
        backend = str(result.get("backend") or request.get("backend") or "").lower()
        if "primal" in backend or backend == "compare":
            ids.append(("primalscheme3", "active-upstream"))
        if "olivar" in backend or backend == "compare":
            ids.append(("olivar", "active-upstream"))
    if module_id == "inverse-pcr" and result.get("topology_validation", {}).get("pydna"):
        ids.append(("pydna", "active-upstream"))

    if command == "multiplex":
        context = _REGISTRY.get("contexts", {}).get("generic-multiplex", {})
        ids.extend((m, "active") for m in context.get("active", []))
        selection = result.get("selection_method") if isinstance(result.get("selection_method"), dict) else {}
        optimizer = str(selection.get("optimizer") or "")
        if optimizer == "pcrstudio-exact-lexicographic-branch-and-bound":
            ids.append(("pcrstudio-multiplex-exact-search", "active"))
        else:
            ids.append(("pcrstudio-multiplex-local-optimizer", "active"))

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for method_id, role in ids:
        if method_id in seen:
            continue
        seen.add(method_id)
        out.append(_row(method_id, use_role=role))
    return out

def context_references(context_id: str) -> list[dict[str, Any]]:
    context = _REGISTRY.get("contexts", {}).get(context_id, {})
    if not isinstance(context, dict):
        return []
    return [_row(str(method_id), use_role="reference") for method_id in context.get("references", [])]

def enforce_scientific_strict(rows: list[dict[str, Any]], *, context: str) -> None:
    from .scientific_integrity import strict
    if not strict():
        return
    blocked = [row for row in rows if row.get("use_role", "").startswith("active") and row.get("scientific_strict_eligible") is False]
    if not blocked:
        return
    names = ", ".join(f"{row['method_id']} ({row['grade']})" for row in blocked)
    raise MethodFidelityError(
        f"Scientific-Strict refuses `{context}` because its active primary method fidelity is insufficient: {names}. "
        "Select an F0/F1/F2 authority path or run the explicitly labelled development/diagnostic method outside Scientific-Strict; PCRStudio will not impersonate the named method."
    )

def registry_identity() -> dict[str, str]:
    projection = _REGISTRY.get("_projection", {})
    return {
        "registry_id": str(_REGISTRY.get("registry_id") or ""),
        "registry_schema_version": str(_REGISTRY.get("schema_version") or ""),
        "canonical_sha256": str(projection.get("canonical_sha256") or ""),
    }
