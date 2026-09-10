# VariantRAG implementation status

Approved implementation, updated 2026-09-08. Resource preference: minimize local requirements while retaining core functionality.

- [x] Package the core and optional research dependencies separately; add locks, exclusions, and CI.
- [x] Replace fabricated production evidence with explicit available, missing, and error states.
- [x] Implement ALT-specific annotation parsing, sample/build checks, optional FASTA validation, and SNV alignment support.
- [x] Implement real ClinVar allele confirmation and Mutalyzer v3 adapters.
- [x] Implement immutable full/bounded CATT refresh and query adapters.
- [x] Use DuckDB for case-table analytics, with guarded SQL and same-proband recovery upstream and downstream within document/table scope.
- [x] Implement Docling ingestion, optional MedCPT/FAISS retrieval, and provenance-bearing EvidenceBundles.
- [x] Implement deterministic comparisons, swapped-order audits, abstention, Bradley–Terry aggregation, and optional local structured judgments.
- [x] Wire Nextflow core, resume, and ranking-only workflows.
- [x] Replace the mockup with an API-backed upload, demonstration, evidence-review, and export interface.
- [x] Run public GIAB technical checks and exploratory real-paper retrieval; document measured results.
- [x] Provide README, demonstration walkthrough, methods, evaluation report, and resource-conscious defaults.

Remaining research acceptance gates:

- [ ] Independently reviewed held-out literature and disease-ranking evaluation, including ablations.
- [ ] Broad cold-reference normalization coverage and transcript/merged-table resolution.
- [ ] Full CATT database validation on an appropriately sized environment (bounded mode is the local default recommendation).
- [ ] Empirical LLM judge evaluation and automatic validated UniProt mapping/residue-level structure evidence.
- [ ] Docker runtime verification and decomposition of all optional research adapters into individual Nextflow processes.

See docs/EVALUATION.md for actual checks and limitations. Implemented interfaces and smoke tests do not establish clinical validity.

Audit follow-up (2026-09-09): disk-first cleanup, packaged demo resources, static UI serving, local API boundaries/retention, conservative transcript/phase fixes, scalable connected comparisons, known-vulnerability scans, MIT licensing, and GitHub preparation are recorded in docs/AUDIT.md. Remaining research gates above still apply.
