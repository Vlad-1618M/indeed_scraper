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
