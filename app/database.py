"""Database schema and helpers for extraction results."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "expdata.db"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    analyte TEXT,
    value TEXT,
    unit TEXT,

    -- OCR source references
    source_document_id TEXT,
    source_document_uri TEXT,
    source_page INTEGER,

    -- source granularity
    source_section TEXT,
    source_table_figure_id TEXT,
    source_char_start INTEGER,
    source_char_end INTEGER,
    source_bbox TEXT,

    -- assay ontology
    assay_type_raw TEXT,
    assay_type_normalized TEXT,
    assay_ontology_id TEXT,

    -- review metadata
    review_state TEXT NOT NULL DEFAULT 'pending',
    review_reason TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS observation_review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,
    queue_state TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 0,
    assigned_to TEXT,
    queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT,
    resolution_note TEXT,
    FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_observations_job_id ON observations(job_id);
CREATE INDEX IF NOT EXISTS idx_observations_review_state ON observations(review_state);
CREATE INDEX IF NOT EXISTS idx_review_queue_state ON observation_review_queue(queue_state);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)


def fetch_observations_by_job(job_id: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                o.id,
                o.job_id,
                o.analyte,
                o.value,
                o.unit,
                o.source_document_id,
                o.source_document_uri,
                o.source_page,
                o.source_section,
                o.source_table_figure_id,
                o.source_char_start,
                o.source_char_end,
                o.source_bbox,
                o.assay_type_raw,
                o.assay_type_normalized,
                o.assay_ontology_id,
                o.review_state,
                o.review_reason,
                o.reviewed_by,
                o.reviewed_at,
                q.queue_state,
                q.priority,
                q.assigned_to,
                q.resolution_note
            FROM observations o
            LEFT JOIN observation_review_queue q ON q.observation_id = o.id
            WHERE o.job_id = ?
            ORDER BY o.id ASC
            """,
            (job_id,),
        ).fetchall()
