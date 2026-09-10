# Third-party provenance

The MIT license in this repository covers VariantRAG's code, not third-party content. No upstream model weights, full databases, or paper PDFs are included in the commit set.

- [CATT](https://github.com/mgbpm/CATT): invoked as a separately downloaded CLI at revision `6815e6a2d67439c0f899416060e0d997d6d07dd8`. Retain its license and source configurations with snapshots. Local manifests record release URLs, hashes, and selected scope.
- [Mutalyzer](https://github.com/mutalyzer/mutalyzer): the optional service calls the real library through a small VariantRAG adapter. This adapter does not vendor or relabel Mutalyzer code. A version- and checksum-guarded installation patch replaces obsolete metadata lookups in three dependencies; it does not alter normalization logic.
- [NCBI MedCPT](https://github.com/ncbi/MedCPT): optional query/article encoders, pinned in the preparation script. Review each model card's licensing before redistribution.
- [Docling](https://github.com/docling-project/docling): optional PDF/table ingestion; its model assets are downloaded separately.
- [AutoPM3 / PM3-Bench](https://github.com/HKU-BAL/AutoPM3): methodology and split audit reference. The checked-in manifest records the inspected dataset hash; it does not redistribute the benchmark or claim a held-out score.
- [GIAB](https://www.nist.gov/programs-projects/genome-bottle): indexed public HG002 interval used for technical validation. The fetch script records source URLs and checksums; downloaded alignments and indexes are excluded.
- [PMC9319862](https://pmc.ncbi.nlm.nih.gov/articles/PMC9319862/): Rosina et al., *Genes* 2022, used for an exploratory ingestion check. The source article is CC BY; it is not bundled in this repository.

ClinVar, ClinGen, and GenCC assertions retain their original attribution, dates, disease scope, and submitter provenance. Their presence in a dossier must not be presented as an independent VariantRAG clinical assertion.
