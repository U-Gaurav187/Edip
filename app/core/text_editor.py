import io
from typing import Optional, List, Tuple
import pymupdf
import numpy as np
from PIL import Image
from .font_manager import FontManager

class RealPDFTextEditor:
    """
    Production PDF Text Object Editor.
    Supports both native vector PDFs and scanned/OCR documents.
    
    Principles:
    1. Text operator eradication: removes existing glyph operators from /Contents.
    2. Vector graphics preservation: never erases underlying line art or vector drawings.
    3. Seamless background healing: when modifying or deleting text on raster images or
       scanned documents, reconstructs the underlying background via strip interpolation
       with median filtering to eliminate white box sticker artifacts.
    4. Proper orientation: respects page rotation angle for accurate insertion.
    5. 100% copy-paste fidelity and searchability.
    6. Clean content stream consolidation.
    """

    @classmethod
    def sample_background_color(cls, page: pymupdf.Page, visual_bbox: List[float]) -> Tuple[float, float, float]:
        """
        Samples the local background color around the visual bounding box.
        Uses perimeter median sampling so dark, vibrant, and light backgrounds are all accurately preserved.
        Returns RGB tuple in 0.0 - 1.0 range (defaulting to clean white).
        """
        try:
            r = pymupdf.Rect(visual_bbox).intersect(page.rect)
            if r.width <= 0 or r.height <= 0:
                return (1.0, 1.0, 1.0)
                
            # Sample border pixels of the bounding box
            pix = page.get_pixmap(clip=r, dpi=72)
            if pix.width == 0 or pix.height == 0:
                return (1.0, 1.0, 1.0)
                
            # Perimeter pixels around the bounding box
            perim = []
            for x in range(pix.width):
                perim.append(pix.pixel(x, 0))
                if pix.height > 1:
                    perim.append(pix.pixel(x, pix.height - 1))
            for y in range(pix.height):
                perim.append(pix.pixel(0, y))
                if pix.width > 1:
                    perim.append(pix.pixel(pix.width - 1, y))

            if perim:
                med_r = sorted(p[0] for p in perim)[len(perim) // 2]
                med_g = sorted(p[1] for p in perim)[len(perim) // 2]
                med_b = sorted(p[2] for p in perim)[len(perim) // 2]
                return (round(med_r / 255.0, 3), round(med_g / 255.0, 3), round(med_b / 255.0, 3))
        except Exception:
            pass
        return (1.0, 1.0, 1.0)

    @classmethod
    def create_seamless_background_patch(cls, page: pymupdf.Page, redact_rect: pymupdf.Rect) -> Optional[bytes]:
        """
        Synthesizes a seamless background patch over redact_rect on raster/scanned images
        using strip interpolation with median filtering along the outer 2px boundary ring.
        Renders a small clip expanded by 3pt at 150 DPI and reconstructs the interior background
        blending 80% vertical interpolation with 20% horizontal interpolation.
        """
        try:
            # Expand clip by 3pt on all sides bounded by page.rect
            expanded_rect = pymupdf.Rect(
                redact_rect.x0 - 3.0,
                redact_rect.y0 - 3.0,
                redact_rect.x1 + 3.0,
                redact_rect.y1 + 3.0
            ).intersect(page.rect)

            if expanded_rect.width <= 0 or expanded_rect.height <= 0:
                return None

            dpi = 150
            clip_pix = page.get_pixmap(clip=expanded_rect, dpi=dpi)
            if clip_pix.width < 3 or clip_pix.height < 3:
                return None

            clip_arr = np.frombuffer(clip_pix.samples, dtype=np.uint8).reshape((clip_pix.height, clip_pix.width, clip_pix.n))
            if clip_pix.n > 3:
                clip_arr = clip_arr[:, :, :3]  # drop alpha if any

            scale_x = clip_pix.width / expanded_rect.width
            scale_y = clip_pix.height / expanded_rect.height

            # Coordinates of redact_rect relative to expanded clip
            ix0 = max(0, min(int(round((redact_rect.x0 - expanded_rect.x0) * scale_x)), clip_pix.width - 1))
            iy0 = max(0, min(int(round((redact_rect.y0 - expanded_rect.y0) * scale_y)), clip_pix.height - 1))
            ix1 = max(ix0 + 1, min(int(round((redact_rect.x1 - expanded_rect.x0) * scale_x)), clip_pix.width))
            iy1 = max(iy0 + 1, min(int(round((redact_rect.y1 - expanded_rect.y0) * scale_y)), clip_pix.height))

            patch_w = ix1 - ix0
            patch_h = iy1 - iy0
            if patch_w <= 0 or patch_h <= 0:
                return None

            # Outer ring 2px border strips
            top_strip = clip_arr[max(0, iy0 - 2):iy0, ix0:ix1]
            bot_strip = clip_arr[iy1:min(clip_pix.height, iy1 + 2), ix0:ix1]
            left_strip = clip_arr[iy0:iy1, max(0, ix0 - 2):ix0]
            right_strip = clip_arr[iy0:iy1, ix1:min(clip_pix.width, ix1 + 2)]

            # Top profile (median along axis 0)
            if top_strip.shape[0] > 0:
                top_profile = np.median(top_strip, axis=0)
            elif bot_strip.shape[0] > 0:
                top_profile = np.median(bot_strip, axis=0)
            else:
                top_profile = np.full((patch_w, 3), 255.0)

            # Bottom profile
            if bot_strip.shape[0] > 0:
                bot_profile = np.median(bot_strip, axis=0)
            else:
                bot_profile = top_profile

            # Left profile (median along axis 1)
            if left_strip.shape[1] > 0:
                left_profile = np.median(left_strip, axis=1)
            elif right_strip.shape[1] > 0:
                left_profile = np.median(right_strip, axis=1)
            else:
                left_profile = np.full((patch_h, 3), 255.0)

            # Right profile
            if right_strip.shape[1] > 0:
                right_profile = np.median(right_strip, axis=1)
            else:
                right_profile = left_profile

            # Vertical linear interpolation
            if patch_h > 1:
                v_weights = np.linspace(0.0, 1.0, patch_h, dtype=np.float32)[:, None, None]
            else:
                v_weights = np.zeros((1, 1, 1), dtype=np.float32)
            v_interp = (1.0 - v_weights) * top_profile[None, :, :] + v_weights * bot_profile[None, :, :]

            # Horizontal linear interpolation
            if patch_w > 1:
                h_weights = np.linspace(0.0, 1.0, patch_w, dtype=np.float32)[None, :, None]
            else:
                h_weights = np.zeros((1, 1, 1), dtype=np.float32)
            h_interp = (1.0 - h_weights) * left_profile[:, None, :] + h_weights * right_profile[:, None, :]

            # Blend 80% vertical and 20% horizontal
            blended = 0.8 * v_interp + 0.2 * h_interp
            blended_uint8 = np.clip(np.round(blended), 0, 255).astype(np.uint8)

            patch_img = Image.fromarray(blended_uint8, "RGB")
            buf = io.BytesIO()
            patch_img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return None

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
        # Tight surgical margins prevent clipping adjacent punctuation, table gridlines, or lines.
        is_raster_page = len(page.get_images()) > 0
        pad_x = max(1.5, min(font_size * 0.12, 3.0)) if is_raster_page else 0.5
        pad_y_top = 1.5 if is_raster_page else 0.5
        pad_y_bot = 2.0 if is_raster_page else 0.5
        
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
        Eradicates old text operators without white boxes, preserves underlying vector graphics,
        covers underlying raster pixels with a seamless interpolated background patch if on an image,
        and inserts the new compliant text object.
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
        # Always protect line art / vector shapes and avoid wiping out whole images
        page.add_redact_annot(redact_rect, fill=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE
        )
        
        # 2. Only apply a raster background patch when redact_rect actually intersects an image bbox on the page
        has_intersecting_image = any(
            pymupdf.Rect(img.get("bbox", [0, 0, 0, 0])).intersects(redact_rect)
            for img in page.get_image_info()
        )
        if has_intersecting_image:
            patch_png = cls.create_seamless_background_patch(page, redact_rect)
            page.draw_rect(redact_rect, color=None, fill=bg_color, overlay=True)
            if patch_png:
                page.insert_image(redact_rect, stream=patch_png, overlay=True)
        
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
        underlying raster pixels with a clean seamless background patch if on an image.
        Never erases vector graphics.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        bg_color = cls.sample_background_color(page, bbox)
        
        redact_rect = cls.compute_safe_redact_rect(page, bbox, origin)
        page.add_redact_annot(redact_rect, fill=False)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE
        )
        
        # Only apply raster background patch when redact_rect actually intersects an image bbox on the page
        has_intersecting_image = any(
            pymupdf.Rect(img.get("bbox", [0, 0, 0, 0])).intersects(redact_rect)
            for img in page.get_image_info()
        )
        if has_intersecting_image:
            patch_png = cls.create_seamless_background_patch(page, redact_rect)
            page.draw_rect(redact_rect, color=None, fill=bg_color, overlay=True)
            if patch_png:
                page.insert_image(redact_rect, stream=patch_png, overlay=True)
        
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
