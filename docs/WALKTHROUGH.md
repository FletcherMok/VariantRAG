# Researcher walkthrough

## 1. Inspect the offline demonstration

Install the core environment and frontend using the README, then:

```bash
.venv/bin/variantrag run --vcf tests/fixtures/demo.vcf \
  --literature tests/fixtures/demo_literature.json --mode demo --out results/demo
```

Inspect `results/demo/EvidenceBundle.json` before opening the ranking. For the first candidate, the table pathway should return four rows: P1's upstream, matched, and downstream rows, plus P3's matched row. The decimal statistic and unrelated cases are absent. Phase stays unknown. CATT remains `not_requested`, with no made-up expert-panel assertion.

The source fixtures are intentionally synthetic. Research mode rejects them as literature input. Use the UI's demonstration button to follow the same path and inspect raw cells, text, comparisons, and provenance. The optional literature upload accepts the JSON corpus format returned by PDF ingestion.

## 2. Reproduce the public VCF/BAM technical check

The fetch script uses official indexed files and downloads a small interval, not an entire genome:

```bash
.venv/bin/python benchmarks/fetch_giab.py
.venv/bin/python benchmarks/annotate_public.py
.venv/bin/variantrag run --vcf results/public-data/HG002.annotated.vcf \
  --bam results/public-data/HG002.bam --out results/public-run
```

The initial interval is GRCh38 chromosome 22:20,000,000–20,002,000, inclusive. The manifest records exact source URLs, source-index reference, subset hashes, sample provenance, and interval. Ensembl VEP annotates only this checksummed public input; its raw response and reported software version are retained. This service-backed annotation is replayable from saved output, but is not a replacement for a pinned local VEP release/cache on a private cohort.

Observed for this subset: six VCF records, 3,466 alignment records, and no retained target consequences after VEP annotation. Empty prioritization is the expected result, not a failed run. Five raw SNVs have measurable support; local haplotype-based indel support is not implemented.

This source BAM lacks SM read-group labels. The fetch script supplies a checksum-bound sidecar identifying HG002 from the official source. Other alignments must identify the selected VCF sample through read groups or equivalent explicit source provenance. CRAM requires its matching reference FASTA. Supply `--reference reference.fa` for REF validation; it must be indexed and use compatible contig names. Assembly is never silently lifted over.

## 3. Prepare research integrations

The optional research environment is larger:

```bash
uv pip install --python .venv/bin/python -r requirements-research.lock
HF_HOME=backend/data/models/hf .venv/bin/python benchmarks/prepare_medcpt.py
```

Model weights live under the ignored project cache. The MedCPT manifest records exact query/article repository revisions. The two encoders are independent models. Embedding occurs in a subprocess; FAISS remains outside that process to avoid conflicting native runtimes.

Ingest a locally available source PDF:

```bash
HF_HOME=backend/data/models/hf .venv/bin/variantrag ingest-pdf \
  --pdf source.pdf --document-id PAPER_IDENTIFIER --pmid PMID \
  --out results/literature.json

.venv/bin/variantrag run --vcf annotated.vcf --sample SAMPLE_ID \
  --literature results/literature.json --medcpt backend/data/models/medcpt \
  --genome-build GRCh38 --out results/research
```

Docling's first run may fetch layout/OCR model files. Confirm the extracted table's first column really identifies probands. Duplicate headers or unresolved merged cells require explicit source-aware cleanup. Do not silently forward-fill blank IDs. Source PDFs and supplements need appropriate access and reuse permissions; the provided smoke-check article is openly licensed.

## 4. Mutalyzer and CATT

The supplied historical Docker repository describes an older Mutalyzer service. VariantRAG's replacement uses the actual `mutalyzer-api` v3 Flask application and its `/api/normalize/<description>` route.

With Docker running:

```bash
docker compose -f backend/docker/docker-compose.yml --profile research up --build
```

The real normalizer is at `http://127.0.0.1:5000/api`; the workbench API is at port 8000. The Mutalyzer cache is a named volume configured via `MUTALYZER_SETTINGS`. Upstream reference retrieval is still needed for cold transcript/genomic references. The v3 route and a sequence-supplied repeat normalization were verified; a cold BRAF transcript request timed out here. Do not treat that as a normalized variant or assume the cache is already primed.

For a native Mutalyzer deployment, create a settings file with `MUTALYZER_CACHE_DIR` pointing to an absolute cache directory, set `MUTALYZER_SETTINGS` to that file, and prime required references with the upstream retriever before full runs. Use the locked Mutalyzer environment, including `setuptools==80.10.2`, required by the current API package's `pkg_resources` import.

CATT is pinned to commit `6815e6a2d67439c0f899416060e0d997d6d07dd8`. Use a bounded snapshot on this Mac, retaining selected Variation IDs and their linked genes:

```bash
.venv/bin/variantrag catt-refresh --checkout /path/to/CATT \
  --revision 6815e6a2d67439c0f899416060e0d997d6d07dd8 \
  --variant-ids 13961 --out /path/to/new-snapshot
```

Bounded refresh scans compressed upstream releases one at a time, retains only matching rows, and deletes each temporary download. Initial network transfer still includes the full source archives (about 860 MB at this checkpoint); subsequent queries are local. Omit `--variant-ids` only when intentionally preparing a full cache on a larger machine.

The checkout must match that full commit. Snapshots are immutable; choose a new destination for each refresh. Query workers copy the snapshot to avoid CATT mutating resources used by other runs. Each source is queried separately, preserving source record identifiers and avoiding cross-source row multiplication. The full workflow can need substantial RAM/disk because upstream loads flat files into pandas and query copies duplicate them. The four primary sources were reachable during validation; a full refresh is not represented as already validated on this 16 GB Mac.

A verified snapshot can be used with explicit network opt-in:

```bash
.venv/bin/variantrag run --vcf annotated.vcf --genome-build GRCh38 \
  --literature results/literature.json --online \
  --mutalyzer-url http://127.0.0.1:5000/api \
  --catt-snapshot /path/to/snapshot --out results/grounded
```

`--online` enables coordinate lookup at NCBI and calls the configured normalizer. CATT consumes only an exactly confirmed Variation ID. Failed lookups remain errors/missing evidence. Every source result should be inspected before ranking conclusions are trusted.

The GitHub CATT workflow is manual and produces a snapshot artifact instead of committing database files. No weekly scheduler was activated; the requested Antigravity scheduler is not available in this environment.

## 5. Rerank frozen evidence

```bash
.venv/bin/variantrag rank --bundles results/research/EvidenceBundle.json \
  --out results/research/ranking-baseline.json
```

Optional local-model experiment, using an exact model name already installed in Ollama:

```bash
.venv/bin/variantrag rank --bundles results/research/EvidenceBundle.json \
  --ollama-model YOUR_INSTALLED_MODEL --judgments-dir results/judgments \
  --out results/research/ranking-llm.json
```

Inspect both presentation orders, disagreement rates, graph coverage, and citations. Missing evidence may warrant abstention. A syntactically valid citation is not proof of source support; expert adjudication remains necessary. The model's outputs and token counts are preserved in the raw judgment artifacts. No paid API is called.

## 6. Evaluate before making performance claims

`benchmarks/pm3_manifest.json` records the upstream dataset hash and split audit. Curator comments and partner labels must never be inserted into the retrieval corpus. The real-paper integration example uses one upstream evaluation case exploratorily; it is not a held-out performance claim.

`benchmarks/evaluate.py` scores independently reviewed evidence-ID labels against predictions, counting absent predictions as abstentions/false negatives:

```bash
.venv/bin/python benchmarks/evaluate.py --labels reviewed-labels.json \
  --predictions predicted-evidence.json --out results/evaluation.json
```

Label records contain `case_id` and `expected_evidence_ids`; predictions contain `case_id` and `evidence_ids`. Keep publication/family groups together when building new splits. Report corpus availability and abstentions, rather than evaluating only successful retrievals.
