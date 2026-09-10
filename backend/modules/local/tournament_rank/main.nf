process TOURNAMENT_RANK {
    publishDir params.outdir, mode: 'copy'
    input:
    path bundles, name: 'EvidenceBundle.json'
    val code_hash
    output:
    path 'ranking.json'
    script:
    """
    # Implementation SHA256: ${code_hash}
    ${params.python} -m variantrag.cli rank --bundles '${bundles}' --out ranking.json
    """
}
