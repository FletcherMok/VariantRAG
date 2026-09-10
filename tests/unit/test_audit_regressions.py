import json
from pathlib import Path

import pytest
from variantrag.io import write_json
from variantrag.ranking import components, schedule
from variantrag.tables import variant_match
from variantrag.variants import parse_variants


def test_transcript_must_belong_to_matched_allele():
    text = "NM_000001.1:c.999A>G; NM_000002.1:c.123A>G"
    assert not variant_match(text, "NM_000001.1:c.123A>G")
    assert variant_match(text, "NM_000002.1:c.123A>G")


@pytest.mark.parametrize("n", [31, 122, 250])
def test_sparse_schedule_is_bounded_unique_and_connected(n):
    pairs = schedule(n)
    assert len(pairs) == max(120, n - 1)
    assert len(set(pairs)) == len(pairs)
    assert len(components(n, pairs)) == 1


def test_explicit_pair_budget_is_respected():
    assert len(schedule(20, 20)) == 20
    with pytest.raises(ValueError, match="connected"):
        schedule(20, 18)


def test_failed_json_write_leaves_no_orphan(tmp_path):
    target = tmp_path / "out.json"
    write_json(target, {"old": True})
    with pytest.raises(ValueError):
        write_json(target, {"bad": float("nan")})
    assert json.loads(target.read_text()) == {"old": True}
    assert list(tmp_path.iterdir()) == [target]


def test_candidate_limit_is_explicit():
    fixture = Path(__file__).parents[1] / "fixtures/demo.vcf"
    with pytest.raises(ValueError, match="Candidate limit"):
        parse_variants(fixture, "GRCh38", max_candidates=1)


def test_snapshot_rejects_unchecked_executable(tmp_path):
    from variantrag.grounding import query_catt
    from variantrag.io import digest

    (tmp_path / "main.py").write_text("# trusted")
    write_json(tmp_path / "manifest.json", {"files": {"main.py": digest(tmp_path / "main.py")}})
    (tmp_path / "injected.py").write_text("# unchecked")
    with pytest.raises(ValueError, match="unchecked executable"):
        query_catt("10", tmp_path, tmp_path / "output")


def test_snapshot_rejects_symlink(tmp_path):
    from variantrag.grounding import query_catt
    from variantrag.io import digest

    (tmp_path / "main.py").write_text("# trusted")
    write_json(tmp_path / "manifest.json", {"files": {"main.py": digest(tmp_path / "main.py")}})
    (tmp_path / "alias").symlink_to(tmp_path / "main.py")
    with pytest.raises(ValueError, match="symlinks"):
        query_catt("10", tmp_path, tmp_path / "output")


def test_streamed_body_limit_precedes_endpoint():
    import asyncio

    from variantrag.security import LocalBoundary

    called = False
    messages = iter(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ]
    )
    sent = []

    async def endpoint(scope, receive, send):
        nonlocal called
        called = True

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    asyncio.run(
        LocalBoundary(endpoint, max_bytes=8)(
            {"type": "http", "method": "POST", "path": "/api/run", "headers": []}, receive, send
        )
    )
    assert not called
    assert sent[0]["status"] == 413


def test_compression_detection_uses_bytes_not_staged_filename(tmp_path):
    import gzip

    fixture = Path(__file__).parents[1] / "fixtures/demo.vcf"
    misleading = tmp_path / "input.vcf.gz"
    misleading.write_bytes(fixture.read_bytes())
    assert len(parse_variants(misleading, "GRCh38")[0]) == 3
    compressed = tmp_path / "input.vcf"
    compressed.write_bytes(gzip.compress(fixture.read_bytes()))
    assert len(parse_variants(compressed, "GRCh38")[0]) == 3
