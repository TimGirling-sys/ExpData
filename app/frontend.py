"""Simple frontend rendering for job results."""

from __future__ import annotations

from html import escape
from typing import Any


def _fmt(value: Any) -> str:
    return "" if value is None else escape(str(value))


def render_results_table(payload: dict[str, Any]) -> str:
    rows = payload.get("results", [])
    table_rows = []

    for row in rows:
        source = row.get("source", {})
        review = row.get("review", {})
        provenance = (
            f"doc={_fmt(source.get('document_id'))}; "
            f"page={_fmt(source.get('page'))}; "
            f"section={_fmt(source.get('section'))}; "
            f"table/figure={_fmt(source.get('table_figure_id'))}; "
            f"chars={_fmt(source.get('char_start'))}-{_fmt(source.get('char_end'))}; "
            f"bbox={_fmt(source.get('bbox'))}"
        )
        review_summary = (
            f"state={_fmt(review.get('state'))}; "
            f"reason={_fmt(review.get('reason'))}; "
            f"queue={_fmt(review.get('queue_state'))}; "
            f"assigned_to={_fmt(review.get('queue_assigned_to'))}"
        )

        table_rows.append(
            "<tr>"
            f"<td>{_fmt(row.get('id'))}</td>"
            f"<td>{_fmt(row.get('analyte'))}</td>"
            f"<td>{_fmt(row.get('value'))}</td>"
            f"<td>{_fmt(row.get('unit'))}</td>"
            f"<td>{provenance}</td>"
            f"<td>{review_summary}</td>"
            "</tr>"
        )

    return (
        "<table border='1'>"
        "<thead><tr>"
        "<th>ID</th><th>Analyte</th><th>Value</th><th>Unit</th>"
        "<th>Provenance</th><th>Review</th>"
        "</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody>"
        "</table>"
    )
