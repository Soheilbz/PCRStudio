"""Getting a sequence from NCBI when somebody has an accession rather than bases.

Most people do not have a sequence in their clipboard. They have an accession
from a paper, or a list of them from a spreadsheet, and asking them to go and
fetch the FASTA themselves is asking them to leave.

Three things this has to get right, all of them NCBI's rules rather than ours:

- **Identify yourself.** Every request carries `tool` and `email`. Without them
  a blocked address has nobody to warn.
- **Stay under the rate limit.** Three requests a second without an API key,
  ten with one. That limit is per address, so on a public service it is a
  shared budget and not a per-user one — which is why the throttle lives in the
  long-running server rather than here, where every call is a new process.
- **Ask once for many.** A list of accessions goes in one request, because
  NCBI asks that it does and because it is faster.

The version matters. An unversioned accession is a moving target, so whatever
comes back is reported with the version it actually had.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .egress import EgressPolicyError, opener, validate_https_url

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

#: Identifies this software to NCBI. Required by their usage policy.
TOOL = "pcrstudio"

#: How long to wait before giving up on NCBI.
TIMEOUT_SECONDS = 30

#: How many accessions one request may name. NCBI suggests a few hundred per
#: fetch; this is well under that and keeps a single failure small.
MAX_ACCESSIONS = 50

#: Keep a malformed or unexpectedly large NCBI response from becoming an
#: unbounded allocation in the worker. This matches the API's 24 MiB JSON
#: request ceiling and still leaves room for a useful multi-record response.
MAX_RESPONSE_BYTES = 24 * 1024 * 1024
RESPONSE_READ_CHUNK_BYTES = 64 * 1024

#: Nucleotide accessions look like `NM_000546.6`, `AB123456`, `NC_000913.3`.
#: Deliberately strict: anything else is more likely a pasted sequence or a
#: gene name, and both have better answers than a failed lookup.
ACCESSION = re.compile(r"^[A-Za-z]{1,6}_?\d{4,9}(\.\d+)?$")


class FetchError(ValueError):
    """A lookup that could not be completed, with a reason a person can act on."""


@dataclass(frozen=True)
class Record:
    """One sequence as NCBI returned it."""

    #: The accession with its version, exactly as the record carries it.
    id: str
    #: The rest of the FASTA header.
    description: str
    sequence: str

    @property
    def length(self) -> int:
        return len(self.sequence)


def check_accessions(raw: list[str] | str) -> list[str]:
    """Tidy a list of accessions and refuse anything that is not one.

    Raises:
        FetchError: naming the entry that is not an accession.
    """
    if isinstance(raw, str):
        # People paste them separated by whatever their spreadsheet used.
        raw = re.split(r"[\s,;]+", raw)
    elif not isinstance(raw, list):
        raise FetchError("Accessions must be text or a list of text values.")

    wanted: list[str] = []
    for index, entry in enumerate(raw, start=1):
        if entry is None or entry == "":
            continue
        if not isinstance(entry, str):
            raise FetchError(f"accession {index} must be text, not {entry!r}.")
        value = entry.strip()
        if value:
            wanted.append(value)
    if not wanted:
        raise FetchError("No accession was given.")
    if len(wanted) > MAX_ACCESSIONS:
        raise FetchError(
            f"{len(wanted)} accessions were given and this fetches up to {MAX_ACCESSIONS} "
            "at a time."
        )

    for entry in wanted:
        if not ACCESSION.match(entry):
            raise FetchError(
                f"`{entry}` does not look like a nucleotide accession. "
                "Expected something like NM_000546.6 or AB123456."
            )
    seen: set[str] = set()
    for entry in wanted:
        identity = entry.upper()
        if identity in seen:
            raise FetchError(
                f"The accession `{entry}` was supplied more than once. "
                "Remove duplicate accessions so each returned record has one "
                "unambiguous place in the design."
            )
        seen.add(identity)
    return wanted


#: Characters an alignment uses for a gap. Kept rather than stripped: an
#: aligned FASTA read back with its gaps removed is no longer an alignment, and
#: the columns a degenerate primer is built from stop lining up.
GAP_CHARACTERS = "-.~"
NUCLEIC_ALPHABET = frozenset("ACGTURYSWKMBDHVN" + GAP_CHARACTERS)
# An accession fetch is an unaligned nucleotide record. NCBI's FASTA guidance
# permits IUPAC nucleotide symbols here, but reserves gap characters for
# alignments; accepting one from a remote response would change the molecule's
# coordinates when it is later used as a template.
FETCH_ALPHABET = frozenset("ACGTURYSWKMBDHVN")


def parse_fasta(text: str) -> list[Record]:
    """Read FASTA into records, keeping the header apart from the sequence."""
    records: list[Record] = []
    header = ""
    chunks: list[str] = []

    def flush() -> None:
        if not header and not chunks:
            return
        identifier, _, description = header.partition(" ")
        sequence = "".join(chunks)
        if sequence:
            records.append(
                Record(
                    id=identifier or "unnamed",
                    description=description.strip(),
                    sequence=sequence.upper(),
                )
            )

    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            flush()
            header = line.lstrip()[1:].strip()
            chunks = []
        else:
            # Preserve non-whitespace symbols. The consumer can then refuse a
            # malformed sequence with its exact character instead of silently
            # changing the molecule before validation.
            chunks.append("".join(c for c in line if not c.isspace()))
    flush()

    return records


def _request_url(accessions: list[str], email: str, api_key: str = "") -> str:
    query = {
        "db": "nuccore",
        "id": ",".join(accessions),
        "rettype": "fasta",
        "retmode": "text",
        "tool": TOOL,
        "email": email,
    }
    key = api_key.strip()
    if key:
        query["api_key"] = key
    return f"{EFETCH}?{urllib.parse.urlencode(query)}"


def _version_mismatches(wanted: list[str], records: list[Record]) -> list[str]:
    """Return requested records that the response did not identify exactly.

    An accession without a dot deliberately means the current version. A
    versioned accession is different: NCBI documents it as the identifier of
    one specific sequence, so matching only the base accession would silently
    change the template used by a design.
    """
    returned_exact = {record.id.upper() for record in records}
    returned_bases = {record.id.split(".")[0].upper() for record in records}
    return [
        entry
        for entry in wanted
        if (
            entry.upper() not in returned_exact
            if "." in entry
            else entry.split(".")[0].upper() not in returned_bases
        )
    ]


def _record_matches(accession: str, record: Record) -> bool:
    """Whether one returned FASTA record can satisfy one requested accession."""
    returned = record.id.upper()
    if "." in accession:
        return returned == accession.upper()
    return returned.split(".", 1)[0] == accession.upper()


def _order_and_validate_response(wanted: list[str], records: list[Record]) -> list[Record]:
    """Require a one-to-one accession/FASTA-record response and restore order.

    EFetch returns formatted records for a list of identifiers. The design
    must not proceed if a proxy, malformed response, or future API behaviour
    makes that list non-bijective: an extra record can be mistaken for a
    requested template and a duplicate record can make provenance ambiguous.
    """
    if len({record.id.upper() for record in records}) != len(records):
        raise FetchError(
            "NCBI returned duplicate FASTA record identifiers. The response "
            "cannot be mapped unambiguously to the requested accessions."
        )

    malformed = {
        record.id: sorted(set(record.sequence.upper()) - FETCH_ALPHABET)
        for record in records
        if set(record.sequence.upper()) - FETCH_ALPHABET
    }
    if malformed:
        details = "; ".join(
            f"{identifier}: {', '.join(repr(symbol) for symbol in symbols)}"
            for identifier, symbols in malformed.items()
        )
        raise FetchError(
            "NCBI returned a non-IUPAC symbol in an unaligned nucleotide FASTA "
            f"record ({details}). The sequence was not used."
        )

    matches: list[Record] = []
    used: set[int] = set()
    for accession in wanted:
        candidates = [
            (index, record)
            for index, record in enumerate(records)
            if index not in used and _record_matches(accession, record)
        ]
        if not candidates:
            continue
        if len(candidates) > 1:
            returned = ", ".join(record.id for _, record in candidates)
            raise FetchError(
                f"NCBI returned multiple records for `{accession}`: {returned}. "
                "Use an accession.version so the template is unambiguous."
            )
        index, record = candidates[0]
        used.add(index)
        matches.append(record)

    missing = [
        accession
        for accession in wanted
        if not any(_record_matches(accession, record) for record in records)
    ]
    unexpected = [record.id for index, record in enumerate(records) if index not in used]
    if missing or unexpected or len(matches) != len(wanted):
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise FetchError(
            "NCBI response did not contain exactly one record for each requested "
            "accession (" + "; ".join(details) + "). Retry with the exact "
            "accession.version identifiers."
        )
    return matches


def _read_response(answer: Any) -> bytes:
    """Read an NCBI response with a hard memory bound."""
    chunks: list[bytes] = []
    total = 0
    while True:
        # Ask for one byte beyond the ceiling so a response exactly at the
        # boundary is accepted while the first excess byte is detected.
        remaining = MAX_RESPONSE_BYTES - total
        chunk = answer.read(min(RESPONSE_READ_CHUNK_BYTES, remaining + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise FetchError(
                "NCBI returned more than the 24 MiB response limit. Narrow the "
                "accession list and try again."
            )
        chunks.append(chunk)


def fetch(accessions: list[str] | str, *, email: str, api_key: str = "") -> list[Record]:
    """Fetch one or more nucleotide records from NCBI.

    Args:
        accessions: One accession, a list, or a string of them separated by
            whitespace, commas or semicolons.
        email: A contact address, which NCBI's usage policy requires.

    Raises:
        FetchError: for a malformed accession, an accession NCBI does not know,
            or a lookup that could not be completed.
    """
    wanted = check_accessions(accessions)
    if not isinstance(email, str) or not email.strip():
        raise FetchError(
            "NCBI asks that every request carries a contact address, and none "
            "arrived with this one. Send an `email` field with the fetch request."
        )

    try:
        url = _request_url(wanted, email.strip(), api_key)
        validate_https_url(url)
        with opener().open(url, timeout=TIMEOUT_SECONDS) as answer:
            # A custom handler already checks redirects. Verify the final URL as
            # a second boundary in case a future opener configuration changes.
            validate_https_url(answer.geturl())
            text = _read_response(answer).decode("utf-8", errors="replace")
    except EgressPolicyError as error:
        raise FetchError(f"Outbound fetch blocked by egress policy: {error}") from error
    except urllib.error.HTTPError as error:
        if error.code == 400:
            raise FetchError(
                f"NCBI does not recognise {', '.join(wanted)}. Check the accession, "
                "including its version."
            ) from error
        if error.code == 429:
            raise FetchError("NCBI is rate-limiting this server. Try again in a moment.") from error
        raise FetchError(f"NCBI answered {error.code}.") from error
    except urllib.error.URLError as error:
        raise FetchError(f"NCBI could not be reached: {error.reason}") from error
    except TimeoutError as error:
        raise FetchError("NCBI did not answer before the 30-second timeout.") from error
    except OSError as error:
        raise FetchError(f"NCBI could not be read: {error}") from error

    records = parse_fasta(text)
    if not records:
        raise FetchError(
            f"NCBI returned nothing for {', '.join(wanted)}. The accession may be "
            "correct but not a nucleotide record."
        )

    missing = _version_mismatches(wanted, records)
    if missing:
        raise FetchError(
            "NCBI did not return the requested accession version(s): "
            + ", ".join(missing)
            + ". A versioned accession identifies one specific sequence; retry "
            "with the exact version or deliberately request the unversioned accession."
        )

    return _order_and_validate_response(wanted, records)


def records_to_dict(records: list[Record]) -> dict[str, Any]:
    """The records as plain data, with the FASTA a person could paste anywhere."""
    return {
        "records": [
            {
                "id": record.id,
                "description": record.description,
                "length": record.length,
                "sequence": record.sequence,
            }
            for record in records
        ],
        "fasta": "\n".join(
            f">{record.id} {record.description}".rstrip() + "\n" + record.sequence
            for record in records
        ),
    }
