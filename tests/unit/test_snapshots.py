import csv
import gzip
import hashlib
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
pytest.importorskip("requests")
snapshots = pytest.importorskip("variantrag.snapshots")
SOURCES = snapshots.SOURCES
bounded_refresh = snapshots.bounded_refresh


def test_bounded_snapshot_filters_variants_and_genes(tmp_path, monkeypatch):
    checkout = tmp_path / "upstream"
    checkout.mkdir()
    (checkout / "main.py").write_text("# fixture tool source\n")
    for name in SOURCES:
        folder = checkout / "sources" / name
        folder.mkdir(parents=True)
        config = {
            "name": name,
            "url": "https://example.invalid/" + name,
            "file": "data.tsv",
            "delimiter": "tab",
            "quoting": 0,
            "gzip": name.startswith("clinvar"),
        }
        (folder / "config.yml").write_text(yaml.safe_dump([config]))
        (folder / "dictionary.csv").write_text("column,join-group\nVariationID,variation-id\n")

    def fake_download(url, path):
        name = url.rsplit("/", 1)[-1]
        if name == "clinvar-variant-summary":
            text = "VariationID\tGeneSymbol\n10\tTARGET\n20\tOTHER\n"
        elif name == "clinvar-submission-summary":
            text = "VariationID\tComment\n10\tselected\n20\tunrelated\n"
        elif name == "gencc-submissions":
            text = "gene_symbol\tclassification_title\nTARGET\tLimited\nOTHER\tDefinitive\n"
        else:
            text = "GENE SYMBOL\tCLASSIFICATION\nTARGET\tLimited\nOTHER\tDefinitive\n"
        payload = gzip.compress(text.encode()) if name.startswith("clinvar") else text.encode()
        Path(path).write_bytes(payload)
        return {"url": url, "sha256": hashlib.sha256(payload).hexdigest()}

    monkeypatch.setattr("variantrag.snapshots.download", fake_download)
    monkeypatch.setattr("variantrag.snapshots.subprocess.check_output", lambda *a, **k: "a" * 40)
    out = tmp_path / "bounded"
    bounded_refresh(checkout, out, "a" * 40, ["10"])
    from variantrag.io import read_json

    manifest = read_json(out / "manifest.json")
    assert manifest["variant_ids"] == ["10"]
    assert manifest["variant_genes"] == {"10": ["TARGET"]}
    for name in SOURCES:
        assert yaml.safe_load((out / "sources" / name / "config.yml").read_text())[0]["skip_rows"] == ""
        rows = list(csv.DictReader((out / "sources" / name / "data.tsv").open(), delimiter="\t"))
        assert len(rows) == 1
        assert "OTHER" not in str(rows)
    with pytest.raises(ValueError, match="exists"):
        bounded_refresh(checkout, out, "a" * 40, ["10"])
