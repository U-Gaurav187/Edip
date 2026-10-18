from typing import Optional, List, Tuple
import pymupdf
from .font_manager import FontManager

class RealPDFTextEditor:
    """
    Production PDF Text Object Editor.
    Supports both native vector PDFs and scanned/OCR documents.
    
    Principles:
    1. Text operator eradication: removes existing glyph operators from /Contents.
    2. Background obliteration: when modifying or deleting text on scanned documents
       or pages with raster images, applies a pixel-matched background patch
       over the old text bounding box so the old raster characters are permanently wiped out.
    3. Proper orientation: respects page rotation angle for accurate insertion.
    4. 100% copy-paste fidelity and searchability.
    5. Clean content stream consolidation.
    """

    @classmethod
    def sample_background_color(cls, page: pymupdf.Page, visual_bbox: List[float]) -> Tuple[float, float, float]:
        """
        Samples the local background color around the visual bounding box.
        Returns RGB tuple in 0.0 - 1.0 range (defaulting to clean white).
        """
        try:
            r = pymupdf.Rect(visual_bbox).intersect(page.rect)
            if r.width <= 0 or r.height <= 0:
                return (1.0, 1.0, 1.0)
                
            # Sample border pixels of the bounding box
            pix = page.get_pixmap(clip=r)
            if pix.width == 0 or pix.height == 0:
                return (1.0, 1.0, 1.0)
                
            corners = [
                pix.pixel(0, 0),
                pix.pixel(pix.width - 1, 0),
                pix.pixel(0, pix.height - 1),
                pix.pixel(pix.width - 1, pix.height - 1)
            ]
            
            # Find brightest non-text pixels (text glyphs are darker than background)
            bright_pixels = [c for c in corners if (c[0] + c[1] + c[2]) > 300]
            if bright_pixels:
                best = max(bright_pixels, key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
                return (round(best[0] / 255.0, 3), round(best[1] / 255.0, 3), round(best[2] / 255.0, 3))
        except Exception:
            pass
        return (1.0, 1.0, 1.0)

    @classmethod
    def compute_safe_redact_rect(
        cls,
        page: pymupdf.Page,
        bbox: List[float],
        origin: Optional[List[float]] = None
    ) -> pymupdf.Rect:
        """
        Computes a surgically constrained redaction rectangle that completely intersects
        the target text span while guaranteeing zero collision with adjacent lines
        (above/below) and adjacent words (left/right).
        """
        derotate = ~page.rotation_matrix
        r_bbox = pymupdf.Rect(bbox)
        r_bbox.transform(derotate)
        r_bbox.normalize()
        
        if origin:
            r_origin = pymupdf.Point(origin[0], origin[1])
            r_origin.transform(derotate)
            # Only use origin if it matches the original text position (hasn't been moved)
            if (r_bbox.y0 - 2.0 <= r_origin.y <= r_bbox.y1 + 5.0) and (r_bbox.x0 - 15.0 <= r_origin.x <= r_bbox.x1 + 15.0):
                origin_y = r_origin.y
            else:
                origin_y = r_bbox.y1 - (r_bbox.y1 - r_bbox.y0) * 0.22
        else:
            # Estimate baseline: standard baseline is ~80% down from top
            origin_y = r_bbox.y1 - (r_bbox.y1 - r_bbox.y0) * 0.22
            
        font_size = max(origin_y - r_bbox.y0, 6.0)
        
        # Start with safe bounding box around target ink.
        # On raster/scanned documents or pages with images, OCR bounding boxes commonly
        # truncate character serifs, italic overhangs, and underlying title underlines
        # by 3 to 6 points. We dynamically scale padding based on typography font size
        # while lines below strictly guard against any neighbor-word or neighbor-line collisions.
        is_raster_page = len(page.get_images()) > 0
        pad_x = max(5.5, min(font_size * 0.35, 8.0)) if is_raster_page else 0.5
        pad_y_top = max(2.5, min(font_size * 0.15, 4.0)) if is_raster_page else 0.5
        pad_y_bot = max(3.0, min(font_size * 0.20, 6.0)) if is_raster_page else 0.5
        
        safe_x0 = max(0.0, r_bbox.x0 - pad_x)
        safe_x1 = min(page.rect.width, r_bbox.x1 + pad_x)
        safe_y0 = max(0.0, min(r_bbox.y0, origin_y - 0.95 * font_size) - pad_y_top)
        safe_y1 = min(page.rect.height, max(r_bbox.y1, origin_y + min(0.35 * font_size, 6.0)) + pad_y_bot)
        
        # Inspect all text spans on page to ensure zero collision with other spans
        try:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        if not span.get("text", "").strip():
                            continue
                        s_bbox = pymupdf.Rect(span["bbox"])
                        s_bbox.transform(derotate)
                        s_bbox.normalize()
                        
                        # Skip target span itself
                        if (abs(s_bbox.x0 - r_bbox.x0) < 1.0 and abs(s_bbox.y0 - r_bbox.y0) < 1.0 and
                            abs(s_bbox.x1 - r_bbox.x1) < 1.0 and abs(s_bbox.y1 - r_bbox.y1) < 1.0):
                            continue
                            
                        # Horizontal overlap check
                        h_overlap = (min(safe_x1, s_bbox.x1) - max(safe_x0, s_bbox.x0)) > 2.0
                        s_orig_y = span.get("origin", [0, s_bbox.y1])[1]
                        
                        # Span below target
                        if s_orig_y > origin_y + 2.0:
                            if h_overlap:
                                limit_y1 = s_bbox.y0 - 0.5
                                if limit_y1 < safe_y1:
                                    safe_y1 = max(limit_y1, origin_y + 0.5)
                        # Span above target
                        elif s_orig_y < origin_y - 2.0:
                            if h_overlap:
                                limit_y0 = s_bbox.y1 + 0.5
                                if limit_y0 > safe_y0:
                                    safe_y0 = min(limit_y0, origin_y - 0.5)
                        # Same line: ensure padding doesn't intrude into immediate neighbor text
                        else:
                            if s_bbox.x1 <= r_bbox.x0 + 1.0:
                                safe_x0 = max(safe_x0, s_bbox.x1 + 0.2)
                            elif s_bbox.x0 >= r_bbox.x1 - 1.0:
                                safe_x1 = min(safe_x1, s_bbox.x0 - 0.2)
        except Exception:
            pass
            
        if safe_x1 <= safe_x0:
            safe_x0, safe_x1 = r_bbox.x0, r_bbox.x1
        if safe_y1 <= safe_y0:
            safe_y0, safe_y1 = r_bbox.y0, origin_y + 0.5
            
        return pymupdf.Rect(safe_x0, safe_y0, safe_x1, safe_y1)

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
        Replaces text in a PDF page.
        Eradicates old text operators, covers underlying raster/scanned pixels with
        a matching background patch, and inserts the new compliant text object.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds (total pages: {len(doc)})")
            
        page = doc[page_index]
        derotate = ~page.rotation_matrix
        
        # Sample background color before applying changes
        bg_color = cls.sample_background_color(page, bbox)
        
        # Compute safe redaction rectangle that will NEVER collide with adjacent lines or words
        redact_rect = cls.compute_safe_redact_rect(page, bbox, origin)
        
        # 1. Add redaction annotation and apply to eradicate vector text operators
        page.add_redact_annot(redact_rect, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        
        # 2. If page contains images or is scanned, apply background patch to obliterate scanned/raster glyphs
        if len(page.get_images()) > 0:
            page.draw_rect(redact_rect, color=None, fill=bg_color, overlay=True)
        
        # 3. If new_text is empty or whitespace, this was a deletion
        if not new_text or not new_text.strip():
            page.clean_contents()
            return True
            
        # 4. Resolve typography
        resolved_font = FontManager.resolve_font_name(font_name)
        size = font_size if font_size and font_size > 0 else 11.0
        
        if color_rgb and len(color_rgb) == 3:
            color_tuple = (float(color_rgb[0]), float(color_rgb[1]), float(color_rgb[2]))
        else:
            color_tuple = (0.0, 0.0, 0.0)
            
        r_origin = pymupdf.Point(origin[0], origin[1])
        r_origin.transform(derotate)
            
        # 5. Insert new text object at baseline with correct rotation and overlay
        page.insert_text(
            r_origin,
            new_text,
            fontname=resolved_font,
            fontsize=size,
            color=color_tuple,
            rotate=page.rotation,
            overlay=True
        )
        
        # 6. Consolidate content streams
        page.clean_contents()
        return True

    @classmethod
    def delete_text_span(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        bbox: List[float],
        origin: Optional[List[float]] = None
    ) -> bool:
        """
        Eradicates text inside the bounding box from content stream and conceals
        underlying raster pixels with a clean matching background patch.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        bg_color = cls.sample_background_color(page, bbox)
        
        redact_rect = cls.compute_safe_redact_rect(page, bbox, origin)
        page.add_redact_annot(redact_rect, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        
        # Obliterate old raster/scanned glyphs if page contains images
        if len(page.get_images()) > 0:
            page.draw_rect(redact_rect, color=None, fill=bg_color, overlay=True)
        
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
            color=color_tuple,
            rotate=page.rotation,
            overlay=True
        )
        page.clean_contents()
        return True
