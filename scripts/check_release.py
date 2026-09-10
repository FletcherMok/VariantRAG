"""Check the proposed Git tree for accidental data/dependencies before committing."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {"node_modules", ".venv", "results", "work", ".next", "__pycache__"}
FORBIDDEN_SUFFIXES = {".bam", ".cram", ".bai", ".tbi", ".crai", ".duckdb", ".sqlite", ".safetensors", ".bin"}


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    problems = []
    total = count = 0
    for name in filter(None, names):
        path = ROOT / name
        if not path.exists():
            continue  # Deletion must be staged before final git diff --cached review.
        if path.is_symlink():
            problems.append(f"Review symlink: {name}")
            continue
        size = path.stat().st_size
        total += size
        count += 1
        if FORBIDDEN_PARTS.intersection(path.relative_to(ROOT).parts) or path.suffix in FORBIDDEN_SUFFIXES:
            problems.append(f"Generated/data asset tracked: {name}")
        if size > 1024 * 1024:
            problems.append(f"File exceeds 1 MiB: {name}")
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Release tree: {count} files, {total:,} bytes; no generated-data or oversized-file matches")


if __name__ == "__main__":
    main()
