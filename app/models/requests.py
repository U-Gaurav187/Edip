from pydantic import BaseModel, Field
from typing import Optional, List, Union

class TextEditRequest(BaseModel):
    page_index: int
    bbox: List[float] = Field(..., description="Target bounding box [x0, y0, x1, y1]")
    origin: List[float] = Field(..., description="Exact text baseline [x, y]")
    new_text: str = Field(..., description="Replacement text content")
    font_name: Optional[str] = Field(default=None, description="Font identifier or closest match")
    font_size: Optional[float] = Field(default=None, description="Font size in points")
    color_rgb: Optional[List[float]] = Field(default=None, description="RGB normalized [r, g, b] (0.0 to 1.0)")

class TextDeleteRequest(BaseModel):
    page_index: int
    bbox: List[float] = Field(..., description="Bounding box to surgically excise from content stream")
    origin: Optional[List[float]] = Field(default=None, description="Optional baseline origin coordinates [x, y]")

class TextInsertRequest(BaseModel):
    page_index: int
    origin: List[float] = Field(..., description="Baseline coordinates [x, y]")
    text: str = Field(..., description="Text string to insert")
    font_name: str = Field(default="helv", description="Font name (e.g. helv, times, couri, or embedded)")
    font_size: float = Field(default=12.0, description="Font size in points")
    color_rgb: List[float] = Field(default=[0.0, 0.0, 0.0], description="RGB normalized [r, g, b]")

class ImageTransformRequest(BaseModel):
    page_index: int
    xref: int = Field(..., description="PDF XObject cross-reference ID")
    old_bbox: List[float] = Field(..., description="Original bounding box [x0, y0, x1, y1]")
    new_bbox: List[float] = Field(..., description="New bounding box [x0, y0, x1, y1]")
    rotation_degrees: float = Field(default=0.0, description="Rotation angle in degrees")

class ImageDeleteRequest(BaseModel):
    page_index: int
    xref: int = Field(..., description="PDF XObject cross-reference ID to remove")

class ImageReplaceRequest(BaseModel):
    page_index: int
    xref: int = Field(..., description="PDF XObject cross-reference ID to replace")

class PageReorderRequest(BaseModel):
    new_order: List[int] = Field(..., description="Array of zero-based page indices in desired order")

class PageRotateRequest(BaseModel):
    page_index: int
    rotation_delta: int = Field(..., description="Rotation delta in degrees: 90, 180, or 270")

class PageDeleteRequest(BaseModel):
    page_indices: List[int] = Field(..., description="List of zero-based page indices to delete")

class PageDuplicateRequest(BaseModel):
    page_index: int = Field(..., description="Zero-based index of page to duplicate")

class PageInsertBlankRequest(BaseModel):
    at_index: int = Field(..., description="Index at which to insert new page")
    width: float = Field(default=612.0, description="Page width in points (default US Letter: 612)")
    height: float = Field(default=792.0, description="Page height in points (default US Letter: 792)")

class OCRRequest(BaseModel):
    page_indices: Optional[List[int]] = Field(default=None, description="Pages to OCR. If omitted, scanned pages are detected automatically")
    language: str = Field(default="eng", description="Tesseract language code (default 'eng')")

class FormFieldUpdateRequest(BaseModel):
    page_index: int
    field_name: str
    value: Union[str, bool]

class FormFieldCreateRequest(BaseModel):
    page_index: int
    field_type: str = Field(..., description="'text', 'checkbox', 'radio', or 'dropdown'")
    field_name: str
    rect: List[float] = Field(..., description="[x0, y0, x1, y1]")
    options: Optional[List[str]] = Field(default=None, description="Dropdown or radio options")
    default_value: Optional[str] = Field(default=None)

class AnnotationAddRequest(BaseModel):
    page_index: int
    annot_type: str = Field(..., description="'highlight', 'underline', 'strikeout', 'text', 'rect', 'circle', 'ink'")
    rect: List[float] = Field(..., description="Bounding box [x0, y0, x1, y1]")
    color: List[float] = Field(default=[1.0, 1.0, 0.0], description="RGB [r, g, b] (0.0 to 1.0)")
    content: Optional[str] = Field(default=None, description="Comment or text note content")
    points: Optional[List[List[float]]] = Field(default=None, description="List of [x, y] coordinates for ink drawing")

class AnnotationDeleteRequest(BaseModel):
    page_index: int
    annot_id: int

class ExportRequest(BaseModel):
    format: str = Field(default="pdf", description="'pdf', 'pdf_a', 'flattened', 'ocr'")
    clean_streams: bool = Field(default=True, description="Run MuPDF stream cleaner and garbage collection")
    deflate: bool = Field(default=True, description="Compress all content and font streams")
