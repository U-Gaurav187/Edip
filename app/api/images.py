from fastapi import APIRouter, HTTPException, UploadFile, File, Response, Form
from ..core.engine import engine_manager
from ..core.image_editor import RealPDFImageEditor
from ..models.requests import ImageTransformRequest, ImageDeleteRequest
from ..models.responses import PageInspection, OperationResult

router = APIRouter(prefix="/documents", tags=["Images"])

@router.get("/{doc_id}/images/{xref}/raw")
async def get_raw_image(doc_id: str, xref: int):
    """
    Extracts and returns the raw binary image from the PDF XObject.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            extracted = session.doc.extract_image(xref)
            if not extracted or "image" not in extracted:
                raise HTTPException(status_code=404, detail="Image XObject not found")
            return Response(
                content=extracted["image"],
                media_type=f"image/{extracted.get('ext', 'png')}"
            )
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/images/transform", response_model=PageInspection)
async def transform_image(doc_id: str, req: ImageTransformRequest):
    """
    Moves, resizes, or rotates an image by rewriting its cm matrix in the /Contents stream.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFImageEditor.transform_image(
                doc=session.doc,
                page_index=req.page_index,
                xref=req.xref,
                old_bbox=req.old_bbox,
                new_bbox=req.new_bbox,
                rotation_degrees=req.rotation_degrees
            )
            session.save_to_disk()
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/images/{xref}/replace", response_model=PageInspection)
async def replace_image(
    doc_id: str,
    xref: int,
    page_index: int = Form(...),
    file: UploadFile = File(...)
):
    """
    Replaces the underlying image XObject stream with a new uploaded image.
    Updates the original PDF object reference.
    """
    try:
        new_bytes = await file.read()
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFImageEditor.replace_image(
                doc=session.doc,
                page_index=page_index,
                xref=xref,
                new_image_bytes=new_bytes
            )
            session.save_to_disk()
        return engine_manager.inspect_page(doc_id, page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/images/delete", response_model=PageInspection)
async def delete_image(doc_id: str, req: ImageDeleteRequest):
    """
    Surgically excises the image Do operator from the content stream.
    """
    try:
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFImageEditor.delete_image(
                doc=session.doc,
                page_index=req.page_index,
                xref=req.xref
            )
            session.save_to_disk()
        return engine_manager.inspect_page(doc_id, req.page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{doc_id}/images/insert", response_model=PageInspection)
async def insert_image(
    doc_id: str,
    page_index: int = Form(...),
    x0: float = Form(...),
    y0: float = Form(...),
    x1: float = Form(...),
    y1: float = Form(...),
    rotation_degrees: float = Form(default=0.0),
    file: UploadFile = File(...)
):
    """
    Inserts an image into the PDF page at [x0, y0, x1, y1].
    Creates a compliant PDF Image XObject and emits a 'Do' operator into the /Contents stream.
    """
    try:
        new_bytes = await file.read()
        session = engine_manager.get_session(doc_id)
        with session.lock:
            RealPDFImageEditor.insert_image(
                doc=session.doc,
                page_index=page_index,
                image_bytes=new_bytes,
                bbox=[x0, y0, x1, y1],
                rotation_degrees=rotation_degrees
            )
            session.save_to_disk()
        return engine_manager.inspect_page(doc_id, page_index)
    except KeyError:
        raise HTTPException(status_code=404, detail="Document not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image insertion failed: {str(e)}")
