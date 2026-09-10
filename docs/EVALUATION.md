# Measured validation

Validation date: 2026-09-08. These are implementation and integration checks, not a claim of clinical validity or superiority over another method.

| Check | Observed result | Interpretation |
| --- | --- | --- |
| Automated core suite | 37 tests passing at the final checkpoint | Covers allele-specific filtering, annotation headers, sample selection, scoped DuckDB recovery, numeric/allele false positives, SQL restrictions, ranking replay/bias/citations, API failure states, and evaluator behavior |
| Frontend | Production build and TypeScript compilation passed | Working application build; browser demo verified separately |
| Browser demo | Completed through the API; 3 candidates, 3 pairs, 4 retrieved rows for first candidate | Upstream/matched/downstream rows visible; synthetic labeling and unknown phase preserved |
| Nextflow 26.04.6 / Java 21 | All 3 core processes completed; unchanged rerun reused all 3 cached tasks | DSL2 execution and resume validated locally; Python sources and the core dependency lock are part of task cache keys |
| Ranking-only workflow | Only the ranking process executed from a frozen bundle | Retrieval is not repeated |
| Public HG002 interval | 6 VCF records and 3,466 BAM records retrieved by indexed range reads | Matched public technical fixture, GRCh38 chr22:20,000,000–20,002,000 |
| Public annotation | Ensembl VEP reported release 116; 0 target-consequence candidates | Correct empty result for this chosen interval; raw response and checksums retained |
| Alignment support | All 5 SNVs yielded supporting ALT reads; indel explicitly unsupported | SNV counting works; this does not validate indel support or calling accuracy |
| Live ClinVar identity | GRCh38 7:140753336 A>T resolved to Variation ID 13961 | Exact VCV XML assembly/allele confirmation, not an esearch-first-hit shortcut |
| Mutalyzer v3 | Actual API route loaded; supplied-sequence `2del` in `AAAA` normalized to `4del` | Real normalization contract verified; cold BRAF transcript lookup timed out and remains an error |
| Real PDF | Docling extracted 152 passages and 2 table segments from a 10-page open-access paper | Ingestion succeeded; counts are not a measure of cell/phase extraction accuracy |
| MedCPT + FAISS | Retrieved 10 passages from that paper using the actual query/article encoders | Native runtime conflict resolved by process isolation; no generic-embedding performance claim |
| Real case inspection | 1 exact DNA text hit; 0 exact DNA table rows | Conservative matching abstained where table representation did not establish the query's DNA identity |
| CATT | Real bounded refresh and four source-specific CLI queries succeeded for Variation ID 13961 / BRAF | 2 ClinVar variant rows, 45 submissions, 23 GenCC rows, 4 ClinGen rows; scope is selected variant plus linked gene, not a full cache |
| PM3-Bench split audit | 1,027 records: 760 fine-tune, 195 eval, 72 others; no PMID across multiple source splits | Useful starting split audit, not a new benchmark score |

## Artifacts

Generated local artifacts are excluded from version control. Reproduce them with the scripts in the walkthrough:

- `results/tests.xml`: machine-readable test results.
- `results/nextflow/trace.tsv`, `report.html`, and pipeline outputs.
- `results/public-data/manifest.json`, `annotation-manifest.json`, and `vep-response.json`.
- `results/live-check/clinvar.json`, `giab-alignment.json`, and `mutalyzer.json`.
- `results/live-check/docling-paper.json`, `docling-evidence.json`, `medcpt.json`, and `table-paper.json`.
- `benchmarks/pm3_manifest.json`: checked-in dataset provenance and split audit.

The actual MedCPT revisions are query `d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc` and article `d05a736da4bb84ee4057b7f7999485be6ed85465`. Model files are not committed.

The exploratory paper is Rosina et al., *Genes* 2022, PMID 35886058 / [PMC9319862](https://pmc.ncbi.nlm.nih.gov/articles/PMC9319862/), openly licensed CC BY. Its query case comes from the upstream evaluation split, but it was used during development and must **not** be advertised as an independent held-out evaluation. Neither its curator comment nor the known partner label was included in the retrieval corpus.

## Limits of the evidence

No disease-priority ground truth was evaluated. There is no defensible NDCG, diagnostic accuracy, sensitivity, or LLM superiority result to report. The pipeline does not yet automatically resolve all transcript aliases, merged case-table layouts, cross-publication duplicates, or PM3 criterion weights. Gene/disease specificity, frequency constraints, and independent partner classification still require review.

The local API uses a single background worker and persisted status; it is not a distributed job service. Uploaded literature corpora are user-supplied evidence artifacts, not independently authenticated publications. Docker configuration was inspected, but its containers were not executed because the Docker daemon was stopped.

The full public CATT databases were not expanded on this Mac: at validation it had 16 GB RAM and roughly 10 GB free disk. A bounded snapshot scans real releases and retains only specified variants and their linked genes, with a manifest explicitly describing the scope. It must never be represented as a complete database cache.

## Bounded resource validation

The final snapshot (`backend/data/catt-bounded-13961-v2`) contains 239,201 bytes of files. Its source URLs, full-download hashes, upstream MD5 checks where offered, row counts, and subset hashes are in its manifest. The revision fixes the upstream CATT empty-skip-row contract while retaining the same downloaded records.

Source-specific queries preserve source/record identifiers and avoid Cartesian duplication across independent submissions and gene assertions. The final dossier JSON is 481,131 bytes with 1,490 nonempty source fields, compared with 213 MiB from the initial cross-source join. This is a storage/representation improvement, not an increase in independent evidence. Source CSV/text files and the normalized field CSV are retained under `results/live-check/catt-bounded`.

Core execution requires no model downloads. Optional MedCPT stores one weight format per encoder and caches corpus embeddings. One API worker limits concurrent memory demand. Disposable download caches and duplicate weights created during this work were removed.

macOS offloaded files in the Desktop environment during validation. After repairing the local dependencies and installing the package normally, all 37 tests and the CLI demo passed in the project’s own `.venv`. Frontend production build and the final browser demonstration both succeeded.

## Next research evaluation

Use independently reviewed evidence IDs and source tables, lock publication/family groups, and compare text-only, table-only, CATT-only, combined, and no-LLM baselines. Count missing predictions and corpus unavailability, examine phase false positives and source support, and report sample sizes and uncertainty. `benchmarks/evaluate.py` provides basic evidence-retrieval precision/recall/F1 with abstentions; the corpus and labels still need scientific review.
