import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_indeed_json(tmp_path):
    """Minimal Indeed scrape artifact."""
    data = {
        "metadata": {
            "board": "indeed",
            "scraped_at": "2026-06-24T12:00:00",
            "search_params": {"query": "devops engineer", "location": "Remote"},
            "total_jobs": 2,
        },
        "jobs": [
            {
                "job_id": "abc123",
                "title": "DevOps Engineer",
                "company": "Acme Inc",
                "location": "Remote",
                "url": "https://www.indeed.com/viewjob?jk=abc123",
            },
            {
                "job_id": "def456",
                "title": "Platform Engineer",
                "company": "Beta LLC",
                "location": "Remote",
                "url": "https://www.indeed.com/viewjob?jk=def456",
            },
        ],
    }
    path = tmp_path / "devops_engineer_20260624_120000.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def json_dir(sample_indeed_json, tmp_path):
    return tmp_path


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_jobs.db"
