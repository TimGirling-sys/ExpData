"""API entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.database import fetch_observations_by_job, init_db
from app.models import JobResultsResponse, ObservationResult

app = FastAPI(title="ExpData API")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/results/{job_id}", response_model=JobResultsResponse)
def get_results(job_id: str) -> JobResultsResponse:
    rows = fetch_observations_by_job(job_id)
    results = []
    for row in rows:
        results.append(
            ObservationResult(
                id=row["id"],
                job_id=row["job_id"],
                analyte=row["analyte"],
                value=row["value"],
                unit=row["unit"],
                source={
                    "document_id": row["source_document_id"],
                    "document_uri": row["source_document_uri"],
                    "page": row["source_page"],
                    "section": row["source_section"],
                    "table_figure_id": row["source_table_figure_id"],
                    "char_start": row["source_char_start"],
                    "char_end": row["source_char_end"],
                    "bbox": row["source_bbox"],
                },
                assay={
                    "assay_type_raw": row["assay_type_raw"],
                    "assay_type_normalized": row["assay_type_normalized"],
                    "assay_ontology_id": row["assay_ontology_id"],
                },
                review={
                    "state": row["review_state"] or "pending",
                    "reason": row["review_reason"],
                    "reviewed_by": row["reviewed_by"],
                    "reviewed_at": row["reviewed_at"],
                    "queue_state": row["queue_state"],
                    "queue_priority": row["priority"],
                    "queue_assigned_to": row["assigned_to"],
                    "queue_resolution_note": row["resolution_note"],
                },
            )
        )

    return JobResultsResponse(job_id=job_id, results=results)
