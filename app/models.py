"""Response models for extraction API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SourceProvenance(BaseModel):
    document_id: Optional[str] = None
    document_uri: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    table_figure_id: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    bbox: Optional[str] = None


class AssayOntology(BaseModel):
    assay_type_raw: Optional[str] = None
    assay_type_normalized: Optional[str] = None
    ontology_id: Optional[str] = Field(default=None, alias="assay_ontology_id")


class ReviewMetadata(BaseModel):
    state: str = "pending"
    reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    queue_state: Optional[str] = None
    queue_priority: Optional[int] = None
    queue_assigned_to: Optional[str] = None
    queue_resolution_note: Optional[str] = None


class ObservationResult(BaseModel):
    id: int
    job_id: str
    analyte: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    source: SourceProvenance
    assay: AssayOntology
    review: ReviewMetadata


class JobResultsResponse(BaseModel):
    job_id: str
    results: list[ObservationResult]
