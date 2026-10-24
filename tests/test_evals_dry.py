"""The dry-mode eval is itself a regression test: tool used on files, never on plain text."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dry_eval_passes(tmp_path):
    out = tmp_path / "r.json"
    p = subprocess.run([sys.executable, "-m", "evals.run_evals", "--mode", "dry", "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    rows = {r["id"]: r for r in json.loads(out.read_text())}
    for case in ("image_clean", "image_photo", "pdf"):
        assert rows[case]["with_tool"]["calls"] == ["read_notice_document"]
        assert rows[case]["baseline"]["calls"] == []
        assert rows[case]["baseline"]["verdict"].startswith("FAIL")
    assert rows["plain_text"]["with_tool"]["calls"] == []  # must NOT call the tool on text
