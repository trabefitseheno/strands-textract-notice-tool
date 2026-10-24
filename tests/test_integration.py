"""Real AWS. Run: NOTICE_BUCKET=<bucket> AWS_PROFILE=<profile> pytest -m integration"""
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("NOTICE_BUCKET"), reason="NOTICE_BUCKET not set"),
]


def test_textract_reads_sample_image_and_pdf():
    from tools.read_notice_document import TextractReader

    r = TextractReader()
    img = r.read("samples/water_shutoff.png")
    assert img.ok and "12 May 2026" in img.text and img.confidence > 90
    pdf = r.read("samples/clinic_hours.pdf")
    assert pdf.ok and "17 October 2026" in pdf.text and pdf.page_count == 1


def test_agent_calls_tool_on_image_not_on_text():
    from agent.agent_with_tool import build

    a = build()
    a("Explain this notice: samples/water_shutoff.png")
    calls = [b["toolUse"]["name"] for m in a.messages for b in m["content"] if "toolUse" in b]
    assert calls == ["read_notice_document"]
    b = build()
    b("Explain this notice: Water will be shut off on 12 May 2026 from 8:00 AM to 2:00 PM.")
    assert not [1 for m in b.messages for x in m["content"] if "toolUse" in x]
