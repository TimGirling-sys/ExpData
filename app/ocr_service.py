"""OCR extraction service with pluggable providers."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Protocol


class OCRServiceError(Exception):
    """Base OCR service error."""


class MalformedPDFError(OCRServiceError):
    """Raised when the supplied payload is not a valid PDF."""


class OCRProviderError(OCRServiceError):
    """Raised when the configured OCR provider fails."""


@dataclass
class BoundingBox:
    left: float
    top: float
    width: float
    height: float


@dataclass
class BlockIR:
    block_type: str
    text: str
    page: int
    confidence: float | None
    bounding_box: BoundingBox | None


@dataclass
class TableCellIR:
    row_index: int
    column_index: int
    text: str
    bounding_box: BoundingBox | None


@dataclass
class TableIR:
    page: int
    bounding_box: BoundingBox | None
    cells: list[TableCellIR]


@dataclass
class PageIR:
    page_number: int
    width: float | None
    height: float | None
    blocks: list[BlockIR]
    tables: list[TableIR]


@dataclass
class DocumentIR:
    pages: list[PageIR]
    extracted_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OCRProvider(Protocol):
    """Provider contract for OCR engines."""

    name: str

    def extract_document(self, pdf_bytes: bytes) -> DocumentIR:
        """Extract normalized document IR from PDF bytes."""


class AWSTextractProvider:
    name = "aws_textract"

    def __init__(self) -> None:
        region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        if not region:
            raise OCRProviderError(
                "AWS region is not configured. Set AWS_REGION or AWS_DEFAULT_REGION."
            )

        try:
            import boto3  # type: ignore
            from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
        except Exception as exc:  # pragma: no cover - import errors vary by environment
            raise OCRProviderError(
                "AWS Textract provider requires boto3 and botocore to be installed."
            ) from exc

        self._boto3 = boto3
        self._BotoCoreError = BotoCoreError
        self._ClientError = ClientError
        self._client = boto3.client("textract", region_name=region)

    def extract_document(self, pdf_bytes: bytes) -> DocumentIR:
        try:
            response = self._client.analyze_document(
                Document={"Bytes": pdf_bytes},
                FeatureTypes=["TABLES", "FORMS"],
            )
        except (self._BotoCoreError, self._ClientError) as exc:
            raise OCRProviderError(f"AWS Textract request failed: {exc}") from exc

        blocks = response.get("Blocks", [])
        blocks_by_id = {block.get("Id"): block for block in blocks if block.get("Id")}

        pages_map: dict[int, PageIR] = {}
        text_lines: list[str] = []

        def page_for(page_number: int) -> PageIR:
            if page_number not in pages_map:
                pages_map[page_number] = PageIR(
                    page_number=page_number,
                    width=None,
                    height=None,
                    blocks=[],
                    tables=[],
                )
            return pages_map[page_number]

        for block in blocks:
            block_type = block.get("BlockType", "UNKNOWN")
            page_number = int(block.get("Page", 1))
            bbox = _bbox_from_textract(block)
            confidence = block.get("Confidence")
            text = block.get("Text", "")

            if block_type in {"LINE", "WORD", "KEY_VALUE_SET", "CELL"}:
                page = page_for(page_number)
                page.blocks.append(
                    BlockIR(
                        block_type=block_type,
                        text=text,
                        page=page_number,
                        confidence=confidence,
                        bounding_box=bbox,
                    )
                )
                if text:
                    text_lines.append(text)

            if block_type == "TABLE":
                table = TableIR(page=page_number, bounding_box=bbox, cells=[])
                relationships = block.get("Relationships", [])
                for rel in relationships:
                    if rel.get("Type") != "CHILD":
                        continue
                    for child_id in rel.get("Ids", []):
                        child = blocks_by_id.get(child_id, {})
                        if child.get("BlockType") != "CELL":
                            continue
                        cell_text = _extract_cell_text(child, blocks_by_id)
                        table.cells.append(
                            TableCellIR(
                                row_index=int(child.get("RowIndex", 0)),
                                column_index=int(child.get("ColumnIndex", 0)),
                                text=cell_text,
                                bounding_box=_bbox_from_textract(child),
                            )
                        )
                page_for(page_number).tables.append(table)

        sorted_pages = [pages_map[key] for key in sorted(pages_map)]
        return DocumentIR(pages=sorted_pages, extracted_text="\n".join(text_lines))


def _bbox_from_textract(block: dict[str, Any]) -> BoundingBox | None:
    geometry = block.get("Geometry") or {}
    bbox = geometry.get("BoundingBox") or {}
    if not bbox:
        return None
    return BoundingBox(
        left=float(bbox.get("Left", 0.0)),
        top=float(bbox.get("Top", 0.0)),
        width=float(bbox.get("Width", 0.0)),
        height=float(bbox.get("Height", 0.0)),
    )


def _extract_cell_text(cell_block: dict[str, Any], blocks_by_id: dict[str, dict[str, Any]]) -> str:
    text_parts: list[str] = []
    for rel in cell_block.get("Relationships", []):
        if rel.get("Type") != "CHILD":
            continue
        for child_id in rel.get("Ids", []):
            word = blocks_by_id.get(child_id, {})
            if word.get("BlockType") == "WORD" and word.get("Text"):
                text_parts.append(word["Text"])
    return " ".join(text_parts)


def _resolve_provider() -> OCRProvider:
    provider_name = os.getenv("OCR_PROVIDER", "aws_textract").strip().lower()
    if provider_name == "aws_textract":
        return AWSTextractProvider()
    raise OCRProviderError(
        f"Unsupported OCR provider '{provider_name}'. Set OCR_PROVIDER=aws_textract."
    )


def extract_document(pdf_bytes: bytes) -> DocumentIR:
    """Validate PDF payload and delegate extraction to configured OCR provider."""
    if not pdf_bytes:
        raise MalformedPDFError("Empty payload; expected non-empty PDF bytes.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise MalformedPDFError("Malformed PDF payload: missing %PDF header.")

    provider = _resolve_provider()
    return provider.extract_document(pdf_bytes)
