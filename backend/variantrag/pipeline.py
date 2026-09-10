from pathlib import Path

from .io import digest, read_json, write_json
from .literature import lexical_retrieve, medcpt_retrieve
from .models import EvidenceBundle, SourceState, Variant, validate_bundles
from .ranking import rank
from .tables import build_database, query_variant
from .variants import TARGET_CONSEQUENCES, alignment_evidence, parse_variants


def assemble(
    variants,
    literature,
    outdir,
    mode="research",
    run_id="local",
    source_path=None,
    medcpt=None,
    bam=None,
    reference=None,
):
    outdir = Path(outdir)
    if mode == "research" and (
        literature.get("synthetic")
        or any(x.get("synthetic") for x in literature.get("tables", []) + literature.get("passages", []))
    ):
        raise ValueError("Synthetic literature can only be used in demo mode")
    database = outdir / "cases.duckdb"
    build_database(literature.get("tables", []), database)
    bundles = []
    for variant in variants:
        query = variant.get("hgvs_c")
        hits = query_variant(database, query, variant.get("transcript"), variant.get("gene")) if query else []
        text = (
            medcpt_retrieve(literature.get("passages", []), variant, medcpt)
            if medcpt
            else lexical_retrieve(literature.get("passages", []), variant)
        )
        missing = [
            "Clinical criterion assignment is not implemented",
            "Population frequency not assessed",
            "Cross-publication proband deduplication requires review",
        ]
        if not hits:
            missing.append("No exact-allele case table evidence recovered")
        if not text:
            missing.append("No text evidence recovered")
        if variant["reference_status"] != "validated":
            missing.append("Reference FASTA was not supplied; assembly identity is user-declared")
        bundle = EvidenceBundle(
            bundle_id=variant["key"],
            run_id=run_id,
            input_mode=mode,
            variant=Variant.model_validate(variant),
            sql_table_evidence=hits,
            rag_text_evidence=text,
            alignment=SourceState.model_validate(alignment_evidence(variant, bam, reference))
            if bam
            else SourceState(status="not_requested"),
            evidence_assessment={
                "missing_evidence": missing,
                "supported_claims": [],
                "conflicts": [],
                "duplicate_groups": [],
                "policy": "Evidence extraction only; co-occurrence does not establish phase",
            },
            provenance={
                "input": {"path": str(source_path), "sha256": digest(source_path)} if source_path else {},
                "table_database_sha256": digest(database),
                "literature_artifacts": [
                    {"document_id": document_id, "sha256": source_hash}
                    for document_id, source_hash in sorted(
                        {
                            (item["document_id"], item.get("source_hash", "not_supplied"))
                            for item in literature.get("tables", []) + literature.get("passages", [])
                        }
                    )
                ],
                "retrieval": "MedCPT" if medcpt else "exact HGVS lexical baseline",
                "tool_version": "0.2.0",
            },
        )
        bundles.append(bundle.model_dump())
    validate_bundles(bundles)
    return bundles


def run_pipeline(
    vcf,
    output,
    build="GRCh38",
    sample=None,
    literature_path=None,
    mode="research",
    reference=None,
    bam=None,
    run_id="local",
    medcpt=None,
    online=False,
    mutalyzer_url=None,
    catt_snapshot=None,
):
    from .grounding import normalize, query_catt, resolve_clinvar
    from .network import CachedHTTP

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    variants, rejected = parse_variants(vcf, build, sample, reference)
    write_json(output / "variants.json", variants)
    write_json(output / "rejected.json", rejected)
    literature = read_json(literature_path) if literature_path else {"tables": [], "passages": []}
    if online and mode == "demo":
        raise ValueError("Online lookups are disabled for synthetic demonstration identities")
    if mutalyzer_url and not online:
        raise ValueError("--mutalyzer-url requires --online to make network access explicit")
    http = CachedHTTP(output / "http_cache") if online else None
    identity_states = {}
    for variant in variants:
        states = {}
        if online:
            if mutalyzer_url:
                states["normalization"] = normalize(variant, http, mutalyzer_url)
                response = states["normalization"].get("data", {}).get("response", {})
                description = response.get("normalized_description")
                if states["normalization"]["status"] == "available" and description and ":c." in description:
                    # Preserve the caller-supplied annotation and store only the returned normalized description.
                    states["original_hgvs_c"] = variant.get("hgvs_c")
                    variant["hgvs_c"] = description
            states["resolution"] = resolve_clinvar(variant, http)
        identity_states[variant["key"]] = states
    write_json(output / "variants.json", variants)
    bundles = assemble(variants, literature, output, mode, run_id, vcf, medcpt, bam, reference)
    for bundle in bundles:
        states = identity_states[bundle["variant"]["key"]]
        for name in ("normalization", "resolution"):
            if name in states:
                bundle[name] = states[name]
        if "original_hgvs_c" in states:
            bundle["provenance"]["original_hgvs_c"] = states["original_hgvs_c"]
        if catt_snapshot:
            resolution = bundle["resolution"]
            if resolution["status"] == "available":
                identity = resolution["data"]["clinvar_variation_id"]
                try:
                    bundle["catt_grounding"] = query_catt(identity, catt_snapshot, output / "catt" / identity)
                except Exception as exc:
                    bundle["catt_grounding"] = {"status": "error", "reason": str(exc)}
            else:
                bundle["catt_grounding"] = {
                    "status": "unavailable",
                    "reason": "No verified ClinVar Variation ID",
                }
    validated = [b.model_dump() for b in validate_bundles(bundles)]
    write_json(output / "EvidenceBundle.json", validated)
    results = rank(validated)
    write_json(output / "ranking.json", results)
    write_json(
        output / "manifest.json",
        {
            "schema_version": "1.0",
            "run_id": run_id,
            "input_mode": mode,
            "genome_build": build,
            "input_sha256": digest(vcf),
            "candidate_count": len(variants),
            "literature_sha256": digest(literature_path) if literature_path else None,
            "reference_sha256": digest(reference) if reference else None,
            "filter": {
                "consequences": sorted(TARGET_CONSEQUENCES),
                "vcf_filter": "PASS or missing",
                "genotype": "selected sample carries ALT",
            },
            "artifacts": {
                p.name: digest(p) for p in [output / "EvidenceBundle.json", output / "ranking.json"]
            },
        },
    )
    return results
