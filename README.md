# VariantRAG

**A provenance-first workbench for variant evidence review.**

VariantRAG filters annotated VCF alleles, preserves source passages and case-table rows, and records reproducible pairwise comparisons. Its DuckDB table pathway recovers the rows before and after a matched variant that share the same proband identifier within the same document and table. The interface makes those relationships inspectable.

This is a research prioritization and evidence-aggregation aid for qualified human review, not a diagnostic classifier or a complete ACMG/AMP implementation. Clinical classification requires evaluating all applicable criteria and an accredited review process.

## Start locally

Python 3.13 and Node 22+ are recommended. Run commands from the repository root.

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.lock
uv pip install --python .venv/bin/python --no-deps .
npm ci --prefix frontend
```

Start the API and frontend in separate terminals:

```bash
.venv/bin/python -m uvicorn variantrag.api:app --host 127.0.0.1 --port 8000
```

```bash
npm run build --prefix frontend
npm run start --prefix frontend
```

Open [the local workbench](http://127.0.0.1:3000). **Open demonstration** runs three explicitly synthetic candidates through real parsing, DuckDB queries, and deterministic comparison code. Uploading your own annotated VCF uses research mode; optionally attach a literature corpus JSON produced by the ingestion command.

The lightweight default needs no model weights, Docker services, or full database cache. Install optional research dependencies only for the adapters you use. CATT supports bounded snapshots; corpus embeddings are cached and Ollama inference is opt-in. Use `npm run dev --prefix frontend` only while editing the interface.

## Run without the interface

```bash
.venv/bin/variantrag run \
  --vcf tests/fixtures/demo.vcf \
  --literature tests/fixtures/demo_literature.json \
  --mode demo --out results/demo

.venv/bin/variantrag rank \
  --bundles results/demo/EvidenceBundle.json \
  --out results/demo/reranked.json
```

The second command uses the frozen evidence only. It does not repeat parsing, retrieval, or external calls.

For Nextflow 26.04.6 with Java 21:

```bash
nextflow run backend/main.nf -profile demo --python "$PWD/.venv/bin/python"
nextflow run backend/main.nf -profile demo --python "$PWD/.venv/bin/python" -resume
nextflow run backend/main.nf --workflow rank \
  --bundles results/nextflow/EvidenceBundle.json \
  --python "$PWD/.venv/bin/python" --outdir results/rank-only
```

## What is implemented

- Header-driven, ALT-specific VEP/SnpEff consequence filtering with sample selection, explicit assembly, and optional reference validation.
- DuckDB position filtering, full HGVS matching, first-column proband recovery in both directions, source-row provenance, and bounded read-only SQL.
- Versioned EvidenceBundles with separate table, text, curated-database, normalization, alignment, and missing-evidence fields.
- A deterministic **evidence-availability baseline**, regularized Bradley–Terry aggregation, swapped-order diagnostics, ties, abstention, and disconnected-graph reporting.
- An optional local Ollama judge with structured outputs, evidence-ID validation, model digest, prompt/input hashes, and recorded raw judgments. This is an experimental mode, not the default baseline.
- Real ClinVar VCV allele confirmation, local Mutalyzer v3 adapter, CATT CLI/snapshot adapters, Docling PDF ingestion, and MedCPT/FAISS retrieval in isolated native runtimes.
- A working local API and interface with persisted run state, failure details, evidence tabs, source-cell inspection, and JSON export.
- Runnable DSL2 core and ranking-only workflows, environment locks, CI definitions, and meaningful regression tests.

## Validation and limits

The default pipeline is deterministic; it is not presented as an LLM agent. Its scores prioritize available evidence for inspection, not disease causality. No source means missing evidence, never an invented PMID, pathogenic partner, CATT assertion, or structure score.

Read the [measured evaluation](docs/EVALUATION.md) for exactly what ran. The public HG002 smoke test validates technical behavior; it does not establish disease-ranking accuracy. The real-paper check is exploratory and does not establish held-out PM3 performance. Full CATT release validation, broad reference/transcript normalization coverage, and expert-adjudicated ranking evaluation remain separate acceptance gates.

- [Researcher walkthrough](docs/WALKTHROUGH.md)
- [Methods and provenance](docs/METHODS.md)
- [Implementation status](TASK_LIST.md)
- [Approved architecture](IMPLEMENTATION_PLAN.md)

## Checks

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check --config pyproject.toml backend/variantrag tests benchmarks
npm run build --prefix frontend
```

Optional research dependencies and model preparation are described in the walkthrough. Large data, model weights, local job state, and runtime credentials are excluded from version control and container builds.
