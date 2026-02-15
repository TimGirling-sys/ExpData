from datetime import datetime, timezone
import json
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.database import get_conn, init_db
from app.models import JobResponse, JobStatus, ResultRecord
from app.pipeline import extract_records, serialize_source
from app.frontend import HTML_PAGE

app = FastAPI(title="ExpData Patent Extraction MVP", version="0.1.0")
init_db()


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(content=HTML_PAGE)


@app.post("/submit", response_model=JobResponse)
async def submit(file: UploadFile = File(...)) -> JobResponse:
    filename = file.filename or "uploaded.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF input is supported.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    try:
        text = payload.decode("utf-8", errors="ignore")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=f"Unable to decode file: {exc}")

    job_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO jobs (id, filename, status, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (job_id, filename, "processing", "Job accepted", created),
    )

    compounds, observations = extract_records(text)

    compound_ids: dict[str, int] = {}
    for comp in compounds:
        cur.execute(
            """
            INSERT OR IGNORE INTO compounds (job_id, compound_label, canonical_smiles, inchi_key, confidence_smiles)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, comp.label, comp.smiles, comp.inchi_key, comp.confidence),
        )
        cur.execute(
            "SELECT id FROM compounds WHERE job_id = ? AND canonical_smiles = ?",
            (job_id, comp.smiles),
        )
        row = cur.fetchone()
        if row:
            compound_ids[comp.label or comp.smiles] = row["id"]

    for obs in observations:
        key = obs.compound_label or "C"
        compound_id = compound_ids.get(key)
        if compound_id is None:
            cur.execute(
                """
                INSERT INTO compounds (job_id, compound_label, canonical_smiles, inchi_key, confidence_smiles)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, obs.compound_label, "C", "UNKNOWN", 0.5),
            )
            compound_id = cur.lastrowid

        requires_review = int(obs.confidence_linking < 0.99 or obs.confidence_experimental < 0.99)
        review_reason = "below_99_precision_threshold" if requires_review else None

        cur.execute(
            """
            INSERT INTO observations (
                job_id, compound_id, metric, value, unit,
                assay_type_raw, assay_type_normalized,
                target, species, source_json,
                confidence_experimental, confidence_linking,
                requires_manual_review, review_reason, review_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                compound_id,
                obs.metric,
                obs.value,
                obs.unit,
                obs.assay_type_raw,
                obs.assay_type_normalized,
                obs.target,
                obs.species,
                serialize_source(obs.source),
                obs.confidence_experimental,
                obs.confidence_linking,
                requires_review,
                review_reason,
                "queued" if requires_review else "not_required",
            ),
        )

    completed = datetime.now(timezone.utc).isoformat()
    cur.execute(
        "UPDATE jobs SET status = ?, message = ?, completed_at = ? WHERE id = ?",
        ("completed", "Extraction completed", completed, job_id),
    )
    conn.commit()
    conn.close()

    return JobResponse(job_id=job_id, status="completed", message="Extraction completed")


@app.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    data = dict(row)
    data["job_id"] = data.pop("id")
    return JobStatus(**data)


@app.get("/results/{job_id}", response_model=list[ResultRecord])
def results(job_id: str) -> list[ResultRecord]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            c.compound_label,
            c.canonical_smiles,
            c.inchi_key,
            c.confidence_smiles,
            o.metric,
            o.value,
            o.unit,
            o.assay_type_raw,
            o.assay_type_normalized,
            o.target,
            o.species,
            o.source_json,
            o.confidence_experimental,
            o.confidence_linking,
            o.requires_manual_review,
            o.review_reason,
            o.review_status
        FROM observations o
        JOIN compounds c ON c.id = o.compound_id
        WHERE o.job_id = ?
        """,
        (job_id,),
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No results for job")

    output: list[ResultRecord] = []
    for row in rows:
        output.append(
            ResultRecord(
                job_id=job_id,
                compound_label=row["compound_label"],
                canonical_smiles=row["canonical_smiles"],
                inchi_key=row["inchi_key"],
                metric=row["metric"],
                value=row["value"],
                unit=row["unit"],
                assay_type_raw=row["assay_type_raw"],
                assay_type_normalized=row["assay_type_normalized"],
                experimental_context={"target": row["target"], "species": row["species"]},
                source=json.loads(row["source_json"]),
                confidence={
                    "smiles_extraction": row["confidence_smiles"],
                    "experimental_extraction": row["confidence_experimental"],
                    "linking": row["confidence_linking"],
                },
                review={
                    "requires_manual_review": bool(row["requires_manual_review"]),
                    "review_reason": row["review_reason"],
                    "status": row["review_status"],
                },
            )
        )
    return output
