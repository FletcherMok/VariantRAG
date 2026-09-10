"""Inspect logical/allocated bytes; delete only explicit rebuildable project caches."""

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def measure(path):
    logical = allocated = count = 0
    if not path.exists():
        return {"logical_bytes": 0, "allocated_bytes": 0, "files": 0}
    for base, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
        for name in files:
            file = Path(base) / name
            if not file.is_symlink():
                info = file.stat()
                logical += info.st_size
                allocated += getattr(info, "st_blocks", 0) * 512
                count += 1
    return {"logical_bytes": logical, "allocated_bytes": allocated, "files": count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean", action="store_true", help="Remove rebuildable caches; preserve results and models"
    )
    parser.add_argument(
        "--frontend-deps", action="store_true", help="Also remove node_modules; npm ci restores it"
    )
    args = parser.parse_args()
    paths = [".pytest_cache", ".ruff_cache", "build", "frontend/.next"]
    if args.frontend_deps:
        paths.append("frontend/node_modules")
    report = {name: measure(ROOT / name) for name in paths}
    if args.clean:
        if not (ROOT / "frontend/out/index.html").is_file() and (ROOT / "frontend/.next").exists():
            raise SystemExit(
                "Build the static export first; do not remove a running development server's cache"
            )
        for name in paths:
            path = ROOT / name
            if path.is_symlink():
                raise SystemExit(f"Refusing symlink: {name}")
            if path.exists():
                shutil.rmtree(path)
    print(json.dumps({"action": "removed" if args.clean else "dry_run", "paths": report}, indent=2))


if __name__ == "__main__":
    main()
