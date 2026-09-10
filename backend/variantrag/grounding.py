"""Real service adapters. Failures and unresolved identities are visible in the bundle."""

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .io import digest, read_json, write_json

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def resolve_clinvar(variant, http):
    build = variant["genome_build"]
    field = "chrpos37" if build == "GRCh37" else "chrpos38"
    chromosome = variant["chrom"].removeprefix("chr")
    term = f"{chromosome}[Chromosome] AND {variant['pos']}[{field}]"
    try:
        search = http.get(
            EUTILS + "esearch.fcgi", {"db": "clinvar", "term": term, "retmode": "json", "retmax": 100}
        )
        ids = search.get("esearchresult", {}).get("idlist", [])
        if int(search.get("esearchresult", {}).get("count", 0)) > 100:
            return {"status": "ambiguous", "reason": "Coordinate lookup exceeded candidate limit"}
        if not ids:
            return {"status": "no_match", "data": {"query": term, "candidates": []}}
        # esummary often leaves ref/alt empty and measure_id is NOT the Variation ID.
        # Confirm the build-specific VCF representation in authoritative VCV XML instead.
        xml = http.get(
            EUTILS + "efetch.fcgi",
            {"db": "clinvar", "id": ",".join(ids), "rettype": "vcv", "is_variationid": "true"},
            response_format="text",
        )
        from defusedxml import ElementTree as ET

        root = ET.fromstring(xml)
        matches, confirmations = [], []
        for archive in root.iter("VariationArchive"):
            # A haplotype's member allele cannot resolve the whole haplotype identifier.
            if archive.get("VariationType") not in {
                "single nucleotide variant",
                "Deletion",
                "Insertion",
                "Indel",
                "Duplication",
                "deletion",
                "insertion",
                "indel",
                "duplication",
            }:
                continue
            for location in archive.findall("./ClassifiedRecord/SimpleAllele/Location/SequenceLocation"):
                if (
                    location.get("Assembly") == build
                    and location.get("Chr", "").removeprefix("chr") == chromosome
                    and location.get("positionVCF") == str(variant["pos"])
                    and location.get("referenceAlleleVCF") == variant["ref"]
                    and location.get("alternateAlleleVCF") == variant["alt"]
                ):
                    matches.append(archive.get("VariationID"))
                    confirmations.append(
                        {
                            "variation_id": archive.get("VariationID"),
                            "accession": archive.get("Accession"),
                            "version": archive.get("Version"),
                            "location": dict(location.attrib),
                        }
                    )
        matches = sorted(set(matches))
        status = "available" if len(matches) == 1 else "ambiguous" if matches else "no_match"
        return {
            "status": status,
            "reason": None if matches else "No exact assembly/position/ref/alt confirmation",
            "data": {
                "clinvar_variation_id": matches[0] if len(matches) == 1 else None,
                "candidates": ids,
                "confirmed_ids": matches,
                "query": term,
                "confirmation": "VCV XML SequenceLocation VCF alleles",
                "records": confirmations,
                "source_sha256": hashlib.sha256(xml.encode()).hexdigest(),
            },
        }

    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


def normalize(variant, http, url):
    description = variant.get("hgvs_c")
    if not description or ":" not in description:
        return {
            "status": "unavailable",
            "reason": "A versioned transcript HGVS is required for normalization",
        }
    try:
        from urllib.parse import quote

        result = http.get(url.rstrip("/") + "/normalize/" + quote(description, safe=""))
        if result.get("errors"):
            return {
                "status": "error",
                "reason": "Mutalyzer rejected description",
                "data": {"response": result},
            }
        if not result.get("normalized_description"):
            return {
                "status": "unavailable",
                "reason": "Response lacks normalized_description",
                "data": {"response": result},
            }
        return {
            "status": "available",
            "data": {
                "input_description": description,
                "genome_build": variant["genome_build"],
                "response": result,
                "scope": "Transcript nomenclature; genomic build projection is not inferred",
            },
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


def refresh_catt(checkout, output, revision):
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"], text=True
    ).strip():
        raise ValueError("CATT checkout has modified tracked files")
    if actual != revision:
        raise ValueError("CATT checkout does not match the requested full commit hash")
    if output.exists():
        raise ValueError("Snapshot destination already exists; choose a new immutable snapshot")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < 20 * 1024**3:
        raise ValueError(
            "Full CATT snapshots need substantial free space; use --variant-ids for a bounded snapshot or select a larger volume"
        )
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / "snapshot"
        shutil.copytree(checkout, stage, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
        subprocess.run(
            [sys.executable, "main.py", "--force", "--loglevel=info"], cwd=stage, check=True, timeout=7200
        )
        files = {str(p.relative_to(stage)): digest(p) for p in stage.rglob("*") if p.is_file()}
        # Require actual configured release files, not README/transform scripts.
        import yaml

        data_files = []
        for name in (
            "clinvar-variant-summary",
            "clinvar-submission-summary",
            "gencc-submissions",
            "clingen-gene-disease",
        ):
            folder = stage / "sources" / name
            config = yaml.safe_load((folder / "config.yml").read_text())[0]
            path = (folder / config["file"]).resolve()
            if not path.is_relative_to(stage.resolve()) or not path.is_file() or not path.stat().st_size:
                raise ValueError(f"Refresh did not produce configured release data for {name}")
            data_files.append(path)
        write_json(
            stage / "manifest.json",
            {
                "tool_revision": actual,
                "files": files,
                "source_data_files": [str(p.relative_to(stage)) for p in data_files],
            },
        )
        stage.rename(output)
    return str(output)


def query_catt(variation_id, snapshot, output):
    snapshot, output = Path(snapshot).resolve(), Path(output).resolve()
    manifest = read_json(snapshot / "manifest.json")
    if "main.py" not in manifest["files"]:
        raise ValueError(
            "Legacy snapshot lacks executable checksums; rebuild or migrate the trusted snapshot"
        )
    for entry in snapshot.rglob("*"):
        if entry.is_symlink():
            raise ValueError("Snapshot symlinks are not allowed")
        if (
            entry.is_file()
            and entry != snapshot / "manifest.json"
            and str(entry.relative_to(snapshot)) not in manifest["files"]
        ):
            raise ValueError("Snapshot contains unchecked executable or data files")
    for name, expected in manifest["files"].items():
        path = (snapshot / name).resolve()
        if not path.is_relative_to(snapshot) or digest(path) != expected:
            raise ValueError("CATT snapshot failed integrity validation")
    if not str(variation_id).isdigit():
        raise ValueError("CATT requires a verified numeric Variation ID")
    if manifest.get("variant_ids") and str(variation_id) not in manifest["variant_ids"]:
        raise ValueError("Variation ID is outside this snapshot scope")
    genes = manifest.get("variant_genes", {}).get(str(variation_id), [])
    if not genes:
        summary = snapshot / "sources/clinvar-variant-summary/variant_summary.txt"
        with summary.open() as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            for row in reader:
                if row.get("VariationID") == str(variation_id):
                    import re

                    genes.extend(g for g in re.split(r"[;,]", row.get("GeneSymbol", "")) if g and g != "-")
    if not genes:
        raise ValueError("No source-confirmed gene mapping; cannot constrain gene-level dossiers")
    output.mkdir(parents=True, exist_ok=True)
    # Query sources separately: cross-source joins multiply independent submissions
    # and gene assertions into a large Cartesian product without adding evidence.
    sources = [
        "clinvar-variant-summary",
        "clinvar-submission-summary",
        "gencc-submissions",
        "clingen-gene-disease",
    ]
    fields, dossiers, artifact_names = [], [], []
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary) / "catt"
        shutil.copytree(snapshot, work)
        for source in sources:
            names = [f"{source}.csv", f"{source}.txt"]
            command = [
                sys.executable,
                "main.py",
                f"--variant={variation_id}",
                "--gene=" + ",".join(sorted(set(genes))),
                "--template",
                f"--sources={source}",
                f"--joined-output={names[0]}",
                f"--template-output={names[1]}",
            ]
            subprocess.run(command, cwd=work, check=True, timeout=1800)
            for name in names:
                if not (work / name).is_file():
                    raise ValueError(f"CATT did not produce {name}")
                shutil.copy2(work / name, output / name)
            artifact_names.extend(names)
            dossiers.append((output / names[1]).read_text())
            with (output / names[0]).open() as stream:
                for i, row in enumerate(csv.DictReader(stream)):
                    for key, value in row.items():
                        if value:
                            fields.append(
                                {
                                    "evidence_id": f"catt:{variation_id}:{source}:{i}:{hashlib.sha256(key.encode()).hexdigest()[:10]}",
                                    "source": source,
                                    "record_id": str(i),
                                    "field": key,
                                    "value": value,
                                }
                            )
    (output / "variant.txt").write_text("\n\n".join(dossiers))
    with (output / "variant.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["evidence_id", "source", "record_id", "field", "value"])
        writer.writeheader()
        writer.writerows(fields)
    artifact_names.extend(["variant.txt", "variant.csv"])
    return {
        "status": "available",
        "data": {
            "snapshot_id": digest(snapshot / "manifest.json"),
            "snapshot_scope": manifest.get("scope", "full"),
            "genes": sorted(set(genes)),
            "tool_revision": manifest["tool_revision"],
            "fields": fields,
            "dossier_text": (output / "variant.txt").read_text(),
            "artifacts": {
                name: {"path": str(output / name), "sha256": digest(output / name)} for name in artifact_names
            },
        },
    }
