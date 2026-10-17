from fastapi import APIRouter, HTTPException
from ..core.engine import engine_manager
from ..core.ocr_engine import RealPDFOCREngine
from ..models.requests import OCRRequest
from ..models.responses import OperationResult

router = APIRouter(prefix="/documents", tags=["OCR Engine"])

@router.post("/{doc_id}/ocr", response_model=OperationResult)
async def run_ocr(doc_id: str, req: OCRRequest):
    """
    Runs C-native MuPDF Tesseract OCR on scanned pages and injects a real searchable
    and selectable text layer into the PDF content stream.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            doc = session.doc
            total_pages = len(doc)
            
            target_indices = req.page_indices
            if target_indices is None:
                # Auto-detect scanned pages
                target_indices = [
                    p_idx for p_idx in range(total_pages)
                    if RealPDFOCREngine.is_page_scanned(doc[p_idx])
                ]

            processed_count = 0
            spans_injected = 0
            for p_idx in target_indices:
                if 0 <= p_idx < total_pages:
                    count = RealPDFOCREngine.process_ocr_page(doc, p_idx, language=req.language)
                    spans_injected += count
                    processed_count += 1

        return OperationResult(
            success=True,
            message=f"OCR processed {processed_count} page(s), created {spans_injected} text spans.",
            document_id=doc_id,
            details={
                "processed_pages": target_indices,
                "spans_injected": spans_injected
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR execution failed: {str(e)}")
