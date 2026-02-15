from typing import Any

from pydantic import BaseModel, HttpUrl


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class SubmitUrlRequest(BaseModel):
    pdf_url: HttpUrl


class ResultRecord(BaseModel):
    job_id: str
    compound_label: str | None
    canonical_smiles: str
    inchi_key: str
    metric: str
    value: float | None
    unit: str | None
    assay_type_raw: str | None
    assay_type_normalized: str | None
    experimental_context: dict[str, Any]
    source: dict[str, Any]
    confidence: dict[str, float]
    review: dict[str, Any]


class JobStatus(BaseModel):
    job_id: str
    filename: str
    status: str
    message: str | None
    created_at: str
    completed_at: str | None
