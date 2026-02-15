"""Persistence helpers for OCR traceability."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL,
            ocr_document_json TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def insert_job_document(
    conn: sqlite3.Connection,
    *,
    job_id: int,
    provider: str,
    status: str,
    document: dict[str, Any] | None,
    error_message: str | None = None,
) -> int:
    payload = json.dumps(document) if document is not None else None
    cursor = conn.execute(
        """
        INSERT INTO job_documents (job_id, provider, status, ocr_document_json, error_message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, provider, status, payload, error_message),
    )
    conn.commit()
    return int(cursor.lastrowid)
