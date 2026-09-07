from pcr_tools import loop_set


def test_current_protocol_catalogue_and_substrate_partition():
    reg = loop_set.LAMP_PROTOCOL_REGISTRY
    assert len(reg) == 72
    dna = [
        k
        for k, v in reg.items()
        if v.get("supports_dna", True) and not v.get("supports_rna", False)
    ]
    rna = [
        k
        for k, v in reg.items()
        if v.get("supports_rna", False) and not v.get("supports_dna", True)
    ]
    dual = [
        k for k, v in reg.items() if v.get("supports_dna", True) and v.get("supports_rna", False)
    ]
    assert (len(dna), len(rna), len(dual)) == (35, 4, 33)


def test_grouped_vendor_primer_table_normalizes_to_explicit_roles():
    p = loop_set.LAMP_PROTOCOL_REGISTRY["vazyme-rp711"]["primer_concentrations_uM"]
    assert p == {"FIP": 1.6, "BIP": 1.6, "F3": 0.2, "B3": 0.2, "LoopF": 0.8, "LoopB": 0.8}
    a = loop_set.LAMP_PROTOCOL_REGISTRY["agdia-lmx54700"]["primer_concentrations_uM"]
    assert a["FIP"] == a["BIP"] == 1.6 and a["LoopF"] == a["LoopB"] == 0.4


def test_unsourced_override_ranges_are_removed_from_worker_authority():
    assert loop_set.LAMP_PROTOCOL_REGISTRY["meridian-mdx126"]["bench_optimization_scope"] == {}
    assert loop_set.LAMP_PROTOCOL_REGISTRY["takara-rr385"]["bench_optimization_scope"] == {}
    assert loop_set.LAMP_NUMERIC_OPTIMIZATION_ENVELOPES["neb-m9204"]["magnesium_mM"] == [6.0, 8.0]


def test_new_exact_product_authorities_exist_without_sequence_impact():
    for pid in [
        "jena-pcr387",
        "nzy-md0696",
        "nippon-dr0401",
        "yeasen-16730",
        "vazyme-rp711",
        "agdia-lmx54700",
    ]:
        assert loop_set.LAMP_PROTOCOL_REGISTRY[pid]["sequence_decision_impact"] == "none"
