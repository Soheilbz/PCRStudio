#!/usr/bin/env python3
"""Source-only Rust-side consumer check for the shared LAMP differential corpus.

This does not claim native Rust compilation. It independently parses the
canonical LAMP authority, shared differential corpus and generated Rust
vocabulary so source qualification can detect Rust projection drift without a
Rust toolchain. The companion Cargo integration test executes the same contract
when native Rust qualification is available.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "contracts/chemistry/lamp-protocols.json"
CORPUS = ROOT / "contracts/chemistry/lamp-differential-corpus.json"
RUST = ROOT / "crates/pcr-core/src/engines/lamp_protocol_ids.generated.rs"


def fail(message: str) -> None:
    raise SystemExit(f"LAMP Rust differential contract FAILED: {message}")


def get(row: dict[str, object], *parts: str) -> object:
    cur: object = row
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            fail(f"missing canonical authority path: {'.'.join(parts)}")
        cur = cur[part]
    return cur


def numeric(row: dict[str, object], *parts: str) -> float:
    value = get(row, *parts)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        fail(f"canonical authority path is not finite numeric: {'.'.join(parts)}")
    return float(value)


def expect(actual: float, expected: object, label: str) -> None:
    if not isinstance(expected, (int, float)) or isinstance(expected, bool):
        fail(f"{label}: corpus expected value is not numeric")
    if not math.isclose(actual, float(expected), rel_tol=0.0, abs_tol=1e-12):
        fail(f"{label}: expected {expected}, got {actual}")


def rust_protocol_ids(text: str) -> set[str]:
    match = re.search(r'const LAMP_PROTOCOLS: &\[&str\] = &\[(.*?)\];', text, re.S)
    if not match:
        fail("generated Rust LAMP_PROTOCOLS constant not found")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def main() -> int:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    rust_ids = rust_protocol_ids(RUST.read_text(encoding="utf-8"))
    protocols = authority.get("protocols")
    if not isinstance(protocols, dict):
        fail("canonical protocols must be an object")
    canonical_ids = set(protocols)
    if rust_ids - {"not-selected"} != canonical_ids:
        missing = sorted(canonical_ids - rust_ids)
        extra = sorted((rust_ids - {"not-selected"}) - canonical_ids)
        fail(f"generated Rust protocol vocabulary drift missing={missing[:10]} extra={extra[:10]}")

    cases = corpus.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("differential corpus has no cases")
    for case in cases:
        if not isinstance(case, dict):
            fail("non-object differential case")
        case_id = str(case.get("id") or "<missing-id>")
        protocol_id = case.get("protocol")
        if not isinstance(protocol_id, str) or protocol_id not in rust_ids:
            fail(f"{case_id}: protocol absent from generated Rust vocabulary: {protocol_id}")
        protocol = protocols.get(protocol_id)
        if not isinstance(protocol, dict):
            fail(f"{case_id}: protocol absent from canonical authority")
        if protocol.get("sequence_decision_impact") != "none":
            fail(f"{case_id}: bench chemistry must not alter sequence ranking")

        values = case.get("expected_values")
        if not isinstance(values, dict):
            fail(f"{case_id}: expected_values must be an object")
        for key, expected in values.items():
            label = f"{case_id}/{key}"
            if key == "reaction_volume_uL":
                expect(numeric(protocol, "reaction_volume_uL"), expected, label)
            elif key == "hold_temperature_c":
                expect(numeric(protocol, "hold_temperature_c"), expected, label)
            elif key == "hold_time_min":
                expect(numeric(protocol, "hold_time_min"), expected, label)
            elif key in {"lyophilized_beads_per_reaction", "primer_mix_10x_uL"}:
                expect(numeric(protocol, "chemistry", key), expected, label)
            elif key == "fip_bip_uM":
                expect(numeric(protocol, "role_concentrations_uM", "FIP"), expected, label + "/FIP")
                expect(numeric(protocol, "role_concentrations_uM", "BIP"), expected, label + "/BIP")
            elif key == "f3_b3_uM":
                expect(numeric(protocol, "role_concentrations_uM", "F3"), expected, label + "/F3")
                expect(numeric(protocol, "role_concentrations_uM", "B3"), expected, label + "/B3")
            elif key == "loop_uM":
                expect(numeric(protocol, "role_concentrations_uM", "LF"), expected, label + "/LF")
                expect(numeric(protocol, "role_concentrations_uM", "LB"), expected, label + "/LB")
            else:
                fail(f"{case_id}: unmapped expected numeric key: {key}")

        unresolved = case.get("expected_unresolved")
        if not isinstance(unresolved, list):
            fail(f"{case_id}: expected_unresolved must be an array")
        for dependency in unresolved:
            if dependency == "vazyme-rp712-exact-recipe":
                status = str(protocol.get("numeric_authority_status") or "")
                snapshot = protocol.get("manual_metadata_snapshot") or {}
                boundary = str(snapshot.get("authority_boundary") or "") if isinstance(snapshot, dict) else ""
                if "exact" not in status.lower() or "unresolved" not in status.lower():
                    fail(f"{case_id}: RP712 must retain an explicit unresolved exact-recipe authority boundary")
                if "content-addressed" not in boundary.lower() or "not promoted" not in boundary.lower():
                    fail(f"{case_id}: RP712 manual snapshot must state the content-addressed promotion boundary")
                if isinstance(snapshot, dict) and snapshot.get("remote_document_sha256") not in (None, ""):
                    fail(f"{case_id}: RP712 must not claim a local document hash that is not part of the canonical source snapshot")
            else:
                fail(f"{case_id}: unknown unresolved dependency {dependency}")

        stages = case.get("expected_thermal_stage_ids")
        if not isinstance(stages, list):
            fail(f"{case_id}: expected_thermal_stage_ids must be an array")
        if "isothermal-amplification" in stages and "hold_time_min" not in protocol:
            fail(f"{case_id}: isothermal stage lacks canonical hold time")
        if "carryover-preincubation" in stages:
            scenario = case.get("python_scenario")
            if not isinstance(scenario, dict) or scenario.get("preincubation_strategy") != "takara-ung-25c-10min":
                fail(f"{case_id}: unsupported preincubation scenario")
            carry = protocol.get("carryover_prevention")
            if not isinstance(carry, dict) or not isinstance(carry.get("optional_pre_hold"), dict):
                fail(f"{case_id}: preincubation lacks canonical optional_pre_hold authority")

    print(f"LAMP Rust differential source contract PASS: cases={len(cases)} protocols={len(canonical_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
