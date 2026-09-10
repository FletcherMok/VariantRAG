process REFRESH_CATT {
    publishDir params.outdir, mode: 'copy'
    input:
    path checkout, name: 'catt-checkout'
    val revision
    output:
    path 'catt-snapshot'
    script:
    if (!(revision ==~ /[a-f0-9]{40}/)) error 'catt_revision must be a full commit SHA'
    if (!(params.catt_variant_ids ==~ /[0-9]+(,[0-9]+)*/)) error 'Provide --catt_variant_ids as comma-separated Variation IDs for a bounded snapshot'
    """
    ${params.python} -m variantrag.cli catt-refresh --checkout '${checkout}' --revision '${revision}' --variant-ids '${params.catt_variant_ids}' --out catt-snapshot
    """
}
