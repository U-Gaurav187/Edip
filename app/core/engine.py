import io
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading
import pymupdf

from ..config import settings
from ..models.responses import (
    DocumentMetadata,
    PageInspection,
    DocumentInspectionResponse,
    TextBlockDetail,
    LineDetail,
    SpanDetail,
    CharDetail,
    ImageObjectDetail,
    DrawingPathDetail,
    FontDetail,
    FormFieldDetail,
    AnnotationDetail,
)
from .font_manager import FontManager
from .ocr_engine import RealPDFOCREngine
from .form_editor import RealPDFFormEditor
from .annot_editor import RealPDFAnnotEditor

class PDFSession:
    """
    Represents an active document session in memory with timestamp for TTL cleanup.
    """
    def __init__(self, doc_id: str, filename: str, doc: pymupdf.Document, file_path: Optional[Path] = None):
        self.doc_id = doc_id
        self.filename = filename
        self.doc = doc
        self.file_path = file_path
        self.last_accessed = time.time()
        self.lock = threading.Lock()

    def touch(self):
        self.last_accessed = time.time()

    def save_to_disk(self):
        """
        Persists the current in-memory document state to disk.
        Ensures edits survive server sleep or container restart.
        """
        if self.file_path and self.doc:
            try:
                pdf_bytes = self.doc.tobytes(garbage=3, deflate=True)
                self.file_path.write_bytes(pdf_bytes)
            except Exception:
                pass

class PDFEngineManager:
    """
    Manages PDF document sessions, concurrency, inspection AST generation,
    and rendering.
    """
    def __init__(self):
        self._sessions: Dict[str, PDFSession] = {}
        self._lock = threading.Lock()

    def create_session_from_bytes(self, pdf_bytes: bytes, filename: str = "document.pdf") -> str:
        doc_id = str(uuid.uuid4())
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        # Persist session copy in STORAGE_DIR
        session_file = settings.STORAGE_DIR / f"{doc_id}.pdf"
        session_file.write_bytes(pdf_bytes)
        
        session = PDFSession(doc_id=doc_id, filename=filename, doc=doc, file_path=session_file)
        with self._lock:
            self._sessions[doc_id] = session
            
        self._cleanup_expired_sessions()
        return doc_id

    def create_session_from_file(self, file_path: Path, filename: str = "document.pdf", doc_id: Optional[str] = None) -> str:
        """
        Creates a PDF session directly from a file path on disk without duplicating bytes in RAM.
        Uses mmap/file-descriptor access to minimize memory usage for large documents.
        """
        if not doc_id:
            doc_id = str(uuid.uuid4())
        doc = pymupdf.open(str(file_path))
        session = PDFSession(doc_id=doc_id, filename=filename, doc=doc, file_path=file_path)
        with self._lock:
            self._sessions[doc_id] = session
            
        self._cleanup_expired_sessions()
        return doc_id

    def get_session(self, doc_id: str) -> PDFSession:
        with self._lock:
            session = self._sessions.get(doc_id)
            if not session:
                # Check if session file exists on disk
                session_file = settings.STORAGE_DIR / f"{doc_id}.pdf"
                if session_file.exists():
                    doc = pymupdf.open(str(session_file))
                    session = PDFSession(doc_id=doc_id, filename="document.pdf", doc=doc, file_path=session_file)
                    self._sessions[doc_id] = session
                else:
                    raise KeyError(f"Session with ID '{doc_id}' not found or expired.")
            session.touch()
            return session

    def close_session(self, doc_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(doc_id, None)
            if session:
                try:
                    session.doc.close()
                    if session.file_path and session.file_path.exists():
                        session.file_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return True
        return False

    def _cleanup_expired_sessions(self):
        now = time.time()
        ttl_seconds = settings.SESSION_TTL_MINUTES * 60
        to_delete = []
        with self._lock:
            for d_id, sess in self._sessions.items():
                if now - sess.last_accessed > ttl_seconds:
                    to_delete.append(d_id)
            for d_id in to_delete:
                sess = self._sessions.pop(d_id, None)
                if sess:
                    try:
                        sess.doc.close()
                        if sess.file_path and sess.file_path.exists():
                            sess.file_path.unlink(missing_ok=True)
                    except Exception:
                        pass

    def inspect_document(self, doc_id: str, max_pages: Optional[int] = None) -> DocumentInspectionResponse:
        session = self.get_session(doc_id)
        with session.lock:
            doc = session.doc
            meta = doc.metadata or {}
            
            metadata = DocumentMetadata(
                title=meta.get("title") or session.filename,
                author=meta.get("author") or "",
                subject=meta.get("subject") or "",
                creator=meta.get("creator") or "",
                producer=meta.get("producer") or "",
                creation_date=meta.get("creationDate") or "",
                mod_date=meta.get("modDate") or "",
                page_count=len(doc),
                is_encrypted=doc.is_encrypted,
                is_pdfa=doc.is_pdfa if hasattr(doc, "is_pdfa") else False
            )
            
            # For documents with up to 5 pages, inspect all.
            # For larger documents (brochures, books, 10-100+ pages), inspect the initial page (page 0)
            # and let subsequent pages be fetched on-demand by /pages/{page_index}/inspect.
            # This guarantees sub-second response times and eliminates 502 Bad Gateway OOM errors on cloud hosts.
            num_to_inspect = len(doc)
            if max_pages is not None:
                num_to_inspect = min(len(doc), max_pages)
            elif len(doc) > 5:
                num_to_inspect = 1

            pages_list: List[PageInspection] = []
            for p_idx in range(num_to_inspect):
                page_data = self._inspect_page_internal(doc, p_idx)
                pages_list.append(page_data)

            return DocumentInspectionResponse(
                document_id=doc_id,
                filename=session.filename,
                page_count=len(doc),
                metadata=metadata,
                pages=pages_list
            )

    def inspect_page(self, doc_id: str, page_index: int) -> PageInspection:
        session = self.get_session(doc_id)
        with session.lock:
            if page_index < 0 or page_index >= len(session.doc):
                raise ValueError(f"Page index {page_index} out of bounds")
            return self._inspect_page_internal(session.doc, page_index)

    def render_page_image(self, doc_id: str, page_index: int, dpi: int = 150) -> bytes:
        session = self.get_session(doc_id)
        with session.lock:
            if page_index < 0 or page_index >= len(session.doc):
                raise ValueError(f"Page index {page_index} out of bounds")
            page = session.doc[page_index]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            return pix.tobytes("png")

    def _inspect_page_internal(self, doc: pymupdf.Document, page_index: int) -> PageInspection:
        page = doc[page_index]
        page_rect = page.rect
        rot_mat = page.rotation_matrix
        
        def transform_bbox(b):
            r = pymupdf.Rect(b)
            r.transform(rot_mat)
            return [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
            
        def transform_point(p):
            pt = pymupdf.Point(p)
            pt.transform(rot_mat)
            return [round(pt.x, 2), round(pt.y, 2)]
        
        # 1. Text blocks extraction
        raw_text_json = page.get_text("json")
        parsed_json = json.loads(raw_text_json)
        
        text_blocks: List[TextBlockDetail] = []
        b_idx = 0
        for block in parsed_json.get("blocks", []):
            if block.get("type") == 0:  # Text block
                lines_list: List[LineDetail] = []
                l_idx = 0
                for line in block.get("lines", []):
                    spans_list: List[SpanDetail] = []
                    s_idx = 0
                    for span in line.get("spans", []):
                        color_int = span.get("color", 0)
                        span_detail = SpanDetail(
                            id=f"spn_{page_index}_{b_idx}_{l_idx}_{s_idx}",
                            text=span.get("text", ""),
                            bbox=transform_bbox(span.get("bbox", [0, 0, 0, 0])),
                            origin=transform_point(span.get("origin", [0, 0])),
                            font=span.get("font", "Helvetica"),
                            size=round(span.get("size", 12.0), 2),
                            color=color_int,
                            color_rgb=[float(x) for x in FontManager.color_int_to_rgb(color_int)],
                            flags=span.get("flags", 0),
                            ascender=round(span.get("ascender", 0.8), 3),
                            descender=round(span.get("descender", -0.2), 3)
                        )
                        spans_list.append(span_detail)
                        s_idx += 1
                    
                    line_detail = LineDetail(
                        id=f"ln_{page_index}_{b_idx}_{l_idx}",
                        bbox=transform_bbox(line.get("bbox", [0, 0, 0, 0])),
                        spans=spans_list
                    )
                    lines_list.append(line_detail)
                    l_idx += 1

                block_detail = TextBlockDetail(
                    id=f"blk_{page_index}_{b_idx}",
                    bbox=transform_bbox(block.get("bbox", [0, 0, 0, 0])),
                    lines=lines_list
                )
                text_blocks.append(block_detail)
                b_idx += 1

        # 2. Images extraction
        image_objects: List[ImageObjectDetail] = []
        try:
            img_infos = page.get_image_info(xrefs=True)
            for idx, img in enumerate(img_infos):
                image_objects.append(ImageObjectDetail(
                    xref=img.get("xref", 0),
                    number=img.get("number", idx),
                    bbox=transform_bbox(img.get("bbox", [0, 0, 0, 0])),
                    width=img.get("width", 0),
                    height=img.get("height", 0),
                    colorspace=str(img.get("cs-name", "RGB")),
                    bpc=img.get("bpc", 8),
                    size_bytes=img.get("size", 0),
                    format=str(img.get("ext", "png"))
                ))
        except Exception:
            pass

        # 3. Vector drawings extraction
        drawings: List[DrawingPathDetail] = []
        try:
            raw_drawings = page.get_drawings()
            for d in raw_drawings[:50]:  # Limit to 50 paths to avoid massive payloads
                fill = [round(x, 3) for x in d["fill"]] if d.get("fill") else None
                stroke = [round(x, 3) for x in d["color"]] if d.get("color") else None
                rect = [round(x, 2) for x in d.get("rect", [0, 0, 0, 0])]
                drawings.append(DrawingPathDetail(
                    type=d.get("type", "path"),
                    rect=rect,
                    fill_color=fill,
                    stroke_color=stroke,
                    line_width=d.get("width", 1.0)
                ))
        except Exception:
            pass

        # 4. Fonts extraction
        fonts: List[FontDetail] = []
        try:
            page_fonts = doc.get_page_fonts(page_index)
            for f in page_fonts:
                xref, ext, ftype, basefont, name, encoding = f[:6]
                fonts.append(FontDetail(
                    xref=xref,
                    name=name or "",
                    basefont=basefont or "",
                    type=ftype or "",
                    encoding=encoding or "",
                    is_embedded=bool(ext and ext != "n/a")
                ))
        except Exception:
            pass

        # 5. Form fields
        form_fields_raw = RealPDFFormEditor.get_page_fields(page)
        form_fields = [FormFieldDetail(**f) for f in form_fields_raw]

        # 6. Annotations
        annots_raw = RealPDFAnnotEditor.get_page_annotations(page)
        annotations = [AnnotationDetail(**a) for a in annots_raw]

        # 7. Scanned detection
        is_scanned = RealPDFOCREngine.is_page_scanned(page)

        rot_rect = page_rect.transform(rot_mat)
        p_width = round(abs(rot_rect.width), 2)
        p_height = round(abs(rot_rect.height), 2)

        return PageInspection(
            page_index=page_index,
            width=p_width,
            height=p_height,
            rotation=page.rotation,
            is_scanned=is_scanned,
            text_blocks=text_blocks,
            images=image_objects,
            drawings=drawings,
            fonts=fonts,
            form_fields=form_fields,
            annotations=annotations
        )

# Global singleton engine instance
engine_manager = PDFEngineManager()
