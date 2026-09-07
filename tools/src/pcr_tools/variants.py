"""Versioned variant normalization and junction-aware genotyping helpers.

This module keeps variant identity separate from allele-specific primer heuristics.
Coordinates are zero-based boundaries/indices in the submitted reference sequence;
all outputs carry the reference provenance supplied by the caller.  Non-SNV
variants are never coerced to a single base without recording the reduction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .design import clean_template

VARIANT_KINDS = (
    "snv",
    "mnv",
    "insertion",
    "deletion",
    "complex-replacement",
    "presence-absence",
)


class VariantError(ValueError):
    pass


@dataclass(frozen=True)
class PrimerVariantMask:
    """Coordinates from supplied variant masking that fall under one primer."""

    positions: tuple[int, ...] = ()
    from_three_prime: tuple[int, ...] = ()

    @property
    def overlaps(self) -> bool:
        return bool(self.positions)

    @property
    def fatal(self) -> bool:
        return self.overlaps

    def to_dict(self) -> dict[str, Any]:
        return {
            "overlaps": self.overlaps,
            "fatal": self.fatal,
            "positions": list(self.positions),
            "from_three_prime": list(self.from_three_prime),
            "policy": "avoid-any-supplied-variant-under-primer",
        }


@dataclass(frozen=True)
class NormalizedVariant:
    kind: str
    at: int
    ref: str
    alt: str
    reference_accession: str | None = None
    assembly: str | None = None
    coordinate_system: str = "0-based-reference"
    strand: str = "plus"
    rsid: str | None = None
    source: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "at": self.at,
            "ref": self.ref,
            "alt": self.alt,
            "reference_accession": self.reference_accession,
            "assembly": self.assembly,
            "coordinate_system": self.coordinate_system,
            "strand": self.strand,
            "rsid": self.rsid,
            "source": self.source,
        }


def infer_kind(ref: str, alt: str) -> str:
    if len(ref) == len(alt) == 1:
        return "snv"
    if len(ref) == len(alt) and len(ref) > 1:
        return "mnv"
    if not ref and alt:
        return "insertion"
    if ref and not alt:
        return "deletion"
    if ref != alt:
        return "complex-replacement"
    raise VariantError("REF and ALT describe no change")


def normalize_variant(request: dict[str, Any], template: str) -> NormalizedVariant:
    """Normalize current single-base fields or the richer ``variant`` object.

    Historical ``at`` + ``alleles`` requests remain valid and become an SNV.
    Rich variants require exact REF/ALT and retain reference-build provenance.
    """
    sequence = clean_template(template)
    raw = request.get("variant")
    if raw is None:
        alleles = request.get("alleles")
        at = request.get("at")
        if not isinstance(alleles, list):
            raise VariantError("variant or historical at+two alleles is required")
        if len(alleles) != 2:
            raise VariantError("historical allele input requires exactly two alleles")
        if at is None:
            raise VariantError(
                "nothing sensible to default: historical allele input requires an explicit `at` coordinate"
            )
        ref, alt = (str(alleles[0]).upper(), str(alleles[1]).upper())
        raw = {"kind": "snv", "at": at, "ref": ref, "alt": alt}
    if not isinstance(raw, dict):
        raise VariantError("variant must be an object")
    at = raw.get("at", raw.get("position"))
    if isinstance(at, bool) or not isinstance(at, int):
        raise VariantError("variant.at must be a zero-based integer")
    ref = str(raw.get("ref") or "").upper().replace("U", "T")
    alt = str(raw.get("alt") or "").upper().replace("U", "T")
    kind = str(raw.get("kind") or raw.get("type") or infer_kind(ref, alt))
    if kind not in VARIANT_KINDS:
        raise VariantError("variant.kind must be one of: " + ", ".join(VARIANT_KINDS))
    if any(base not in "ACGT" for base in ref + alt):
        raise VariantError("variant REF/ALT must be unambiguous A/C/G/T sequence")
    if kind == "snv" and not (len(ref) == len(alt) == 1):
        raise VariantError("SNV requires one-base REF and ALT")
    if kind == "mnv" and not (len(ref) == len(alt) and len(ref) > 1):
        raise VariantError("MNV requires equal-length multi-base REF and ALT")
    if kind == "insertion" and not (not ref and alt):
        raise VariantError("insertion uses empty REF and non-empty ALT at a reference boundary")
    if kind == "deletion" and not (ref and not alt):
        raise VariantError("deletion uses non-empty REF and empty ALT")
    if kind == "presence-absence" and not (ref and not alt):
        raise VariantError(
            "presence-absence uses the submitted reference as the present allele: "
            "REF must contain the non-empty present sequence and ALT must be empty. "
            "Use insertion when the submitted reference is the absence allele."
        )
    if ref == alt:
        raise VariantError("REF and ALT are identical")
    if at < 0 or at > len(sequence):
        raise VariantError("variant coordinate lies outside the reference template")
    if ref:
        if at + len(ref) > len(sequence):
            raise VariantError("variant REF extends beyond the reference template")
        observed = sequence[at : at + len(ref)]
        if observed != ref:
            raise VariantError(
                f"reference template reads {observed!r} at the declared locus, not REF {ref!r}"
            )
    coordinate_system = str(
        raw.get("coordinate_system") or raw.get("coordinateSystem") or "0-based-reference"
    )
    if coordinate_system not in {"0-based-reference", "0-based-half-open"}:
        raise VariantError("only explicit zero-based reference coordinate systems are executable")
    strand = str(raw.get("strand") or "plus")
    if strand not in {"plus", "minus"}:
        raise VariantError("variant.strand must be plus or minus")
    return NormalizedVariant(
        kind=kind,
        at=at,
        ref=ref,
        alt=alt,
        reference_accession=(
            str(raw.get("reference_accession") or raw.get("referenceAccession") or "").strip()
            or None
        ),
        assembly=(str(raw.get("assembly") or "").strip() or None),
        coordinate_system=coordinate_system,
        strand=strand,
        rsid=(str(raw.get("rsid") or raw.get("rsId") or "").strip() or None),
        source=(str(raw.get("source") or "").strip() or None),
    )


def allele_sequences(reference: str, variant: NormalizedVariant) -> tuple[str, str]:
    sequence = clean_template(reference)
    ref_seq = sequence
    alt_seq = sequence[: variant.at] + variant.alt + sequence[variant.at + len(variant.ref) :]
    return ref_seq, alt_seq


def differing_anchor(variant: NormalizedVariant) -> dict[str, Any] | None:
    """Return a transparent single-base reduction when equal-length alleles permit it."""
    if not variant.ref or not variant.alt or len(variant.ref) != len(variant.alt):
        return None
    diffs = [i for i, (a, b) in enumerate(zip(variant.ref, variant.alt, strict=True)) if a != b]
    if not diffs:
        return None
    # Prefer the variant edge closest to an allele-specific 3' terminus. This is
    # a deterministic candidate-policy choice, not a claim that it is optimal.
    offset = diffs[-1]
    return {
        "at": variant.at + offset,
        "alleles": [variant.ref[offset], variant.alt[offset]],
        "offset_within_variant": offset,
        "other_differences": [variant.at + i for i in diffs if i != offset],
        "policy": "rightmost-differing-base-single-anchor",
        "claim_boundary": "Full REF/ALT is retained. The current ARMS/Tetra/KASP SNV geometry is anchored on one exact differing base; other differences are evidence/masking context, not discarded variant identity.",
    }


def parse_vcf_mask(
    text: str | None, *, reference_accession: str | None = None
) -> list[dict[str, Any]]:
    """Parse a small caller-supplied VCF into zero-based nearby-variant masks.

    This is intentionally an offline parser. It does not infer population
    frequency, fetch dbSNP, or silently change reference assemblies.
    """
    if not text:
        return []
    out: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 5:
            raise VariantError(f"nearby VCF line {line_no} has fewer than five columns")
        chrom, pos, vid, ref, alt = fields[:5]
        try:
            pos0 = int(pos) - 1
        except ValueError as exc:
            raise VariantError(f"nearby VCF line {line_no} POS is not an integer") from exc
        out.append(
            {
                "chrom": chrom,
                "at": pos0,
                "id": vid if vid != "." else None,
                "ref": ref,
                "alt": alt.split(","),
                "reference_accession": reference_accession,
            }
        )
    return out


def parse(values: Any, *, length: int) -> list[int]:
    """Validate the legacy coordinate-only variant-mask request."""
    if values in (None, ""):
        return []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise VariantError("known variant coordinates must be an integer array")
    parsed: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise VariantError("known variant coordinates must be integers")
        if value < 0 or value >= length:
            raise VariantError(
                f"known variant coordinate {value} lies outside the template of length {length}"
            )
        parsed.append(value)
    return sorted(set(parsed))


def _mask(
    start: int,
    length: int,
    variants: Sequence[int],
    *,
    circular_length: int | None,
    reverse: bool,
) -> PrimerVariantMask:
    if length < 0:
        raise VariantError("primer length cannot be negative")
    if circular_length is not None and circular_length <= 0:
        raise VariantError("circular template length must be positive")
    supplied = set(variants)
    positions: list[int] = []
    distances: list[int] = []
    for distance in range(length):
        coordinate = start - distance if reverse else start + distance
        if circular_length is not None:
            coordinate %= circular_length
        if coordinate in supplied:
            positions.append(coordinate)
            distances.append(distance if reverse else length - 1 - distance)
    return PrimerVariantMask(tuple(positions), tuple(distances))


def under_left(
    start: int,
    length: int,
    variants: Sequence[int],
    *,
    circular_length: int | None = None,
) -> PrimerVariantMask:
    """Return supplied variant coordinates under a forward-facing primer."""
    return _mask(start, length, variants, circular_length=circular_length, reverse=False)


def under_right(
    start: int,
    length: int,
    variants: Sequence[int],
    *,
    circular_length: int | None = None,
) -> PrimerVariantMask:
    """Return supplied variant coordinates under a reverse-facing primer."""
    return _mask(start, length, variants, circular_length=circular_length, reverse=True)


def not_assessed() -> tuple[float, str]:
    return 0.0, "Not assessed. No supplied variant coordinates were provided."


def summary(
    variants: Sequence[int],
    *,
    considered: int,
    rejected: int,
) -> dict[str, Any]:
    checked = bool(variants)
    return {
        "checked": checked,
        "supplied": len(variants),
        "coordinates": list(variants),
        "considered": considered,
        "rejected": rejected,
        "policy": "avoid-any-supplied-variant-under-primer" if checked else None,
    }
