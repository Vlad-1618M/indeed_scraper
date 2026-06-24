from modules.job_titles_config import load_job_titles, parse_title_selection


def test_load_job_titles_from_repo_config():
    titles = load_job_titles()
    assert len(titles) >= 5
    assert "DevOps Engineer" in titles


def test_parse_title_selection_all():
    titles = ["A", "B", "C"]
    assert parse_title_selection("all", titles) == titles


def test_parse_title_selection_indices():
    titles = ["A", "B", "C", "D"]
    assert parse_title_selection("1,3", titles) == ["A", "C"]


def test_parse_title_selection_range():
    titles = ["A", "B", "C", "D"]
    assert parse_title_selection("1-2", titles) == ["A", "B"]


def test_parse_title_selection_custom_text():
    titles = ["A", "B"]
    assert parse_title_selection("Staff SDET Engineer", titles) == ["Staff SDET Engineer"]
