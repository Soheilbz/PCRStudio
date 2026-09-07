from pcr_tools.lamp_numeric_recipes import (
    LAMP_NUMERIC_OPTIMIZATION_ENVELOPES,
    resolve_numeric_recipe,
)


def r(protocol, **kw):
    base = dict(
        readout="not-specified",
        chemistry="not-specified",
        from_rna=False,
        matrix="purified-nucleic-acid",
        preparation="purified",
        formulation="liquid",
        carryover_strategy="protocol-default",
        reconstitution_x="protocol-default",
        specificity_additive="none",
        acceleration_additive="none",
        primer_kinetics_profile="protocol-default",
        preincubation_strategy="protocol-default",
        sample_buffer_type="none",
        instrument_profile="not-specified",
    )
    base.update(kw)
    return resolve_numeric_recipe(protocol, None, base, {})


def test_m1712_readout_numbers_change():
    x = r("neb-m1712", readout="colorimetric", chemistry="calcein")
    assert x["values"]["calcein_uM"] == 25 and x["values"]["mncl2_mM"] == 0.5
    y = r("neb-m1712", readout="colorimetric", chemistry="eriochrome-black-t")
    assert y["values"]["eriochrome_black_t_uM"] == 60


def test_thermo_calcein_and_syto9_are_distinct_numeric_recipes():
    assert r("thermo-a5180x", readout="fluorescence", chemistry="syto9")["values"]["syto9_uM"] == 5
    z = r("thermo-a5180x", readout="colorimetric", chemistry="calcein")
    assert z["values"]["calcein_uM"] == 80 and z["values"]["mncl2_mM"] == 0.25


def test_bst_xt_substrate_and_carryover_add_numbers():
    z = r("neb-m9204", from_rna=True, carryover_strategy="reviewed-dutp-udg")
    assert (
        z["values"]["rt_units"] == 7.5
        and z["values"]["dutp_mM"] == 0.7
        and z["values"]["thermolabile_udg_u_per_ml"] == 20
    )


def test_optigene_koh_and_primer_profiles():
    z = r("optigene-iso001-lnl", matrix="koh-lysate", preparation="koh-lyse-and-lamp")
    assert z["values"]["koh_mM"] == 60
    q = r("optigene-iso001", primer_kinetics_profile="optigene-high")
    assert q["values"]["fip_bip_uM"] == 2.0 and q["values"]["loop_uM"] == 1.0


def test_vazyme_instrument_stoichiometry_and_other_instrument_unresolved_exact():
    z = r(
        "vazyme-rp711",
        readout="fluorescence",
        chemistry="supplied-intercalating-dye",
        instrument_profile="vazyme-slan96p",
    )
    assert (
        z["values"]["fluorescent_dye_x"] == 0.1
        and abs(z["values"]["fluorescent_dye_uL_per_25uL"] - 0.05) < 1e-9
    )
    q = r(
        "vazyme-rp711",
        readout="fluorescence",
        chemistry="supplied-intercalating-dye",
        instrument_profile="vazyme-cfx96-touch",
    )
    assert (
        q["values"]["fluorescent_dye_x"] == 1.0
        and abs(q["values"]["fluorescent_dye_uL_per_25uL"] - 0.5) < 1e-9
    )
    o = r(
        "vazyme-rp711",
        readout="fluorescence",
        chemistry="supplied-intercalating-dye",
        instrument_profile="other-qpcr",
    )
    assert "fluorescent_dye_x" not in o["values"] and o["ranges"]["fluorescent_dye_x"] == [0.1, 1.0]


def test_agdia_rna_adds_external_rt_only_when_needed():
    d = r("agdia-lmx54700")
    assert "external_rt_units" not in d["values"]
    x = r("agdia-lmx54700", from_rna=True, instrument_profile="agdia-amplifire")
    assert (
        x["values"]["external_rt_units"] == 50
        and x["values"]["external_rt_uL"] == 0.25
        and x["values"]["hold_temperature_c"] == 65
    )


def test_yeasen_lyo_changes_stabilizer_number():
    assert "lyophilization_stabilizer_uL_per_25uL" not in r("yeasen-16730")["values"]
    assert (
        r("yeasen-16730", formulation="lyophilized")["values"][
            "lyophilization_stabilizer_uL_per_25uL"
        ]
        == 6
    )


def test_unsourced_ranges_are_not_resurrected():
    assert "meridian-mdx126" not in LAMP_NUMERIC_OPTIMIZATION_ENVELOPES
    assert "takara-rr385" not in LAMP_NUMERIC_OPTIMIZATION_ENVELOPES


def test_eiken_and_ph_colorimetric_fail_closed_for_wrong_buffer_context():
    import pytest

    with pytest.raises(ValueError):
        r("eiken-lmp204", chemistry="eiken-fd-lmp221", sample_buffer_type="te")
    with pytest.raises(ValueError):
        r(
            "neb-m1800",
            readout="colorimetric",
            chemistry="ph-colorimetric",
            sample_buffer_type="other-buffered",
            sample_buffer_ph=6.5,
            sample_buffer_percent=20,
        )
