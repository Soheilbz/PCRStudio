"""A real Gunicorn worker timeout must not emit request or exception content."""
from __future__ import annotations

import importlib.util
import logging
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("safe_server_logging", ROOT / "ops/safe_gunicorn.py")
assert SPEC and SPEC.loader
SERVER_LOGGING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER_LOGGING)


class ServerLoggingTests(unittest.TestCase):
    def test_filter_discards_preformatted_exception_and_stack_content(self) -> None:
        marker = "synthetic-exception-privacy-probe"
        record = logging.LogRecord("gunicorn.error", logging.ERROR, __file__, 1, f"request?value={marker}", (), None)
        record.exc_text = marker
        record.stack_info = marker
        self.assertTrue(SERVER_LOGGING.ConfidentialServerFilter().filter(record))
        self.assertEqual("server.event", record.getMessage())
        self.assertIsNone(record.exc_text)
        self.assertIsNone(record.stack_info)

    def test_real_timeout_keeps_neutral_diagnostic_and_discards_query(self) -> None:
        marker = "synthetic-query-privacy-probe"
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "application.py").write_text(
                "import time\n"
                "def application(environ, start_response):\n"
                "    if environ['PATH_INFO'] != '/health/': time.sleep(5)\n"
                "    start_response('200 OK', [('Content-Type', 'text/plain')])\n"
                "    return [b'ok']\n"
            )
            process = subprocess.Popen(
                (sys.executable, "-m", "gunicorn", "application:application", "--bind", f"127.0.0.1:{port}", "--workers", "1", "--timeout", "1", "--graceful-timeout", "1", "--access-logfile", "/dev/null", "--error-logfile", "-", "--logger-class", "ops.safe_gunicorn.SafeLogger"),
                cwd=temporary,
                env={**os.environ, "PYTHONPATH": str(ROOT)},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                for _attempt in range(50):
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/health/", timeout=1):
                            break
                    except (URLError, TimeoutError):
                        if process.poll() is not None:
                            self.fail("Isolated Gunicorn process failed to start")
                        time.sleep(0.05)
                else:
                    self.fail("Isolated Gunicorn readiness timed out")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/?confidential={marker}", timeout=5):
                        pass
                except (URLError, TimeoutError, ConnectionError):
                    pass
            finally:
                process.terminate()
                try:
                    captured, _ = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    captured, _ = process.communicate(timeout=5)
            self.assertTrue('"event":"worker.timeout"' in captured, "Neutral timeout diagnostic missing")
            self.assertTrue(marker not in captured, "Query content appeared in Gunicorn operational logs")
