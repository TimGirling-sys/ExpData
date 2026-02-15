from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes with a safe fallback.

    Uses pypdf for real PDF parsing. If parsing fails, falls back to UTF-8 decode
    to preserve current MVP test behavior.
    """
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        chunks: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                chunks.append(page_text)
        text = "\n".join(chunks)
        if text.strip():
            return text
    except Exception:
        pass

    return pdf_bytes.decode("utf-8", errors="ignore")
