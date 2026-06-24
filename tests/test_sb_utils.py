import os

from modules.sb_utils import build_sb_options, running_in_docker, use_scraper_profile, use_scraper_uc


def test_running_in_docker_env():
    os.environ["RUNNING_IN_DOCKER"] = "1"
    try:
        assert running_in_docker() is True
        assert use_scraper_profile("dice") is False
        assert use_scraper_uc() is True
    finally:
        os.environ.pop("RUNNING_IN_DOCKER", None)


def test_build_sb_options_docker_flags(monkeypatch):
    monkeypatch.setenv("RUNNING_IN_DOCKER", "1")
    opts = build_sb_options(use_uc=True)
    assert "no-sandbox" in opts.get("chromium_arg", "")
