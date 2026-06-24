import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_build_sh_auto_blocks_indeed():
    result = subprocess.run(
        ["bash", "build/build.sh", "auto"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "INDEED IS NOT SUPPORTED IN DOCKER" in result.stdout


def test_build_sh_syntax():
    result = subprocess.run(
        ["bash", "-n", "build/build.sh"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_attach_common_sh_exists():
    path = ROOT / "maintance/lib/attach_common.sh"
    assert path.is_file(), "maintance/lib/attach_common.sh must be in repo (not gitignored)"


def test_scraper_attach_empty_pass_args():
    """Empty PASS_ARGS with set -u must not raise unbound variable (macOS bash)."""
    result = subprocess.run(
        ["bash", "maintance/run_scraper_attach.sh", "--board", "indeed", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Usage" in result.stdout + result.stderr
