"""Auditable comparison experiments; preference scores are never pathogenicity probabilities."""

import hashlib
import itertools
import json
import math
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

from .models import validate_bundles


def supported_cases(bundle):
    # Baseline orders evidence-review workload, not disease causality. No frequency/PM3 points inferred.
    cases = {}
    for row in bundle.sql_table_evidence:
        if row.get("proband_id") and row.get("match_validation") == "exact_allele":
            key = (row["document_id"], row.get("family_id") or row["proband_id"])
            cases[key] = row["evidence_id"]
    return sorted(cases.values())


def baseline_compare(a, b):
    refs_a, refs_b = supported_cases(a), supported_cases(b)
    winner = "A" if len(refs_a) > len(refs_b) else "B" if len(refs_b) > len(refs_a) else "tie"
    return {
        "winner": winner,
        "evidence_ids": refs_a + refs_b,
        "rationale": f"Exact-allele case groups available for review: A={len(refs_a)}, B={len(refs_b)}. "
        "This baseline measures evidence availability, not pathogenicity.",
    }


def schedule(n, budget=None):
    total = n * (n - 1) // 2
    budget = min(total, max(120, n - 1) if budget is None else budget)
    if budget < max(0, n - 1):
        raise ValueError("Pair budget must allow a connected comparison graph (at least n-1)")
    if budget >= total:
        return list(itertools.combinations(range(n), 2))
    # Seed a spanning path: a merely large enough budget does not guarantee connectivity.
    pairs = [(i, i + 1) for i in range(n - 1)]
    seen = set(pairs)
    ring = list(range(n)) + ([-1] if n % 2 else [])
    for _ in range(len(ring) - 1):
        for left, right in zip(ring[: len(ring) // 2], reversed(ring[len(ring) // 2 :]), strict=True):
            if len(pairs) >= budget:
                return pairs
            pair = tuple(sorted((left, right)))
            if left != -1 and right != -1 and pair not in seen:
                pairs.append(pair)
                seen.add(pair)
        ring = [ring[0], ring[-1], *ring[1:-1]]
    return pairs


def bradley_terry(n, outcomes, regularization=1.0):
    if not outcomes:
        return [None] * n

    def objective(theta):
        loss = regularization * np.dot(theta, theta) / 2
        grad = regularization * theta.copy()
        for winner, loser in outcomes:
            delta = theta[loser] - theta[winner]
            loss += np.logaddexp(0, delta)
            p = 1 / (1 + math.exp(-float(np.clip(delta, -700, 700))))
            grad[winner] -= p
            grad[loser] += p
        return loss, grad

    fit = minimize(objective, np.zeros(n), jac=True, method="L-BFGS-B")
    if not fit.success:
        raise RuntimeError(f"Bradley-Terry failed to converge: {fit.message}")
    scores = np.exp(fit.x - max(fit.x))
    return (scores / scores.sum()).tolist()


def components(n, edges):
    graph = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    remaining, groups = set(range(n)), []
    while remaining:
        stack, group = [min(remaining)], set()
        while stack:
            vertex = stack.pop()
            if vertex in group:
                continue
            group.add(vertex)
            stack.extend(graph[vertex] - group)
        remaining -= group
        groups.append(sorted(group))
    return groups


def rank(records, comparator=None, budget=None, method="evidence_availability_baseline"):
    bundles = sorted(validate_bundles(records), key=lambda b: b.variant.key)
    comparator = comparator or baseline_compare
    n = len(bundles)
    pairs = schedule(n, budget)
    outcomes, comparisons = [], []
    for i, j in pairs:
        a, b = bundles[i], bundles[j]
        available = {
            h["evidence_id"]
            for bundle in (a, b)
            for h in bundle.sql_table_evidence + bundle.rag_text_evidence
        }
        available.update(
            f["evidence_id"] for bundle in (a, b) for f in bundle.catt_grounding.data.get("fields", [])
        )
        forward, reverse = comparator(a, b), comparator(b, a)
        for judgment in (forward, reverse):
            if judgment.get("winner") not in {"A", "B", "tie", "abstain"}:
                raise ValueError("Judge returned an invalid outcome")
            if not set(judgment.get("evidence_ids", [])).issubset(available):
                raise ValueError("Judge cites evidence absent from supplied bundles")
            if judgment["winner"] in {"A", "B"} and not judgment.get("evidence_ids"):
                raise ValueError("Decisive judgment requires evidence citations")
        f, r = forward["winner"], reverse["winner"]
        status = "disagreement"
        if f == "A" and r == "B":
            outcomes.append((i, j))
            status = "consistent"
        elif f == "B" and r == "A":
            outcomes.append((j, i))
            status = "consistent"
        elif f == r == "tie":
            status = "tie"
        elif "abstain" in (f, r):
            status = "abstention"
        comparisons.append(
            {
                "variant_1": a.variant.key,
                "variant_2": b.variant.key,
                "forward": forward,
                "reverse": reverse,
                "status": status,
            }
        )
    scores = bradley_terry(n, outcomes)
    decisive_groups = components(n, outcomes)
    globally_orderable = n > 1 and len(decisive_groups) == 1
    wins, played = defaultdict(int), defaultdict(int)
    for winner, loser in outcomes:
        wins[winner] += 1
        played[winner] += 1
        played[loser] += 1
    order = (
        sorted(range(n), key=lambda i: (-(scores[i] or 0), bundles[i].variant.key))
        if globally_orderable
        else list(range(n))
    )
    ranked = [
        {
            "variant_key": bundles[i].variant.key,
            "rank": (1 + sum((scores[j] or 0) > (scores[i] or 0) + 1e-10 for j in range(n)))
            if globally_orderable
            else None,
            "preference_score": scores[i],
            "win_rate": wins[i] / played[i] if played[i] else None,
            "bundle": bundles[i].model_dump(),
        }
        for i in order
    ]
    edges = set(outcomes)
    outgoing = defaultdict(set)
    incoming = defaultdict(set)
    for winner, loser in edges:
        outgoing[winner].add(loser)
        incoming[loser].add(winner)
    cycles = sum(len(outgoing[b] & incoming[a]) for a, b in edges) // 3
    return {
        "schema_version": "1.0",
        "method": method,
        "ranked_variants": ranked,
        "pairwise_comparisons": comparisons,
        "diagnostics": {
            "candidate_count": n,
            "pair_count": len(pairs),
            "judge_calls": 2 * len(pairs),
            "coverage": len(pairs) / (n * (n - 1) / 2) if n > 1 else 0,
            "disagreement_count": sum(c["status"] == "disagreement" for c in comparisons),
            "cycle_count": cycles,
            "decisive_components": [[bundles[i].variant.key for i in g] for g in decisive_groups],
            "scheduled_components": components(n, pairs),
            "global_order_available": globally_orderable,
            "aggregation": "L2-regularized Bradley-Terry; lambda=1; normalized exp(theta)",
            "limitation": "Relative evidence-review preference, not a calibrated clinical probability. "
            "Disconnected decisive graphs have no global rank.",
        },
        "input_hash": hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
    }
