"""Dependency-light digital-PCR quantification helpers.

These functions interpret *measured run evidence*. They never participate in
primer candidate generation/ranking. Partition volume and dilution are explicit
inputs because platform names alone do not establish the effective analysed
volume of a particular run.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


class DpcrQuantificationError(ValueError):
    pass


@dataclass(frozen=True)
class DpcrQuantification:
    accepted_partitions: int
    positive_partitions: int
    positive_fraction: float
    lambda_copies_per_partition: float
    copies_per_ul: float
    copies_per_reaction: float | None
    ci95_copies_per_ul: tuple[float, float]
    partition_volume_nl: float
    dilution_factor: float
    analysed_volume_ul: float | None
    method: str = "Poisson occupancy with Wilson-binomial 95% interval transformed to lambda"
    design_decision_impact: str = "none"

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    p = successes / total
    z2 = z * z
    den = 1.0 + z2 / total
    centre = (p + z2 / (2.0 * total)) / den
    half = z * math.sqrt((p * (1.0 - p) / total) + z2 / (4.0 * total * total)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def quantify_dpcr(
    *,
    accepted_partitions: int,
    positive_partitions: int,
    partition_volume_nl: float,
    dilution_factor: float = 1.0,
    analysed_volume_ul: float | None = None,
) -> DpcrQuantification:
    if isinstance(accepted_partitions, bool) or accepted_partitions <= 0:
        raise DpcrQuantificationError("accepted_partitions must be a positive integer")
    if isinstance(positive_partitions, bool) or not 0 <= positive_partitions <= accepted_partitions:
        raise DpcrQuantificationError(
            "positive_partitions must be between 0 and accepted_partitions"
        )
    if positive_partitions == accepted_partitions:
        raise DpcrQuantificationError(
            "all accepted partitions are positive; the run is saturated and finite Poisson concentration is unresolved"
        )
    if not math.isfinite(partition_volume_nl) or partition_volume_nl <= 0:
        raise DpcrQuantificationError("partition_volume_nl must be explicit, finite and >0")
    if not math.isfinite(dilution_factor) or dilution_factor <= 0:
        raise DpcrQuantificationError("dilution_factor must be finite and >0")
    if analysed_volume_ul is not None and (
        not math.isfinite(analysed_volume_ul) or analysed_volume_ul <= 0
    ):
        raise DpcrQuantificationError("analysed_volume_ul must be >0 when supplied")

    p = positive_partitions / accepted_partitions
    lam = -math.log1p(-p)
    partition_volume_ul = partition_volume_nl / 1000.0
    copies_per_ul = lam / partition_volume_ul * dilution_factor

    low_p, high_p = _wilson_interval(positive_partitions, accepted_partitions)
    low_lam = -math.log1p(-low_p)
    # high_p can mathematically reach 1 for tiny n; finite concentration then has no finite upper bound.
    high_lam = math.inf if high_p >= 1.0 else -math.log1p(-high_p)
    ci = (
        low_lam / partition_volume_ul * dilution_factor,
        high_lam / partition_volume_ul * dilution_factor,
    )
    copies_reaction = copies_per_ul * analysed_volume_ul if analysed_volume_ul is not None else None
    return DpcrQuantification(
        accepted_partitions=accepted_partitions,
        positive_partitions=positive_partitions,
        positive_fraction=p,
        lambda_copies_per_partition=lam,
        copies_per_ul=copies_per_ul,
        copies_per_reaction=copies_reaction,
        ci95_copies_per_ul=ci,
        partition_volume_nl=partition_volume_nl,
        dilution_factor=dilution_factor,
        analysed_volume_ul=analysed_volume_ul,
    )
