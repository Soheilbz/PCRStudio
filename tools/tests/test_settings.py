"""Shared profile preparation must apply the same contract to every engine."""

from __future__ import annotations

import pytest

from pcr_tools.settings import prepare


def test_default_purpose_is_applied_before_specialized_search() -> None:
    settings = prepare(
        {
            "template": "A" * 600,
            "assay": {
                "id": "colony-pcr",
                "defaults": {
                    "defaultPurpose": "screen",
                    "purposes": ["general", "screen", "sanger"],
                },
            },
        }
    )

    assert settings.intent.id == "screen"


def test_single_allowed_purpose_is_applied_when_default_is_omitted() -> None:
    settings = prepare(
        {
            "template": "A" * 600,
            "assay": {
                "id": "restriction-cloning",
                "defaults": {"purposes": ["cloning"]},
            },
        }
    )

    assert settings.intent.id == "cloning"


def test_strand_displacing_profile_rejects_a_thermocycled_polymerase() -> None:
    with pytest.raises(ValueError, match="strand-displacing"):
        prepare(
            {
                "template": "A" * 600,
                "polymerase": "taq-standard",
                "assay": {
                    "id": "lamp",
                    "defaults": {
                        "polymerase": "bst",
                        "purposes": ["general"],
                    },
                    "enzyme": ["strand-displacing"],
                },
            },
            require_product_room=False,
        )


def test_recommended_default_can_tune_inside_an_outer_qualification_envelope() -> None:
    settings = prepare(
        {
            "template": "A" * 600,
            "constraints": {"product_max": 450},
            "assay": {
                "id": "rpa-test",
                "defaults": {
                    "purposes": ["general"],
                    "constraints": {"product_min": 100, "product_max": 200},
                    "constraintEnvelope": {"product_max": {"max": 500}},
                },
            },
        }
    )

    assert settings.limits.product_max == 450
    resolved = settings.parameter_resolution["constraints"]["product_max"]
    assert resolved["change_class"] == "recommended-tuning"
    assert resolved["qualification_envelope"] == {"max": 500}


def test_outer_qualification_envelope_refuses_named_branch_extrapolation() -> None:
    with pytest.raises(ValueError, match="outside the versioned.*qualification envelope"):
        prepare(
            {
                "template": "A" * 800,
                "constraints": {"product_max": 600},
                "assay": {
                    "id": "rpa-test",
                    "defaults": {
                        "purposes": ["general"],
                        "constraints": {"product_min": 100, "product_max": 200},
                        "constraintEnvelope": {"product_max": {"max": 500}},
                    },
                },
            }
        )
