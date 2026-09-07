from __future__ import annotations

import subprocess
import sys

import pytest

from pcr_tools.process_boundary import (
    ProcessOutputLimitExceeded,
    ProcessTransportError,
    run_bounded_text,
)


def test_bounded_process_preserves_complete_output() -> None:
    result = run_bounded_text(
        [sys.executable, "-c", "import sys; print('ok'); print('warn', file=sys.stderr)"],
        timeout=5,
        stdout_limit=1024,
        stderr_limit=1024,
    )
    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert result.stderr == "warn\n"


def test_bounded_process_fails_on_first_byte_beyond_limit() -> None:
    with pytest.raises(ProcessOutputLimitExceeded) as exc:
        run_bounded_text(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1025); sys.stdout.flush()"],
            timeout=5,
            stdout_limit=1024,
            stderr_limit=1024,
        )
    assert exc.value.stream == "stdout"


def test_bounded_process_avoids_stdin_stdout_pipe_deadlock() -> None:
    payload = "x" * (2 * 1024 * 1024)
    result = run_bounded_text(
        [sys.executable, "-c", "import sys; sys.stdout.write('y' * 200000); sys.stdout.flush(); data=sys.stdin.read(); print(len(data))"],
        input_text=payload,
        timeout=10,
        stdout_limit=1024 * 1024,
        stderr_limit=1024,
    )
    assert result.returncode == 0
    assert result.stdout.endswith(f"{len(payload)}\n")


def test_bounded_process_preserves_timeout() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        run_bounded_text(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.1,
            stdout_limit=1024,
            stderr_limit=1024,
        )


def test_bounded_process_rejects_incomplete_stdin_transport() -> None:
    payload = "x" * (8 * 1024 * 1024)
    with pytest.raises(ProcessTransportError) as exc:
        run_bounded_text(
            [
                sys.executable,
                "-c",
                "import os, time; os.close(0); time.sleep(0.2)",
            ],
            input_text=payload,
            timeout=5,
            stdout_limit=1024,
            stderr_limit=1024,
        )
    assert exc.value.phase == "stdin"


def test_write_all_handles_short_progress_until_payload_is_complete() -> None:
    from pcr_tools.process_boundary import _write_all

    class ShortWriter:
        def __init__(self) -> None:
            self.data = bytearray()
            self.flushed = False

        def write(self, payload) -> int:
            count = min(3, len(payload))
            self.data.extend(bytes(payload[:count]))
            return count

        def flush(self) -> None:
            self.flushed = True

    writer = ShortWriter()
    _write_all(writer, b"abcdefghij")
    assert bytes(writer.data) == b"abcdefghij"
    assert writer.flushed is True


@pytest.mark.skipif(sys.platform != "linux", reason="production process-group contract is Linux-specific")
def test_bounded_process_reaps_grandchild_after_wrapper_exits() -> None:
    import os
    import time

    result = run_bounded_text(
        [
            sys.executable,
            "-c",
            (
                "import subprocess,sys; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                "print(child.pid, flush=True)"
            ),
        ],
        timeout=5,
        stdout_limit=1024,
        stderr_limit=1024,
    )
    grandchild = int(result.stdout.strip())

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        stat = f"/proc/{grandchild}/stat"
        try:
            state = open(stat, encoding="utf-8").read().split()[2]
        except (FileNotFoundError, ProcessLookupError):
            return
        if state == "Z":
            return
        time.sleep(0.02)

    # The process should not survive the request boundary in a runnable state.
    os.kill(grandchild, 0)
    pytest.fail(f"grandchild process {grandchild} survived bounded process cleanup")
