"""Primer3's account of what it discarded, turned into a sentence."""

from __future__ import annotations

from pcr_tools.explain import account_to_dict, parse, why_nothing

REAL = "considered 4010, GC content failed 2, low tm 3524, high tm 127, high hairpin stability 27, ok 330"


def test_the_counts_come_out_of_a_real_explain_string():
    account = parse(REAL, stage="left primers")
    assert account.considered == 4010
    assert account.accepted == 330
    assert account.rejections[0].reason == "low tm"
    assert account.rejections[0].count == 3524


def test_reasons_are_ordered_by_how_many_they_killed():
    account = parse(REAL, stage="left primers")
    counts = [r.count for r in account.rejections]
    assert counts == sorted(counts, reverse=True)


def test_the_sentence_names_the_commonest_refusal_and_what_to_do():
    sentence = parse(REAL, stage="left primers").sentence()
    assert "4010" in sentence
    assert "low tm" in sentence
    assert "melting-temperature window" in sentence


def test_considered_and_ok_are_not_reported_as_failures():
    account = parse(REAL, stage="left primers")
    assert "considered" not in {r.reason for r in account.rejections}
    assert "ok" not in {r.reason for r in account.rejections}


def test_a_reason_we_have_no_advice_for_is_still_shown():
    account = parse("considered 10, something new 7, ok 3", stage="left primers")
    assert account.rejections[0].reason == "something new"
    assert account.rejections[0].advice == ""


def test_shares_are_worked_out_for_the_interface():
    entry = account_to_dict(parse("considered 200, low tm 150, ok 50", stage="x"))
    assert entry["rejections"][0]["share"] == 75.0


def test_a_run_with_no_pairs_names_the_stage_that_killed_everything():
    accounts = [
        parse("considered 4010, low tm 4010, ok 0", stage="left primers"),
        parse("considered 4010, ok 300", stage="right primers"),
    ]
    message = why_nothing(accounts)
    assert "left primers" in message
    assert "low tm" in message


def test_an_unparseable_fragment_is_skipped_rather_than_raised_on():
    # Diagnostics that can fail a run are worse than no diagnostics.
    account = parse("considered 10, nonsense, ok 3", stage="x")
    assert account.considered == 10
    assert account.accepted == 3
