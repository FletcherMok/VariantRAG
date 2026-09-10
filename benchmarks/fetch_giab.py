"""Download only a matched HG002 interval, using indexed HTTP range reads.

Source: official GIAB v4.2.1 benchmark and GIAB alignment index.
This is technical validation data, not a disease-positive case.
"""

import argparse
import hashlib
import json
from pathlib import Path

import pysam

BASE = "https://ftp.ncbi.nlm.nih.gov/ReferenceSamples/giab/"
VCF = (
    BASE
    + "release/AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/GRCh38/HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz"
)
BAM = (
    BASE
    + "data/AshkenazimTrio/HG002_NA24385_son/NIST_HiSeq_HG002_Homogeneity-10953946/NHGRI_Illumina300X_AJtrio_novoalign_bams/HG002.GRCh38.300x.bam"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="results/public-data")
    parser.add_argument("--region", default="22:20000000-20002000", help="1-based closed interval")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chrom, interval = args.region.split(":")
    start, end = map(int, interval.split("-"))
    if end - start > 20000 or start < 1 or end < start:
        raise ValueError("Keep the smoke-test region within 20 kb")
    with pysam.VariantFile(VCF) as source:
        contig = chrom if chrom in source.header.contigs else "chr" + chrom
        with pysam.VariantFile(str(out / "HG002.raw.vcf.gz"), "wz", header=source.header) as target:
            count = 0
            for record in source.fetch(contig, start - 1, end):
                target.write(record)
                count += 1
    pysam.tabix_index(str(out / "HG002.raw.vcf.gz"), preset="vcf", force=True)
    with pysam.AlignmentFile(BAM) as source:
        contig = chrom if chrom in source.references else "chr" + chrom
        with pysam.AlignmentFile(str(out / "HG002.bam"), "wb", header=source.header) as target:
            reads = 0
            for record in source.fetch(contig, start - 1, end):
                target.write(record)
                reads += 1
        samples = sorted({r.get("SM") for r in source.header.to_dict().get("RG", []) if r.get("SM")})
    pysam.index(str(out / "HG002.bam"))
    manifest = {
        "assembly": "GRCh38",
        "sample": "HG002",
        "alignment_sample_names": samples,
        "region_1_based_closed": args.region,
        "vcf_url": VCF,
        "bam_url": BAM,
        "vcf_records": count,
        "alignment_records": reads,
        "note": "Raw benchmark VCF requires real consequence annotation before prioritization.",
        "source_index": "https://github.com/genome-in-a-bottle/giab_data_indexes/blob/master/AshkenazimTrio/alignment.index.AJtrio_Illumina300X_wgs_novoalign_GRCh37_GRCh38_NHGRI_07282015.HG002",
        "artifacts": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "HG002.bam.manifest.json").write_text(
        json.dumps(
            {
                "sample": "HG002",
                "assembly": "GRCh38",
                "sha256": hashlib.sha256((out / "HG002.bam").read_bytes()).hexdigest(),
                "source_url": BAM,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps({"variants": count, "reads": reads, "samples": samples}))


if __name__ == "__main__":
    main()
