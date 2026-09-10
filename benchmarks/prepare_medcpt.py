"""Explicit model preparation; record immutable upstream revisions for replay."""

import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

root = Path("backend/data/models/medcpt")
manifest = {}
for folder, repo in [("query", "ncbi/MedCPT-Query-Encoder"), ("article", "ncbi/MedCPT-Article-Encoder")]:
    info = HfApi().model_info(repo)
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
