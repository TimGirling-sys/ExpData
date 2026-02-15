"""Table extraction utilities for structured DocumentIR payloads."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


METRIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "IC50": ("ic50", "ic-50"),
    "EC50": ("ec50", "ec-50"),
    "Ki": ("ki",),
    "MIC": ("mic", "minimum inhibitory concentration"),
    "% inhibition": ("% inhibition", "percent inhibition", "%inh", "inhibition %"),
}

COMPOUND_HEADER_HINTS = (
    "compound",
    "cmpd",
    "ligand",
    "molecule",
    "id",
    "name",
)

UNIT_PATTERN = re.compile(r"(?:\(|\b)(n?m|µm|um|mm|pm|fg/ml|mg/ml|ug/ml|µg/ml|ng/ml|%)(?:\)|\b)", re.IGNORECASE)
VALUE_PATTERN = re.compile(
    r"(?P<comparator><=|>=|<|>|~|≈)?\s*(?P<number>[+-]?\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(?P<unit>n?m|µm|um|mm|pm|mg/ml|ug/ml|µg/ml|ng/ml|%|percent)?",
    re.IGNORECASE,
)
COMPOUND_PATTERN = re.compile(
    r"(CHEMBL\d+|CID[:\s-]*\d+|ZINC\d+|[A-Za-z]{1,5}-?\d{2,6}|compound\s+[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MetricColumn:
    index: int
    metric: str
    unit: str | None


def _cell_text(cell: Any) -> str:
    if isinstance(cell, dict):
        text = cell.get("text")
        return str(text).strip() if text is not None else ""
    return str(cell).strip() if cell is not None else ""


def _cell_coords(cell: Any, row_idx: int, col_idx: int) -> tuple[int, int]:
    if isinstance(cell, dict):
        row = cell.get("row_index", row_idx)
        col = cell.get("col_index", col_idx)
        return int(row), int(col)
    return row_idx, col_idx


def _normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    unit = unit.strip().lower().replace(" ", "")
    mapping = {
        "um": "µM",
        "µm": "µM",
        "nm": "nM",
        "mm": "mM",
        "pm": "pM",
        "%": "%",
        "percent": "%",
        "ug/ml": "µg/mL",
        "µg/ml": "µg/mL",
        "mg/ml": "mg/mL",
        "ng/ml": "ng/mL",
    }
    return mapping.get(unit, unit)


def _infer_unit_from_header(header: str) -> str | None:
    match = UNIT_PATTERN.search(header)
    return _normalize_unit(match.group(1)) if match else None


def _detect_metric_columns(header_row: list[Any]) -> list[MetricColumn]:
    metric_columns: list[MetricColumn] = []
    for idx, cell in enumerate(header_row):
        header = _cell_text(cell)
        lowered = header.lower()
        for canonical, aliases in METRIC_PATTERNS.items():
            if any(alias in lowered for alias in aliases):
                metric_columns.append(MetricColumn(index=idx, metric=canonical, unit=_infer_unit_from_header(header)))
                break
    return metric_columns


def _find_compound_column(header_row: list[Any]) -> int:
    for idx, cell in enumerate(header_row):
        header = _cell_text(cell).lower()
        if any(hint in header for hint in COMPOUND_HEADER_HINTS):
            return idx
    return 0


def _extract_compound_identifier(raw_label: str) -> str:
    label = raw_label.strip()
    if not label:
        return ""
    match = COMPOUND_PATTERN.search(label)
    if match:
        value = match.group(1)
        return re.sub(r"\s+", "", value.upper())
    return label


def _parse_numeric_value(raw: str, default_unit: str | None = None) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None

    match = VALUE_PATTERN.search(text)
    if not match:
        return None

    number_text = match.group("number").replace(",", "")
    try:
        value = float(number_text)
    except ValueError:
        return None

    comparator = match.group("comparator")
    unit = _normalize_unit(match.group("unit")) or default_unit
    return {
        "raw_value": text,
        "value": value,
        "value_normalized": value,
        "comparator": comparator,
        "unit": unit,
    }


def _iter_tables(document_ir: dict[str, Any]) -> list[dict[str, Any]]:
    tables = document_ir.get("tables") or document_ir.get("document", {}).get("tables") or []
    return [table for table in tables if isinstance(table, dict)]


def extract_table_observations(document_ir: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract metric observations from tables in a DocumentIR payload."""
    observations: list[dict[str, Any]] = []

    for table_index, table in enumerate(_iter_tables(document_ir)):
        rows = table.get("rows") or []
        if not rows:
            continue

        header = rows[0]
        metric_columns = _detect_metric_columns(header)
        if not metric_columns:
            continue

        compound_column = _find_compound_column(header)
        page_number = table.get("page_number")
        table_id = table.get("table_id", f"table_{table_index}")

        for row_idx, row in enumerate(rows[1:], start=1):
            if compound_column >= len(row):
                continue
            raw_label = _cell_text(row[compound_column])
            compound_id = _extract_compound_identifier(raw_label)
            if not compound_id:
                continue

            for metric_col in metric_columns:
                if metric_col.index >= len(row):
                    continue
                cell = row[metric_col.index]
                cell_text = _cell_text(cell)
                parsed_value = _parse_numeric_value(cell_text, metric_col.unit)
                if parsed_value is None:
                    continue
                coord_row, coord_col = _cell_coords(cell, row_idx, metric_col.index)
                observations.append(
                    {
                        "compound": compound_id,
                        "metric": metric_col.metric,
                        **parsed_value,
                        "source": "table",
                        "provenance": {
                            "page_number": page_number,
                            "table_id": table_id,
                            "cell": {"row": coord_row, "col": coord_col},
                        },
                    }
                )

    return observations
