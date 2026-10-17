from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union

class DocumentMetadata(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    mod_date: Optional[str] = None
    page_count: int
    is_encrypted: bool
    is_pdfa: bool

class CharDetail(BaseModel):
    c: str
    bbox: List[float]
    origin: List[float]

class SpanDetail(BaseModel):
    id: str
    text: str
    bbox: List[float]
    origin: List[float]
    font: str
    size: float
    color: int
    color_rgb: List[float]
    flags: int
    ascender: float
    descender: float
    chars: Optional[List[CharDetail]] = None

class LineDetail(BaseModel):
    id: str
    bbox: List[float]
    spans: List[SpanDetail]

class TextBlockDetail(BaseModel):
    id: str
    bbox: List[float]
    lines: List[LineDetail]

class ImageObjectDetail(BaseModel):
    xref: int
    number: int
    bbox: List[float]
    width: int
    height: int
    colorspace: str
    bpc: int
    size_bytes: int
    format: str

class DrawingPathDetail(BaseModel):
    type: str
    rect: List[float]
    fill_color: Optional[List[float]] = None
    stroke_color: Optional[List[float]] = None
    line_width: Optional[float] = None

class FontDetail(BaseModel):
    xref: int
    name: str
    basefont: str
    type: str
    encoding: str
    is_embedded: bool

class FormFieldDetail(BaseModel):
    name: str
    type: str
    value: Union[str, bool, None]
    rect: List[float]
    options: Optional[List[str]] = None
    is_read_only: bool

class AnnotationDetail(BaseModel):
    id: int
    type: str
    rect: List[float]
    color: List[float]
    content: Optional[str] = None
    author: Optional[str] = None
    mod_date: Optional[str] = None

class PageInspection(BaseModel):
    page_index: int
    width: float
    height: float
    rotation: int
    is_scanned: bool
    text_blocks: List[TextBlockDetail]
    images: List[ImageObjectDetail]
    drawings: List[DrawingPathDetail]
    fonts: List[FontDetail]
    form_fields: List[FormFieldDetail]
    annotations: List[AnnotationDetail]

class DocumentInspectionResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    metadata: DocumentMetadata
    pages: List[PageInspection]

class OperationResult(BaseModel):
    success: bool
    message: str
    document_id: str
    page_index: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
