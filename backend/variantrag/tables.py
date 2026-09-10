"""DuckDB table pathway with scoped bidirectional proband recovery.

The first source column is the proband identifier. Row position is retained separately.
SQL finds candidate positions; full allele matching rejects numeric coincidences.
"""

import hashlib
import json
import re
import threading
from pathlib import Path

import duckdb
import sqlglot
from sqlglot import exp


def compact(value):
    return re.sub(r"\s+", "", str(value)).replace("→", ">").replace("−", "-")


def position_match(text, position):
    # Excludes decimal statistics and matches embedded in longer digit strings.
    return bool(
        re.search(rf"(?:(?<![\d.])|(?<=[cgnmp]\.)){re.escape(str(position))}(?![\d.])", compact(text))
    )


def variant_match(text, query, transcript=None):
    query = compact(query)
    query_transcript, allele = query.rsplit(":", 1) if ":" in query else (transcript, query)
    if not re.match(r"^[cgnmp]\.", allele):
        return False
    text = str(text).replace("→", ">").replace("−", "-")
    explicit = re.findall(r"((?:NM_|NR_|ENST)[A-Za-z0-9_.]+):", text)
    if explicit and query_transcript and query_transcript not in explicit:
        return False
    # Boundaries prevent c.123A>G matching c.123A>GG, and c.123del matching c.123delinsA.
    pattern = r"\s*".join(re.escape(char) for char in allele)
    return bool(re.search(rf"(?<![A-Za-z0-9_.]){pattern}(?![A-Za-z0-9_])", text))


def context_verified(row, query, transcript=None):
    expected = query.rsplit(":", 1)[0] if ":" in query else transcript
    if not expected:
        return False
    if row.get("transcript") == expected:
        return True
    return bool(re.search(re.escape(expected) + r"\s*:", row["variant_text"]))


SCHEMA = """
CREATE TABLE cases (
 proband_id VARCHAR, document_id VARCHAR, table_id VARCHAR, row_id INTEGER,
 pmid VARCHAR, gene_id VARCHAR, transcript VARCHAR, variant_text VARCHAR,
 phase VARCHAR, phase_method VARCHAR, family_id VARCHAR, phenotype VARCHAR,
 partner_classification VARCHAR, partner_classification_source VARCHAR,
 raw_cells VARCHAR, synthetic BOOLEAN,
 PRIMARY KEY(document_id, table_id, row_id)
)
"""


def build_database(tables, database):
    database = Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database)) as con:
        con.execute("BEGIN TRANSACTION")
        con.execute("DROP TABLE IF EXISTS cases")
        con.execute(SCHEMA)
        for table in tables:
            if not table.get("document_id") or not table.get("table_id"):
                raise ValueError("Table needs document_id and table_id")
            headers = table["headers"]
            if len(set(headers)) != len(headers):
                raise ValueError("Duplicate table headers require explicit disambiguation")
            if not headers:
                raise ValueError("Table must retain its first source column for proband ID")
            for index, row in enumerate(table["rows"]):
                cells = row["cells"]
                if len(cells) != len(headers):
                    raise ValueError("Table row width does not match headers")
                # Do not forward-fill an empty ID: only an explicit source merge can justify that.
                proband = str(cells[0]).strip() or None
                source = dict(zip(headers, cells, strict=True))
                lookup = {h.strip().lower(): str(v).strip() for h, v in source.items()}
                phase = lookup.get("phase", "unknown").lower()
                if phase not in {"trans", "cis", "unknown"}:
                    phase = "unknown"
                con.execute(
                    "INSERT INTO cases VALUES (" + ",".join(["?"] * 16) + ")",
                    [
                        proband,
                        table["document_id"],
                        table["table_id"],
                        row.get("row_id", index),
                        table.get("pmid"),
                        lookup.get("gene") or table.get("gene"),
                        lookup.get("transcript") or table.get("transcript"),
                        " | ".join(str(c) for c in cells[1:]),
                        phase,
                        lookup.get("phase_method"),
                        lookup.get("family_id"),
                        lookup.get("phenotype"),
                        lookup.get("classification"),
                        lookup.get("classification_source"),
                        json.dumps(source),
                        table.get("synthetic", False),
                    ],
                )
        con.execute("COMMIT")


def safe_select(database, sql, parameters=None, limit=1000, timeout=3):
    """Only relational SELECT over cases; no filesystem/network/table functions or extensions."""
    expressions = sqlglot.parse(sql, read="duckdb")
    if len(expressions) != 1 or not isinstance(expressions[0], exp.Select):
        raise ValueError("Exactly one SELECT is allowed")
    tree = expressions[0]
    forbidden = (exp.Command, exp.Into, exp.Subquery, exp.Union)
    if any(isinstance(node, forbidden) for node in tree.walk()):
        raise ValueError("Unsupported SQL construct")
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier) or table.name != "cases" or table.db or table.catalog:
            raise ValueError("Only the cases table is allowed")
    if not list(tree.find_all(exp.Table)):
        raise ValueError("SELECT must read cases")
    for node in tree.find_all(exp.Func):
        if not isinstance(node, (exp.Count, exp.Lower, exp.Upper, exp.Coalesce, exp.And, exp.Or)):
            raise ValueError("Function is outside the SQL allowlist")
    with duckdb.connect(str(database), read_only=True, config={"enable_external_access": False}) as con:
        con.execute("SET memory_limit='256MB'")
        timer = threading.Timer(timeout, con.interrupt)
        timer.start()
        try:
            cursor = con.execute(sql, parameters or [])
            names = [item[0] for item in cursor.description]
            result = cursor.fetchmany(limit + 1)
            if len(result) > limit:
                raise ValueError(f"Query exceeds {limit} rows; narrow the query")
            return [dict(zip(names, row, strict=True)) for row in result]
        finally:
            timer.cancel()


def query_variant(database, query, transcript=None, gene=None):
    allele = compact(query).split(":")[-1]
    positions = re.findall(r"\d+", allele)
    if not positions:
        return []
    sql = "SELECT * FROM cases WHERE variant_text LIKE ? ORDER BY document_id, table_id, row_id"
    candidates = safe_select(database, sql, ["%" + positions[0] + "%"])
    anchors = [
        r
        for r in candidates
        if position_match(r["variant_text"], positions[0])
        and variant_match(r["variant_text"], query, transcript)
        and (not r["transcript"] or not transcript or r["transcript"] == transcript)
        and (not gene or not r["gene_id"] or r["gene_id"] == gene)
    ]
    evidence = {}
    for anchor in anchors:
        neighbor_sql = (
            "SELECT * FROM cases WHERE document_id = ? AND table_id = ? AND proband_id = ? ORDER BY row_id"
        )
        neighbors = (
            safe_select(
                database, neighbor_sql, [anchor["document_id"], anchor["table_id"], anchor["proband_id"]]
            )
            if anchor["proband_id"]
            else [anchor]
        )
        for row in neighbors:
            if gene and row["gene_id"] and row["gene_id"] != gene:
                continue
            identity = f"{row['document_id']}:{row['table_id']}:{row['row_id']}"
            evidence_id = "table:" + hashlib.sha256(identity.encode()).hexdigest()[:20]
            direction = (
                "matched"
                if row["row_id"] == anchor["row_id"]
                else ("upstream" if row["row_id"] < anchor["row_id"] else "downstream")
            )
            if evidence_id not in evidence:
                evidence[evidence_id] = {
                    **row,
                    "raw_cells": json.loads(row["raw_cells"]),
                    "evidence_id": evidence_id,
                    "query_variant": query,
                    "retrieval_links": [],
                    "match_validation": "exact_allele"
                    if variant_match(row["variant_text"], query, transcript)
                    and context_verified(row, query, transcript)
                    else "allele_context_unresolved"
                    if variant_match(row["variant_text"], query, transcript)
                    else "same_proband_context",
                    "query_id": hashlib.sha256((sql + neighbor_sql + query).encode()).hexdigest()[:16],
                    "executed_sql": [sql, neighbor_sql],
                    "phase_supported": row["phase"] == "trans" and bool(row["phase_method"]),
                }
            evidence[evidence_id]["retrieval_links"].append(
                {"anchor_row_id": anchor["row_id"], "direction": direction}
            )
    return sorted(evidence.values(), key=lambda r: (r["document_id"], r["table_id"], r["row_id"]))
