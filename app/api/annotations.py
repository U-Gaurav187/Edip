from fastapi import APIRouter, HTTPException
from ..core.engine import engine_manager
from ..core.annot_editor import RealPDFAnnotEditor
from ..models.requests import AnnotationAddRequest, AnnotationDeleteRequest
from ..models.responses import PageInspection, OperationResult

router = APIRouter(prefix="/documents", tags=["Annotations"])

@router.post("/{doc_id}/annotations/add", response_model=PageInspection)
async def add_annotation(doc_id: str, req: AnnotationAddRequest):
    """
    Adds a PDF annotation object (highlight, underline, note, ink drawing, etc.)
    to the page's /Annots array.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            annot_xref = RealPDFAnnotEditor.add_annotation(
                doc=session.doc,
                page_index=req.page_index,
                annot_type=req.annot_type,
                rect=req.rect,
                color=req.color,
                content=req.content,
                points=req.points
            )
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{doc_id}/annotations/{page_index}/{annot_id}", response_model=PageInspection)
async def delete_annotation(doc_id: str, page_index: int, annot_id: int):
    """
    Removes the specified annotation object from the page.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFAnnotEditor.delete_annotation(
                doc=session.doc,
                page_index=page_index,
                annot_xref=annot_id
            )
        return engine_manager.inspect_page(doc_id, page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
