"""Explicit model preparation; record immutable upstream revisions for replay."""

import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

root = Path("backend/data/models/medcpt")
manifest = {}
for folder, repo, revision in [
    ("query", "ncbi/MedCPT-Query-Encoder", "d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc"),
    ("article", "ncbi/MedCPT-Article-Encoder", "d05a736da4bb84ee4057b7f7999485be6ed85465"),
]:
    info = HfApi().model_info(repo, revision=revision)
    filenames = {file.rfilename for file in info.siblings}
    weights = "model.safetensors" if "model.safetensors" in filenames else "pytorch_model.bin"
    snapshot_download(
        repo_id=repo,
        revision=info.sha,
        local_dir=root / folder,
        allow_patterns=[
            "config.json",
            weights,
            "vocab.txt",
            "tokenizer*",
            "special_tokens_map.json",
        ],
    )
    manifest[folder] = {"repository": repo, "revision": info.sha}
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest))
