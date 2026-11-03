import logging
import os
from io import BytesIO
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from starlette.concurrency import run_in_threadpool

from claims_pipeline.workflow import process_claim


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claim Processing Pipeline",
    description="Classify claim PDF pages and extract identity, discharge, and bill data.",
    version="1.0.0",
)


def _positive_limit(variable: str, default: int) -> int:
    try:
        value = int(os.getenv(variable, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{variable} must be a positive integer") from exc
    if value < 1:
        raise RuntimeError(f"{variable} must be a positive integer")
    return value


@app.get("/health/")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/process")
async def process_pdf_claim(
    claim_id: str = Form(min_length=1, max_length=128),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    claim_id = claim_id.strip()
    if not claim_id:
        raise HTTPException(status_code=422, detail="claim_id cannot be blank")

    max_bytes = _positive_limit("MAX_PDF_BYTES", 20 * 1024 * 1024)
    pdf_bytes = await file.read(max_bytes + 1)
    if len(pdf_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="PDF exceeds the configured size limit")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Upload must be a valid PDF file")

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise HTTPException(status_code=422, detail="Encrypted PDFs are not supported")
        max_pages = _positive_limit("MAX_PDF_PAGES", 100)
        if len(reader.pages) > max_pages:
            raise HTTPException(
                status_code=413,
                detail=f"PDF exceeds the configured limit of {max_pages} pages",
            )
        pages = [
            {
                "page_number": page_number,
                "text": (page.extract_text() or "").strip(),
            }
            for page_number, page in enumerate(reader.pages, start=1)
        ]
    except HTTPException:
        raise
    except (PdfReadError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail="Could not read the uploaded PDF") from exc

    if not pages:
        raise HTTPException(status_code=422, detail="PDF contains no pages")
    if not any(page["text"] for page in pages):
        raise HTTPException(
            status_code=422,
            detail="PDF contains no extractable text; OCR scanned documents before submitting",
        )

    try:
        return await run_in_threadpool(process_claim, claim_id, pages)
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            raise HTTPException(
                status_code=503,
                detail="Claim extraction is not configured; set OPENAI_API_KEY",
            ) from exc
        logger.exception("Claim processing configuration failed for %s", claim_id)
        raise HTTPException(status_code=503, detail="Claim processing is not configured") from exc
    except Exception as exc:
        logger.exception("Claim processing failed for %s", claim_id)
        raise HTTPException(
            status_code=502,
            detail="Claim extraction failed; check the service configuration and logs",
        ) from exc
