#!/usr/bin/env python3
"""Source-only guard for load-bearing Flanking Rust transport invariants.

This deliberately does not pretend to replace cargo/rustc. It protects the
cross-language serde boundary and catches accidental duplicate/syntactic
residue when native Rust qualification is delegated to the target Linux host.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "crates/pcr-core/src/engines/flanking_pair.rs"
TEXT = PATH.read_text(encoding="utf-8")
TEST_PATH = ROOT / "crates/pcr-core/src/engines/flanking_pair_tests.rs"
TEST_TEXT = TEST_PATH.read_text(encoding="utf-8") if TEST_PATH.is_file() else ""
GENERATED_PATH = ROOT / "crates/pcr-core/src/engines/flanking_protocol_ids.generated.rs"
GENERATED = GENERATED_PATH.read_text(encoding="utf-8") if GENERATED_PATH.is_file() else ""
NORMALIZED = re.sub(r"\s+", " ", TEXT)

checks = {
    "balanced-braces": TEXT.count("{") == TEXT.count("}"),
    "balanced-parentheses": TEXT.count("(") == TEXT.count(")"),
    "balanced-brackets": TEXT.count("[") == TEXT.count("]"),
    "single-digital-protocol-authority": (
        TEXT.count('include!("flanking_protocol_ids.generated.rs")') == 1
        and TEXT.count("const DIGITAL_PROTOCOLS") == 0
        and GENERATED.count("const DIGITAL_PROTOCOLS") == 1
    ),
    "public-camelcase-worker-snakecase": (
        re.search(
            r"#\[serde\(\s*rename_all\(deserialize = \"camelCase\", serialize = \"snake_case\"\),\s*deny_unknown_fields\s*\)\]",
            TEXT,
        ) is not None
    ),
    "worker-snakecase-regression": (
        'context["primer_each_nm"]' in TEXT + TEST_TEXT
        and 'context["rpa_temperature_c"]' in TEXT + TEST_TEXT
        and 'context.get("rpaTemperatureC").is_none()' in TEXT + TEST_TEXT
    ),
    "canonical-digital-consumable-matrix": (
        GENERATED.count("const DIGITAL_CONSUMABLE_IDS") == 1
        and GENERATED.count("const DIGITAL_CONSUMABLE_PLATFORM_PAIRS") == 1
        and "DIGITAL_CONSUMABLE_PLATFORM_PAIRS .iter() .any" in NORMALIZED
    ),
    "m0689-colony-direct-transfer-runtime": (
        '"neb-onetaq-m0689-colony"' in NORMALIZED
        and 'preparation == "direct-transfer"' in NORMALIZED
    ),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("Flanking Rust source-boundary check failed: " + ", ".join(failed))
print(
    "FLANKING_RUST_SOURCE_BOUNDARY=PASS "
    f"braces={TEXT.count('{')}/{TEXT.count('}')} "
    f"parens={TEXT.count('(')}/{TEXT.count(')')} "
    f"brackets={TEXT.count('[')}/{TEXT.count(']')}"
)
