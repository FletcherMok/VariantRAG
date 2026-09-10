# VariantRAG implementation plan

Approved for implementation — 2026-09-08, including the DuckDB and proband-neighbor amendments below. Milestones describe acceptance targets, not completed functionality.

## Direction and boundaries

Proposed focus: a reproducible research tool for inspecting variant evidence, with measured extraction and ranking behavior and a clear interactive demonstration. Target audience, deadlines, compute resources, and willingness to use paid APIs remain open questions. No claims about current San Diego hiring needs have been inferred.

Intended use: candidate prioritization and evidence aggregation for qualified human review. This is not a diagnostic classifier or a complete ACMG/AMP implementation; classification requires all applicable criteria and an accredited review process.

Start with small germline SNVs/indels and recessive-disease case evidence. Do not imply that this covers somatic variants, structural variants, all inheritance models, or all disease mechanisms. Preserve uncertainty and negative findings. Default to an offline reproducible demonstration; enable real external services explicitly. Synthetic fixtures must be labeled and must never supply purported real evidence.

## Existing-build audit

| Component | Observed condition | Required correction |
| --- | --- | --- |
| Nextflow | All five included module paths are absent | Create executable DSL2 processes and explicit channel contracts |
| VCF parser | Fixed annotation offsets, all ALT alleles accepted when any annotation matches, first unconfirmed ClinVar hit | Header-driven, allele-specific parsing; retain transcript/sample; confirm reference/build/allele identity |
| HGVS | Genomic substitution strings constructed for every allele; Mutalyzer call only a comment | Reference-accession-aware normalization; explicit unsupported/unresolved outcomes |
| CATT | Generated expert-panel and definitive claims; three cache files are empty | Actual CLI outputs with release/hash provenance and separate gene/variant assertions |
| Literature | Dummy PDF, fake PMID, hardcoded pathogenic partner and phase; SQL never executes | Real source extraction, exact evidence locations and supported case facts |
| Ranking | Random winners/scores, hardcoded BRCA1 context and model confidence | Reproducible baseline, real judge interface, actual aggregation and diagnostics |
| Infrastructure | “Mutalyzer API” is Python's static file server; tool dependencies not locked | Verified upstream service configuration and stage-specific reproducible environments |
| API/UI | No durable failure state, no result JSON response; form has no handler | Bounded uploads, persistent job status, real results and failure display |
| Refresh | GitHub workflow touches empty files and proposes committing cache data | Real refresh command with snapshot validation; external scheduling |

No Git repository or tests were found. Runtime-generated Ollama files, including a private-key filename, are present under the Docker folder; do not publish runtime state. Add exclusions before repository initialization. Do not delete existing user files.

## Proposed repository layout

```text
README.md                 TASK_LIST.md
IMPLEMENTATION_PLAN.md    pyproject.toml
backend/
  main.nf                 nextflow.config
  api.py                  bin/                 # thin CLI entrypoints
  variantrag/             # tested Python implementation
    schemas/ variants/ grounding/ literature/ ranking/ infrastructure/
  modules/local/
    parse_variants/ alignment_evidence/ mutalyzer_normalize/
    clinvar_id_resolve/ catt_refresh/ catt_query/
    pdf_bifurcate/ rag_index/ text2sql_query/ assemble_evidence/
    tournament_rank/ alphafold_lookup/
  conf/                   docker/
  data/cache/             # ignored immutable snapshots
frontend/src/app/         # runs, candidates, evidence, comparisons
tests/unit/ tests/integration/ tests/fixtures/
benchmarks/               # manifest, labels, split definitions, evaluation commands
docs/WALKTHROUGH.md docs/METHODS.md docs/EVALUATION.md
.github/workflows/        # lint, tests, small integration checks
```

Keep Python logic outside Nextflow scripts. Pass paths and validated metadata between processes. Preserve per-stage artifacts for inspection and ranking-only reuse. Use explicit container images rather than a generic Python container lacking required tools.

## Input identity, build, and filtering

Declare `params.genome_build` as exactly GRCh37 or GRCh38; GRCh38 is the proposed demo default. Require explicit sample selection for multisample VCFs and validated reference FASTA/transcript resources. No implicit liftover.

Use cyvcf2 and named VEP CSQ/SnpEff ANN header fields. Select annotations per ALT, with regression cases for multiallelic indels and transcript-specific consequences. Exact initial consequence set: `stop_gained`, `frameshift_variant`, `splice_donor_variant`, `splice_acceptor_variant`, `missense_variant`. These are candidate-selection terms, not synonymous with pathogenicity. An unannotated VCF must produce an actionable annotation requirement, never a misleading successful empty analysis. Include an explicit pinned annotation preparation step for the public example.

Retain sample GT, phase set, FILTER, quality, allele depth where available, transcript accession/version, HGNC identifier, and population-frequency provenance when supplied. Filter policy and missingness must appear in the run manifest. Use pysam for optional indexed BAM/CRAM read evidence; missing alignment is distinct from zero support. Validate sample/reference compatibility; require the correct FASTA for CRAM.

| Stage | Build/identity contract |
| --- | --- |
| Parsing/alignment | Build plus contig/accession map and reference checksum; validate REF and coordinates |
| Mutalyzer | Build selects genomic reference accession; transcript version enables coding/protein projection; unavailable mappings remain null |
| ClinVar resolution | Search by build-aware identity; confirm with esummary/efetch against exact allele and assembly; ambiguous is not resolved |
| CATT | Query only verified Variation IDs; retain input identity and snapshot metadata; gene-level records stay gene-level |
| Literature/SQL | Match transcript-aware HGVS and vetted aliases; do not compare unrelated coordinate systems as bare numbers |
| Assembly/ranking | Reject mixed-build bundles; include schema/reference/resource versions in input hashes |
| UniProt/AlphaFold | Derive protein mapping from the validated transcript/translation; genome build alone does not select a protein isoform |

ClinVar cache keys include assembly and normalized allele. Preserve candidates and resolution method; cache service failures separately from no-match results with appropriate expiry. Confirm current NCBI query fields against fixtures before implementation. [NCBI documentation](https://www.ncbi.nlm.nih.gov/clinvar/docs/programmatic_access/)

## CATT and Mutalyzer

CATT is an upstream Python CLI. The supplied clingen-ai-tools URL currently redirects to CATT. Pin a reviewed commit; use its real `main.py` arguments and working-directory/source configuration. Save original text/CSV artifacts plus hashes. The proposed wrapper has no invented upstream `--cache-dir` API. [Upstream usage](https://github.com/mgbpm/CATT)

`CATT_REFRESH` is a separate workflow entry point that stages sources, validates sizes/schema/checksums, and atomically publishes a snapshot manifest. `CATT_QUERY` consumes a fixed snapshot, resolves dossiers for verified IDs, and never manufactures missing assertions. Cache refresh must not mutate resources under an active run. Scheduling is external to Nextflow; the requested Antigravity scheduler is not available in this environment. Final scheduler choice remains open; no recurring task will be created during this pass.

Replace the static HTTP server with a validated pinned Mutalyzer service configuration based on [the upstream Docker reference](https://github.com/mutalyzer/docker-mutalyzer) and [Mutalyzer documentation](https://mutalyzer.readthedocs.io/en/latest/). Verify its current API and actual dependencies instead of assuming the supplied Postgres/Redis arrangement is correct. Test substitutions and indels against expected normalized references.

Each network adapter needs timeouts, bounded exponential retry with jitter, Retry-After handling, service-wide rate limits, cache keys, and recorded failure state. Pin actual compatible versions in a tested lock/environment file after approval; do not invent version combinations in the plan.

## Literature, PM3, and exact hand-off

Case tables carry proband-level genotype, phase, and phenotype relationships that prose retrieval can miss; preserve them separately. Docling ingests PDFs into body passages and tables with page/table/cell locations. Retain original files and extraction hashes. Include supported open-access XML where useful, without claiming PDF support was tested through XML alone.

Text retrieval starts with the MedCPT query/article encoder pair and FAISS, evaluated against a lexical baseline on held-out variant–paper pairs. Record model revision, query, similarity, chunk offsets, and exact source quote. The model choice is a hypothesis to test, not a guarantee that biomedical embeddings always outperform every generic alternative.

DuckDB case schema: `evidence_id, document_id, pmid, table_id, row_id, proband_id, family_id, gene_id, transcript, variant_1_raw, variant_2_raw, variant_1_normalized, variant_2_normalized, phase, phase_method, zygosity, phenotype, partner_classification, partner_classification_source, raw_cells`. Unknown fields remain unknown. Distinguish literature probands from the uploaded sample.

Guarded Text2SQL uses a read-only connection, an allowlisted single SELECT, bound values, execution/row limits and recorded query/results. Begin with deterministic analyst query templates; add a model only with equivalent safeguards and evaluation. After a variant row matches, extract its first-column proband ID and fetch all upstream and downstream rows with that ID, scoped to the same document and table. Preserve row order and direction; blank IDs must not join unrelated cases. Co-occurrence alone must not establish trans phase. Retrieved candidate rows undergo AutoPM3-style position-string postfiltering, then full allele/transcript validation. Test decimals/statistics, longer digit strings, similar positions, substitutions and indels. Inspect the upstream implementation before claiming exact AutoPM3 reproduction; comments in the existing code do not implement this filter. [AutoPM3 paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12263107/), [code](https://github.com/HKU-BAL/AutoPM3)

Use this versioned JSON hand-off (types, not sample biological claims):

```text
EvidenceBundle {
  schema_version, bundle_id, run_id, input_mode,
  variant: {key, genome_build, chrom, pos, ref, alt, sample_id,
            genotype, phase_set, consequences[], transcript, hgvs_g, hgvs_c, hgvs_p},
  resolution: {status, clinvar_variation_id?, candidates[], reference_hash, evidence_refs[]},
  alignment: {status, depth?, ref_reads?, alt_reads?, method?, artifact_ref?},
  catt_grounding: {status, snapshot_id, tool_revision, dossier_artifact,
                  csv_artifact, fields[{evidence_id, source, record_id, field, value}]},
  rag_text_evidence: [{evidence_id, document_id, pmid?, page?, chunk_id,
                      offsets, exact_quote, retrieval_score, model_revision}],
  sql_table_evidence: [{evidence_id, document_id, pmid?, table_id, row_id,
                       proband_id, normalized_genotypes, phase, phase_method,
                       partner_classification, classification_evidence_refs[],
                       raw_cells, query_id, match_validation}],
  context: {phenotype_terms[], inheritance?, population_frequency?, structural_mapping?},
  evidence_assessment: {supported_claims[], conflicts[], missing_evidence[], duplicate_groups[]},
  provenance: {artifacts[], hashes, resource_versions, extraction_versions, timestamps}
}
```

CATT does not become a proband table. Its text/CSV go to `catt_grounding`; source-derived SQL hits independently go to `sql_table_evidence`; vector results go to `rag_text_evidence`. `ASSEMBLE_EVIDENCE` joins them on normalized variant identity, validates citations and deduplicates shared facts/cases. Ranking consumes this frozen bundle, not mutable indexes or unlogged search results. Gene-disease validity must never be relabeled variant pathogenicity.

PM3 phase is not established merely by finding two alleles in a table. Record the reported method; parental testing is not the only possible confirmation method. Unknown phase can receive different treatment under applicable guidance. Deduplicate probands/families across papers, record condition applicability and partner-classification independence, and flag missing frequency data. The first release extracts reviewable PM3-relevant evidence; automatic criterion-strength assignment is deferred until a versioned, separately tested policy is agreed. [ClinGen SVI PM3](https://www.clinicalgenome.org/docs/pm3-recommendation-for-in-trans-criterion-pm3-version-1.0/), [Richards et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4544753/)

## Ranking and structural context

Establish a transparent deterministic prioritization baseline before enabling an LLM judge. Do not market a deterministic comparator as agentic. The judge receives only validated bundle evidence and returns a structured preference/tie/abstention with existing evidence IDs and rationale. Validate citation existence; evaluate actual support separately because valid IDs alone do not establish entailment.

For at most 30 candidates, compare every unordered pair twice with swapped positions: n(n−1) calls. Preserve both raw outcomes and rationales. Agreement supplies a preference; disagreement remains explicitly flagged and is excluded from decisive outcomes. Fit regularized Bradley–Terry scores, document regularization and normalization, and compare with win rates. Scores are relative preferences, not disease probabilities. No informative comparisons means no evidential ordering. Report coverage, disconnected components, position disagreement, cycles and repeat-run variability.

For larger sets, use a seeded balanced partial round-robin with explicit comparison budget, no repeat pairs, and connectivity checks. Label it as partial comparison rather than calling an arbitrary schedule Swiss. Do not truncate the candidate list silently. Record model/version/settings, prompt hash, input hashes, latency and cost. Ranking-only entry point accepts frozen bundles and a new ranking configuration.

For top missense candidates, map validated transcript/protein isoform to UniProt and verify residue identity before querying AlphaFold. Report missing/mismatched mappings. Display actual residue confidence if retrieved; never substitute a dummy accession or generic pLDDT claim. Structural context is exploratory and does not automatically contribute pathogenicity evidence.

## Demo, orchestration, and evaluation

Three incremental release gates:

1. **Trustworthy local core:** versioned schemas, truthful missing/error states, allele parser, real DuckDB evidence queries, deterministic baseline, fixtures and tests. Acceptance: repeated inputs reproduce rankings; malformed/unannotated/multiallelic inputs behave explicitly; no synthetic assertion enters real mode.
2. **Research integrations:** verified Mutalyzer/CATT/ClinVar, real PDF/retrieval path, executable DSL2 processes, public data subset and optional judge. Acceptance: end-to-end run produces inspectable source artifacts; ranking-only run does not repeat retrieval; frozen cache replay is reproducible.
3. **Portfolio release:** functioning UI, measured benchmark, documented limitations and walkthrough. Acceptance: reviewer can start a run, see failures, inspect a candidate's quotes/table rows/CATT fields, compare rationales, and export results.

FastAPI should persist queued/running/completed/failed state in SQLite, use safe generated upload paths and size limits, isolate per-run working directories, capture logs and exit codes, and recover interrupted states on restart. Nextflow process metadata feeds the status view. Serve actual bundle content through validated result endpoints. The frontend provides run history, candidate table, evidence detail, comparison diagnostics and prominent demo/live provenance. Local deployment first; public hosting is outside this draft.

Data plan: a small matched HG002 GRCh38 interval subset, from the versioned GIAB v4.2.1 VCF and a compatible indexed HG002 alignment selected from the official index. Preserve exact file URLs, checksums, reference identity, selected intervals and extraction commands before claiming the example verified. Whole-genome alignments are large; fetch only required intervals where supported. Exact alignment file and intervals are still to be verified after approval. [GIAB data index](https://github.com/genome-in-a-bottle/giab_data_indexes), [benchmark VCF reference](https://github.com/nf-core/variantbenchmarking/blob/master/docs/truth.md)

GIAB tests technical parsing and alignment behavior, not disease causality or PM3 extraction. Use a separate licensed subset of AutoPM3's PM3-Bench and open literature for extraction evaluation. Keep development and held-out cases grouped by publication/family to limit leakage. Document label origin and adjudication limits; do not treat unreviewed outputs as ground truth.

Report extraction precision/recall/F1 by field; phase false positives; citation support and missing-evidence behavior; retrieval recall@k; and ranking agreement/NDCG only where defensible relevance labels exist. Add ablations for CATT, text and tables; compare the deterministic baseline with the judge. Separate curated-database summarization from discovery evaluation to avoid target-label leakage through ClinVar. Include sample counts, confidence intervals where supportable, runtime, memory, tokens/cost, and error examples. Never reuse upstream performance numbers as VariantRAG results.

The supplied Precision Grounding version is a 2025 preprint, readable through [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12204447/); a [later journal article](https://www.sciencedirect.com/science/article/pii/S1386505626001644) is also available. Its variant-summary findings motivate CATT but do not validate this ranking task or establish universal superiority. No MedRAG fallback is planned.

Follow [nf-core module conventions](https://nf-co.re/docs/specifications/overview) without claiming nf-core compliance until relevant checks run. CI should cover scientific edge cases and an offline integration fixture, with separate opt-in service/model tests. Lock dependencies after resolving compatibility; record container/tool/model versions in every run.

Final walkthrough must cover the matched VCF/BAM example and annotation preparation, verified Mutalyzer/CATT initialization, inspecting one complete bundle, interpreting unsupported claims and ranking diagnostics, and reranking without retrieval. Deliver actual measured results, not a projected benchmark or screenshot of fabricated output.

## Review decisions

Please resolve the pending audience/scope/budget questions. The recommended first implementation milestone is the trustworthy local core, with subsequent integrations prioritized around your target role and available hardware. The complete architecture remains the destination; nothing beyond planning has been represented as complete.




Changes:
Enforce DuckDB over SQLite: In the "Literature, PM3, and exact hand-off" section, the plan specifies an "SQLite case schema." Please correct this and strictly use DuckDB for the Table Pathway. We need DuckDB's column-oriented analytical performance for the Text2SQL module.

Implement AutoPM3 Upstream/Downstream Row Fetching: The plan correctly mentions the AutoPM3 position-string post-filtering, but it misses the core extraction heuristic. Update the Text2SQL execution logic so that when the query variant's row is identified, the system extracts the proband ID (first column) and automatically fetches the upstream and downstream rows sharing that ID. This is strictly required to identify the in trans partner variant.

## Approved resource constraint (2026-09-08)

Minimize resource requirements while maintaining core functionality. Default to the deterministic local pipeline, one API worker, bounded CATT snapshots for selected variants and linked genes, cached evidence, and optional model inference. Keep core and research dependencies separate; store one weight format per encoder. Full public database expansion is deferred to a larger environment.
