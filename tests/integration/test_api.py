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
    with TestClient(create_app(tmp_path)) as client:
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
