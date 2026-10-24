"""Strands tool: read a photo, scan or PDF of a public notice with Amazon Textract.

Plug-in pattern: ``Agent(tools=[read_notice_document])``. The docstring below is what the
model sees, so it states *when* to call the tool as well as what it returns.
"""

from __future__ import annotations

import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, Field
from strands import tool

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PDF_EXT = {".pdf"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # Textract sync limit
MAX_PDF_BYTES = 50 * 1024 * 1024
LOW_CONFIDENCE = float(os.environ.get("TEXTRACT_LOW_CONFIDENCE", "80"))
PDF_TIMEOUT_S = float(os.environ.get("TEXTRACT_TIMEOUT_S", "60"))


class NoticeDocument(BaseModel):
    """Result of reading a notice document. ``ok`` False means ``error`` explains why."""

    ok: bool
    text: str = ""
    confidence: Optional[float] = Field(None, description="Mean line confidence, 0-100")
    page_count: int = 0
    low_confidence: bool = False
    warning: Optional[str] = None
    error: Optional[str] = None


def _fail(msg: str) -> NoticeDocument:
    return NoticeDocument(ok=False, error=msg)


class TextractReader:
    """Uploads (if needed) and runs Textract. Clients are injectable for tests."""

    def __init__(self, bucket: str | None = None, s3=None, textract=None, sleep=time.sleep):
        self.bucket = bucket or os.environ.get("NOTICE_BUCKET", "")
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        self.s3 = s3 or boto3.client("s3", region_name=region)
        self.textract = textract or boto3.client("textract", region_name=region)
        self._sleep = sleep

    def _resolve(self, source: str) -> tuple[str, str, str]:
        """Return (bucket, key, extension), uploading a local file first."""
        if source.startswith("s3://"):
            bucket, _, key = source[5:].partition("/")
            if not bucket or not key:
                raise ValueError(f"Malformed S3 URI: {source}")
            return bucket, key, Path(key).suffix.lower()
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"No such file: {source}")
        ext = path.suffix.lower()
        if ext not in IMAGE_EXT | PDF_EXT:
            raise ValueError(f"Unsupported file type '{ext}'. Use PNG, JPG, TIFF or PDF.")
        limit = MAX_PDF_BYTES if ext in PDF_EXT else MAX_IMAGE_BYTES
        if path.stat().st_size > limit:
            raise ValueError(f"File too large ({path.stat().st_size} bytes; limit {limit}).")
        if not self.bucket:
            raise ValueError("NOTICE_BUCKET is not set; cannot upload local files.")
        key = f"uploads/{uuid.uuid4().hex}{ext}"
        self.s3.upload_file(
            str(path), self.bucket, key,
            ExtraArgs={"ContentType": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                       "ServerSideEncryption": "AES256"},
        )
        return self.bucket, key, ext

    def read(self, source: str) -> NoticeDocument:
        try:
            bucket, key, ext = self._resolve(source)
            if ext in PDF_EXT:
                blocks, pages = self._read_pdf(bucket, key)
            elif ext in IMAGE_EXT:
                resp = self.textract.detect_document_text(
                    Document={"S3Object": {"Bucket": bucket, "Name": key}})
                blocks, pages = resp.get("Blocks", []), 1
            else:
                return _fail(f"Unsupported file type '{ext}'. Use PNG, JPG, TIFF or PDF.")
        except (ValueError, FileNotFoundError) as e:
            return _fail(str(e))
        except TimeoutError as e:
            return _fail(str(e))
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "ClientError")
            hint = {"UnsupportedDocumentException": "Textract cannot read this file (corrupt or unsupported).",
                    "InvalidS3ObjectException": "Textract cannot access that S3 object.",
                    "AccessDeniedException": "Access denied calling Textract/S3.",
                    "ProvisionedThroughputExceededException": "Textract is throttling; retry shortly."}
            return _fail(hint.get(code, f"AWS error {code}."))
        except BotoCoreError as e:
            return _fail(f"AWS connection problem: {type(e).__name__}")
        return self._summarise(blocks, pages)

    def _read_pdf(self, bucket: str, key: str) -> tuple[list[dict[str, Any]], int]:
        job = self.textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}})["JobId"]
        deadline = time.monotonic() + PDF_TIMEOUT_S
        blocks: list[dict[str, Any]] = []
        pages, token = 0, None
        while True:
            kwargs = {"JobId": job, **({"NextToken": token} if token else {})}
            resp = self.textract.get_document_text_detection(**kwargs)
            status = resp.get("JobStatus")
            if status == "FAILED":
                raise ValueError(resp.get("StatusMessage") or "Textract could not process this PDF.")
            if status == "IN_PROGRESS":
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Textract did not finish within {PDF_TIMEOUT_S:.0f}s.")
                self._sleep(2)
                continue
            blocks += resp.get("Blocks", [])
            pages = max(pages, resp.get("DocumentMetadata", {}).get("Pages", 0))
            token = resp.get("NextToken")
            if not token:
                return blocks, pages

    @staticmethod
    def _summarise(blocks: list[dict[str, Any]], pages: int) -> NoticeDocument:
        lines = [b for b in blocks if b.get("BlockType") == "LINE"]
        if not lines:
            return _fail("No text found in the document.")
        lines.sort(key=lambda b: (b.get("Page", 1)))  # stable: keeps reading order within a page
        text = "\n".join(b["Text"] for b in lines)
        conf = round(sum(b.get("Confidence", 0.0) for b in lines) / len(lines), 1)
        low = conf < LOW_CONFIDENCE
        return NoticeDocument(
            ok=True, text=text, confidence=conf, page_count=pages or 1, low_confidence=low,
            warning=(f"Mean OCR confidence {conf} is below {LOW_CONFIDENCE:.0f}. Figures such as dates "
                     "and amounts may be misread; tell the user to check them against the original.")
            if low else None,
        )


_reader: TextractReader | None = None


def read_document(source: str, reader: TextractReader | None = None) -> NoticeDocument:
    """Read ``source``; builds the default AWS-backed reader lazily (so imports need no credentials)."""
    global _reader
    if reader is None:
        _reader = _reader or TextractReader()
        reader = _reader
    return reader.read(source)


@tool
def read_notice_document(source: str) -> str:
    """Extract the text of a notice that was given as a photo, scan or PDF (not as plain text).

    Call this FIRST whenever the user's input is a file path or s3:// URI ending in .png, .jpg,
    .jpeg, .tif, .tiff or .pdf. Do NOT call it when the notice text is already in the message.

    Args:
        source: Local file path or s3://bucket/key URI of the image or PDF.

    Returns:
        JSON with ok, text, confidence (0-100), page_count, low_confidence, warning, error.
        If ok is false, tell the user the error; do not invent the notice text. If
        low_confidence is true, rewrite what was read but warn that figures need checking.
    """
    return read_document(source).model_dump_json()


__all__ = ["read_notice_document", "TextractReader", "NoticeDocument", "read_document"]
