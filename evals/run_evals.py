"""Run the same inputs through the baseline agent and the agent with the Textract tool.

  python -m evals.run_evals --mode dry     # no AWS: scripted model + fake Textract (wiring check)
  python -m evals.run_evals --mode live    # real Bedrock + Textract (needs NOTICE_BUCKET, credentials)

Checks per case: (1) tool called iff a file was given, (2) key facts survive, (3) bad input
is reported rather than invented.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from samples.make_samples import NOTICES  # noqa: E402
from tools import read_notice_document as tool_mod  # noqa: E402

S = Path("samples")  # relative: the evals run from the repo root
CASES = [
    {"id": "image_clean", "input": f"Explain this notice: {S/'water_shutoff.png'}", "file": True,
     "facts": ["12 May 2026", "8:00 AM", "2:00 PM"], "notice": "water_shutoff", "conf": 98.5},
    {"id": "image_photo", "input": f"What do I need to do? {S/'permit_deadline.png'}", "file": True,
     "facts": ["30 June 2026", "$85.00", "$20.00"], "notice": "permit_deadline", "conf": 84.0},
    {"id": "pdf", "input": f"Summarise this: {S/'clinic_hours.pdf'}", "file": True,
     "facts": ["17 October 2026", "9:00 AM", "65"], "notice": "clinic_hours", "conf": 99.0},
    {"id": "plain_text", "input": "Explain this notice:\n" + (ROOT / S / "plain_text.txt").read_text(),
     "file": False, "facts": ["12 May 2026", "8:00 AM", "2:00 PM"]},
    {"id": "bad_file", "input": "Explain this notice: {tmp}/notice.docx", "file": True,
     "facts": [], "expect_error": True},
]


class FakeAWS:
    """Stands in for S3 + Textract: 'uploads' a sample and returns its known text."""

    def __init__(self):
        self.by_key: dict[str, dict] = {}

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        stem = Path(path).stem
        self.by_key[key] = {"stem": stem}

    def _blocks(self, key):
        case = next(c for c in CASES if c.get("notice") == self.by_key[key]["stem"])
        return [{"BlockType": "LINE", "Text": t, "Confidence": case["conf"], "Page": 1}
                for t in NOTICES[case["notice"]] if t]

    def detect_document_text(self, Document):
        return {"Blocks": self._blocks(Document["S3Object"]["Name"])}

    def start_document_text_detection(self, DocumentLocation):
        return {"JobId": DocumentLocation["S3Object"]["Name"]}

    def get_document_text_detection(self, JobId, NextToken=None):
        return {"JobStatus": "SUCCEEDED", "DocumentMetadata": {"Pages": 1}, "Blocks": self._blocks(JobId)}


_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_US_DATE = re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})\b")


_MONTH_RE = re.compile(_MONTHS)


def normalise(text: str) -> str:
    """Accept 'May 12, 2026' for '12 May 2026'; drop markdown bold and NBSPs."""
    text = text.replace("\u00a0", " ").replace("**", "")
    return _US_DATE.sub(r"\2 \1 \3", text)


def tool_calls(agent) -> list[str]:
    return [b["toolUse"]["name"] for m in agent.messages for b in m["content"] if "toolUse" in b]


def final_text(agent) -> str:
    return " ".join(b["text"] for b in agent.messages[-1]["content"] if "text" in b)


def run_case(build, case, tmp) -> dict:
    prompt = case["input"].replace("{tmp}", tmp)
    agent = build()
    try:
        agent(prompt)
        out, calls, err = final_text(agent), tool_calls(agent), None
    except Exception as e:  # noqa: BLE001 - report, don't crash the table
        out, calls, err = "", [], f"{type(e).__name__}: {e}"[:120]
    norm = normalise(re.sub(r"<thinking>.*?</thinking>", "", out, flags=re.S))
    facts_ok = bool(case["facts"]) and all(f in norm for f in case["facts"])
    admitted = any(w in out.lower() for w in ("can't", "cannot", "couldn't", "unable", "please paste", "please send", "not supported",
                                 "unsupported", "sorry", "supported format", "could you please"))
    return {"calls": calls, "facts_ok": facts_ok, "admitted": admitted, "error": err, "output": out}


def verdict(case, r, with_tool: bool) -> str:
    if r["error"]:
        return "ERROR"
    called = "read_notice_document" in r["calls"]
    if called != (case["file"] and with_tool):
        return "FAIL (tool use)"
    if case.get("expect_error"):
        return "PASS (reported error)" if r["admitted"] and not _MONTH_RE.search(r["output"]) else "FAIL (invented)"
    if case["file"] and not with_tool:
        return "FAIL (cannot read)" if not r["facts_ok"] else "FAIL"
    return "PASS" if r["facts_ok"] else "FAIL (facts lost)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dry", "live"], default="dry")
    ap.add_argument("--out", default=str(ROOT / "evals" / "results.json"))
    a = ap.parse_args()
    os.chdir(ROOT)

    from agent import agent_with_tool, baseline

    if a.mode == "dry":
        from strands import Agent

        from agent.common import SYSTEM_PROMPT
        from evals.dry_model import DryRunModel

        fake = FakeAWS()
        tool_mod._reader = tool_mod.TextractReader(bucket="dry-bucket", s3=fake, textract=fake)
        baseline_build = lambda: Agent(model=DryRunModel(), system_prompt=SYSTEM_PROMPT, callback_handler=None)  # noqa: E731
        tool_build = lambda: Agent(model=DryRunModel(), system_prompt=SYSTEM_PROMPT,  # noqa: E731
                                   tools=[tool_mod.read_notice_document], callback_handler=None)
    else:
        baseline_build, tool_build = baseline.build, agent_with_tool.build

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "notice.docx").write_bytes(b"not a supported type")
        for c in CASES:
            b, t = run_case(baseline_build, c, tmp), run_case(tool_build, c, tmp)
            rows.append({"id": c["id"], "baseline": {**b, "verdict": verdict(c, b, False)},
                         "with_tool": {**t, "verdict": verdict(c, t, True)}})

    print(f"mode={a.mode}" + ("  (scripted model: checks wiring, not model judgement)" if a.mode == "dry" else ""))
    print(f"{'case':<13}| {'BEFORE (baseline)':<22}| {'AFTER (with tool)':<24}| tool calls (after)")
    print("-" * 80)
    for r in rows:
        print(f"{r['id']:<13}| {r['baseline']['verdict']:<22}| {r['with_tool']['verdict']:<24}| "
              f"{', '.join(r['with_tool']['calls']) or '-'}")
    Path(a.out).write_text(json.dumps(rows, indent=2))
    ok = all(r["with_tool"]["verdict"].startswith("PASS") for r in rows)
    print("\nAFTER all pass:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
