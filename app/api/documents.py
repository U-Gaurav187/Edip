import logging
import uuid
from pathlib import Path
import pymupdf
from fastapi import APIRouter, UploadFile, File, HTTPException, Response, Query
from fastapi.responses import Response
from typing import Optional
from ..config import settings
from ..core.engine import engine_manager
from ..core.exporter import RealPDFExporter
from ..models.responses import DocumentInspectionResponse, OperationResult
from ..models.requests import ExportRequest

logger = logging.getLogger("pdf_engine")

router = APIRouter(prefix="/documents", tags=["Documents"])

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")

@router.post("/upload", response_model=DocumentInspectionResponse)
async def upload_document(
    file: UploadFile = File(...),
    max_inspect_pages: Optional[int] = Query(None, description="Max pages to inspect in initial upload response")
):
    """
    Upload any PDF document or document photo/scan (PNG, JPG, WebP).
    Streams chunks directly to disk to minimize memory usage for large files (e.g. 30MB+ brochures).
    Images are seamlessly converted to high-fidelity PDF pages.
    """
    filename = file.filename or "document.pdf"
    content_type = file.content_type or ""
    logger.info(f"Upload received: filename='{filename}', content_type='{content_type}', size_header={file.size}")

    is_image = any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS) or content_type.startswith("image/")
    is_pdf = filename.lower().endswith(".pdf") or content_type == "application/pdf"

    if not is_pdf and not is_image:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Please upload a PDF or image file (PNG, JPG, JPEG, WebP). Got: '{filename}'"
        )

    doc_id = str(uuid.uuid4())
    session_file = settings.STORAGE_DIR / f"{doc_id}.pdf"
    
    file_size = 0
    header_bytes = b""
    first_chunk = True

    try:
        with open(session_file, "wb") as f_out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB stream buffer
                if not chunk:
                    break
                if first_chunk:
                    header_bytes = chunk[:1024]
                    first_chunk = False
                f_out.write(chunk)
                file_size += len(chunk)
                if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
                    f_out.close()
                    session_file.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."
                    )
    except HTTPException:
        raise
    except Exception as read_err:
        session_file.unlink(missing_ok=True)
        logger.exception("Failed to stream uploaded file to storage")
        raise HTTPException(status_code=500, detail=f"Failed to read upload stream: {str(read_err)}")

    logger.info(f"Upload streamed to disk: {file_size} bytes for '{filename}' -> {session_file}")

    if file_size == 0:
        session_file.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file '{filename}' is empty (0 bytes received). Please check the file and try again."
        )

    # Convert image to genuine PDF document if image
    if is_image:
        try:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
            if ext not in ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"]:
                ext = "png"
            img_doc = pymupdf.open(str(session_file), filetype=ext)
            pdf_bytes = img_doc.convert_to_pdf()
            img_doc.close()
            session_file.write_bytes(pdf_bytes)
            base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
            filename = f"{base_name}.pdf"
            logger.info(f"Successfully converted photo/scan '{file.filename}' to PDF on disk")
        except Exception as img_err:
            session_file.unlink(missing_ok=True)
            logger.exception(f"Failed to convert image '{filename}' to PDF")
            raise HTTPException(status_code=400, detail=f"Could not convert document image to PDF: {str(img_err)}")
    else:
        # Basic PDF header validation
        if not header_bytes[:5] in (b"%PDF-", b"\xef\xbb\xbf%P"):
            session_file.unlink(missing_ok=True)
            raise HTTPException(
                status_code=400,
                detail=f"File '{filename}' does not appear to be a valid PDF (missing %PDF- header)."
            )

    try:
        doc_id = engine_manager.create_session_from_file(session_file, filename=filename, doc_id=doc_id)
        return engine_manager.inspect_document(doc_id, max_pages=max_inspect_pages)
    except Exception as e:
        session_file.unlink(missing_ok=True)
        logger.exception(f"Failed to parse PDF: {filename}")
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF document: {str(e)}")

@router.get("/{doc_id}/inspect", response_model=DocumentInspectionResponse)
async def inspect_document(
    doc_id: str,
    max_pages: Optional[int] = Query(None, description="Max pages to inspect")
):
    """
    Returns full structural object inspection for pages in the document.
    """
    try:
        return engine_manager.inspect_document(doc_id, max_pages=max_pages)
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
