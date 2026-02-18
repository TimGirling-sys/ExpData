import os
import sqlite3
from pathlib import Path


VOLUME_TMP_DB = Path('/tmp/expdata.db')
LOCAL_DB = Path('expdata.db')


def _running_on_vercel() -> bool:
    return bool(
        os.getenv('VERCEL')
        or os.getenv('VERCEL_ENV')
        or os.getenv('NOW_REGION')
    )


def _db_path() -> Path:
    # Serverless runtimes should use /tmp for writable storage.
    if _running_on_vercel():
        return VOLUME_TMP_DB
    return LOCAL_DB


DB_PATH = _db_path()


def get_conn() -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(DB_PATH)
    except sqlite3.OperationalError:
        # Fallback for read-only deployment filesystems.
        conn = sqlite3.connect(VOLUME_TMP_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS compounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            compound_label TEXT,
            canonical_smiles TEXT NOT NULL,
            inchi_key TEXT NOT NULL,
            confidence_smiles REAL NOT NULL,
            UNIQUE(job_id, canonical_smiles),
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            compound_id INTEGER NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            unit TEXT,
            assay_type_raw TEXT,
            assay_type_normalized TEXT,
            target TEXT,
            species TEXT,
            source_json TEXT NOT NULL,
            confidence_experimental REAL NOT NULL,
            confidence_linking REAL NOT NULL,
            requires_manual_review INTEGER NOT NULL,
            review_reason TEXT,
            review_status TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id),
            FOREIGN KEY(compound_id) REFERENCES compounds(id)
        )
        """
    )
    conn.commit()
    conn.close()
