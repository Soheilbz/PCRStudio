"""Two synthetic capabilities prove the seam does not assume old engine fields."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pcrstudio_contract_snapshot", ROOT / "snapshot.py")
assert SPEC and SPEC.loader
SNAPSHOT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SNAPSHOT
SPEC.loader.exec_module(SNAPSHOT)


@pytest.fixture
def envelope() -> dict:
    return {
        "contract_version": "pcrstudio.execution.v1",
        "run_id": str(uuid4()),
        "attempt_id": str(uuid4()),
        "capability_id": "test.echo",
        "capability_version": "1",
        "input": {"message": "Synthetic fixture only"},
        "files": [],
        "limits": {"wall_seconds": 1, "memory_bytes": 1048576, "input_bytes": 4096, "output_bytes": 4096},
    }


def validator() -> Draft202012Validator:
    schema = json.loads((ROOT / "execution-request.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_mutating_caller_and_decoded_input_cannot_change_snapshot(envelope: dict) -> None:
    snapshot = SNAPSHOT.FrozenInput.create(envelope)
    envelope["input"]["message"] = "Changed later"
    decoded = snapshot.decoded()
    decoded["input"]["message"] = "Changed again"
    assert snapshot.decoded()["input"]["message"] == "Synthetic fixture only"
    assert SNAPSHOT.FrozenInput.create(snapshot.decoded()).sha256 == snapshot.sha256
    with pytest.raises(FrozenInstanceError):
        snapshot.document = "replaced"


def test_different_capability_shapes_share_only_envelope(envelope: dict) -> None:
    capabilities = (
        {"type": "object", "required": ["message"], "additionalProperties": False, "properties": {"message": {"type": "string"}}},
        {"type": "object", "required": ["values"], "additionalProperties": False, "properties": {"values": {"type": "array", "items": {"type": "integer"}}}},
    )
    for index, input_schema in enumerate(capabilities):
        SNAPSHOT.check_local_schema(input_schema)
        request = {**envelope, "capability_id": f"test.shape{index}", "input": ({"message": "synthetic"} if index == 0 else {"values": [1, 2]})}
        validator().validate(request)
        Draft202012Validator(input_schema).validate(request["input"])
        # A local test mock, never installed in the API runtime.
        response = {"simulation": True, "input_digest": SNAPSHOT.FrozenInput.create(request).sha256, "output": request["input"]}
        assert response["simulation"] is True
        assert response["output"] == request["input"]
    with pytest.raises(ValidationError):
        Draft202012Validator(capabilities[1]).validate(envelope["input"])


@pytest.mark.parametrize("field,value", [("run_id", "invalid"), ("contract_version", "legacy"), ("capability_id", "../file")])
def test_rejects_invalid_contract_identity(envelope: dict, field: str, value: str) -> None:
    envelope[field] = value
    with pytest.raises(ValidationError):
        validator().validate(envelope)


def test_rejects_unbounded_resources_and_account_credentials(envelope: dict) -> None:
    envelope["limits"]["wall_seconds"] = 0
    with pytest.raises(ValidationError):
        validator().validate(envelope)
    envelope["limits"]["wall_seconds"] = 1
    envelope["browser_session"] = "must-not-cross-executor-boundary"
    with pytest.raises(ValidationError):
        validator().validate(envelope)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "not-a-JSON-key"}, object()])
def test_rejects_ambiguous_or_non_json_input(value: object) -> None:
    with pytest.raises(ValueError):
        SNAPSHOT.canonical_json(value)


def test_digest_includes_version_and_file_references(envelope: dict) -> None:
    first = SNAPSHOT.FrozenInput.create(envelope)
    envelope["capability_version"] = "2"
    assert SNAPSHOT.FrozenInput.create(envelope).sha256 != first.sha256
    envelope["files"] = [{"id": str(uuid4()), "version": 1, "sha256": "a" * 64, "size_bytes": 2}]
    validator().validate(envelope)
    assert SNAPSHOT.FrozenInput.create(envelope).sha256 != first.sha256


def test_snapshot_cannot_be_constructed_with_a_forged_digest(envelope: dict) -> None:
    snapshot = SNAPSHOT.FrozenInput.create(envelope)
    with pytest.raises(ValueError):
        SNAPSHOT.FrozenInput(snapshot.document, "0" * 64)


@pytest.mark.parametrize("keyword", ["$ref", "$dynamicRef"])
def test_capability_schema_cannot_fetch_network_or_filesystem(keyword: str) -> None:
    with pytest.raises(ValueError):
        SNAPSHOT.check_local_schema({"properties": {"x": {keyword: "https://example.invalid/private"}}})
    SNAPSHOT.check_local_schema({"$defs": {"word": {"type": "string"}}, "properties": {"x": {keyword: "#/$defs/word"}}})
