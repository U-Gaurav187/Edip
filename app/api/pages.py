from fastapi import APIRouter, HTTPException, Response, Query
from ..core.engine import engine_manager
from ..core.page_editor import RealPDFPageEditor
from ..models.requests import (
    PageReorderRequest,
    PageRotateRequest,
    PageDeleteRequest,
    PageDuplicateRequest,
    PageInsertBlankRequest
)
from ..models.responses import PageInspection, OperationResult

router = APIRouter(prefix="/documents", tags=["Pages"])

@router.get("/{doc_id}/pages/{page_index}/inspect", response_model=PageInspection)
async def inspect_page(doc_id: str, page_index: int):
    """
    Returns object AST for a specific page (text blocks, images, vector paths, fonts).
    """
    try:
        return engine_manager.inspect_page(doc_id, page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{doc_id}/pages/{page_index}/render")
async def render_page(
    doc_id: str,
    page_index: int,
    dpi: int = Query(150, ge=20, le=300, description="Rendering resolution (20 to 300 DPI)"),
    format: str = Query("png", description="'png' (default) or 'jpeg' for fast lightweight transfer"),
    quality: int = Query(85, ge=30, le=100)
):
    """
    Renders high-fidelity rasterized view of the PDF page for web display.
    Supports fast compressed JPEG (85% for page, 75% for thumbnail) and PNG.
    """
    try:
        q = quality if dpi > 50 else min(quality, 75)
        img_bytes, media_type = engine_manager.render_page_image(doc_id, page_index, dpi=dpi, img_format=format, quality=q)
        return Response(
            content=img_bytes,
            media_type=media_type,
            headers={
                "Content-Type": media_type,
                "Cache-Control": "public, max-age=1800"
            }
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{doc_id}/pages/reorder", response_model=OperationResult)
async def reorder_pages(doc_id: str, req: PageReorderRequest):
    """
    Reorders pages in the PDF document tree.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFPageEditor.reorder_pages(session.doc, req.new_order)
            session.save_to_disk()
        return OperationResult(
            success=True,
            message="Pages reordered successfully",
            document_id=doc_id,
            details={"new_order": req.new_order}
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/pages/rotate", response_model=OperationResult)
async def rotate_page(doc_id: str, req: PageRotateRequest):
    """
    Rotates a single page by 90, 180, or 270 degrees.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            new_rotation = RealPDFPageEditor.rotate_page(session.doc, req.page_index, req.rotation_delta)
            session.save_to_disk()
        return OperationResult(
            success=True,
            message=f"Page {req.page_index} rotated to {new_rotation} degrees",
            document_id=doc_id,
            page_index=req.page_index,
            details={"rotation": new_rotation}
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/pages/delete", response_model=OperationResult)
async def delete_pages(doc_id: str, req: PageDeleteRequest):
    """
    Deletes pages from the document.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFPageEditor.delete_pages(session.doc, req.page_indices)
            session.save_to_disk()
        return OperationResult(
            success=True,
            message=f"Deleted {len(req.page_indices)} page(s)",
            document_id=doc_id,
            details={"deleted_indices": req.page_indices}
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/pages/duplicate", response_model=OperationResult)
async def duplicate_page(doc_id: str, req: PageDuplicateRequest):
    """
    Duplicates a page in the document.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            new_index = RealPDFPageEditor.duplicate_page(session.doc, req.page_index)
            session.save_to_disk()
        return OperationResult(
            success=True,
            message=f"Page {req.page_index} duplicated at index {new_index}",
            document_id=doc_id,
            page_index=new_index
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/pages/insert-blank", response_model=OperationResult)
async def insert_blank_page(doc_id: str, req: PageInsertBlankRequest):
    """
    Inserts a blank page at the given index.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            new_idx = RealPDFPageEditor.insert_blank_page(
                session.doc,
                at_index=req.at_index,
                width=req.width,
                height=req.height
            )
            session.save_to_disk()
        return OperationResult(
            success=True,
            message=f"Blank page inserted at index {new_idx}",
            document_id=doc_id,
            page_index=new_idx
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
