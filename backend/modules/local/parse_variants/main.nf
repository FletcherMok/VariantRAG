process PARSE_VARIANTS {
    tag "${vcf}"
    publishDir params.outdir, mode: 'copy'
    input:
    path vcf, name: 'input.vcf.gz'
    val code_hash
    output:
    path 'variants.json'
    script:
    def sample = params.sample ? "--sample '" + params.sample.replace("'", "'\\''") + "'" : ''
    """
    # Implementation SHA256: ${code_hash}
    ${params.python} -m variantrag.cli parse --vcf '${vcf}' --genome-build '${params.genome_build}' ${sample} --out variants.json
    """
}
