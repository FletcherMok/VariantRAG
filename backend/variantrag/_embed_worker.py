"""Isolated PyTorch worker: never imports FAISS into the same native runtime."""

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


def main():
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))
    config = json.loads(Path(sys.argv[1]).read_text())
    root = Path(config["model_directory"])
    corpus = Path(config["corpus_vectors"])
    with torch.no_grad():
        if not corpus.exists():
            tokenizer = AutoTokenizer.from_pretrained(root / "article", local_files_only=True)
            model = AutoModel.from_pretrained(root / "article", local_files_only=True).eval()
            vectors = []
            for start in range(0, len(config["passages"]), 16):
                batch = config["passages"][start : start + 16]
                tokens = tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt")
                vectors.append(model(**tokens).last_hidden_state[:, 0].numpy())
            with tempfile.NamedTemporaryFile(dir=corpus.parent, suffix=".npy", delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    np.save(stream, np.concatenate(vectors).astype("float32"))
                    stream.flush()
                    os.replace(temporary, corpus)
                finally:
                    temporary.unlink(missing_ok=True)
            del model, tokenizer
        tokenizer = AutoTokenizer.from_pretrained(root / "query", local_files_only=True)
        model = AutoModel.from_pretrained(root / "query", local_files_only=True).eval()
        tokens = tokenizer([config["query"]], return_tensors="pt", truncation=True, max_length=64)
        np.save(config["query_vectors"], model(**tokens).last_hidden_state[:, 0].numpy().astype("float32"))


if __name__ == "__main__":
    main()
