from modules.get_cookies import normalize_indeed_cookies


def test_normalize_indeed_cookies_filters_and_sets_domain():
    raw = [
        {"name": "a", "domain": "www.indeed.com", "value": "1"},
        {"name": "b", "domain": "google.com", "value": "2"},
        {"name": "c", "domain": ".indeed.com", "value": "3"},
    ]
    out = normalize_indeed_cookies(raw)
    assert len(out) == 2
    assert all(c["domain"] == ".indeed.com" for c in out)
    assert {c["name"] for c in out} == {"a", "c"}
