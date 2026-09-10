from pathlib import Path

import pytest
from variantrag.variants import parse_variants

FIXTURE = Path(__file__).parents[1] / "fixtures/demo.vcf"


def test_multiallelic_does_not_leak_synonymous_allele():
    variants, _ = parse_variants(FIXTURE, "GRCh38")
    assert len(variants) == 3
    assert variants[0]["alt"] == "G"
    assert variants[0]["hgvs_g"] is None
    assert variants[0]["sample_id"] == "DEMO"


def test_unannotated_is_actionable(tmp_path):
    vcf = tmp_path / "raw.vcf"
    vcf.write_text("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
    with pytest.raises(ValueError, match="annotations"):
        parse_variants(vcf, "GRCh38")


def test_multisample_requires_selection(tmp_path):
    path = tmp_path / "multi.vcf"
    text = FIXTURE.read_text().replace("\tDEMO\n", "\tDEMO\tSECOND\n")
    text = (
        "\n".join(line + "\t0/0" if not line.startswith("#") else line for line in text.splitlines()) + "\n"
    )
    path.write_text(text)
    with pytest.raises(ValueError, match="sample"):
        parse_variants(path, "GRCh38")
    assert parse_variants(path, "GRCh38", "SECOND")[0] == []


def test_annotation_order_uses_header(tmp_path):
    path = tmp_path / "reorder.vcf"
    text = FIXTURE.read_text().replace("Allele|Consequence|SYMBOL", "Consequence|Allele|SYMBOL")
    import re

    text = re.sub(r"([GTA])\|(missense_variant|stop_gained|synonymous_variant)\|", r"\2|\1|", text)
    path.write_text(text)
    assert len(parse_variants(path, "GRCh38")[0]) == 3
