import pytest
from variantrag.tables import build_database, position_match, query_variant, safe_select, variant_match


def fixture_table(document="paper", table="T1"):
    return {
        "document_id": document,
        "table_id": table,
        "headers": ["patient", "variant", "phase", "phase_method"],
        "rows": [
            {"cells": ["P1", "c.90del", "unknown", ""]},
            {"cells": ["P1", "c.123A>G", "unknown", ""]},
            {"cells": ["P1", "c.456T>C", "trans", "parental testing"]},
            {"cells": ["P2", "c.900C>A", "unknown", ""]},
            {"cells": ["", "c.123A>G", "unknown", ""]},
            {"cells": ["", "c.888T>C", "unknown", ""]},
            {"cells": ["P3", "0.91234", "unknown", ""]},
        ],
    }


def test_bidirectional_proband_recovery_and_scope(tmp_path):
    path = tmp_path / "evidence.duckdb"
    other = fixture_table("unrelated")
    other["rows"] = [{"cells": ["P1", "c.777A>C", "unknown", ""]}]
    other_table = {**other, "document_id": "paper", "table_id": "T2"}
    build_database([fixture_table(), other, other_table], path)
    rows = query_variant(path, "NM_001.1:c.123A>G")
    assert [r["row_id"] for r in rows] == [0, 1, 2, 4]
    assert rows[0]["retrieval_links"][0]["direction"] == "upstream"
    assert rows[2]["retrieval_links"][0]["direction"] == "downstream"
    assert rows[0]["phase_supported"] is False
    assert rows[2]["phase_supported"] is False
    assert rows[2]["phase_reported_with_method"] is True
    assert all(r["document_id"] == "paper" and r["table_id"] == "T1" for r in rows)


@pytest.mark.parametrize("text", ["0.91234", "1234", "9123", "123.4", "0.123"])
def test_statistical_positions_rejected(text):
    assert not position_match(text, 123)


@pytest.mark.parametrize("text", ["c.123A>T", "c.123A>GG", "c.1123A>G", "NM_002.1:c.123A>G"])
def test_wrong_alleles_and_transcripts_rejected(text):
    assert not variant_match(text, "NM_001.1:c.123A>G")


def test_deletion_is_not_delins():
    assert variant_match("c.90del", "NM_001.1:c.90del")
    assert not variant_match("c.90delinsA", "NM_001.1:c.90del")


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE cases",
        "SELECT * FROM cases; DELETE FROM cases",
        "SELECT * FROM read_csv_auto('/etc/passwd')",
        "SELECT * FROM cases WHERE getenv('HOME') IS NOT NULL",
        "SELECT * FROM other",
        "SELECT * FROM cases INTO OUTFILE '/tmp/leak'",
        "SELECT * FROM information_schema.tables",
    ],
)
def test_sql_guards(tmp_path, sql):
    path = tmp_path / "e.duckdb"
    build_database([fixture_table()], path)
    with pytest.raises((ValueError, Exception)):
        safe_select(path, sql)
    assert len(safe_select(path, "SELECT * FROM cases")) == 7


def test_variant_match_in_prose_preserves_word_boundaries():
    assert variant_match("The variant c.123A>G was observed.", "NM_001.1:c.123A>G")
    assert variant_match("The variant c.123 A > G was observed.", "NM_001.1:c.123A>G")
    assert not variant_match("c.123A>GG was observed.", "NM_001.1:c.123A>G")
