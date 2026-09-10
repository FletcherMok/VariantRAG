process ASSEMBLE_EVIDENCE {
    publishDir params.outdir, mode: 'copy'
    input:
    path variants, name: 'variants.json'
    path literature, name: 'literature.json'
    val code_hash
    output:
    path 'EvidenceBundle.json'
    script:
    """
    # Implementation SHA256: ${code_hash}
    ${params.python} -m variantrag.cli assemble --variants '${variants}' --literature '${literature}' --mode '${params.mode}' --out EvidenceBundle.json
    """
}
