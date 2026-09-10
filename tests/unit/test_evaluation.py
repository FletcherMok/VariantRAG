import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "evaluate", Path(__file__).parents[2] / "benchmarks/evaluate.py"
)
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


def test_missing_predictions_count_against_recall():
    metrics = evaluate.score(
        [{"case_id": "a", "expected_evidence_ids": ["x"]}, {"case_id": "b", "expected_evidence_ids": ["y"]}],
        [{"case_id": "a", "evidence_ids": ["x", "false"]}],
    )
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["abstentions"] == 1


def test_duplicate_predictions_rejected():
    with pytest.raises(ValueError):
        evaluate.score(
            [{"case_id": "a", "expected_evidence_ids": []}],
            [{"case_id": "a", "evidence_ids": []}, {"case_id": "a", "evidence_ids": []}],
        )
