"""Bounded, shell-free subprocess execution for scientific process boundaries.

The standard ``subprocess.run(capture_output=True)`` buffers arbitrary child
output in memory before the caller can inspect or truncate it. Scientific tools
and helper workers are treated as untrusted process boundaries here: stdout and
stderr are drained concurrently, hard byte limits are enforced while the child
is running, and timeouts terminate the whole process group on POSIX.
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Sequence
from pathlib import Path


class ProcessOutputLimitExceeded(subprocess.SubprocessError):
    """A child exceeded the configured stdout/stderr byte ceiling."""

    def __init__(self, stream: str, limit: int):
        super().__init__(f"subprocess {stream} exceeded the {limit}-byte limit")
        self.stream = stream
        self.limit = limit


class ProcessTransportError(subprocess.SubprocessError):
    """The parent could not complete the bounded subprocess I/O exchange."""

    def __init__(self, phase: str, detail: str):
        super().__init__(f"subprocess {phase} transport failed: {detail}")
        self.phase = phase
        self.detail = detail


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the request process group even when its direct parent already exited.

    A native grandchild can outlive a wrapper while inheriting stdout/stderr.
    Checking only ``process.poll()`` therefore leaks the real computation and
    leaves pipe readers waiting forever. ``start_new_session=True`` gives every
    request its own POSIX process group, whose id remains the direct child's pid
    for as long as any descendant survives.
    """
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:  # pragma: no cover - production target is Linux
            process.kill()
    except ProcessLookupError:
        pass


def _write_all(pipe, payload: bytes) -> None:
    """Write a complete protocol payload, rejecting zero/short-progress stalls."""
    remaining = memoryview(payload)
    while remaining:
        written = pipe.write(remaining)
        if written is None or written <= 0:
            raise OSError("subprocess stdin write made no forward progress")
        remaining = remaining[written:]
    pipe.flush()


def run_bounded_text(
    command: Sequence[str],
    *,
    input_text: str | None = None,
    cwd: str | Path | None = None,
    timeout: float,
    stdout_limit: int,
    stderr_limit: int,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> subprocess.CompletedProcess[str]:
    """Run one argument-vector command with bounded concurrent I/O.

    Output limits are measured in bytes, before decoding. Crossing a limit is a
    hard failure rather than silent truncation because parsers must never consume
    a partial scientific result. ``shell`` is deliberately unavailable.
    """
    if stdout_limit < 0 or stderr_limit < 0:
        raise ValueError("output limits must be non-negative")
    argv = [str(part) for part in command]
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd is not None else None,
        shell=False,
        start_new_session=(os.name == "posix"),
    )
    assert process.stdout is not None
    assert process.stderr is not None

    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    totals = {"stdout": 0, "stderr": 0}
    exceeded: list[tuple[str, int]] = []
    transport_errors: list[tuple[str, str]] = []
    exceeded_event = threading.Event()
    lock = threading.Lock()

    def record_transport_error(phase: str, error: BaseException | str) -> None:
        with lock:
            transport_errors.append((phase, str(error)))

    def drain(name: str, pipe, limit: int) -> None:
        try:
            while True:
                block = pipe.read(64 * 1024)
                if not block:
                    return
                with lock:
                    totals[name] += len(block)
                    if totals[name] > limit:
                        if not exceeded:
                            exceeded.append((name, limit))
                        exceeded_event.set()
                        return
                    chunks[name].append(block)
        except (OSError, ValueError) as error:
            record_transport_error(name, error)
        finally:
            try:
                pipe.close()
            except OSError as error:
                record_transport_error(name, error)

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout, stdout_limit), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr, stderr_limit), daemon=True),
    ]
    for thread in readers:
        thread.start()

    writer: threading.Thread | None = None
    if input_text is not None:
        assert process.stdin is not None
        payload = input_text.encode(encoding, errors="strict")

        def write_input() -> None:
            try:
                _write_all(process.stdin, payload)
            except (BrokenPipeError, OSError) as error:
                record_transport_error("stdin", error)
            finally:
                try:
                    process.stdin.close()
                except OSError as error:
                    record_transport_error("stdin", error)

        writer = threading.Thread(target=write_input, daemon=True)
        writer.start()

    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while process.poll() is None:
            if exceeded_event.is_set():
                _terminate_group(process)
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _terminate_group(process)
                break
            try:
                process.wait(timeout=min(0.05, remaining))
            except subprocess.TimeoutExpired:
                pass
        process.wait()
    finally:
        # Kill the process group unconditionally. A wrapper may already have
        # exited while a native grandchild still owns the request's pipes.
        _terminate_group(process)
        if process.poll() is None:
            process.wait()
        if writer is not None:
            writer.join(timeout=1)
            if writer.is_alive():
                record_transport_error("stdin", "writer thread did not stop after child termination")
        for name, thread in zip(("stdout", "stderr"), readers, strict=True):
            thread.join(timeout=1)
            if thread.is_alive():
                record_transport_error(name, "reader thread did not reach EOF after child termination")

    if timed_out:
        raise subprocess.TimeoutExpired(argv, timeout)
    if exceeded:
        stream, limit = exceeded[0]
        raise ProcessOutputLimitExceeded(stream, limit)
    if transport_errors:
        phase, detail = transport_errors[0]
        raise ProcessTransportError(phase, detail)

    stdout = b"".join(chunks["stdout"]).decode(encoding, errors=errors)
    stderr = b"".join(chunks["stderr"]).decode(encoding, errors=errors)
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
