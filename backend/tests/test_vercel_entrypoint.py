import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


# Remove o atalho da instalacao editavel (pip -e), que ja expoe os pacotes.
PROBE = """
import sys
sys.meta_path = [f for f in sys.meta_path if "editable" not in repr(f).lower()]
sys.path = [p for p in sys.path if p != %r]
import index
print(index.app.title)
""" % str(BACKEND)


def test_entrypoint_imports_with_only_api_dir_on_path():
    """A Vercel pode carregar api/index.py sem a raiz do backend no sys.path."""
    env = {**os.environ, "PYTHONPATH": ""}
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=BACKEND / "api",
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "my-finance-bot API" in result.stdout
