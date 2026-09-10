"""Annotate the public GIAB subset with Ensembl VEP, preserving the exact response and version.

For large/private cohorts use a pinned local VEP cache; this script only accepts the public fetch manifest.
"""

import hashlib
import json
from pathlib import Path

import httpx
import pysam

ROOT = Path("results/public-data")
manifest = json.loads((ROOT / "manifest.json").read_text())
path = ROOT / "HG002.raw.vcf.gz"
if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifacts"]["HG002.raw.vcf.gz"]:
    raise ValueError("Public input changed since fetch; refusing network annotation")
with pysam.VariantFile(path) as source:
    records = list(source)
    header = source.header.copy()
inputs = [
    " ".join([r.chrom.removeprefix("chr"), str(r.pos), ".", r.ref, ",".join(r.alts), ".", ".", "."])
    for r in records
]
with httpx.Client(timeout=90) as client:
    info = client.get("https://rest.ensembl.org/info/software", headers={"Accept": "application/json"})
    info.raise_for_status()
    response = client.post(
        "https://rest.ensembl.org/vep/human/region",
        json={"variants": inputs, "hgvs": 1, "canonical": 1, "transcript_version": 1},
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    result = response.json()
(ROOT / "vep-response.json").write_text(json.dumps(result, indent=2) + "\n")
header.add_meta("reference", value="GRCh38")
header.add_meta(
    "INFO",
    items=[
        ("ID", "CSQ"),
        ("Number", "."),
        ("Type", "String"),
        (
            "Description",
            "VEP REST transcript annotations. Format: Allele|Consequence|SYMBOL|Feature|HGVSc|HGVSp|ALLELE_NUM",
        ),
    ],
)
by_input = {item["input"]: item for item in result}
with pysam.VariantFile(ROOT / "HG002.annotated.vcf", "w", header=header) as out:
    for record, input_text in zip(records, inputs, strict=True):
        record.translate(header)
        item = by_input[input_text]
        if item.get("assembly_name") != "GRCh38":
            raise ValueError("VEP assembly mismatch")
        annotations = []
        for t in item.get("transcript_consequences", []):
            annotations.append(
                "|".join(
                    [
                        t["variant_allele"],
                        "&".join(t["consequence_terms"]),
                        t.get("gene_symbol", ""),
                        t.get("transcript_id", ""),
                        t.get("hgvsc", ""),
                        t.get("hgvsp", ""),
                        "1",
                    ]
                )
            )
        if annotations:
            record.info["CSQ"] = ",".join(annotations)
        out.write(record)
(ROOT / "annotation-manifest.json").write_text(
    json.dumps(
        {
            "service": "Ensembl VEP REST",
            "software": info.json(),
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "response_sha256": hashlib.sha256((ROOT / "vep-response.json").read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256((ROOT / "HG002.annotated.vcf").read_bytes()).hexdigest(),
        },
        indent=2,
    )
    + "\n"
)
print("Annotated", len(records), "public variants; service", info.json())
