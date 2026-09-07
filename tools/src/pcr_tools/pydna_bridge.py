"""Tiny stdio bridge executed by PCRStudio's isolated scientific-tools Python.

It intentionally imports only pydna + stdlib so the main worker environment
never has to carry pydna's optional dependency graph. Input/output are one JSON
object and no user sequence is written outside the process.
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib.metadata import distribution


def _record_identity() -> dict[str, str | None]:
    dist = distribution("pydna")
    record = dist.read_text("RECORD") or ""
    return {
        "pydna_version": str(dist.version),
        "pydna_record_sha256": hashlib.sha256(record.encode("utf-8", "replace")).hexdigest() if record else None,
    }


def _sha(sequence: str) -> str:
    return hashlib.sha256(sequence.upper().encode("ascii", "replace")).hexdigest()


def _restriction_ligation(request: dict) -> dict:
    from Bio import Restriction
    from pydna.amplify import pcr
    from pydna.dseqrecord import Dseqrecord

    forward = str(request.get("forward") or "")
    reverse = str(request.get("reverse") or "")
    insert = str(request.get("template") or "")
    vector = str(request.get("vector") or "")
    forward_enzyme_name = str(request.get("forward_enzyme") or "")
    reverse_enzyme_name = str(request.get("reverse_enzyme") or "")
    if not all((forward, reverse, insert, vector, forward_enzyme_name, reverse_enzyme_name)):
        raise ValueError("forward, reverse, template, vector and both restriction enzymes are required")
    try:
        forward_enzyme = getattr(Restriction, forward_enzyme_name)
        reverse_enzyme = getattr(Restriction, reverse_enzyme_name)
    except AttributeError as error:
        raise ValueError(f"Bio.Restriction does not recognise selected enzyme: {error}") from error

    insert_record = Dseqrecord(insert, circular=False)
    vector_record = Dseqrecord(vector, circular=True)
    amplicon = pcr(forward, reverse, insert_record)
    insert_frags = amplicon.cut(forward_enzyme, reverse_enzyme)
    vector_frags = vector_record.cut(forward_enzyme, reverse_enzyme)

    insert_upper = insert.upper()
    rc_insert = str(Dseqrecord(insert_upper).reverse_complement().seq).upper()
    relevant_insert_frags = []
    for frag in insert_frags:
        sequence = str(frag.seq).upper()
        if insert_upper in sequence or rc_insert in sequence or len(frag) >= len(insert):
            relevant_insert_frags.append(frag)
    if not relevant_insert_frags:
        relevant_insert_frags = list(insert_frags)

    products: dict[str, dict] = {}
    errors: list[str] = []
    for vector_index, vector_frag in enumerate(vector_frags):
        for insert_index, insert_frag in enumerate(relevant_insert_frags):
            orientations = [("forward", insert_frag), ("reverse-complement", insert_frag.reverse_complement())]
            for orientation, oriented_insert in orientations:
                for order, pieces in (
                    ("vector+insert", (vector_frag, oriented_insert)),
                    ("insert+vector", (oriented_insert, vector_frag)),
                ):
                    try:
                        linear = pieces[0] + pieces[1]
                        circular = linear.looped()
                    except Exception as error:
                        if len(errors) < 12:
                            errors.append(f"{vector_index}:{insert_index}:{orientation}:{order}:{type(error).__name__}")
                        continue
                    sequence = str(circular.seq).upper()
                    digest = _sha(sequence)
                    products.setdefault(digest, {
                        "length": len(circular),
                        "sequence_sha256": digest,
                        "insert_orientation": (
                            "forward" if insert_upper in sequence else
                            "reverse-complement" if rc_insert in sequence else
                            "unresolved"
                        ),
                        "vector_fragment_index": vector_index,
                        "vector_fragment_length": len(vector_frag),
                        "insert_fragment_index": insert_index,
                        "insert_fragment_length": len(insert_frag),
                    })

    return {
        "operation": "restriction-ligation-construct",
        "amplicon_length": len(amplicon),
        "amplicon_sha256": _sha(str(amplicon.seq)),
        "vector_digest_fragment_lengths": [len(fragment) for fragment in vector_frags],
        "insert_digest_fragment_lengths": [len(fragment) for fragment in insert_frags],
        "constructs": list(products.values()),
        "construct_count": len(products),
        "unique_construct": len(products) == 1,
        "attempt_errors": errors,
        "interpretation": (
            "A unique in-silico circular construct was recovered from compatible pydna restriction/ligation ends."
            if len(products) == 1 else
            "Multiple or zero circular constructs remain possible in-silico; PCRStudio does not select one by fragment-size heuristic."
        ),
        **_record_identity(),
    }


def main() -> int:
    request = json.load(sys.stdin)
    operation = str(request.get("operation") or "pcr-product")

    if operation == "restriction-ligation-construct":
        answer = _restriction_ligation(request)
    elif operation == "pcr-product":
        from pydna.amplify import pcr
        from pydna.dseqrecord import Dseqrecord

        forward = str(request.get("forward") or "")
        reverse = str(request.get("reverse") or "")
        template = str(request.get("template") or "")
        if not forward or not reverse or not template:
            raise ValueError("forward, reverse and template are required")
        ds = Dseqrecord(template, circular=bool(request.get("circular")))
        product = pcr(forward, reverse, ds)
        sequence = str(product.seq).upper()
        answer = {
            "length": len(product),
            "sequence_sha256": _sha(sequence),
            "circular_template": bool(request.get("circular")),
            **_record_identity(),
        }
    else:
        raise ValueError(f"unsupported pydna bridge operation: {operation}")

    json.dump(answer, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
