import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from tools.read_notice_document import TextractReader, read_notice_document


def line(text, conf=99.0, page=1):
    return {"BlockType": "LINE", "Text": text, "Confidence": conf, "Page": page}


def reader(textract=None, s3=None, bucket="b"):
    return TextractReader(bucket=bucket, s3=s3 or MagicMock(), textract=textract or MagicMock(),
                          sleep=lambda s: None)


def err(code):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "op")


def test_image_s3_uri_ok():
    t = MagicMock()
    t.detect_document_text.return_value = {"Blocks": [line("A", 98), line("B", 96)]}
    r = reader(t).read("s3://b/k.png")
    assert r.ok and r.text == "A\nB" and r.confidence == 97.0 and r.page_count == 1
    assert not r.low_confidence


def test_local_file_is_uploaded(tmp_path):
    f = tmp_path / "n.png"
    f.write_bytes(b"x")
    s3, t = MagicMock(), MagicMock()
    t.detect_document_text.return_value = {"Blocks": [line("A")]}
    r = reader(t, s3).read(str(f))
    assert r.ok
    bucket, key = s3.upload_file.call_args[0][1:3]
    assert bucket == "b" and key.startswith("uploads/") and key.endswith(".png")
    assert s3.upload_file.call_args[1]["ExtraArgs"]["ServerSideEncryption"] == "AES256"


def test_low_confidence_flagged():
    t = MagicMock()
    t.detect_document_text.return_value = {"Blocks": [line("A", 50)]}
    r = reader(t).read("s3://b/k.jpg")
    assert r.ok and r.low_confidence and "check" in r.warning


@pytest.mark.parametrize("name,payload", [("x.docx", b"x"), ("missing.png", None)])
def test_bad_file(tmp_path, name, payload):
    p = tmp_path / name
    if payload:
        p.write_bytes(payload)
    r = reader().read(str(p))
    assert not r.ok and r.error


def test_no_bucket_for_local(tmp_path):
    f = tmp_path / "n.png"
    f.write_bytes(b"x")
    assert "NOTICE_BUCKET" in reader(bucket="").read(str(f)).error


def test_empty_text():
    t = MagicMock()
    t.detect_document_text.return_value = {"Blocks": []}
    assert reader(t).read("s3://b/k.png").error == "No text found in the document."


def test_unsupported_document():
    t = MagicMock()
    t.detect_document_text.side_effect = err("UnsupportedDocumentException")
    assert "cannot read" in reader(t).read("s3://b/k.png").error


def test_pdf_polls_and_paginates():
    t = MagicMock()
    t.start_document_text_detection.return_value = {"JobId": "j"}
    t.get_document_text_detection.side_effect = [
        {"JobStatus": "IN_PROGRESS"},
        {"JobStatus": "SUCCEEDED", "DocumentMetadata": {"Pages": 2}, "Blocks": [line("p1")], "NextToken": "n"},
        {"JobStatus": "SUCCEEDED", "DocumentMetadata": {"Pages": 2}, "Blocks": [line("p2", page=2)]},
    ]
    r = reader(t).read("s3://b/k.pdf")
    assert r.ok and r.page_count == 2 and r.text == "p1\np2"


def test_pdf_timeout(monkeypatch):
    monkeypatch.setattr("tools.read_notice_document.PDF_TIMEOUT_S", -1)
    t = MagicMock()
    t.start_document_text_detection.return_value = {"JobId": "j"}
    t.get_document_text_detection.return_value = {"JobStatus": "IN_PROGRESS"}
    assert "did not finish" in reader(t).read("s3://b/k.pdf").error


def test_pdf_failed_job():
    t = MagicMock()
    t.start_document_text_detection.return_value = {"JobId": "j"}
    t.get_document_text_detection.return_value = {"JobStatus": "FAILED", "StatusMessage": "bad pdf"}
    assert reader(t).read("s3://b/k.pdf").error == "bad pdf"


def test_tool_schema_and_json(monkeypatch):
    assert read_notice_document.tool_spec["name"] == "read_notice_document"
    assert "source" in read_notice_document.tool_spec["inputSchema"]["json"]["properties"]
    monkeypatch.setattr("tools.read_notice_document._reader", reader(MagicMock()))
    out = json.loads(read_notice_document("s3://b/k.xyz"))
    assert out["ok"] is False
