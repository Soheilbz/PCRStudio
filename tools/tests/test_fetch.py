"""Accessions, and the parsing around them.

Nothing here reaches the network. What is worth testing is the part that
decides whether a request is worth making at all, and the part that reads what
comes back — a test that depends on NCBI being up tests NCBI.
"""

from __future__ import annotations

import pytest

from pcr_tools.align import AlignError, align
from pcr_tools.fetch import (
    MAX_ACCESSIONS,
    MAX_RESPONSE_BYTES,
    FetchError,
    Record,
    check_accessions,
    fetch,
    _request_url,
    parse_fasta,
)


class _FakeOpenedResponse:
    """Adapt a test response to the strict egress opener contract."""

    def __init__(self, inner):
        self.inner = inner

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.inner.read(size)

    def geturl(self):
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class _FakeOpener:
    def __init__(self, response):
        self.response = response

    def open(self, *_args, **_kwargs):
        return _FakeOpenedResponse(self.response)


def _install_fetch_response(monkeypatch, response):
    monkeypatch.setattr("pcr_tools.fetch.opener", lambda: _FakeOpener(response))




def test_ncbi_api_key_is_explicit_request_data_not_ambient_environment(monkeypatch):
    monkeypatch.setenv("PCR_NCBI_API_KEY", "ambient-must-not-leak")
    anonymous = _request_url(["NM_000546.6"], "bench@example.org")
    authenticated = _request_url(["NM_000546.6"], "bench@example.org", "explicit-key")
    assert "api_key=" not in anonymous
    assert "api_key=explicit-key" in authenticated
    assert "ambient-must-not-leak" not in anonymous + authenticated


def test_a_single_accession_survives_untouched():
    assert check_accessions("NM_000546.6") == ["NM_000546.6"]


def test_accessions_arrive_separated_by_whatever_the_spreadsheet_used():
    assert check_accessions("NM_000546.6, NC_000913.3;AB123456") == [
        "NM_000546.6",
        "NC_000913.3",
        "AB123456",
    ]


def test_a_pasted_sequence_is_refused_as_an_accession():
    # The commonest mistake, and it has a much better answer than a lookup.
    with pytest.raises(FetchError, match="does not look like"):
        check_accessions("ACGTACGTACGTACGT")


def test_a_gene_name_is_refused_by_name():
    with pytest.raises(FetchError, match="TP53"):
        check_accessions("TP53")


def test_nothing_at_all_says_so():
    with pytest.raises(FetchError, match="No accession"):
        check_accessions("   ")


def test_too_many_at_once_says_how_many():
    too_many = ["NM_000546.6"] * (MAX_ACCESSIONS + 1)
    with pytest.raises(FetchError, match=str(MAX_ACCESSIONS)):
        check_accessions(too_many)


def test_non_text_accession_is_refused_as_input_not_an_internal_error():
    with pytest.raises(FetchError, match="must be text"):
        check_accessions(["NM_000546.6", 123])


def test_duplicate_accessions_are_refused_before_network_use():
    with pytest.raises(FetchError, match="more than once"):
        check_accessions(["NM_000546.6", "nm_000546.6"])


def test_versioned_accessions_are_not_satisfied_by_a_different_sequence_version():
    returned = [Record(id="NM_000546.7", description="", sequence="ACGT")]

    # The unversioned form intentionally means the latest version.
    from pcr_tools.fetch import _version_mismatches

    assert _version_mismatches(["NM_000546"], returned) == []
    assert _version_mismatches(["NM_000546.6"], returned) == ["NM_000546.6"]


def test_fasta_keeps_the_identifier_apart_from_its_description():
    records = parse_fasta(">NM_000546.6 Homo sapiens tumor protein p53 (TP53), mRNA\nACGT\nACGT\n")
    assert len(records) == 1
    assert records[0].id == "NM_000546.6"
    assert records[0].description.startswith("Homo sapiens")
    assert records[0].sequence == "ACGTACGT"
    assert records[0].length == 8


def test_several_records_stay_separate():
    records = parse_fasta(">a x\nACGT\n>b y\nTTTT\n>c z\nGGGG\n")
    assert [r.id for r in records] == ["a", "b", "c"]


def test_a_record_with_no_sequence_is_not_a_record():
    records = parse_fasta(">empty\n\n>real\nACGT\n")
    assert [r.id for r in records] == ["real"]


def test_fasta_parser_preserves_invalid_symbols_for_the_consumer_to_refuse():
    records = parse_fasta("  >target\nACGT!12\n")
    assert records[0].id == "target"
    assert records[0].sequence == "ACGT!12"


def test_alignment_refuses_invalid_symbols_before_starting_an_external_tool():
    with pytest.raises(AlignError, match="invalid symbol"):
        align(">target\nACGT!\n>other\nACGT\n")


def test_alignment_refuses_duplicate_input_identifiers():
    with pytest.raises(AlignError, match="duplicate record identifier"):
        align(">same\nACGT\n>same\nACGT\n")


def test_alignment_never_auto_substitutes_a_different_aligner(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_TOOLCHAIN_MODE", "compatible")
    monkeypatch.setattr(
        "pcr_tools.align.available",
        lambda: {
            "available": True,
            "aligners": [{"id": "muscle", "name": "MUSCLE", "path": "/usr/local/bin/muscle"}],
        },
    )

    with pytest.raises(AlignError, match="another aligner cannot be substituted implicitly"):
        align(">target\nACGT\n>other\nACGT\n")


def test_alignment_refuses_unverified_mafft_version_in_every_policy(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_TOOLCHAIN_MODE", "compatible")
    monkeypatch.setattr(
        "pcr_tools.align.available",
        lambda: {"available": True, "aligners": [{"id": "mafft", "name": "MAFFT", "path": "mafft"}]},
    )
    monkeypatch.setattr(
        "pcr_tools.align.tool_status",
        lambda _tool: {"version_matches_contract": False, "observed_version": "7.525"},
    )
    with pytest.raises(AlignError, match="requires the pinned 7.526 version"):
        align(">target\nACGT\n>other\nACGT\n")


def test_alignment_refuses_an_aligner_that_drops_a_record(monkeypatch):
    monkeypatch.setattr("pcr_tools.align.tool_status", lambda _tool: {"version_matches_contract": True, "observed_version": "v7.526"})
    monkeypatch.setattr(
        "pcr_tools.align.available",
        lambda: {
            "available": True,
            "aligners": [{"id": "mafft", "name": "MAFFT", "path": "mafft"}],
        },
    )
    monkeypatch.setattr(
        "pcr_tools.align._with_mafft",
        lambda _path, _fasta, **_context: [Record(id="target", description="", sequence="ACGT")],
    )

    with pytest.raises(AlignError, match="missing 'other'"):
        align(">target\nACGT\n>other\nACGT\n")


def test_alignment_refuses_an_aligner_that_changes_bases(monkeypatch):
    monkeypatch.setattr("pcr_tools.align.tool_status", lambda _tool: {"version_matches_contract": True, "observed_version": "v7.526"})
    monkeypatch.setattr(
        "pcr_tools.align.available",
        lambda: {
            "available": True,
            "aligners": [{"id": "mafft", "name": "MAFFT", "path": "mafft"}],
        },
    )
    monkeypatch.setattr(
        "pcr_tools.align._with_mafft",
        lambda _path, _fasta, **_context: [
            Record(id="target", description="", sequence="ACGT"),
            Record(id="other", description="", sequence="ACGA"),
        ],
    )

    with pytest.raises(AlignError, match="changed the bases"):
        align(">target\nACGT\n>other\nACGT\n")


def test_an_oversized_ncbi_response_is_refused_before_it_can_grow_memory(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size=-1):
            assert size != -1, "the fetcher must never request an unbounded read"
            return b"N" * (MAX_RESPONSE_BYTES + 1)

    _install_fetch_response(monkeypatch, Response())

    with pytest.raises(FetchError, match="24 MiB response limit"):
        fetch("NM_000546.6", email="bench@example.org")


def test_a_fetch_response_must_contain_exactly_the_requested_records(monkeypatch):
    class Response:
        payload = b">NM_000546.6\nACGT\n>EXTRA.1\nTTTT\n"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size=-1):
            payload, self.payload = self.payload[:size], self.payload[size:]
            return payload

    _install_fetch_response(monkeypatch, Response())

    with pytest.raises(FetchError, match=r"unexpected EXTRA\.1"):
        fetch("NM_000546.6", email="bench@example.org")


def test_unversioned_fetch_is_refused_when_multiple_versions_return(monkeypatch):
    class Response:
        payload = b">NM_000546.6\nACGT\n>NM_000546.7\nTTTT\n"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size=-1):
            payload, self.payload = self.payload[:size], self.payload[size:]
            return payload

    _install_fetch_response(monkeypatch, Response())

    with pytest.raises(FetchError, match="multiple records"):
        fetch("NM_000546", email="bench@example.org")


def test_a_fetched_unaligned_record_cannot_contain_alignment_or_punctuation_symbols(
    monkeypatch,
):
    class Response:
        payload = b">NM_000546.6\nACGT-!\n"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size=-1):
            payload, self.payload = self.payload[:size], self.payload[size:]
            return payload

    _install_fetch_response(monkeypatch, Response())

    with pytest.raises(FetchError, match="non-IUPAC"):
        fetch("NM_000546.6", email="bench@example.org")


def test_fetch_restores_requested_accession_order(monkeypatch):
    class Response:
        payload = b">NC_000913.3\nTTTT\n>NM_000546.6\nACGT\n"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size=-1):
            payload, self.payload = self.payload[:size], self.payload[size:]
            return payload

    _install_fetch_response(monkeypatch, Response())

    records = fetch(["NM_000546.6", "NC_000913.3"], email="bench@example.org")
    assert [record.id for record in records] == ["NM_000546.6", "NC_000913.3"]
