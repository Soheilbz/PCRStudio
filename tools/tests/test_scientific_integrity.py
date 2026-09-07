"""Scientific identity invariants may not be weakened by development policy."""

from __future__ import annotations

import pytest

from pcr_tools.scientific_integrity import (
    enforce_constraint_overrides,
    enforce_polymerase_identity,
    enforce_reaction_overrides,
    require_named_assay,
    resolve_purpose,
)


def test_development_cannot_change_named_assay_chemistry(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    with pytest.raises(ValueError, match="scientifically bound to chemistry"):
        enforce_polymerase_identity("q5", "taq-standard", assay_id="standard-pcr")
    with pytest.raises(ValueError, match="anonymous reaction-condition"):
        enforce_reaction_overrides(
            {"mv_conc": 60.0}, {"mv_conc": 50.0}, context="assay `standard-pcr`"
        )


def test_development_cannot_escape_profile_constraint_authority(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    with pytest.raises(ValueError, match="outside the versioned"):
        enforce_constraint_overrides(
            {"product_max": 600},
            {"product_max": 200},
            envelopes={"product_max": {"max": 500}},
            context="assay `rpa`",
        )
    with pytest.raises(ValueError, match="locked"):
        enforce_constraint_overrides(
            {"tm_min": 55.0},
            {"tm_min": 58.0},
            policies={"tm_min": "locked"},
            context="assay `named`",
        )


def test_development_cannot_invent_assay_or_purpose(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    with pytest.raises(ValueError, match=r"explicit named `assay.id`"):
        require_named_assay({}, command="run")
    with pytest.raises(ValueError, match="multiple supported purposes"):
        resolve_purpose(None, None, ["general", "cloning"], assay_name="Example")


def test_release_profile_authority_is_required_in_development_too(monkeypatch):
    monkeypatch.setenv("PCRSTUDIO_SCIENTIFIC_POLICY", "development")
    with pytest.raises(ValueError, match="server-injected canonical profile authority"):
        require_named_assay(
            {"assay": {"id": "standard-pcr"}},
            command="run",
            require_profile_authority=True,
        )
