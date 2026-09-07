"""Real sequences, cached, so the evaluation suite is the same every time.

Why a cache rather than fetching:

- A test that hits NCBI fails when NCBI is slow, when the network is down, and
  when somebody is on a train. A test that fails for reasons unrelated to the
  code teaches people to ignore failures.
- A record can change. `NM_000546.5` became `NM_000546.6`, and a suite that
  silently followed would have quietly changed what it was measuring.

So the sequences live in this directory, each with the checksum of what was
downloaded and the date it was downloaded on. `refresh.py` re-downloads them and
says what changed; nothing else touches the network.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass

HERE = pathlib.Path(__file__).parent
MANIFEST = HERE / "manifest.json"


@dataclass(frozen=True)
class Record:
    """One cached sequence and what it is here to test."""

    accession: str
    """The versioned accession, so the record is pinned rather than followed."""
    organism: str
    description: str
    what_it_tests: str
    """Why this record earns its place in the suite."""
    length: int
    sha256: str
    """Of the bases, not of the file: a header reflow must not read as a change."""

    @property
    def path(self) -> pathlib.Path:
        return HERE / f"{self.accession}.fasta"

    def sequence(self) -> str:
        """The bases, with the header dropped and the lines joined."""
        text = self.path.read_text(encoding="utf-8")
        bases = "".join(
            line.strip() for line in text.splitlines() if not line.startswith(">")
        )
        digest = hashlib.sha256(bases.encode("ascii")).hexdigest()
        if digest != self.sha256:
            raise ValueError(
                f"{self.accession} on disk does not match the manifest. Either the "
                "file was edited or the manifest was: run refresh.py to see which."
            )
        return bases

    def fasta(self) -> str:
        """The record as it arrived, header and all."""
        return self.path.read_text(encoding="utf-8")


def manifest() -> dict[str, Record]:
    """Every record in the corpus, by accession."""
    if not MANIFEST.exists():
        return {}
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {entry["accession"]: Record(**entry) for entry in raw["records"]}


def record(accession: str) -> Record:
    """One record, or a message naming what is actually here.

    Raises:
        KeyError: with the list, because "KeyError: 'NM_000546.5'" on its own
            sends somebody looking for a bug that is a typo.
    """
    records = manifest()
    if accession not in records:
        raise KeyError(
            f"{accession} is not in the corpus. It holds: "
            + (", ".join(sorted(records)) or "nothing yet")
        )
    return records[accession]
