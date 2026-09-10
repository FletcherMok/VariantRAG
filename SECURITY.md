# Security scope

VariantRAG is a single-user, loopback-only research workbench. Do not expose its API or the optional normalizer to a public network. It has no multi-user authentication, authorization, tenant isolation, or regulated-data compliance claim.

The API rejects unknown Host and browser Origin headers, bounds request bodies before multipart parsing, restricts upload and decompressed VCF sizes, limits candidate counts and retained jobs, and supports explicit deletion of completed runs. These controls reduce local-browser abuse and accidental resource exhaustion; they do not sandbox native parsers or protect against a malicious local user.

Case SQL is restricted to a read-only DuckDB allowlist with row, time, memory, and external-access limits. CATT executes a trusted local upstream checkout: a full revision, clean tracked files, executable/data checksums, and symlink rejection detect accidental modification. A checksum manifest is not a signature or proof that a source is trustworthy. Never run an untrusted snapshot.

Online lookup is opt-in and sends variant coordinates/HGVS to the configured services. Do not enable it for restricted data without appropriate authorization. Source text and model responses are untrusted. Citation-ID validation does not prove that a citation supports an assertion or eliminate prompt injection.

## Known optional dependency limitation

The optional Docling environment includes Accelerate 1.14.0, affected by [CVE-2026-69112](https://github.com/advisories/GHSA-4j2p-28q2-5m79). The advisory lists no patched release as of 2026-09-09. The affected operation loads attacker-controlled sharded checkpoint indexes. Use only trusted model repositories and pinned revisions; do not load third-party checkpoints. Model assistance is optional and excluded from the default environment. This limitation is not treated as a clean vulnerability scan.

The audit also found [CVE-2026-59890](https://github.com/advisories/GHSA-h35f-9h28-mq5c) in the old setuptools dependency. The obsolete `mutalyzer-api` wrapper has been removed; the adapter now calls the actual Mutalyzer library. Builds require setuptools >=83. Three pinned Mutalyzer dependencies still use `pkg_resources` for metadata; the isolated adapter setup applies the checksum-guarded `scripts/patch_mutalyzer_metadata.py` compatibility patch rather than reinstalling vulnerable setuptools.

## Reporting

Use this repository's GitHub Security Advisories private reporting interface if enabled. Otherwise contact the maintainer through their GitHub profile to arrange private disclosure. Do not publish credentials, patient data, or exploitable details in public issues. No private reporting feature is claimed to be enabled by this repository alone.

Run the commands in `docs/AUDIT.md` to refresh known-vulnerability and secret scans. A successful scan is time-bounded evidence, not a guarantee of security.
