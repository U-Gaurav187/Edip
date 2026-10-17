import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Response, Query
from fastapi.responses import Response
from typing import Optional
from ..core.engine import engine_manager
from ..core.exporter import RealPDFExporter
from ..models.responses import DocumentInspectionResponse, OperationResult
from ..models.requests import ExportRequest

logger = logging.getLogger("pdf_engine")

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentInspectionResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload any PDF document. Parses all objects, fonts, text, images, and vectors.
    """
    filename = file.filename or "document.pdf"
    content_type = file.content_type or ""
    logger.info(f"Upload received: filename='{filename}', content_type='{content_type}', size_header={file.size}")

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"Only PDF files are supported. Got: '{filename}'")

    # Read file bytes — use a chunked approach to handle large files
    chunks = []
    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        chunks.append(chunk)
    contents = b"".join(chunks)

    logger.info(f"Upload read complete: {len(contents)} bytes from '{filename}'")

    if len(contents) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file '{filename}' is empty (0 bytes received). Please check the file and try again."
        )

    # Basic PDF header validation
    if not contents[:5] in (b"%PDF-", b"\xef\xbb\xbf%P"):
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' does not appear to be a valid PDF (missing %PDF- header)."
        )

    try:
        doc_id = engine_manager.create_session_from_bytes(contents, filename=filename)
        return engine_manager.inspect_document(doc_id)
    except Exception as e:
        logger.exception(f"Failed to parse PDF: {filename}")
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF document: {str(e)}")

@router.get("/{doc_id}/inspect", response_model=DocumentInspectionResponse)
async def inspect_document(doc_id: str):
    """
    Returns full structural object inspection for all pages in the document.
    """
    try:
        return engine_manager.inspect_document(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document session not found or expired.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{doc_id}/export")
async def export_document(
    doc_id: str,
    format: str = Query("pdf", description="'pdf', 'pdf_a', 'flattened', 'ocr'"),
    clean_streams: bool = Query(True),
    deflate: bool = Query(True)
):
    """
    Exports clean, production-grade PDF with consolidated objects,
    garbage-collected xrefs, and deflated streams.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            pdf_bytes = RealPDFExporter.export(
                session.doc,
                export_format=format,
                clean_streams=clean_streams,
                deflate=deflate
            )
            
        base_name = session.filename.rsplit(".", 1)[0]
        output_filename = f"{base_name}_edited.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"',
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document session not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.delete("/{doc_id}", response_model=OperationResult)
async def close_document(doc_id: str):
    """
    Closes the document session and releases memory and temp storage.
    """
    success = engine_manager.close_session(doc_id)
    return OperationResult(
        success=success,
        message="Session closed" if success else "Session not found",
        document_id=doc_id
    )
