import json

from modules.job_store import (
    detect_board_from_json,
    external_id_for_job,
    get_db_board_counts,
    get_db_summary,
    import_all_json,
    import_json_file,
    init_db,
    normalize_company,
    normalize_title,
    search_db_jobs,
    set_application_by_external_id,
    upsert_jobs,
)


def test_normalize_company_strips_suffix():
    assert normalize_company("Acme Inc.") == normalize_company("Acme")


def test_normalize_title_strips_remote():
    assert "remote" not in normalize_title("Senior DevOps Engineer Remote")


def test_external_id_prefers_job_id():
    job = {"job_id": "jk123", "url": "https://example.com/job/1"}
    assert external_id_for_job(job) == "jk123"


def test_import_json_file_creates_jobs(sample_indeed_json, db_path):
    stats = import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    assert stats["new"] == 2
    assert stats.get("skipped") is not True

    summary = get_db_summary(db_path=db_path)
    assert summary["jobs"] == 2
    assert summary["companies"] == 2


def test_import_json_file_skips_duplicate_source(sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    again = import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    assert again.get("skipped") is True


def test_search_db_jobs_board_filter(sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    jobs, total = search_db_jobs(board="indeed", db_path=db_path)
    assert total == 2
    assert len(jobs) == 2

    jobs_dice, total_dice = search_db_jobs(board="dice", db_path=db_path)
    assert total_dice == 0
    assert jobs_dice == []


def test_search_db_jobs_text_query(sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    jobs, total = search_db_jobs(q="platform", db_path=db_path)
    assert total == 1
    assert "Platform" in jobs[0]["title"]


def test_import_all_json_skips_combined(sample_indeed_json, json_dir, db_path):
    combined = json_dir / "combined_run.json"
    combined.write_text(json.dumps({"jobs": [{"job_id": "x", "title": "T", "company": "C"}]}), encoding="utf-8")
    totals = import_all_json(json_dir=json_dir, db_path=db_path)
    assert totals["files"] == 1
    assert totals["new"] == 2


def test_detect_board_from_json_filename():
    path = __import__("pathlib").Path("dice_data_test.json")
    assert detect_board_from_json(path, {"jobs": []}) == "dice"


def test_board_counts(sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    counts = get_db_board_counts(db_path=db_path)
    assert counts.get("indeed") == 2


def test_set_application_by_external_id(sample_indeed_json, db_path):
    import_json_file(sample_indeed_json, board="indeed", db_path=db_path)
    ok = set_application_by_external_id("indeed", "abc123", "applied", db_path=db_path)
    assert ok is True
    jobs, total = search_db_jobs(status="applied", db_path=db_path)
    assert total == 1


def test_upsert_updates_seen_count(sample_indeed_json, db_path):
    init_db(db_path)
    jobs = json.loads(sample_indeed_json.read_text())["jobs"]
    upsert_jobs(jobs, board="indeed", json_source="run1.json", db_path=db_path)
    stats = upsert_jobs(jobs, board="indeed", json_source="run2.json", db_path=db_path)
    assert stats["updated"] >= 1
    summary = get_db_summary(db_path=db_path)
    assert summary["jobs"] == 2
