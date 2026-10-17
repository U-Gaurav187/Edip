from fastapi import APIRouter, HTTPException
from ..core.engine import engine_manager
from ..core.text_editor import RealPDFTextEditor
from ..models.requests import TextEditRequest, TextDeleteRequest, TextInsertRequest
from ..models.responses import PageInspection

router = APIRouter(prefix="/documents", tags=["Text Editing"])

@router.post("/{doc_id}/text/edit", response_model=PageInspection)
async def edit_text(doc_id: str, req: TextEditRequest):
    """
    Surgically replaces text in the PDF content stream.
    Eradicates old text operators without white boxes and inserts new compliant text object.
    Returns the refreshed page object AST.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFTextEditor.edit_text_span(
                doc=session.doc,
                page_index=req.page_index,
                bbox=req.bbox,
                origin=req.origin,
                new_text=req.new_text,
                font_name=req.font_name,
                font_size=req.font_size,
                color_rgb=req.color_rgb
            )
            session.save_to_disk()
        # Return updated page inspection
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document session not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text editing failed: {str(e)}")

@router.post("/{doc_id}/text/delete", response_model=PageInspection)
async def delete_text(doc_id: str, req: TextDeleteRequest):
    """
    Surgically excises text drawing operators from the PDF content stream.
    Zero visual artifacts or hidden text left behind.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFTextEditor.delete_text_span(
                doc=session.doc,
                page_index=req.page_index,
                bbox=req.bbox,
                origin=req.origin
            )
            session.save_to_disk()
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document session not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text deletion failed: {str(e)}")

@router.post("/{doc_id}/text/insert", response_model=PageInspection)
async def insert_text(doc_id: str, req: TextInsertRequest):
    """
    Inserts a genuine PDF text object into the page content stream.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFTextEditor.insert_new_text(
                doc=session.doc,
                page_index=req.page_index,
                origin=req.origin,
                text=req.text,
                font_name=req.font_name,
                font_size=req.font_size,
                color_rgb=req.color_rgb
            )
            session.save_to_disk()
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document session not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Text insertion failed: {str(e)}")
