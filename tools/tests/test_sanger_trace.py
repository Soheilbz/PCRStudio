from __future__ import annotations

import base64

import pytest

from pcr_tools.sanger_trace import SangerTraceError, _longest_q20, parse_ab1_base64


def test_q20_interval_is_longest_contiguous_run():
    assert _longest_q20([5, 20, 21, 22, 7, 30, 31]) == {"start": 1, "end": 4, "length": 3}


def test_non_abif_payload_fails_closed():
    raw = base64.b64encode(b"not-an-abif-file").decode("ascii")
    with pytest.raises(SangerTraceError):
        parse_ab1_base64(raw, filename="bad.ab1")


def test_trace_review_has_a_hard_input_bound():
    oversized = base64.b64encode(b"A" * (4 * 1024 * 1024 + 1)).decode("ascii")
    with pytest.raises(SangerTraceError, match="4 MiB"):
        parse_ab1_base64(oversized)
