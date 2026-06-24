import pytest
from modules.job_report_api import app
from fastapi.testclient import TestClient
from modules.job_store import import_json_file


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_list_jobs_empty_db(client, db_path):
    resp = client.get("/api/jobs", params={"db": str(db_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert "rows_html" in data


def test_list_jobs_after_import(client, sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    resp = client.get("/api/jobs", params={"db": str(db_path), "board": "indeed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert "DevOps" in data["rows_html"] or "Platform" in data["rows_html"]


def test_scrape_jobs_not_found(client, tmp_path):
    resp = client.get("/api/scrapes/missing.json/jobs", params={"json_dir": str(tmp_path), "db": str(tmp_path / "x.db")},)
    assert resp.status_code == 404


def test_scrape_jobs_rejects_combined(client, tmp_path):
    resp = client.get("/api/scrapes/combined_run.json/jobs", params={"json_dir": str(tmp_path)},)
    assert resp.status_code == 400


def test_scrape_jobs_returns_html(client, sample_indeed_json, json_dir, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    resp = client.get(f"/api/scrapes/{sample_indeed_json.name}/jobs", params={"json_dir": str(json_dir), "db": str(db_path)},)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert "table_html" in data


def test_set_external_status(client, sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    resp = client.post("/api/jobs/by-external/indeed/abc123/status", json={"status": "applied"}, params={"db": str(db_path)},)
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


def test_set_external_status_invalid(client, db_path):
    resp = client.post("/api/jobs/by-external/indeed/nope/status", json={"status": "not_a_real_status"}, params={"db": str(db_path)},)
    assert resp.status_code == 400
