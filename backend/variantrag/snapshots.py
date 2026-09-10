"""Resource-bounded CATT snapshots from real upstream releases.

Only selected variant records and their linked gene records are retained. Entire archives
are scanned, but never loaded into pandas or expanded wholesale on disk.
"""

import csv
import gzip
import hashlib
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests
import yaml

from .io import digest, write_json

SOURCES = [
    "clinvar-variant-summary",
    "clinvar-submission-summary",
    "gencc-submissions",
    "clingen-gene-disease",
]


def download(url, path):
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                with Path(path).open("wb") as target:
                    for chunk in response.iter_content(1024 * 1024):
                        target.write(chunk)
                return {
                    "url": url,
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "sha256": digest(path),
                }
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def bounded_refresh(checkout, output, revision, variant_ids):
    ids = {str(x) for x in variant_ids}
    if not ids or any(not x.isdigit() for x in ids):
        raise ValueError("Provide numeric ClinVar Variation IDs for a bounded snapshot")
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != revision:
        raise ValueError("CATT checkout does not match the full commit SHA")
    if output.exists():
        raise ValueError("Snapshot destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    genes, variant_genes, source_manifest = set(), {}, {}
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        stage = Path(temporary) / "snapshot"
        shutil.copytree(
            checkout,
            stage,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "__pycache__", "sources", "example_catt_outputs_for_llm", "icon_github.jpg"
            ),
        )
        for name in SOURCES:
            destination = stage / "sources" / name
            shutil.copytree(
                checkout / "sources" / name,
                destination,
                ignore=shutil.ignore_patterns("*_HCM.txt", "__pycache__"),
            )
            config = yaml.safe_load((destination / "config.yml").read_text())[0]
            archive = Path(temporary) / "source-download"
            print(f"Scanning {name} for bounded snapshot...", flush=True)
            metadata = download(config["url"], archive)
            if config.get("md5_url"):
                checksum = Path(temporary) / "checksum"
                download(config["md5_url"], checksum)
                expected = checksum.read_text().split()[0]
                hasher = hashlib.md5()
                with archive.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        hasher.update(block)
                if hasher.hexdigest() != expected:
                    raise ValueError(f"{name} upstream MD5 mismatch; source may have changed during refresh")
                metadata["upstream_md5"] = expected
            opener = gzip.open if config.get("gzip") else open
            delimiter = "\t" if config["delimiter"] == "tab" else ","
            selected = 0
            with opener(archive, "rt", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream, delimiter=delimiter, quoting=config.get("quoting", 0))
                key = (
                    "VariationID"
                    if name.startswith("clinvar")
                    else "gene_symbol"
                    if name == "gencc-submissions"
                    else "GENE SYMBOL"
                )
                header = None
                for raw in reader:
                    cleaned = [c.lstrip("#").strip() for c in raw]
                    if key in cleaned:
                        header = cleaned
                        break
                if header is None:
                    raise ValueError(f"{name} no longer exposes required column {key}")
                with (destination / config["file"]).open("w", newline="") as target:
                    writer = csv.writer(target, delimiter=delimiter)
                    writer.writerow(header)
                    for row in reader:
                        if len(row) != len(header):
                            continue
                        record = dict(zip(header, row, strict=True))
                        if record[key] not in (ids if name.startswith("clinvar") else genes):
                            continue
                        if name == "clinvar-variant-summary":
                            related = {
                                g for g in re.split(r"[;,]", record.get("GeneSymbol", "")) if g and g != "-"
                            }
                            genes.update(related)
                            variant_genes.setdefault(record[key], set()).update(related)
                        writer.writerow(row)
                        selected += 1
            if name == "clinvar-variant-summary" and ids - set(variant_genes):
                raise ValueError("Some selected IDs were not found in the current ClinVar summary")
            # Subset file has a clean first-row header. The upstream template/dictionary is unchanged.
            config["skip_rows"] = ""
            config["header_row"] = 0
            config["quoting"] = 0
            (destination / "config.yml").write_text(yaml.safe_dump([config], sort_keys=False))
            archive.unlink()
            source_manifest[name] = {
                **metadata,
                "selected_rows": selected,
                "subset_sha256": digest(destination / config["file"]),
            }
        manifest = {
            "tool_revision": revision,
            "scope": "selected variants and linked genes",
            "variant_ids": sorted(ids),
            "variant_genes": {v: sorted(g) for v, g in variant_genes.items()},
            "sources": source_manifest,
            "files": {
                str(p.relative_to(stage)): digest(p) for p in (stage / "sources").rglob("*") if p.is_file()
            },
            "source_data_files": [
                str(
                    Path("sources")
                    / name
                    / yaml.safe_load((stage / "sources" / name / "config.yml").read_text())[0]["file"]
                )
                for name in SOURCES
            ],
        }
        write_json(stage / "manifest.json", manifest)
        stage.rename(output)
    return str(output)
