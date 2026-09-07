"""Re-download the corpus from NCBI and say what changed.

Run by hand, never by the test suite:

    python tests/corpus/refresh.py            # check, change nothing
    python tests/corpus/refresh.py --write    # update the files and the manifest

A record that has changed under a version it should not have is the interesting
case, and this is what would find it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request

from . import HERE, MANIFEST, manifest

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

#: NCBI asks for no more than three requests a second without an API key.
PAUSE_SECONDS = 0.4


def fetch(accession: str, email: str) -> str:
    query = urllib.parse.urlencode(
        {
            "db": "nuccore",
            "id": accession,
            "rettype": "fasta",
            "retmode": "text",
            "email": email,
            "tool": "PCRStudio-corpus",
        }
    )
    with urllib.request.urlopen(f"{EUTILS}?{query}", timeout=60) as response:
        return response.read().decode("utf-8")


def bases_of(fasta: str) -> str:
    return "".join(
        line.strip() for line in fasta.splitlines() if not line.startswith(">")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="update files and manifest"
    )
    parser.add_argument(
        "--email", default="soheil1751216@gmail.com", help="NCBI asks for one"
    )
    parser.add_argument(
        "accession", nargs="*", help="default: everything in the manifest"
    )
    arguments = parser.parse_args()

    records = manifest()
    wanted = arguments.accession or sorted(records)
    if not wanted:
        print("The corpus is empty and nothing was named on the command line.")
        return 1

    changed = []
    for accession in wanted:
        fasta = fetch(accession, arguments.email)
        time.sleep(PAUSE_SECONDS)
        bases = bases_of(fasta)
        digest = hashlib.sha256(bases.encode("ascii")).hexdigest()

        known = records.get(accession)
        if known and known.sha256 == digest:
            print(f"  same  {accession}  {len(bases):>9,} bp")
            continue

        changed.append(
            (accession, known.sha256 if known else None, digest, len(bases), fasta)
        )
        was = f"was {known.sha256[:12]}" if known else "new"
        print(f"CHANGED {accession}  {len(bases):>9,} bp  {was} -> {digest[:12]}")

    if not changed:
        print("\nNothing changed.")
        return 0

    if not arguments.write:
        print("\nRun again with --write to accept these.")
        return 1

    raw = (
        json.loads(MANIFEST.read_text(encoding="utf-8"))
        if MANIFEST.exists()
        else {"records": []}
    )
    by_accession = {entry["accession"]: entry for entry in raw["records"]}
    for accession, _, digest, length, fasta in changed:
        (HERE / f"{accession}.fasta").write_text(fasta, encoding="utf-8")
        entry = by_accession.setdefault(accession, {"accession": accession})
        entry.update(length=length, sha256=digest)
        entry.setdefault("organism", "")
        entry.setdefault("description", "")
        entry.setdefault("what_it_tests", "")
    raw["records"] = [by_accession[a] for a in sorted(by_accession)]
    MANIFEST.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {len(changed)} record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
