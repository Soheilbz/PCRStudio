#!/usr/bin/env python3
"""Run the unified engine acceptance suite on the canonical Linux host."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from acceptance_common import *  # noqa: F403

ROOT = Path(__file__).resolve().parents[1]

PYTHON_CASES = [
    ("consensus-panel-formulation-boundary", ["tools/tests/test_universal.py", "tools/tests/test_engine_contract_regressions.py"], None),
    ("kasp-plus-minus-endpoint-boundary", ["tools/tests/test_discriminate.py", "tools/tests/test_kasp.py", "tools/tests/test_engine_contract_regressions.py"], None),
    ("junction-gibson-nebuilder-separation", ["tools/tests/test_junction.py", "tools/tests/test_engine_contract_regressions.py"], None),
    ("mutagenic-topology-input-separation", ["tools/tests/test_mutagenic.py", "tools/tests/test_engine_contract_regressions.py"], None),
    ("nested-two-round-transfer-causality", ["tools/tests/test_nested.py", "tools/tests/test_engine_contract_regressions.py"], None),
    ("inverse-topology-circle-boundary", ["tools/tests/test_inverse.py"], "test_standard_result_has_one_intact_anchor_circle_and_no_internal_cut or test_nonstandard_inverse_branch_is_not_silently_approximated"),
    ("qpcr-probe-independent-structure", ["tools/tests/test_probe.py", "tools/tests/test_engine_authority_contract.py"], "test_the_probe_temperature_reported_is_the_one_measured_in_the_reaction or test_qpcr_vendor_rules_are_not_internal_search_defaults or test_taqman_mgb_is_reference_only_until_mgb_aware_tm_authority_exists"),
    ("race-substrate-adapter-round-boundary", ["tools/tests/test_single.py", "tools/tests/test_engine_authority_contract.py"], "test_current_firstchoice_partners_are_exact_and_versioned or test_race_named_chemistry_and_adapter_cannot_cross_wire or test_firstchoice_is_versioned_and_smarter_remains_source_limited"),
    ("sanger-instrument-trace-boundary", ["tools/tests/test_single.py"], "test_named_bigdye_overlay_is_explicit_and_versioned or test_the_window_keeps_the_whole_target_inside_the_read"),
]

NATIVE_TILING_CASES = [
    ("tiling-scheme-create", "scheme-create"),
    ("tiling-panel-create", "panel-create"),
    ("tiling-repair-mode", "repair-mode"),
    ("tiling-scheme-replace", "scheme-replace"),
]


def logged(cmd: list[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    with log.open("w", encoding="utf-8") as stream:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=stream, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise SystemExit(f"Command failed ({proc.returncode}); evidence: {log}")


def main() -> None:
    ensure_linux()  # noqa: F405
    py = ROOT / "tools/.venv/bin/python"
    if not py.is_file():
        raise SystemExit("tools/.venv is required; run scripts/prepare-linux.py --sync-dependencies")
    for command in ("node", "cargo", "pnpm"):
        if not shutil.which(command):
            raise SystemExit(f"Required command unavailable: {command}")

    if not DEFAULT_RESULTS.is_file():  # noqa: F405
        bind_template(path=DEFAULT_RESULTS)  # noqa: F405
    doc = load(DEFAULT_RESULTS)  # noqa: F405
    assert_bound(doc)  # noqa: F405
    canonical = {row["id"] for row in load(ROOT / "knowledge/runtime/linux-integration-scenarios.json")["scenarios"]}  # noqa: F405

    for scenario_id, files, selector in PYTHON_CASES:
        if scenario_id not in canonical:
            raise SystemExit(f"Missing canonical integration scenario: {scenario_id}")
        log = ROOT / ".local/logs/acceptance/engines" / f"{scenario_id}.log"
        temp = ROOT / ".local/tmp" / f"engine-acceptance-{scenario_id}"
        cmd = [str(py), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *files]
        if selector:
            cmd += ["-k", selector]
        cmd += ["--basetemp", str(temp)]
        logged(cmd, log)
        doc["integration_scenarios"][scenario_id].update(
            status="pass",
            evidence=evidence(log, " ".join(cmd), selector or ",".join(files)),  # noqa: F405
            notes=["Unified engine Linux acceptance passed."],
        )

    for scenario_id, operation in NATIVE_TILING_CASES:
        if scenario_id not in canonical:
            raise SystemExit(f"Missing mandatory scenario: {scenario_id}")
        log = ROOT / ".local/logs/acceptance/engines" / f"{scenario_id}.log"
        output = log.with_suffix(".native.json")
        cmd = [str(py), "-B", "scripts/run-native-tiling-lifecycle-acceptance.py", "--operation", operation, "--output", str(output)]
        logged(cmd, log)
        doc["integration_scenarios"][scenario_id].update(
            status="pass",
            evidence=evidence(log, " ".join(cmd), f"native tiling lifecycle: {operation}"),  # noqa: F405
            notes=["Unified engine Linux native lifecycle acceptance passed."],
        )

    subprocess.run(["node", "scripts/check-engine-web-contract.js"], cwd=ROOT, check=True)
    subprocess.run(["cargo", "test", "--locked", "-p", "pcr-core", "--test", "engine_differential_contract"], cwd=ROOT, check=True)
    subprocess.run(["pnpm", "--filter", "web", "test", "--", "src/lib/engine-authorities.test.ts", "src/lib/projects/engine-transport-parity.test.ts"], cwd=ROOT, check=True)

    doc.update(executed_at=now(), host=host())  # noqa: F405
    save(DEFAULT_RESULTS, doc)  # noqa: F405
    print("ENGINE_ACCEPTANCE=PASS platform=linux")


if __name__ == "__main__":
    main()
