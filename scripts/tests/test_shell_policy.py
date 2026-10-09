"""The edge must serve exactly the script permissions required by its built shell."""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "verify_operations.py"
SPEC = importlib.util.spec_from_file_location("live_operations", SOURCE)
assert SPEC and SPEC.loader
OPERATIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPERATIONS)


class ShellPolicyTests(unittest.TestCase):
    def test_served_shell_requires_exact_inline_permission(self) -> None:
        content = "window.syntheticBoot = 1;"
        digest = base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
        policy = f"default-src 'self'; script-src 'self' 'sha256-{digest}';"
        OPERATIONS.verify_shell_policy(f'<script src="/assets/app.js"></script><script>{content}</script>', policy)
        for changed in (policy.replace(digest, "stale"), policy.replace(" 'sha256-", " 'sha256-extra' 'sha256-"), "script-src 'self';"):
            with self.subTest(policy=changed), self.assertRaisesRegex(AssertionError, "hashes differ"):
                OPERATIONS.verify_shell_policy(f"<script>{content}</script>", changed)

    def test_arbitrary_inline_and_eval_permissions_fail(self) -> None:
        for source in ("'unsafe-inline'", "'unsafe-eval'", "*", "https:"):
            with self.subTest(source=source), self.assertRaisesRegex(AssertionError, "unsafe script policy"):
                OPERATIONS.verify_shell_policy("<script src='/assets/app.js'></script>", f"script-src 'self' {source};")
