"""What people actually paste, and what we are allowed to conclude from it."""

from __future__ import annotations

import pytest

from pcr_tools.intake import IntakeError, resolve, target_to_dict


def kinds(target) -> set[str]:
    return {note.kind for note in target.notes}


def test_a_bare_sequence_needs_no_interpretation():
    target = resolve("ACGTACGTACGTACGT")
    assert target.sequence == "ACGTACGTACGTACGT"
    assert not target.notes


def test_a_fasta_header_becomes_the_name():
    target = resolve(">NM_000546.6 Homo sapiens TP53\nACGTACGT\nACGTACGT\n")
    assert target.name == "NM_000546.6 Homo sapiens TP53"
    assert target.sequence == "ACGTACGTACGTACGT"


def test_a_second_fasta_record_is_reported_rather_than_silently_dropped():
    target = resolve(">one\nACGTACGT\n>two\nTTTTTTTT\n")
    assert target.sequence == "ACGTACGT"
    assert "multipleRecords" in kinds(target)


def test_genbank_line_coordinates_do_not_become_bases():
    # The trap: strip non-letters naively and the coordinates weld themselves in.
    flat = (
        "        1 gatcctccat atacaacggt atctccacct caggtttaga tctcaacaac\n"
        "       61 ggaaccctgc cctgtcagat tctcaacaac ggaaccctgc cctgtcagat\n"
        "      121 tctcaacaac ggaaccctgc cctgtcagat tctcaacaac ggaaccctgc\n"
    )
    target = resolve(flat, lowercase_masking=False)
    assert "genbankLayout" in kinds(target)
    assert "1" not in target.sequence
    # Fifty bases a line, three lines.
    assert target.length == 150


def test_malformed_genbank_coordinate_is_refused_instead_of_rewritten():
    with pytest.raises(IntakeError, match=r"formatting symbols.*'1'"):
        resolve("ORIGIN\n        1acgtacgt\n//\n")


def test_a_complete_genbank_record_uses_only_origin_not_metadata_or_features():
    flat = (
        "LOCUS       example  12 bp    DNA     linear   01-JAN-2000\n"
        "DEFINITION  a record whose annotations are not sequence.\n"
        "FEATURES             Location/Qualifiers\n"
        "     CDS             1..12\n"
        '                     /translation="MEEPQSDPSVEP"\n'
        "ORIGIN\n"
        "        1 acgtacgtacgt\n"
        "//\n"
    )

    target = resolve(flat, lowercase_masking=False)

    assert target.sequence == "ACGTACGTACGT"
    assert target.length == 12
    assert "genbankLayout" in kinds(target)


def test_rna_is_converted_and_the_person_is_told():
    target = resolve("ACGUACGUACGU")
    assert target.sequence == "ACGTACGTACGT"
    assert target.rna_input
    assert "rnaConverted" in kinds(target)


def test_dna_is_not_marked_as_rna():
    assert not resolve("ACGTACGTACGT").rna_input


def test_a_protein_sequence_is_refused_by_name():
    with pytest.raises(IntakeError, match="protein"):
        resolve("MEEPQSDPSVEPPLSQETFSDLWKLLPEN")


def test_an_unknown_letter_is_refused_with_the_letter_in_the_message():
    with pytest.raises(IntakeError, match="Z"):
        resolve("ACGTZACGT")


def test_alignment_gaps_are_refused_instead_of_silently_removed():
    with pytest.raises(IntakeError, match="formatting symbols"):
        resolve("ACGT-ACGT")


def test_digits_in_raw_sequence_are_refused_instead_of_silently_removed():
    with pytest.raises(IntakeError, match=r"formatting symbols.*'1'"):
        resolve("ACGT1234ACGT")


def test_ambiguity_is_kept_counted_and_located():
    target = resolve("ACGTNACGTRACGT")
    assert len(target.ambiguous_at) == 2
    assert "ambiguity" in kinds(target)
    # One-based on the way out, because every genome browser counts from one.
    assert target_to_dict(target)["ambiguous_at"] == [5, 10]


def test_lowercase_requires_an_explicit_interpretation():
    with pytest.raises(IntakeError, match="does not infer whether lowercase"):
        resolve("ACGT" * 10 + "acgtacgtacgt" + "ACGT" * 10)


def test_explicit_soft_masking_preserves_case():
    target = resolve("ACGT" * 10 + "acgtacgtacgt" + "ACGT" * 10, lowercase_masking=True)
    assert target.soft_masked
    assert "softMasked" in kinds(target)
    assert "a" in target.sequence


def test_explicit_formatting_case_is_flattened():
    target = resolve("ACGT" * 30 + "a", lowercase_masking=False)
    assert not target.soft_masked
    assert target.sequence.isupper()
    assert "caseFlattened" in kinds(target)


def test_word_processor_spaces_do_not_become_an_error():
    # A no-break space is what a pasted sequence from a document carries.
    target = resolve("ACGT ACGT ACGT")
    assert target.sequence == "ACGTACGTACGT"


def test_an_empty_input_says_so_rather_than_producing_an_empty_template():
    with pytest.raises(IntakeError, match="No sequence"):
        resolve("   \n  ")


def test_the_confirmation_panel_does_not_carry_the_sequence():
    # It is shown back to a person before they commit; a wall of bases is not
    # information, and the sequence is already theirs.
    panel = target_to_dict(resolve(">t\nACGTACGTGGCC"))
    assert "sequence" not in panel
    assert panel["length"] == 12
    # Eight of the twelve bases are G or C.
    assert panel["gc_percent"] == 66.7
    assert panel["rna_input"] is False
