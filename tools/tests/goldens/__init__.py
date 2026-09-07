"""Recorded answers, so a change that was meant to be mechanical can prove it.

Most of this project's tests say what the code should do. A golden says what it
*did*, on a real sequence, on a day somebody looked at the answer and agreed
with it. That is a different and weaker claim, and it is worth making anyway:
when a shared engine is refactored under five assays, the only cheap way to
know nothing moved is to have written down where everything was.

What is recorded is the stable core -- the primer sequences, where they sit,
the product size, the score, and the shape of the funnel. Not every float:
a golden that breaks whenever a number moves in the third decimal place is a
golden nobody reads, and one nobody reads is one somebody regenerates without
looking.

Regenerate deliberately, never in passing:

    PCR_WRITE_GOLDENS=1 python -m pytest tests/test_goldens.py

and read the diff in the commit. A golden updated without a reason in the
commit message is the failure mode this whole idea has.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

HERE = pathlib.Path(__file__).parent


def reduce_result(answer: dict[str, Any]) -> dict[str, Any]:
    """The part of a result worth pinning.

    Sequences and positions, because those are what somebody orders. Scores,
    because the ranking is the product's opinion and a silent change to it is
    the most damaging thing that can happen quietly. The funnel's counts,
    because they are how a change in what was searched shows up.
    """
    return {
        "engine": answer.get("engine"),
        "assay": (answer.get("assay") or {}).get("id", ""),
        "purpose": (answer.get("purpose") or {}).get("id", ""),
        "constraints": answer.get("constraints", {}),
        "why_nothing": answer.get("why_nothing", ""),
        "stages": [
            {
                "key": stage["key"],
                "went_in": stage.get("went_in"),
                "came_out": stage.get("came_out"),
            }
            for stage in answer.get("stages", [])
        ],
        "pairs": [
            {
                "left": pair["left"]["sequence"],
                "right": pair["right"]["sequence"],
                "left_at": pair["left_at"]["start"],
                "right_at": pair["right_at"]["start"],
                "product_size": pair["product_size"],
                "score": round(float(pair["score"]), 2),
                "left_tm": round(float(pair["left"]["tm"]), 1),
                "right_tm": round(float(pair["right"]["tm"]), 1),
            }
            for pair in answer.get("pairs", [])
        ],
        "order_sheet": [oligo["name"] for oligo in answer.get("order_sheet", [])],
    }


def check(
    name: str,
    answer: dict[str, Any],
    *,
    reduced: dict[str, Any] | None = None,
) -> None:
    """Compare a run against its golden, or record one.

    Args:
        reduced: The stable core, when this engine's answer has a shape
            `reduce_result` does not know. A nested answer holds two pairs per
            design and an outward one holds a known span where a product size
            would be, so each supplies its own rather than being squeezed into
            a shape it does not have.

    Raises:
        AssertionError: naming the first thing that moved, rather than dumping
            two documents and leaving somebody to find it.
    """
    path = HERE / f"{name}.json"
    now = reduced if reduced is not None else reduce_result(answer)
    provenance = answer.get("provenance") or {}

    if os.environ.get("PCR_WRITE_GOLDENS") or not path.exists():
        path.write_text(
            json.dumps({"provenance": provenance, "result": now}, indent=2) + "\n",
            encoding="utf-8",
        )
        if not os.environ.get("PCR_WRITE_GOLDENS"):
            raise AssertionError(
                f"{name} had no golden, so this run was recorded as one. Read it, "
                "agree with it, and commit it -- or delete it and say why."
            )
        return

    recorded = json.loads(path.read_text(encoding="utf-8"))
    was, is_now = recorded["result"], now

    if was == is_now:
        return

    # A library that moved is a different situation from a result that moved,
    # and reporting them the same way trains people to regenerate goldens.
    stale = [
        key
        for key in ("primer3_py", "python", "worker", "model")
        if recorded.get("provenance", {}).get(key) != provenance.get(key)
    ]
    prefix = (
        f"{name} differs, and so does {', '.join(stale)} since it was recorded -- "
        "so this may be the library rather than the code. Check which before "
        "regenerating.\n"
        if stale
        else f"{name} differs from its golden.\n"
    )

    raise AssertionError(prefix + _first_difference(was, is_now))


def _first_difference(was: Any, now: Any, path: str = "") -> str:
    """Where two recorded answers stop agreeing, in words."""
    if isinstance(was, dict) and isinstance(now, dict):
        for key in sorted(set(was) | set(now)):
            if key not in was:
                return f"  {path}.{key} is new: {now[key]!r}"
            if key not in now:
                return f"  {path}.{key} is gone. It was {was[key]!r}"
            if was[key] != now[key]:
                return _first_difference(was[key], now[key], f"{path}.{key}")
        return "  (no difference found, which should not happen)"

    if isinstance(was, list) and isinstance(now, list):
        if len(was) != len(now):
            return f"  {path} was {len(was)} long and is now {len(now)}"
        for index, (before, after) in enumerate(zip(was, now)):
            if before != after:
                return _first_difference(before, after, f"{path}[{index}]")
        return "  (no difference found, which should not happen)"

    return f"  {path} was {was!r} and is now {now!r}"
