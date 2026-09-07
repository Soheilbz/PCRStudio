from __future__ import annotations
import pytest
from pcr_tools.modified_oligos import provenance_block, validate_modified_oligos


def test_modified_oligo_schema_normalizes_sequence_and_preserves_no_design_impact():
    value = [{"role":"FIP","sequence":"acgt","fluorophore":"FAM","threePrimeBlock":"C3","internalModifications":[{"kind":"thf","position":2,"identity":"THF"}]}]
    normalized = validate_modified_oligos(value)
    assert normalized and normalized[0]["sequence"] == "ACGT"
    provenance = provenance_block(value)
    assert provenance and provenance["decision_impact"] == "none"
    assert provenance["schema"] == "contracts/oligos/modified-oligo.schema.json"


def test_modified_oligo_schema_fails_closed_on_unknown_fields_positions_and_ambiguity():
    with pytest.raises(ValueError, match="unknown field"):
        validate_modified_oligos([{"role":"FIP","unknown":True}])
    with pytest.raises(ValueError, match="A/C/G/T"):
        validate_modified_oligos([{"role":"FIP","sequence":"ACGN"}])
    with pytest.raises(ValueError, match="position"):
        validate_modified_oligos([{"role":"FIP","internalModifications":[{"kind":"thf","position":500}]}])
