import time

from fastapi.testclient import TestClient
from variantrag.api import create_app


def wait(client, identity):
    for _ in range(100):
        response = client.get("/api/results/" + identity).json()
        if response["status"] in {"completed", "failed"}:
            return response
        time.sleep(0.05)
    raise AssertionError("Worker did not finish")


def test_demo_and_real_failure_states(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://localhost") as client:
        assert client.get("/api/health").json()["table_engine"] == "DuckDB"
        job = client.post("/api/demo").json()
        result = wait(client, job["run_id"])
        assert result["status"] == "completed", result
        assert len(result["result"]["ranked_variants"]) == 3
        assert client.get("/api/results/" + job["run_id"] + "/bundles").status_code == 200
        invalid = client.post("/api/run", files={"file": ("bad.vcf", b"not a vcf")}).json()
        assert wait(client, invalid["run_id"])["status"] == "failed"
        assert client.get("/api/results/not-a-uuid").status_code == 404
        assert client.post("/api/run", files={"file": ("empty.vcf", b"")}).status_code == 422


def test_local_boundary_rejects_host_origin_and_large_body(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://localhost") as client:
        assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400
        assert client.get("/api/runs", headers={"Origin": "https://attacker.example"}).status_code == 403
        assert client.post("/api/demo", headers={"Origin": "null"}).status_code == 403
        assert client.post("/api/run", headers={"Content-Length": str(43 * 1024**2)}).status_code == 413
        assert client.get("/api/health", headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200


def test_failed_upload_cleanup_and_run_deletion(tmp_path):
    with TestClient(create_app(tmp_path), base_url="http://localhost") as client:
        response = client.post("/api/run", files={"file": ("empty.vcf", b"")})
        assert response.status_code == 422
        assert not [p for p in tmp_path.iterdir() if p.is_dir()]
        job = client.post("/api/demo").json()
        assert wait(client, job["run_id"])["status"] == "completed"
        assert client.delete("/api/runs/" + job["run_id"]).status_code == 200
        assert client.get("/api/results/" + job["run_id"]).status_code == 404
        assert not (tmp_path / job["run_id"]).exists()


def test_retention_limit_does_not_leave_files(tmp_path, monkeypatch):
    monkeypatch.setenv("VARIANTRAG_MAX_RUNS", "0")
    with TestClient(create_app(tmp_path), base_url="http://localhost") as client:
        assert client.post("/api/demo").status_code == 429
        assert not [p for p in tmp_path.iterdir() if p.is_dir()]
