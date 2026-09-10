"""Evaluate source-retrieval labels with missing predictions counted as abstentions.

Labels must be independently reviewed. PM3-Bench curator comments are never treated as source passages.
"""

import argparse
import json
from pathlib import Path


def score(labels, predictions):
    ids = [r["case_id"] for r in labels]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs in labels")
    pred_ids = [r["case_id"] for r in predictions]
    if len(pred_ids) != len(set(pred_ids)) or set(pred_ids) - set(ids):
        raise ValueError("Duplicate or unknown prediction case IDs")
    predicted = {r["case_id"]: r for r in predictions}
    tp = fp = fn = abstentions = 0
    details = []
    for row in labels:
        expected = set(row["expected_evidence_ids"])
        actual = set(predicted.get(row["case_id"], {}).get("evidence_ids", []))
        tp += len(expected & actual)
        fp += len(actual - expected)
        fn += len(expected - actual)
        abstentions += not actual
        details.append(
            {
                "case_id": row["case_id"],
                "true_positives": len(expected & actual),
                "false_positives": len(actual - expected),
                "false_negatives": len(expected - actual),
            }
        )
    return {
        "cases": len(ids),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "abstentions": abstentions,
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = score(json.loads(Path(args.labels).read_text()), json.loads(Path(args.predictions).read_text()))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
