"""Allele-specific consequence parsing. No unverified HGVS or ClinVar identifiers are invented."""

import re
from pathlib import Path

from cyvcf2 import VCF

from .models import Variant

TARGET_CONSEQUENCES = frozenset(
    {
        "stop_gained",
        "frameshift_variant",
        "splice_donor_variant",
        "splice_acceptor_variant",
        "missense_variant",
    }
)


def allele_token(ref, alt):
    while ref and alt and ref[0] == alt[0]:
        ref, alt = ref[1:], alt[1:]
    while ref and alt and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    return alt or "-"


def annotation_fields(reader, name):
    try:
        description = reader.get_header_type(name)["Description"]
    except KeyError:
        return None
    match = re.search(r"Format:\s*([^\"]+)", description, re.I)
    if match:
        return [x.strip(" '\"") for x in match.group(1).split("|")]
    if name == "ANN":
        match = re.search(r"'(Allele\s*\|[^']+)'", description)
        if match:
            return [x.strip() for x in match.group(1).split("|")]
    raise ValueError(f"{name} header lacks named annotation fields; use annotated VEP CSQ or SnpEff ANN")


def parse_variants(vcf, build, sample=None, reference=None, max_records=100000, max_candidates=1000):
    if build not in {"GRCh37", "GRCh38"}:
        raise ValueError("genome_build must be GRCh37 or GRCh38")
    with open(vcf, "rb") as stream:
        compressed = stream.read(2) == b"\x1f\x8b"
    if compressed:
        import gzip

        expanded = 0
        with gzip.open(vcf, "rb") as stream:
            while chunk := stream.read(1024 * 1024):
                expanded += len(chunk)
                if expanded > 100 * 1024**2:
                    raise ValueError("Decompressed VCF exceeds 100 MiB; submit a smaller interval")
    reader = VCF(str(vcf))
    fasta = None
    try:
        declared = re.findall(r"##reference=.*?(GRCh3[78])", reader.raw_header)
        if declared and any(value != build for value in declared):
            raise ValueError("VCF reference header conflicts with requested genome build")
        fields = {name: annotation_fields(reader, name) for name in ("CSQ", "ANN")}
        if not any(fields.values()):
            raise ValueError("VCF requires VEP CSQ or SnpEff ANN annotations before filtering")
        if len(reader.samples) > 1 and sample is None:
            raise ValueError("Select --sample explicitly for a multisample VCF")
        sample = sample or (reader.samples[0] if reader.samples else None)
        if sample and sample not in reader.samples:
            raise ValueError(f"Sample {sample!r} is not in VCF")
        sample_index = reader.samples.index(sample) if sample else None
        if reference:
            import pysam

            fasta = pysam.FastaFile(str(reference))
        records, rejected = [], []
        for record_number, record in enumerate(reader, 1):
            if record_number > max_records:
                raise ValueError("VCF record limit exceeded; submit a smaller candidate set")
            if record.FILTER not in (None, "PASS"):
                rejected.append({"chrom": record.CHROM, "pos": record.POS, "reason": "VCF_FILTER"})
                continue
            if (
                fasta
                and fasta.fetch(record.CHROM, record.POS - 1, record.POS - 1 + len(record.REF)).upper()
                != record.REF.upper()
            ):
                raise ValueError(f"Reference mismatch at {record.CHROM}:{record.POS}")
            genotype = record.genotypes[sample_index] if sample_index is not None else []
            for alt_index, alt in enumerate(record.ALT, 1):
                if not re.fullmatch(r"[ACGT]+", alt or "", re.I):
                    rejected.append(
                        {"chrom": record.CHROM, "pos": record.POS, "alt": alt, "reason": "unsupported_allele"}
                    )
                    continue
                if genotype and alt_index not in genotype[:-1]:
                    continue
                annotations = []
                for name, columns in fields.items():
                    raw = record.INFO.get(name) if columns else None
                    for item in (raw or "").split(","):
                        if not item:
                            continue
                        entry = dict(zip(columns, item.split("|"), strict=False))
                        token = entry.get("Allele")
                        if entry.get("ALLELE_NUM"):
                            matches = entry["ALLELE_NUM"] == str(alt_index)
                        elif token == alt:
                            matches = True
                        else:
                            compatible = [a for a in record.ALT if allele_token(record.REF, a) == token]
                            matches = token == allele_token(record.REF, alt) and len(compatible) == 1
                        consequence = entry.get("Consequence", entry.get("Annotation", ""))
                        if matches and TARGET_CONSEQUENCES.intersection(consequence.split("&")):
                            annotations.append(entry)
                if not annotations:
                    continue
                # Stable transcript choice; all retained annotations remain inspectable.
                annotations.sort(
                    key=lambda a: (
                        not bool(a.get("MANE_SELECT")),
                        a.get("CANONICAL") != "YES",
                        a.get("Feature", a.get("Feature_ID", "")),
                    )
                )
                primary = annotations[0]
                consequences = sorted(
                    {c for a in annotations for c in a.get("Consequence", a.get("Annotation", "")).split("&")}
                )

                def fmt(name, current_record=record):
                    try:
                        value = current_record.format(name)
                        return (
                            value[sample_index].tolist()
                            if value is not None and sample_index is not None
                            else []
                        )
                    except (KeyError, ValueError):
                        return []

                ps = fmt("PS")
                key = f"{build}:{record.CHROM.removeprefix('chr')}:{record.POS}:{record.REF}:{alt}"
                if len(records) >= max_candidates:
                    raise ValueError("Candidate limit exceeded; prefilter to at most 1000 alleles")
                records.append(
                    Variant(
                        key=key,
                        genome_build=build,
                        chrom=record.CHROM,
                        pos=record.POS,
                        ref=record.REF,
                        alt=alt,
                        sample_id=sample,
                        genotype=genotype[:-1],
                        phased=bool(genotype[-1]) if genotype else False,
                        phase_set=str(ps[0]) if ps and ps[0] >= 0 else None,
                        consequences=consequences,
                        annotations=annotations,
                        transcript=primary.get("Feature", primary.get("Feature_ID")) or None,
                        gene=primary.get("SYMBOL", primary.get("Gene_Name")) or None,
                        hgnc_id=primary.get("HGNC_ID") or None,
                        hgvs_c=primary.get("HGVSc", primary.get("HGVS.c")) or None,
                        hgvs_p=primary.get("HGVSp", primary.get("HGVS.p")) or None,
                        quality=record.QUAL,
                        allele_depths=fmt("AD"),
                        reference_status="validated" if fasta else "not_checked",
                    ).model_dump()
                )
        if len({r["key"] for r in records}) != len(records):
            raise ValueError("Duplicate allele records; normalize/deduplicate the input VCF first")
        return records, rejected
    finally:
        reader.close()
        if fasta:
            fasta.close()


def alignment_evidence(variant, bam, reference=None):
    import pysam

    if str(bam).endswith(".cram") and not reference:
        raise ValueError("CRAM requires the matching reference FASTA")
    with pysam.AlignmentFile(str(bam), reference_filename=str(reference) if reference else None) as alignment:
        if not alignment.has_index():
            raise ValueError("Alignment requires a BAI/CRAI index")
        samples = {r.get("SM") for r in alignment.header.to_dict().get("RG", []) if r.get("SM")}
        if variant["sample_id"] and samples != {variant["sample_id"]}:
            from .io import digest, read_json

            sidecar = Path(str(bam) + ".manifest.json")
            provenance = read_json(sidecar) if sidecar.exists() else {}
            if (
                samples
                or provenance.get("sample") != variant["sample_id"]
                or provenance.get("sha256") != digest(bam)
                or provenance.get("assembly") != variant["genome_build"]
                or not provenance.get("source_url")
            ):
                raise ValueError(
                    "Alignment read groups or a checksummed source manifest must identify the selected VCF sample"
                )
        if len(variant["ref"]) != 1 or len(variant["alt"]) != 1:
            return {
                "status": "unavailable",
                "reason": "Indel read support requires local haplotype realignment",
            }
        counts = alignment.count_coverage(
            variant["chrom"], variant["pos"] - 1, variant["pos"], quality_threshold=20, read_callback="all"
        )
        bases = {b: int(c[0]) for b, c in zip("ACGT", counts, strict=True)}
        return {
            "status": "available",
            "data": {
                "depth": sum(bases.values()),
                "ref_reads": bases[variant["ref"]],
                "alt_reads": bases[variant["alt"]],
                "method": "pysam count_coverage; base quality >=20; read_callback=all",
                "artifact_ref": str(Path(bam).resolve()),
            },
        }
