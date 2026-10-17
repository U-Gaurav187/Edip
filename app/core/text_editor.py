from typing import Optional, List, Tuple
import pymupdf
from .font_manager import FontManager

class RealPDFTextEditor:
    """
    Production PDF Text Object Editor.
    Operates strictly at the PDF Object / Content Stream layer.
    
    Principles:
    1. Zero visual overlay hacks (NO white rectangles, NO masking annotations).
    2. Surgical operator eradication: physically removes glyph operators from /Contents.
    3. True PDF object re-insertion: creates compliant BT ... ET text objects.
    4. 100% copy-paste fidelity and searchability.
    5. Clean content stream consolidation.
    """

    @classmethod
    def edit_text_span(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        bbox: List[float],
        origin: List[float],
        new_text: str,
        font_name: Optional[str] = None,
        font_size: Optional[float] = None,
        color_rgb: Optional[List[float]] = None
    ) -> bool:
        """
        Surgically replaces text in a PDF page.
        Eradicates the existing text drawing operators and inserts the new text object.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds (total pages: {len(doc)})")
            
        page = doc[page_index]
        derotate = ~page.rotation_matrix
        
        # Un-rotate coordinates from frontend visual space to internal unrotated PDF space
        r_bbox = pymupdf.Rect(bbox)
        r_bbox.transform(derotate)
        
        r_origin = pymupdf.Point(origin[0], origin[1])
        r_origin.transform(derotate)
        origin_unrot = [r_origin.x, r_origin.y]
        
        # 1. Expand bbox by a sub-pixel margin (0.2pt) to ensure all glyph bounding curves are captured
        x0, y0, x1, y1 = r_bbox
        redact_rect = pymupdf.Rect(x0 - 0.2, y0 - 0.2, x1 + 0.2, y1 + 0.2)
        
        # 2. Add redaction annotation with fill=False (crucial: zero fill color, no white box)
        page.add_redact_annot(redact_rect, fill=False)
        
        # 3. Apply redaction, targeting text only (protecting underlying images and vectors)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        
        # 4. If new_text is empty, we are simply deleting the text
        if not new_text or not new_text.strip():
            page.clean_contents()
            return True
            
        # 5. Resolve typography
        resolved_font = FontManager.resolve_font_name(font_name)
        size = font_size if font_size and font_size > 0 else 11.0
        
        # Resolve color
        if color_rgb and len(color_rgb) == 3:
            color_tuple = (float(color_rgb[0]), float(color_rgb[1]), float(color_rgb[2]))
        else:
            color_tuple = (0.0, 0.0, 0.0)
            
        # 6. Insert new text object at exact origin baseline (in unrotated space)
        insert_pt = pymupdf.Point(origin_unrot[0], origin_unrot[1])
        page.insert_text(
            insert_pt,
            new_text,
            fontname=resolved_font,
            fontsize=size,
            color=color_tuple
        )
        
        # 7. Consolidate content streams into a single optimized stream
        page.clean_contents()
        return True

    @classmethod
    def delete_text_span(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        bbox: List[float]
    ) -> bool:
        """
        Surgically eradicates text inside the bounding box from the content stream.
        Leaves no residual graphics or white boxes.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        derotate = ~page.rotation_matrix
        
        r_bbox = pymupdf.Rect(bbox)
        r_bbox.transform(derotate)
        x0, y0, x1, y1 = r_bbox
        
        redact_rect = pymupdf.Rect(x0 - 0.2, y0 - 0.2, x1 + 0.2, y1 + 0.2)
        
        page.add_redact_annot(redact_rect, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        page.clean_contents()
        return True

    @classmethod
    def insert_new_text(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        origin: List[float],
        text: str,
        font_name: str = "helv",
        font_size: float = 12.0,
        color_rgb: Optional[List[float]] = None
    ) -> bool:
        """
        Inserts a new text object at the specified coordinate.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        derotate = ~page.rotation_matrix
        
        r_origin = pymupdf.Point(origin[0], origin[1])
        r_origin.transform(derotate)
        
        resolved_font = FontManager.resolve_font_name(font_name)
        color_tuple = tuple(color_rgb) if color_rgb and len(color_rgb) == 3 else (0.0, 0.0, 0.0)
        
        page.insert_text(
            r_origin,
            text,
            fontname=resolved_font,
            fontsize=font_size,
            color=color_tuple
        )
        page.clean_contents()
        return True
