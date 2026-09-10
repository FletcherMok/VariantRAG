import hashlib

from .io import digest
from .tables import variant_match


def extract_pdf(path, document_id, pmid=None):
    from docling.document_converter import DocumentConverter

    source_hash = digest(path)
    doc = DocumentConverter().convert(str(path)).document
    passages, tables = [], []
    for index, item in enumerate(doc.texts):
        text = item.text
        if not text.strip():
            continue
        provenance = item.prov[0] if item.prov else None
        passages.append(
            {
                "document_id": document_id,
                "pmid": pmid,
                "chunk_id": f"text-{index}",
                "text": text,
                "page": provenance.page_no if provenance else None,
                "offsets": [0, len(text)],
                "source_hash": source_hash,
                "synthetic": False,
            }
        )
    for index, table in enumerate(doc.tables):
        frame = table.export_to_dataframe(doc=doc)
        tables.append(
            {
                "document_id": document_id,
                "pmid": pmid,
                "table_id": f"table-{index}",
                "headers": [str(c) for c in frame.columns],
                "rows": [
                    {"row_id": row, "cells": [str(v) for v in values]}
                    for row, values in enumerate(frame.itertuples(index=False, name=None))
                ],
                "source_hash": source_hash,
                "synthetic": False,
            }
        )
    return {"passages": passages, "tables": tables}


def lexical_retrieve(passages, variant, limit=10):
    query = variant.get("hgvs_c")
    if not query:
        return []
    hits = []
    for passage in passages:
        if not variant_match(passage["text"], query, variant.get("transcript")):
            continue
        identity = passage["document_id"] + ":" + passage["chunk_id"]
        hits.append(
            {
                **passage,
                "evidence_id": "text:" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                "exact_quote": passage["text"],
                "retrieval_score": 1.0,
                "model_revision": "exact-hgvs-lexical-v1",
                "retrieval_method": "lexical",
            }
        )
    return hits[:limit]


def medcpt_retrieve(passages, variant, model_directory, limit=10):
    """Run PyTorch in a separate process so its OpenMP runtime cannot conflict with FAISS.

    Corpus embeddings are cached by exact source text and model manifest hash.
    """
    import json
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    import faiss
    import numpy as np

    from .io import write_json

    if not passages:
        return []
    root = Path(model_directory).resolve()
    manifest_hash = digest(root / "manifest.json")
    corpus_hash = hashlib.sha256(
        json.dumps([manifest_hash, [p["text"] for p in passages]], sort_keys=True).encode()
    ).hexdigest()
    cache = root / "indexes"
    cache.mkdir(parents=True, exist_ok=True)
    query = " ".join(filter(None, [variant.get("gene"), variant.get("hgvs_c"), variant.get("hgvs_p")]))
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        settings = {
            "model_directory": str(root),
            "corpus_vectors": str(cache / (corpus_hash + ".npy")),
            "query_vectors": str(temporary / "query.npy"),
            "query": query,
            "passages": [p["text"] for p in passages],
        }
        write_json(temporary / "request.json", settings)
        environment = {
            **os.environ,
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "1"),
            "TOKENIZERS_PARALLELISM": "false",
        }
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("_embed_worker.py")),
                str(temporary / "request.json"),
            ],
            env=environment,
            check=True,
            timeout=600,
        )
        matrix = np.load(settings["corpus_vectors"], allow_pickle=False)
        q = np.load(settings["query_vectors"], allow_pickle=False)
    faiss.omp_set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))
    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    scores, positions = index.search(q, min(limit, len(passages)))
    hits = []
    for score, position in zip(scores[0], positions[0], strict=True):
        p = passages[int(position)]
        hits.append(
            {
                **p,
                "evidence_id": "text:"
                + hashlib.sha256((p["document_id"] + ":" + p["chunk_id"]).encode()).hexdigest()[:20],
                "exact_quote": p["text"],
                "retrieval_score": float(score),
                "retrieval_method": "MedCPT inner product",
                "model_revision": manifest_hash,
                "corpus_hash": corpus_hash,
                "query": query,
            }
        )
    return hits


def extract_bioc(path, document_id, pmid=None):
    """Read native BioC passages and embedded XML tables without whitespace table heuristics."""
    from defusedxml import ElementTree as ET

    source_hash = digest(path)
    root = ET.parse(path).getroot()
    passages, tables = [], []
    for index, passage in enumerate(root.findall(".//passage")):
        info = {item.get("key"): item.text for item in passage.findall("infon")}
        text = passage.findtext("text") or ""
        if info.get("type") == "table" and info.get("xml"):
            table = ET.fromstring(info["xml"])
            headers = [" ".join(cell.itertext()).strip() for cell in table.findall("./thead/tr/th")]
            rows = []
            for row_index, row in enumerate(table.findall("./tbody/tr")):
                cells = row.findall("td")
                if any(c.get("rowspan", "1") != "1" or c.get("colspan", "1") != "1" for c in cells):
                    raise ValueError("Merged BioC table cells require explicit cell-span expansion")
                rows.append({"row_id": row_index, "cells": [" ".join(c.itertext()).strip() for c in cells]})
            tables.append(
                {
                    "document_id": document_id,
                    "pmid": pmid,
                    "table_id": info.get("id", str(index)),
                    "headers": headers,
                    "rows": rows,
                    "source_hash": source_hash,
                    "synthetic": False,
                }
            )
        elif info.get("section_type") not in {"TABLE", "REF"} and text:
            offset = int(passage.findtext("offset") or 0)
            passages.append(
                {
                    "document_id": document_id,
                    "pmid": pmid,
                    "chunk_id": str(index),
                    "text": text,
                    "offsets": [offset, offset + len(text)],
                    "source_hash": source_hash,
                    "synthetic": False,
                }
            )
    return {"passages": passages, "tables": tables, "source_format": "BioC XML"}
