# Methods and design decisions

## Variant identity

The retained consequence terms are `stop_gained`, `frameshift_variant`, `splice_donor_variant`, `splice_acceptor_variant`, and `missense_variant`. Consequence selection is allele-specific and reads field names from the annotation header. VEP `ALLELE_NUM` takes precedence; otherwise exact ALT and unambiguous trimmed allele matches are used. Unsupported symbolic alleles are excluded with a reason. Multisample inputs require sample selection. Only ALT alleles carried by the selected sample are retained; filtered records are excluded. A raw, unannotated VCF fails with an annotation requirement.

GRCh37/GRCh38 is explicit and conflicting recognizable VCF reference headers fail. Without a matching reference FASTA, reference validation remains `not_checked`. Retained transcript annotations do not imply that transcript/genome projection has been independently verified. Mutalyzer output is recorded independently, and no generic genomic HGVS string is fabricated for an indel.

ClinVar coordinate search supplies candidates, not a resolved identity. The resolver accepts only matching assembly, chromosome, VCF position, REF, and ALT in a simple allele's VCV XML. It uses the archive Variation ID, never an Allele/Measure ID or an unconfirmed first search hit. Haplotype members are not confused with a whole haplotype.

## DuckDB proband recovery

1. Preserve source table headers, raw cells, document/table IDs, and zero-based source row position. The first source column is the proband identifier.
2. Run a parameter-bound DuckDB SELECT for the variant position.
3. Reject numeric coincidences such as decimal statistics or longer digit strings, then match the complete HGVS allele and available transcript/gene context.
4. For each surviving anchor, query **all earlier and later rows with its proband ID in that same document and table**. Preserve anchor row and upstream/matched/downstream direction.
5. Do not fill blank proband IDs implicitly. Do not join a repeated ID across another table or publication. Retain raw phase and method, with missing phase explicitly unknown.

This independently implemented adaptation follows the filtering and neighboring-row rationale in [AutoPM3](https://github.com/HKU-BAL/AutoPM3) and its [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12263107/). Upstream checks immediate previous/next rows after matching the first source column (following its generated row index); VariantRAG expands to all matching rows as requested. It does not claim to reproduce every AutoPM3 component or its reported metrics.

SQL is restricted to a single relational SELECT over `cases`, with an AST allowlist, read-only database access, external access disabled, a row limit, memory limit, and execution timeout. This release uses deterministic query templates. Free-form model-generated Text2SQL is not enabled. The first source column, zero-based row index, and source table identity remain distinct.

A bare coding allele without matching transcript context can be retrieved for inspection but is marked `allele_context_unresolved`; it does not count as an exact case in the baseline. Raw table phase is not a clinical PM3 determination. Gene validity, partner classification, proband co-occurrence, and established phase remain separate facts.

## Evidence assembly

CATT dossier fields enter `catt_grounding`; body-text hits enter `rag_text_evidence`; case rows enter `sql_table_evidence`. A versioned Pydantic model rejects duplicate IDs, mixed builds, and explicit synthetic evidence in research mode. Source files, resource/model revisions, hashes, queries, and missingness remain available for inspection. Evidence-ID validation verifies references exist; it does not prove that a judgment's cited text entails its conclusion.

CATT remains an upstream CLI with immutable snapshot manifests and per-query private copies. It is not impersonated by a fabricated API. See [CATT](https://github.com/mgbpm/CATT) and [Precision Grounding](https://pmc.ncbi.nlm.nih.gov/articles/PMC12204447/). Published summarization results are not VariantRAG ranking results.

Docling separates PDF body passages and table structures. Native BioC XML is a second supported ingestion function; its tables are parsed structurally, not by whitespace. Neither pipeline automatically interprets every merged-cell layout. MedCPT query/article encoders use first-token representations and inner-product FAISS retrieval. A lexical exact-HGVS baseline is separately identified. Semantic matches are candidate passages, not proof of variant identity or phase. PyTorch embedding runs in a separate process from FAISS to avoid conflicting native OpenMP runtimes observed on this macOS environment.

## Comparisons

The reproducible baseline counts unique exact-allele case groups available for review, deduplicating repeated probands within a publication and grouping known family IDs. It does not award PM3 points or claim cross-publication case adjudication.

For at most 30 candidates, every pair is evaluated twice with positions swapped. A decisive preference contributes one win only when both presentations agree. Disagreements and abstentions are retained and excluded from decisive outcomes. Ties remain explicit. For larger lists, a balanced circle schedule supplies bounded partial round-robin comparisons; this is not labeled Swiss.

Bradley–Terry fitting minimizes logistic pair loss plus `0.5 * sum(theta**2)`, then reports normalized `exp(theta)` scores. The regularizer avoids divergent estimates under separation; scores are relative preferences, not probabilities of disease. A disconnected decisive graph has no globally defensible order and receives null ranks. Equal scores share ranks. Diagnostics include comparison coverage, order disagreement, decisive components, and directed three-cycles.

The local Ollama adapter pins the installed model digest and saves both raw judgments and rationale citations. Temperature zero and a seed reduce variability but do not establish hardware-independent determinism. A local model must already be installed; no model purchase or paid API is needed by default.

## Structural and clinical limits

The structural adapter requires an explicit transcript/build/UniProt mapping and matching protein sequence/residue before looking up AlphaFold. It does not infer a canonical isoform from a gene symbol, invent a model, or add a confidence-based pathogenicity score. Automatic transcript-to-UniProt mapping and residue pLDDT extraction are not yet validated.

PM3 interpretation requires disease-appropriate evidence, classification independence, rarity, phase assessment, and duplicate-case review. Extraction alone does not perform those tasks. [ClinGen guidance](https://www.clinicalgenome.org/docs/pm3-recommendation-for-in-trans-criterion-pm3-version-1.0/) and [Richards et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC4544753/) are the starting references.
