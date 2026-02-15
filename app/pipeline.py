"""Observation extraction pipeline."""

from __future__ import annotations

from typing import Any

from app.table_extractor import extract_table_observations


def _source_key(observation: dict[str, Any]) -> str:
    provenance = observation.get("provenance") or {}
    source = observation.get("source")
    page = provenance.get("page_number")
    table_id = provenance.get("table_id")
    cell = provenance.get("cell")
    if isinstance(cell, dict):
        cell_key = f"{cell.get('row')}:{cell.get('col')}"
    else:
        cell_key = str(cell)
    return f"{source}|{page}|{table_id}|{cell_key}"


def _dedup_key(observation: dict[str, Any]) -> tuple[Any, Any, Any, str]:
    return (
        observation.get("compound"),
        observation.get("metric"),
        observation.get("value_normalized", observation.get("value")),
        _source_key(observation),
    )


def deduplicate_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, Any, Any, str], dict[str, Any]] = {}
    for obs in observations:
        unique[_dedup_key(obs)] = obs
    return list(unique.values())


def extract_text_observations(document_ir: dict[str, Any]) -> list[dict[str, Any]]:
    """Return text-derived observations from DocumentIR.

    Expected location is `document_ir["text_observations"]`.
    """
    text_observations = document_ir.get("text_observations") or []
    return [obs for obs in text_observations if isinstance(obs, dict)]


def run_pipeline(document_ir: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract and merge observations from text and tables."""
    text_observations = extract_text_observations(document_ir)
    table_observations = extract_table_observations(document_ir)
    return deduplicate_observations(text_observations + table_observations)
