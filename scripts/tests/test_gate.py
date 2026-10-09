"""A failure or unavailable command must propagate through the single quality gate."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "project_gate.py"
SPEC = importlib.util.spec_from_file_location("project_quality_gate", SOURCE)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GATE
SPEC.loader.exec_module(GATE)


class GateFailureTests(unittest.TestCase):
    def run_with_result(self, results: list) -> dict:
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            target = Path(temporary)
            checks = [GATE.Check("first", ("first-tool",)), GATE.Check("second", ("second-tool",))]
            with patch.object(GATE, "ARTIFACTS", target), patch.object(GATE, "checks", return_value=checks), patch.object(GATE.subprocess, "run", side_effect=results) as runner:
                self.assertEqual(1, GATE.run_gate())
                self.assertEqual(2, runner.call_count)
            return json.loads((target / "gate.json").read_text())

    def test_failed_check_cannot_be_marked_passed(self) -> None:
        report = self.run_with_result([subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 0)])
        self.assertFalse(report["passed"])
        self.assertEqual(1, report["checks"][0]["exit_code"])

    def test_unavailable_tool_cannot_be_marked_passed(self) -> None:
        report = self.run_with_result([FileNotFoundError("unavailable"), subprocess.CompletedProcess([], 0)])
        self.assertFalse(report["passed"])
        self.assertEqual(127, report["checks"][0]["exit_code"])
