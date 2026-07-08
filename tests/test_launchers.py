import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_unix_launcher_does_not_bootstrap_dependencies(tmp_path):
    launcher = tmp_path / "run.sh"
    shutil.copy2(ROOT / "run.sh", launcher)
    launcher.chmod(0o755)

    result = subprocess.run(
        [str(launcher), "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert not (tmp_path / ".venv").exists()
    assert "does not create environments or install packages" in result.stderr


def test_launchers_do_not_invoke_package_installers():
    forbidden_tokens = (
        "-m pip",
        "pip install",
        "-m venv",
        "-m virtualenv",
    )

    for script_name in ("run.sh", "run.bat"):
        script = (ROOT / script_name).read_text(encoding="utf-8").lower()

        for token in forbidden_tokens:
            assert token not in script

    assert os.access(ROOT / "run.sh", os.X_OK)
