"""Versioned hand-off: absent evidence is explicit and never converted to a positive claim."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Variant(StrictModel):
    key: str
    genome_build: Literal["GRCh37", "GRCh38"]
    chrom: str
    pos: int = Field(gt=0)
    ref: str
    alt: str
    sample_id: str | None = None
    genotype: list[int] = Field(default_factory=list)
    phase_set: str | None = None
    phased: bool = False
    consequences: list[str]
    transcript: str | None = None
    gene: str | None = None
    hgnc_id: str | None = None
    hgvs_g: str | None = None
    hgvs_c: str | None = None
    hgvs_p: str | None = None
    annotations: list[dict] = Field(default_factory=list)
    quality: float | None = None
    allele_depths: list[int] = Field(default_factory=list)
    reference_status: str = "not_checked"


class SourceState(StrictModel):
    status: Literal["available", "unavailable", "not_requested", "no_match", "ambiguous", "error"]
    reason: str | None = None
    data: dict = Field(default_factory=dict)


class EvidenceBundle(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    bundle_id: str
    run_id: str
    input_mode: Literal["demo", "research"]
    variant: Variant
    resolution: SourceState = Field(default_factory=lambda: SourceState(status="not_requested"))
    normalization: SourceState = Field(default_factory=lambda: SourceState(status="not_requested"))
    alignment: SourceState = Field(default_factory=lambda: SourceState(status="not_requested"))
    catt_grounding: SourceState = Field(default_factory=lambda: SourceState(status="not_requested"))
    rag_text_evidence: list[dict] = Field(default_factory=list)
    sql_table_evidence: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    evidence_assessment: dict = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def verify_evidence(self):
        ids = []
        for hit in self.rag_text_evidence + self.sql_table_evidence:
            if not hit.get("evidence_id") or not hit.get("document_id"):
                raise ValueError("Evidence must identify its source document and stable evidence ID")
            if self.input_mode == "research" and hit.get("synthetic", False):
                raise ValueError("Synthetic evidence is forbidden in research mode")
            ids.append(hit["evidence_id"])
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evidence IDs in bundle")
        return self


def validate_bundles(records):
    bundles = [EvidenceBundle.model_validate(r) for r in records]
    if len({b.variant.genome_build for b in bundles}) > 1:
        raise ValueError("Cannot combine genome builds")
    if len({b.variant.key for b in bundles}) != len(bundles):
        raise ValueError("Duplicate variant identities")
    if len({b.input_mode for b in bundles}) > 1:
        raise ValueError("Cannot mix demonstration and research evidence")
    return bundles
