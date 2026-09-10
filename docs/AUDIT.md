# Project audit — 2026-09-09

Scope: tracked source, local generated assets, packaging, the API/UI, Nextflow, scientific matching/ranking behavior, dependency advisories, and Git history. Findings combine code review, regression tests, live advisory queries, package installation checks, and browser validation. This is not a penetration test or proof that every possible flaw has been found.

## Candid assessment for hiring and scientific review

**A credible research-software portfolio project, but not yet a validated variant-prioritization method.** The inspectable case-table pathway, explicit uncertainty, source provenance, functional interface, and reproducible execution are useful engineering signals. They can support a strong interview if the author can explain the code and demonstrate a realistic failure case.

A hiring manager is likely to value a working clean install, readable code, disciplined scope, tests that catch plausible errors, and honest evaluation. The original repository weakened those signals through accidentally tracked genome indexes, an installed-package demo bug, large optional dependencies in the default environment, and densely compressed frontend code. Those problems have been addressed in this audit.

A postdoc is likely to ask whether the recovered evidence is biologically correct and useful. The project cannot yet answer that with independent results. The baseline counts exact-allele case groups; more published evidence is not greater pathogenicity. The default does not integrate phenotype match, inheritance, allele frequency, segregation, penetrance, or a calibrated disease model. Bradley–Terry makes a preference graph interpretable; it does not make its inputs clinically meaningful. Calling this an autonomous clinical agent or advertising improved diagnostic accuracy would overstate the work.

The same-proband recovery is an adaptation of a useful published idea, not evidence of a novel algorithm. MedCPT, Docling, Mutalyzer, and CATT are integrations whose contribution should be attributed. The clearest original contribution here is an inspectable, resource-conscious workflow with conservative checks and reproducible evidence handoffs.

**Best next scientific investment:** independently review a modest set of real source tables, lock publication/family groups, and measure false positives, recall, abstentions, phase mistakes, and extraction failures. Compare exact text, table recovery, semantic retrieval, and their combination. Include negative cases and unavailable corpora. A small defensible evaluation would improve this portfolio more than another model or dashboard feature.

## Findings and disposition

Severity reflects this local research tool's intended use. “Remaining” items are not silently treated as fixed.

| ID | Priority | Finding | Disposition |
| --- | --- | --- | --- |
| S01 | High | UploadFile size checks ran after multipart intake could already spool a large body | Fixed: request intake is bounded before parsing, including streamed bodies |
| S02 | High | CORS alone did not stop cross-origin requests from executing against the local API | Fixed: Host and Origin checks plus cross-site request checks; still no multi-user authentication |
| S03 | High | Failed/rejected uploads could leave directories and literature files behind | Fixed: full unaccepted-run cleanup, tested |
| S04 | High | Repeated runs had no storage ceiling or deletion path | Fixed: configurable retained-run limit, free-space guard, completed-run deletion; no automatic deletion of user results |
| S05 | High | Compressed VCF size did not bound expanded work | Fixed: 100 MiB expanded input, 100,000 records, 1,000 candidate limits |
| S06 | High | CATT manifests covered source data but omitted executable code | Fixed: executable checksums, unchecked-code/symlink rejection, clean upstream checkout checks; legacy snapshots need trusted migration |
| S07 | Medium | Standard XML parser accepted remote ClinVar XML | Fixed: defusedxml |
| S08 | Medium | Atomic JSON failures left temporary files | Fixed: cleanup even on serialization failure; compact JSON reduces repeated disk overhead |
| S09 | Medium | Optional setuptools 80.10.2 has a known advisory | Fixed: removed obsolete Mutalyzer API dependency and require patched build tooling |
| S10 | Medium | Optional Accelerate 1.14.0 has an advisory with no patched release | Remaining: absent from default environment, disclosed in SECURITY.md and separately scanned |
| S11 | Medium | CATT executes upstream Python/templates | Remaining trust boundary: pinned source/checksums are not a sandbox or signature |
| S12 | Medium | PDF/native VCF parsers operate in the local user's context | Remaining: no hostile-document process sandbox; use trusted research inputs |
| S13 | Medium | LLM citations can be syntactically valid but unsupported | Remaining: no entailment/faithfulness adjudication; prompt injection not solved by a system prompt |
| S14 | Medium | Mutable GitHub Action tags increased supply-chain variability | Fixed: pinned action commits, explicit read-only permissions, security workflows and Dependabot configuration |
| S15 | Medium | Docker images ran as root and the normalizer retained build tools | Improved: non-root users, separate normalizer build stage, one bounded service; runtime images not executed here |
| C01 | High | A matching transcript elsewhere in a row could validate an allele attached to a different transcript | Fixed: match accession and allele together; adversarial regression test |
| C02 | High | Installed wheel searched for demo fixtures under site-packages-relative tests | Fixed: package demonstration assets and verify installed-package execution |
| C03 | High | Default pair budget failed when candidate count exceeded 121 | Fixed: bounded connected schedule with at least n−1 edges |
| C04 | Medium | A sufficient number of comparisons did not guarantee a connected schedule | Fixed: seed a spanning path and test connectivity, uniqueness, and budget |
| C05 | Medium | Triangle diagnostics enumerated all candidate triples | Fixed: sparse edge-intersection counting |
| C06 | Medium | Reported trans phase plus any method string was marked “supported” | Fixed: retain reported fields, explicitly leave independent phase support unvalidated |
| C07 | Medium | Repeated per-variant hashing reread identical VCF and DuckDB files | Fixed: hash each shared artifact once per assembly |
| C08 | Medium | PDF/BioC extraction reread the full input to hash every passage/table | Fixed: hash once per document |
| C09 | Medium | Multiple anchors repeated the same proband query | Fixed: per-query neighbor cache and scoped DuckDB index |
| C10 | Medium | HTTP clients lacked deterministic cleanup | Fixed: close after identity-resolution stage |
| C11 | Medium | Frontend polling could overlap requests or apply stale responses | Improved: sequential, cancellable polling for active runs |
| C12 | Low | Available CATT evidence could still show a “no snapshot” message | Fixed |
| D01 | High | Optional ML/OCR stack lived in the default environment | Fixed: lean core/development locks; separate CATT and normalizer environments |
| D02 | High | Downloaded optional models represented roughly 1.4 GB logical storage | Removed with authorization; immutable MedCPT revisions and setup script retained |
| D03 | Medium | Node server/dependencies remained necessary during routine operation | Fixed: static export served by Python; build dependencies may be removed afterward |
| D04 | Medium | Full remote genome indexes leaked into the repository root and initial commit | Fixed current tree and fetch destination; published history still contains old blobs |
| D05 | Medium | CATT workflow installed the full ML/PDF environment | Fixed: minimal CATT lock |
| D06 | Medium | Superseded CATT snapshots and build caches duplicated reproducible files | Removed disposable copies while preserving snapshot manifests and research outputs |
| D07 | Medium | HTSlib automatically cached indexes in the current working directory | Fixed: explicit temporary index paths, removed after fetch |
| D08 | Low | GIAB manifest could hash old manifest files on rerun | Fixed: enumerate only intended output artifacts |
| R01 | High | No independent disease-ranking or held-out extraction benchmark | Remaining scientific acceptance gate |
| R02 | High | One exploratory paper was used during development | Remaining: cannot call it held out or infer general accuracy |
| R03 | High | Public GIAB interval yielded zero target candidates | Valid technical check, inadequate positive disease-prioritization demonstration |
| R04 | High | Transcript aliases, merged cells, and ambiguous first-column identifiers remain hard cases | Remaining: manual source-aware review; no silent imputation |
| R05 | High | Case/family duplication across publications is unresolved | Remaining: can inflate evidence counts |
| R06 | High | Table presence/co-occurrence does not establish phase, pathogenic partner, or PM3 eligibility | Remaining domain review; deliberately not inferred |
| R07 | Medium | Lexical matching is conservative; semantic relevance is not allele identity | Remaining: report abstentions and false positives before accuracy claims |
| R08 | Medium | Transcript selection is deterministic but not a clinically reviewed policy | Remaining: MANE/canonical preference does not settle every isoform choice |
| R09 | Medium | Full genomic normalization/liftover, robust indel read support, and MAPQ-aware allele counting are incomplete | Remaining; no inference of these capabilities |
| R10 | Medium | Some evidence fields are untyped dictionaries rather than strict domain schemas | Remaining: schema depth and version migration need further work |
| R11 | Medium | Source dates, disease specificity, review level, and ascertainment bias are not ranking features | Remaining; curated database presence alone is insufficient |
| R12 | Medium | Optional structure adapter is not wired into the pipeline and has no residue pLDDT extraction | Remaining prototype; no structural ranking claim |
| R13 | Medium | Optional Ollama judgments have not been empirically evaluated | Remaining: model availability is not reproducible scientific performance |
| R14 | Medium | MedCPT reloads its query encoder per variant and rebuilds a FAISS index | Remaining performance issue in optional mode; corpus vectors are cached, no default model workload |
| R15 | Medium | Raw evidence is duplicated across candidate bundles and exported ranking | Remaining schema tradeoff; compact serialization helps but a future normalized evidence store would scale better |
| R16 | Medium | Candidate SQL enforces a 1,000-row cap and may reject broad position hits before exact filtering | Remaining bounded behavior; needs a scalable exact-query index for larger corpora |
| R17 | Medium | Optional CATT/normalization/retrieval stages are not all separate Nextflow processes | Remaining architecture gate; core and ranking-only execution are supported |
| R18 | Medium | Dependency versions are pinned but complete artifact hashes/container digests are not | Remaining supply-chain reproducibility limit; CI actions are immutable |
| R19 | Medium | Model manifest revisions alone do not authenticate a replaced local weight file | Remaining trusted-local-model boundary; no arbitrary checkpoint upload |
| R20 | Low | Workflow assertions, type checking, and local tests are not hosted CI results | Remaining: run GitHub CI after the reviewed commit; no remote CI success claimed |
| P01 | Medium | Frontend was compressed into very long lines | Fixed: formatted source suitable for review |
| P02 | Medium | Repository lacked license, contribution guidance, security policy, and provenance notices | Fixed: MIT, CONTRIBUTING, SECURITY, THIRD_PARTY, PR template |
| P03 | Medium | Marketing implied more “agentic”/clinical capability than demonstrated | Improved: README centers evidence retrieval, shows limits and links evaluation |
| P04 | Low | No independently validated performance figure or realistic positive interview case | Remaining: high-value portfolio work, not replaceable with cosmetic polish |

## Security evidence and interpretation

Scans query current public advisory databases using package names and versions; no genomic inputs are sent. Gitleaks scans local files and history with redaction. Bandit findings were reviewed: shell-free subprocess calls, retry jitter, fixed SQL placeholders, and trusted local Hugging Face directories are not treated as remote exploits merely because the scanner flags a pattern. Findings about XML parsing and legacy MD5 usage were addressed (MD5 remains only a non-security upstream release checksum alongside SHA-256).

Commands and raw reports are under `scripts/security_scan.sh` and ignored `results/audit/`. The optional research scan is expected to report the outstanding Accelerate issue. A zero-advisory result for core does not cover unknown vulnerabilities, malicious dependencies, native OS libraries, containers not built here, or clinical correctness.

## GitHub readiness

The intended commit contains code, locks, synthetic fixtures, documentation, and CI configuration. Generated research data, model downloads, database files, results, Node dependencies, and virtual environments are excluded. The two public indexes are removed from the current tree. No force-push or history rewrite is part of this work. MIT applies to original code; upstream content retains its own licenses.

The existing remote is already at the original commit, so old index blobs remain in history. A future coordinated history cleanup is optional; do not pretend a normal deletion purges existing commits.

## Measured validation

Local validation completed on 2026-09-09. Measurements include the project virtual environment, retained research results, local snapshots, static UI, and Git history. Sizes use decimal MB/GB and filesystem metadata; macOS offloaded files explain the difference between logical and allocated size.

| Metric | Before | After cleanup | Reduction |
| --- | ---: | ---: | ---: |
| Logical project size | 3.441 GB | 294.4 MB | 91.4% |
| Allocated disk blocks | 650.4 MB | 245.4 MB | 62.3% |
| File count | 49,809 | 6,214 | 87.5% |

The static UI is 643 KB. Node dependencies are unnecessary at runtime; `npm ci` restores them for development. Optional models were removed with approval and remain opt-in. Scientific accuracy improvement from those models has not been demonstrated. Small subsequent documentation and staging changes can alter totals slightly.

- Regression suite: **51 passed** in 1.81 seconds; two dependency deprecation warnings. Ruff and whitespace checks passed.
- Frontend: production static export and TypeScript validation passed; browser demo recovered three candidates and four table rows after removing Node dependencies.
- Packaging: installed-wheel demo also passed from outside the checkout, with three candidates and packaged synthetic fixtures.
- Nextflow: all three core processes completed, unchanged resume cached all three, and ranking-only mode executed only tournament ranking.
- Optional services: bounded CATT snapshot queried all four configured sources with integrity validation; real Mutalyzer normalized `2del` against `AAAA` to `4del` in an isolated environment using the checksum-guarded metadata compatibility patch.
- Security: no known advisories in core, development, CATT, or normalizer locks; npm reported zero vulnerabilities. Gitleaks found no secrets in the one-commit history or proposed source tree. Optional research dependencies retain one unpatched Accelerate advisory, documented in SECURITY.md.
- Not verified here: Docker runtime builds, hosted GitHub CI, penetration resistance, and independent biological accuracy. Historical integration measurements remain in EVALUATION.md and are not substitutes for a new independent scientific evaluation.
