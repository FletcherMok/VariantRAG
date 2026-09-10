from pathlib import Path

import pytest
from variantrag.io import read_json
from variantrag.models import validate_bundles
from variantrag.pipeline import run_pipeline
from variantrag.ranking import rank

FIXTURE = Path(__file__).parents[1] / "fixtures"


def demo(tmp_path):
    return run_pipeline(
        FIXTURE / "demo.vcf", tmp_path, literature_path=FIXTURE / "demo_literature.json", mode="demo"
    )


def test_replay_and_neighbor_evidence(tmp_path):
    result = demo(tmp_path)
    frozen = read_json(tmp_path / "EvidenceBundle.json")
    assert result == rank(frozen)
    assert len(frozen) == 3
    assert len(frozen[0]["sql_table_evidence"]) == 4
    assert frozen[0]["catt_grounding"]["status"] == "not_requested"
    assert result["diagnostics"]["judge_calls"] == 6
    assert result["ranked_variants"][0]["variant_key"].endswith(":100:A:G")


def test_research_rejects_synthetic(tmp_path):
    with pytest.raises(ValueError, match="Synthetic"):
        run_pipeline(FIXTURE / "demo.vcf", tmp_path, literature_path=FIXTURE / "demo_literature.json")


def test_missing_evidence_is_unranked(tmp_path):
    result = run_pipeline(FIXTURE / "demo.vcf", tmp_path)
    assert all(r["rank"] is None for r in result["ranked_variants"])
    assert all(r["preference_score"] is None for r in result["ranked_variants"])


def test_position_biased_judge_is_flagged(tmp_path):
    demo(tmp_path)

    def biased(a, b):
        refs = [r["evidence_id"] for r in a.sql_table_evidence + b.sql_table_evidence]
        return {
            "winner": "A" if refs else "tie",
            "evidence_ids": refs,
            "rationale": "Position-biased test judge",
        }

    result = rank(read_json(tmp_path / "EvidenceBundle.json"), comparator=biased)
    assert result["diagnostics"]["disagreement_count"] == 2
    assert not result["diagnostics"]["global_order_available"]


def test_fabricated_citation_rejected(tmp_path):
    demo(tmp_path)
    with pytest.raises(ValueError, match="absent"):
        rank(
            read_json(tmp_path / "EvidenceBundle.json"),
            comparator=lambda a, b: {"winner": "A", "evidence_ids": ["fake"]},
        )


def test_mixed_build_rejected(tmp_path):
    demo(tmp_path)
    bundles = read_json(tmp_path / "EvidenceBundle.json")
    bundles[1]["variant"]["genome_build"] = "GRCh37"
    with pytest.raises(ValueError, match="build"):
        validate_bundles(bundles)
