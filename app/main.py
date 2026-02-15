"""Main ingestion entrypoints."""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from app.db import init_schema, insert_job_document
from app.ocr_service import MalformedPDFError, OCRProviderError, extract_document


def submit(job_id: int, payload: bytes, conn: sqlite3.Connection) -> dict[str, Any]:
    """Ingest an uploaded PDF using OCR provider and persist normalized output."""
    init_schema(conn)
    provider = os.getenv("OCR_PROVIDER", "aws_textract")

    try:
        document = extract_document(payload)
    except MalformedPDFError as exc:
        message = f"Malformed PDF: {exc}"
        insert_job_document(
            conn,
            job_id=job_id,
            provider=provider,
            status="failed",
            document=None,
            error_message=message,
        )
        return {"status": "error", "error": message}
    except OCRProviderError as exc:
        message = f"OCR provider failed: {exc}"
        insert_job_document(
            conn,
            job_id=job_id,
            provider=provider,
            status="failed",
            document=None,
            error_message=message,
        )
        return {"status": "error", "error": message}

    doc_id = insert_job_document(
        conn,
        job_id=job_id,
        provider=provider,
        status="completed",
        document=document.to_dict(),
    )
    return {
        "status": "ok",
        "job_id": job_id,
        "job_document_id": doc_id,
        "pages": len(document.pages),
    }
