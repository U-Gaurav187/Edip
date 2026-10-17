from fastapi import APIRouter, HTTPException
from ..core.engine import engine_manager
from ..core.form_editor import RealPDFFormEditor
from ..models.requests import FormFieldUpdateRequest, FormFieldCreateRequest
from ..models.responses import PageInspection, OperationResult

router = APIRouter(prefix="/documents", tags=["Forms"])

@router.post("/{doc_id}/forms/update", response_model=PageInspection)
async def update_form_field(doc_id: str, req: FormFieldUpdateRequest):
    """
    Updates the value of an AcroForm field and recalculates appearance streams.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            success = RealPDFFormEditor.update_field_value(
                doc=session.doc,
                page_index=req.page_index,
                field_name=req.field_name,
                value=req.value
            )
            if not success:
                raise HTTPException(status_code=404, detail=f"Field '{req.field_name}' not found.")
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/forms/create", response_model=PageInspection)
async def create_form_field(doc_id: str, req: FormFieldCreateRequest):
    """
    Creates a new interactive form widget on the page.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFFormEditor.create_field(
                doc=session.doc,
                page_index=req.page_index,
                field_type_str=req.field_type,
                field_name=req.field_name,
                rect=req.rect,
                options=req.options,
                default_value=req.default_value
            )
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
