"""Primer3's account of what it threw away, turned into something readable.

Every run, Primer3 reports how many candidates it considered and how many died
of what:

    considered 4010, GC content failed 2, low tm 3524, high tm 127, ok 330

Almost every tool built on Primer3 discards this and prints "no primers found".
It is the difference between *there are no primers here* and *your constraints
were too tight*, and the second one is fixable in five seconds if anybody says
so. Parsing it costs about forty lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

#: `key value` pairs, comma separated, where the key contains spaces and the
#: value is always the trailing integer.
_ENTRY = re.compile(r"^(?P<reason>.+?)\s+(?P<count>\d+)$")

#: What each of Primer3's reasons means, and what a person could do about it.
#: Anything not listed here still gets counted and shown, just without advice —
#: a reason we have not seen before is not a reason to hide it.
ADVICE: dict[str, str] = {
    "low tm": "widen the melting-temperature window downwards",
    "high tm": "widen the melting-temperature window upwards",
    "GC content failed": "widen the GC range",
    "high hairpin stability": "allow a less stable hairpin, or pick a different region",
    "high any compl": "allow more self-complementarity",
    "high end compl": "allow more 3' self-complementarity",
    "high repeat similarity": "the region is repetitive — try a different target",
    "long poly-x seq": "allow a longer run of one base",
    "high 3' stability": "allow a less stable 3' end",
    "unacceptable product size": "widen the product size range",
    "high any compl pair": "allow more complementarity between the two primers",
    "high end compl pair": "allow more 3' complementarity between the two primers",
    "tm diff too large": "allow the two primers' melting temperatures to differ more",
    "no target": "the target region leaves no room for a primer on one side",
    "not in any ok region": "the allowed region is too narrow",
    "lowercase masking of 3' end": "the 3' end falls on masked sequence",
}

#: Not failures. Excluding them is what keeps "ok 330" out of a sentence about
#: why nothing worked.
NOT_A_FAILURE = frozenset({"considered", "ok"})


@dataclass(frozen=True)
class Rejection:
    """One reason candidates were discarded, and how many went that way."""

    reason: str
    count: int
    advice: str

    @property
    def share(self) -> float:
        """Filled in by the reader; kept for symmetry with the dict form."""
        return 0.0


@dataclass(frozen=True)
class Account:
    """What one stage of the search considered, and what became of it."""

    stage: str
    considered: int
    accepted: int
    rejections: tuple[Rejection, ...]

    def sentence(self) -> str:
        """One line a person can act on, or an empty string if there is nothing to say."""
        if not self.considered:
            return ""
        if not self.rejections:
            return f"{self.considered} {self.stage} considered, {self.accepted} acceptable."

        worst = self.rejections[0]
        share = round(100.0 * worst.count / self.considered)
        tail = f" — {worst.advice}" if worst.advice else ""
        return (
            f"{self.considered} {self.stage} considered, {self.accepted} acceptable. "
            f"The commonest refusal was {worst.reason} at {worst.count} "
            f"({share}%){tail}."
        )


def parse(explain: str, *, stage: str) -> Account:
    """Read one PRIMER_*_EXPLAIN string.

    Unparseable fragments are skipped rather than raised on: this is
    diagnostics, and diagnostics that can fail a run are worse than no
    diagnostics.
    """
    considered = 0
    accepted = 0
    rejections: list[Rejection] = []

    for fragment in (part.strip() for part in explain.split(",")):
        match = _ENTRY.match(fragment)
        if not match:
            continue
        reason = match.group("reason").strip()
        count = int(match.group("count"))

        if reason == "considered":
            considered = count
        elif reason == "ok":
            accepted = count
        elif count > 0:
            rejections.append(Rejection(reason=reason, count=count, advice=ADVICE.get(reason, "")))

    rejections.sort(key=lambda r: r.count, reverse=True)
    return Account(
        stage=stage,
        considered=considered,
        accepted=accepted,
        rejections=tuple(rejections),
    )


def account_to_dict(account: Account) -> dict[str, Any]:
    """The account as plain data, with each reason's share worked out."""
    return {
        "stage": account.stage,
        "considered": account.considered,
        "accepted": account.accepted,
        "sentence": account.sentence(),
        "rejections": [
            {
                "reason": r.reason,
                "count": r.count,
                "share": round(100.0 * r.count / account.considered, 1)
                if account.considered
                else 0.0,
                "advice": r.advice,
            }
            for r in account.rejections
        ],
    }


def why_nothing(accounts: list[Account]) -> str:
    """The single sentence to show when a run produced no pairs at all.

    Reads the stages in order and reports the first one that killed everything,
    because that is the constraint to loosen — telling somebody their product
    size range is wrong is no help when no primer passed the Tm filter either.
    """
    for account in accounts:
        if account.considered and not account.accepted and account.rejections:
            worst = account.rejections[0]
            tail = f" Try to {worst.advice}." if worst.advice else ""
            return (
                f"No {account.stage} survived. Of {account.considered} considered, "
                f"{worst.count} failed on {worst.reason}.{tail}"
            )

    for account in accounts:
        if account.considered and not account.accepted:
            return f"No {account.stage} survived out of {account.considered} considered."

    return (
        "Primer3 found no candidates at all, which usually means the template is "
        "too short for the product size that was asked for."
    )
