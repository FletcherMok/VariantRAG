import argparse
from pathlib import Path

from .io import read_json, write_json


def main():
    parser = argparse.ArgumentParser(description="VariantRAG evidence workbench")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--vcf", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--genome-build", choices=["GRCh37", "GRCh38"], default="GRCh38")
    run.add_argument("--sample")
    run.add_argument("--literature")
    run.add_argument("--mode", choices=["demo", "research"], default="research")
    run.add_argument("--reference")
    run.add_argument("--bam")
    run.add_argument("--medcpt")
    run.add_argument("--online", action="store_true")
    run.add_argument("--mutalyzer-url")
    run.add_argument("--catt-snapshot")
    rerank = commands.add_parser("rank")
    rerank.add_argument("--bundles", required=True)
    rerank.add_argument("--out", required=True)
    rerank.add_argument("--pair-budget", type=int, default=120)
    rerank.add_argument("--ollama-model")
    rerank.add_argument("--judgments-dir", default="results/judgments")
    parse = commands.add_parser("parse")
    parse.add_argument("--vcf", required=True)
    parse.add_argument("--genome-build", required=True, choices=["GRCh37", "GRCh38"])
    parse.add_argument("--sample")
    parse.add_argument("--reference")
    parse.add_argument("--out", required=True)
    assemble = commands.add_parser("assemble")
    assemble.add_argument("--variants", required=True)
    assemble.add_argument("--literature", required=True)
    assemble.add_argument("--mode", choices=["demo", "research"], default="research")
    assemble.add_argument("--out", required=True)
    pdf = commands.add_parser("ingest-pdf")
    pdf.add_argument("--pdf", required=True)
    pdf.add_argument("--document-id", required=True)
    pdf.add_argument("--pmid")
    pdf.add_argument("--out", required=True)
    refresh = commands.add_parser("catt-refresh")
    refresh.add_argument("--checkout", required=True)
    refresh.add_argument("--revision", required=True)
    refresh.add_argument("--out", required=True)
    refresh.add_argument("--variant-ids", help="Comma-separated IDs for a bounded source snapshot")
    query = commands.add_parser("catt-query")
    query.add_argument("--variation-id", required=True)
    query.add_argument("--snapshot", required=True)
    query.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.command == "run":
            from .pipeline import run_pipeline

            run_pipeline(
                args.vcf,
                args.out,
                args.genome_build,
                args.sample,
                args.literature,
                args.mode,
                args.reference,
                args.bam,
                medcpt=args.medcpt,
                online=args.online,
                mutalyzer_url=args.mutalyzer_url,
                catt_snapshot=args.catt_snapshot,
            )
        elif args.command == "rank":
            from .ranking import rank

            comparator = None
            method = "evidence_availability_baseline"
            if args.ollama_model:
                from .judge import OllamaJudge

                comparator = OllamaJudge(args.ollama_model, args.judgments_dir)
                method = "ollama:" + args.ollama_model
            write_json(
                args.out,
                rank(read_json(args.bundles), comparator=comparator, budget=args.pair_budget, method=method),
            )
        elif args.command == "parse":
            from .variants import parse_variants

            records, rejected = parse_variants(args.vcf, args.genome_build, args.sample, args.reference)
            write_json(args.out, records)
            write_json(str(args.out) + ".rejected.json", rejected)
        elif args.command == "assemble":
            from .pipeline import assemble as assemble_evidence

            write_json(
                args.out,
                assemble_evidence(
                    read_json(args.variants), read_json(args.literature), Path(args.out).parent, args.mode
                ),
            )
        elif args.command == "ingest-pdf":
            from .literature import extract_pdf

            write_json(args.out, extract_pdf(args.pdf, args.document_id, args.pmid))
        elif args.command == "catt-refresh":
            from .grounding import refresh_catt

            if args.variant_ids:
                from .snapshots import bounded_refresh

                bounded_refresh(args.checkout, args.out, args.revision, args.variant_ids.split(","))
            else:
                refresh_catt(args.checkout, args.out, args.revision)
        elif args.command == "catt-query":
            from .grounding import query_catt

            write_json(
                Path(args.out) / "grounding.json", query_catt(args.variation_id, args.snapshot, args.out)
            )
    except (ValueError, FileNotFoundError, ImportError) as exc:
        parser.exit(2, f"VariantRAG: {exc}\n")


if __name__ == "__main__":
    main()
