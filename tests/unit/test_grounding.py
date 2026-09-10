from variantrag.grounding import normalize, resolve_clinvar

XML = """<ClinVarResult-Set><VariationArchive VariationID="13961" VariationType="single nucleotide variant" Accession="VCV000013961" Version="143"><ClassifiedRecord><SimpleAllele><Location><SequenceLocation Assembly="GRCh38" Chr="7" positionVCF="140753336" referenceAlleleVCF="A" alternateAlleleVCF="T"/></Location></SimpleAllele></ClassifiedRecord></VariationArchive></ClinVarResult-Set>"""


class HTTP:
    def get(self, url, params=None, **kwargs):
        if "esearch" in url:
            return {"esearchresult": {"count": "1", "idlist": ["13961"]}}
        return XML


def variant(**changes):
    return {"genome_build": "GRCh38", "chrom": "7", "pos": 140753336, "ref": "A", "alt": "T", **changes}


def test_clinvar_confirms_vcf_alleles():
    result = resolve_clinvar(variant(), HTTP())
    assert result["status"] == "available"
    assert result["data"]["clinvar_variation_id"] == "13961"


def test_wrong_allele_and_build_do_not_resolve():
    assert resolve_clinvar(variant(alt="G"), HTTP())["status"] == "no_match"
    assert resolve_clinvar(variant(genome_build="GRCh37"), HTTP())["status"] == "no_match"


def test_mutalyzer_v3_route():
    class Normalizer:
        def get(self, url, params=None):
            assert url == "http://localhost:5000/api/normalize/NM_004333.6%3Ac.1799T%3EA"
            return {"normalized_description": "NM_004333.6:c.1799T>A"}

    result = normalize(
        {"hgvs_c": "NM_004333.6:c.1799T>A", "genome_build": "GRCh38"},
        Normalizer(),
        "http://localhost:5000/api",
    )
    assert result["status"] == "available"


def test_catt_keeps_source_records_separate(tmp_path, monkeypatch):
    import csv

    from variantrag.grounding import query_catt
    from variantrag.io import write_json

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    write_json(
        snapshot / "manifest.json",
        {
            "files": {},
            "tool_revision": "a" * 40,
            "variant_ids": ["10"],
            "variant_genes": {"10": ["TARGET"]},
        },
    )
    calls = []

    def run(command, cwd, **kwargs):
        source = next(x.split("=", 1)[1] for x in command if x.startswith("--sources="))
        assert "," not in source
        assert "--gene=TARGET" in command and "--variant=10" in command
        calls.append(source)
        with (cwd / (source + ".csv")).open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerows([["assertion"], ["first"], ["second"]])
        (cwd / (source + ".txt")).write_text("Source assertions")

    monkeypatch.setattr("variantrag.grounding.subprocess.run", run)
    result = query_catt("10", snapshot, tmp_path / "out")
    fields = result["data"]["fields"]
    assert len(calls) == 4
    assert len(fields) == 8
    assert len({f["evidence_id"] for f in fields}) == 8
    assert {f["source"] for f in fields} == set(calls)
