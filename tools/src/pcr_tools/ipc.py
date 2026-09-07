"""Versioned Rust↔Python worker envelope for Generation 1 foundation.

The scientific request remains an engine-owned dictionary.  The process
boundary itself is no longer an unversioned JSON blob: protocol/schema/module
identity is validated before the handler or any external scientific tool runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from .runtime_contract import (
    COMMAND_TO_ENGINE,
    FOUNDATION,
    MODULE_TO_ENGINE,
)

IPC_PROTOCOL_VERSION = str(FOUNDATION["ipc_protocol_version"])
REQUEST_SCHEMA_VERSION = int(FOUNDATION["request_schema_version"])
RESULT_SCHEMA_VERSION = int(FOUNDATION["result_schema_version"])


class IpcError(ValueError):
    """Envelope failed before scientific computation began."""


class RequestEnvelopeDict(TypedDict):
    protocolVersion: str
    requestSchema: int
    resultSchema: int
    requestId: str
    command: str
    engine: str
    module: str | None
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RequestEnvelope:
    protocol_version: str
    request_schema: int
    result_schema: int
    request_id: str
    command: str
    engine: str
    module: str | None
    payload: dict[str, Any]


def _module_from_payload(payload: dict[str, Any]) -> str | None:
    assay = payload.get("assay")
    if isinstance(assay, dict):
        value = assay.get("id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_request(raw: Any, argv_command: str) -> RequestEnvelope:
    """Validate and unwrap one v2 request before any scientific handler runs."""
    if not isinstance(raw, dict):
        raise IpcError("worker IPC expects a JSON object")
    required = {
        "protocolVersion",
        "requestSchema",
        "resultSchema",
        "requestId",
        "command",
        "engine",
        "module",
        "payload",
    }
    missing = sorted(required - raw.keys())
    unknown = sorted(set(raw) - required)
    if missing:
        raise IpcError(f"worker IPC envelope is missing: {', '.join(missing)}")
    if unknown:
        raise IpcError(f"worker IPC envelope has unknown field(s): {', '.join(unknown)}")
    if raw["protocolVersion"] != IPC_PROTOCOL_VERSION:
        raise IpcError(
            f"worker IPC protocol mismatch: expected {IPC_PROTOCOL_VERSION}, got {raw['protocolVersion']!r}"
        )
    if raw["requestSchema"] != REQUEST_SCHEMA_VERSION:
        raise IpcError(
            f"worker request schema mismatch: expected {REQUEST_SCHEMA_VERSION}, got {raw['requestSchema']!r}"
        )
    if raw["resultSchema"] != RESULT_SCHEMA_VERSION:
        raise IpcError(
            f"worker result schema mismatch: expected {RESULT_SCHEMA_VERSION}, got {raw['resultSchema']!r}"
        )
    request_id = raw["requestId"]
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        raise IpcError("worker requestId must be 1..128 characters")
    command = raw["command"]
    if command != argv_command:
        raise IpcError(f"worker command mismatch: argv={argv_command!r}, envelope={command!r}")
    payload = raw["payload"]
    if not isinstance(payload, dict):
        raise IpcError("worker IPC payload must be an object")
    module = raw["module"]
    if module is not None and (not isinstance(module, str) or not module.strip()):
        raise IpcError("worker module must be a non-empty string or null")
    payload_module = _module_from_payload(payload)
    if module != payload_module:
        raise IpcError(
            f"worker module mismatch: envelope={module!r}, payload assay={payload_module!r}"
        )
    expected_engine = MODULE_TO_ENGINE.get(module or "") or COMMAND_TO_ENGINE.get(command)
    engine = raw["engine"]
    if not isinstance(engine, str) or not engine:
        raise IpcError("worker engine must be a non-empty string")
    if expected_engine and engine != expected_engine:
        raise IpcError(f"worker engine mismatch: expected {expected_engine!r}, got {engine!r}")
    return RequestEnvelope(
        protocol_version=IPC_PROTOCOL_VERSION,
        request_schema=REQUEST_SCHEMA_VERSION,
        result_schema=RESULT_SCHEMA_VERSION,
        request_id=request_id,
        command=command,
        engine=engine,
        module=module,
        payload=payload,
    )


def success(envelope: RequestEnvelope, payload: Any) -> dict[str, Any]:
    """Wrap a successful worker result in the negotiated protocol identity."""
    return {
        "protocolVersion": IPC_PROTOCOL_VERSION,
        "resultSchema": RESULT_SCHEMA_VERSION,
        "requestId": envelope.request_id,
        "ok": True,
        "payload": payload,
    }


def failure(
    request_id: str,
    kind: str,
    detail: str,
    *,
    code: str | None = None,
    stage: str = "worker-boundary",
    retryable: bool = False,
) -> dict[str, Any]:
    """Wrap a structured worker failure without leaking request sequence data."""
    return {
        "protocolVersion": IPC_PROTOCOL_VERSION,
        "resultSchema": RESULT_SCHEMA_VERSION,
        "requestId": request_id or "unbound",
        "ok": False,
        "error": {
            "code": code or f"WORKER_{kind.upper()}",
            "kind": kind,
            "detail": detail,
            "stage": stage,
            "retryable": retryable,
        },
    }
