"""Pipeline orchestration for compound extraction and normalization."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.chem_extractor import ChemExtractor

LOGGER = logging.getLogger(__name__)


class CompoundPipeline:
    """Run extraction over text and persist compounds + unresolved items."""

    def __init__(self, extractor: ChemExtractor | None = None) -> None:
        self.extractor = extractor or ChemExtractor()

    def run(self, text: str, resolve_structures: bool = True) -> dict[str, list[dict[str, Any]]]:
        compounds, unresolved = self.extractor.process_text(text, resolve_structures=resolve_structures)

        unresolved_logs = [asdict(item) for item in unresolved]
        for item in unresolved_logs:
            LOGGER.info(
                "Unresolved compound for manual review",
                extra={
                    "label": item.get("label"),
                    "name": item.get("name"),
                    "reason_code": item.get("reason_code"),
                    "details": item.get("details"),
                },
            )

        return {
            "compounds": compounds,
            "unresolved_compounds": unresolved_logs,
        }

    def persist_results(
        self,
        results: dict[str, list[dict[str, Any]]],
        output_path: str | Path,
        unresolved_path: str | Path,
    ) -> None:
        """Persist normalized compounds and unresolved compound logs to disk."""
        output_path = Path(output_path)
        unresolved_path = Path(unresolved_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        unresolved_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as compounds_file:
            json.dump(results.get("compounds", []), compounds_file, indent=2)

        with unresolved_path.open("w", encoding="utf-8") as unresolved_file:
            json.dump(results.get("unresolved_compounds", []), unresolved_file, indent=2)


def run_pipeline(
    text: str,
    output_path: str | Path,
    unresolved_path: str | Path,
    resolve_structures: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    """Convenience wrapper for one-shot pipeline execution."""
    pipeline = CompoundPipeline()
    results = pipeline.run(text=text, resolve_structures=resolve_structures)
    pipeline.persist_results(results, output_path=output_path, unresolved_path=unresolved_path)
    return results
