# Contributing

Use the locked Python and npm environments in the README. Install the package again after changing its source when using the non-editable local installation. Do not commit generated runs, genomic datasets, model weights, credentials, or patient data. Keep synthetic test fixtures explicitly labeled.

Changes to allele matching or table recovery need tests that demonstrate a plausible false positive or false negative. Changes to ranking should preserve replay, citations, order-bias detection, and disconnected-graph behavior. Avoid tests that merely assert the implementation's own output without an independent expectation.

## Before a commit

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check backend/variantrag tests benchmarks scripts
npm ci --prefix frontend
npm run build --prefix frontend
git diff --check
git diff --cached --stat
```

Run `scripts/security_scan.sh` for current vulnerability and secret scans. It needs `uv`, `npm`, and a Gitleaks executable on PATH. Review the optional research dependency report even when core scans pass.

CI definitions are included; a local audit does not establish that GitHub-hosted CI has run successfully. Docker runtime verification and independent scientific evaluation are separate release gates.

## Reviewable release

Use a small, descriptive commit such as “Reduce local footprint and harden evidence workbench”. Review every staged path before committing. The repository's existing first commit already contains two downloaded public genome indexes; removing them in a new commit prevents future accidental additions but does not remove the blobs from published history. Do not rewrite shared history without coordinating with the owner.
