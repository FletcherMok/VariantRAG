"""Local workbench API. SQLite stores job state only; all case-table analytics use DuckDB."""

import json
import os
import shutil
import sqlite3
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.staticfiles import StaticFiles

from .pipeline import run_pipeline
from .security import ALLOWED_ORIGINS, LocalBoundary

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MAX_UPLOAD = 20 * 1024 * 1024


def create_app(data_dir=None):
    data = Path(
        data_dir or os.environ.get("VARIANTRAG_DATA", Path.cwd() / "backend" / "data" / "workbench")
    ).resolve()
    data.mkdir(parents=True, exist_ok=True)
    database = data / "jobs.sqlite"
    executor = ThreadPoolExecutor(max_workers=1)
    admission = Lock()
    max_runs = int(os.environ.get("VARIANTRAG_MAX_RUNS", "100"))
    with sqlite3.connect(database) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT, created TEXT, mode TEXT, error TEXT)"
        )

    def update(identity, status, error=None):
        with sqlite3.connect(database) as db:
            db.execute("UPDATE jobs SET status=?,error=? WHERE id=?", (status, error, identity))

    @asynccontextmanager
    async def lifespan(app):
        with sqlite3.connect(database) as db:
            db.execute(
                "UPDATE jobs SET status='failed',error='Worker interrupted; rerun with preserved input' WHERE status IN ('queued','running')"
            )
        yield
        executor.shutdown(wait=True)

    app = FastAPI(title="VariantRAG", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    app.add_middleware(LocalBoundary)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    def get_job(identity):
        try:
            uuid.UUID(identity)
        except ValueError:
            raise HTTPException(404, "Run not found") from None
        with sqlite3.connect(database) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
        if not row:
            raise HTTPException(404, "Run not found")
        return dict(row)

    def worker(identity, vcf, build, sample, literature, mode, medcpt=None):
        folder = data / identity
        update(identity, "running")
        try:
            run_pipeline(
                vcf, folder / "output", build, sample, literature, mode, run_id=identity, medcpt=medcpt
            )
            update(identity, "completed")
        except Exception as exc:
            (folder / "error.log").write_text(traceback.format_exc())
            update(identity, "failed", str(exc))

    def submit(identity, vcf, build, sample, literature, mode, medcpt=None):
        with admission:
            with sqlite3.connect(database) as db:
                total = db.execute("SELECT count(*) FROM jobs").fetchone()[0]
                if total >= max_runs:
                    raise HTTPException(429, "Run storage limit reached; delete old runs before submitting")
                if shutil.disk_usage(data).free < 512 * 1024**2:
                    raise HTTPException(507, "Less than 512 MiB free disk; clear old runs or caches")
                active = db.execute(
                    "SELECT count(*) FROM jobs WHERE status IN ('queued','running')"
                ).fetchone()[0]
                if active >= 8:
                    raise HTTPException(429, "Local queue is full; wait for existing runs")
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?,NULL)",
                    (identity, "queued", datetime.now(timezone.utc).isoformat(), mode),
                )
            executor.submit(worker, identity, vcf, build, sample, literature, mode, medcpt)
        return {"run_id": identity, "status": "queued"}

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "version": "0.2.0",
            "table_engine": "DuckDB",
            "worker": "local Python",
            "ranking": "evidence availability baseline",
        }

    @app.get("/api/runs")
    def runs():
        with sqlite3.connect(database) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 100")]

    @app.post("/api/demo")
    def demo():
        identity = str(uuid.uuid4())
        (data / identity).mkdir()
        try:
            return submit(
                identity,
                FIXTURES / "demo.vcf",
                "GRCh38",
                None,
                FIXTURES / "demo_literature.json",
                "demo",
            )
        except Exception:
            shutil.rmtree(data / identity)
            raise

    @app.post("/api/run")
    async def upload(
        file: UploadFile = File(...),
        genome_build: str = Form("GRCh38"),
        sample: str = Form(""),
        retrieval_mode: str = Form("exact"),
        literature: UploadFile | None = File(None),
    ):
        if genome_build not in {"GRCh37", "GRCh38"}:
            raise HTTPException(422, "Invalid genome build")
        if retrieval_mode not in {"exact", "medcpt"}:
            raise HTTPException(422, "Unknown retrieval mode")
        models = Path(os.environ.get("VARIANTRAG_MEDCPT", Path.cwd() / "backend/data/models/medcpt"))
        if retrieval_mode == "medcpt" and (
            not literature
            or not (models / "query/model.safetensors").is_file()
            or not (models / "article/model.safetensors").is_file()
        ):
            raise HTTPException(
                422, "MedCPT requires a literature corpus and model setup; see docs/WALKTHROUGH.md"
            )
        name = file.filename or ""
        if not name.endswith((".vcf", ".vcf.gz")):
            raise HTTPException(422, "Upload a .vcf or .vcf.gz file")
        identity = str(uuid.uuid4())
        folder = data / identity
        folder.mkdir()
        path = folder / ("input.vcf.gz" if name.endswith(".gz") else "input.vcf")
        size = 0
        try:
            with path.open("wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, "Upload limit is 20 MiB")
                    stream.write(chunk)
            if size == 0:
                raise HTTPException(422, "File is empty")
            literature_path = None
            if literature:
                content = await literature.read(MAX_UPLOAD + 1)
                if len(content) > MAX_UPLOAD:
                    raise HTTPException(413, "Literature JSON exceeds 20 MiB")
                try:
                    corpus = json.loads(content)
                    if (
                        not isinstance(corpus, dict)
                        or not isinstance(corpus.get("tables", []), list)
                        or not isinstance(corpus.get("passages", []), list)
                    ):
                        raise ValueError("Expected a literature corpus object")
                except (ValueError, UnicodeDecodeError) as exc:
                    raise HTTPException(422, "Invalid literature corpus JSON") from exc
                literature_path = folder / "literature.json"
                literature_path.write_bytes(content)
            return submit(
                identity,
                path,
                genome_build,
                sample or None,
                literature_path,
                "research",
                models if retrieval_mode == "medcpt" else None,
            )
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            await file.close()
            if literature:
                await literature.close()

    @app.get("/api/results/{identity}")
    def result(identity: str):
        job = get_job(identity)
        if job["status"] == "completed":
            job["result"] = json.loads((data / identity / "output/ranking.json").read_text())
        return job

    @app.get("/api/results/{identity}/bundles")
    def bundles(identity: str):
        job = get_job(identity)
        if job["status"] != "completed":
            raise HTTPException(409, "Results are not complete")
        return json.loads((data / identity / "output/EvidenceBundle.json").read_text())

    @app.delete("/api/runs/{identity}")
    def delete_run(identity: str):
        with admission:
            job = get_job(identity)
            if job["status"] in {"queued", "running"}:
                raise HTTPException(409, "Wait for this run to finish before deleting")
            shutil.rmtree(data / identity, ignore_errors=True)
            with sqlite3.connect(database) as db:
                db.execute("DELETE FROM jobs WHERE id=?", (identity,))
        return {"deleted": identity}

    ui = Path(os.environ.get("VARIANTRAG_UI", Path.cwd() / "frontend/out"))
    if (ui / "index.html").is_file():
        app.mount("/", StaticFiles(directory=ui, html=True), name="workbench")
    return app


app = create_app()
