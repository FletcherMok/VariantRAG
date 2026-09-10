nextflow.enable.dsl=2

include { PARSE_VARIANTS } from './modules/local/parse_variants/main'
include { ASSEMBLE_EVIDENCE } from './modules/local/assemble_evidence/main'
include { TOURNAMENT_RANK } from './modules/local/tournament_rank/main'
include { REFRESH_CATT } from './modules/local/catt_refresh/main'

def sourceDigest() {
    def digest = java.security.MessageDigest.getInstance('SHA-256')
    def files = []
    new File(projectDir.toString(), 'variantrag').eachFileRecurse { f -> if (f.name.endsWith('.py')) files << f }
    files << new File(projectDir.toString(), '../requirements.lock')
    files.sort { a, b -> a.path <=> b.path }.each { f -> digest.update(f.bytes) }
    return digest.digest().encodeHex().toString()
}

workflow {
    if (params.workflow == 'rank') {
        if (!params.bundles) error 'Provide --bundles EvidenceBundle.json'
        TOURNAMENT_RANK(Channel.fromPath(params.bundles, checkIfExists: true), sourceDigest())
    } else if (params.workflow == 'catt-refresh') {
        if (!params.catt_checkout || !params.catt_revision) error 'Provide --catt_checkout and --catt_revision'
        REFRESH_CATT(Channel.value(file(params.catt_checkout, checkIfExists: true)), params.catt_revision)
    } else if (params.workflow == 'run') {
        if (!(params.genome_build in ['GRCh37','GRCh38'])) error 'genome_build must be GRCh37 or GRCh38'
        if (!(params.mode in ['demo','research'])) error 'mode must be demo or research'
        if (!params.vcf) error 'Provide --vcf with a VEP/SnpEff annotated VCF'
        if (!params.literature) error 'Provide --literature JSON; use an explicit empty corpus for variant-only analysis'
        variants = PARSE_VARIANTS(Channel.fromPath(params.vcf, checkIfExists: true), sourceDigest())
        bundles = ASSEMBLE_EVIDENCE(variants, Channel.value(file(params.literature, checkIfExists: true)), sourceDigest())
        TOURNAMENT_RANK(bundles, sourceDigest())
    } else {
        error 'workflow must be run, rank, or catt-refresh'
    }
}
