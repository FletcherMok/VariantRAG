#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 4 ]; then
  echo "Usage: backend/init.sh CATT_CHECKOUT FULL_COMMIT_SHA NEW_SNAPSHOT_DIRECTORY VARIATION_IDS" >&2
  exit 2
fi
python -m variantrag.cli catt-refresh --checkout "$1" --revision "$2" --out "$3" --variant-ids "$4"
