import json
import re
from pathlib import Path
from typing import List, Optional
import pymupdf
from ..config import settings

class RealPDFOCREngine:
    """
    Production OCR Engine using MuPDF's native C Tesseract engine.
    Detects scanned pages and constructs clean searchable/editable text layers.
    Includes phrase grouping, native text deduplication, and true foreground ink color extraction.
    """

    @classmethod
    def is_page_scanned(
        cls,
        page: pymupdf.Page,
        text_blocks: Optional[List] = None,
        img_infos: Optional[List] = None
    ) -> bool:
        """
        Determines whether a page is a scanned document or hybrid brochure page.
        Criteria:
        1. Low native text content (< 40 characters) and dominant image (>= 60% area)
        2. OR any raster image covering >= 25% of the page area (hybrid brochure pages).
        Reuses pre-extracted text_blocks and img_infos when supplied.
        """
        page_area = page.rect.width * page.rect.height
        if page_area <= 0:
            return False

        images = img_infos if img_infos is not None else page.get_image_info()
        has_large_image = False
        has_dominant_scan = False
        for img in images:
            bbox = pymupdf.Rect(img.get("bbox", [0, 0, 0, 0]))
            img_area = bbox.width * bbox.height
            coverage = img_area / page_area
            if coverage >= 0.25:
                has_large_image = True
            if coverage >= 0.60:
                has_dominant_scan = True

        if text_blocks is not None:
            text_len = sum(
                len(span.text.strip())
                for b in text_blocks
                for l in getattr(b, "lines", [])
                for span in getattr(l, "spans", [])
            )
        else:
            text_len = len(page.get_text().strip())

        if has_large_image:
            return True

        if text_len <= 40 and has_dominant_scan:
            return True

        return text_len == 0 and len(images) > 0

    @classmethod
    def process_ocr_page(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        language: str = "eng"
    ) -> int:
        """
        Runs OCR on the given page and injects a real searchable text layer (render_mode 3)
        into the page's /Contents stream.
        Deduplicates against native text, groups words into coherent editable phrases,
        and samples the true ink color and boldness from the page raster.
        Returns the number of text spans injected.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")

        page = doc[page_index]
        tessdata_path = str(settings.TESSDATA_DIR)

        # 1. Remove existing invisible OCR text layer (render_mode 3) from content stream
        # so repeat OCR scans never duplicate or pile up phantom text blocks
        try:
            page.clean_contents()
            contents = page.get_contents()
            if contents:
                xref = contents[0]
                stream = page.read_contents().decode('latin1', errors='ignore')
                if "3 Tr" in stream:
                    pattern = re.compile(r'q\s*(?:(?!q\b).)*?3\s+Tr.*?ET\s*Q\s*', re.DOTALL)
                    cleaned_stream = pattern.sub('', stream)
                    doc.update_stream(xref, cleaned_stream.encode('latin1'))
                    page.clean_contents()
        except Exception:
            pass

        # 2. Record existing native (non-OCR) vector text span bboxes for deduplication
        native_span_rects: List[pymupdf.Rect] = []
        try:
            td = page.get_text("dict")
            for b in td.get("blocks", []):
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        if s.get("text", "").strip():
                            r = pymupdf.Rect(s["bbox"]).normalize()
                            if r.width > 0 and r.height > 0:
                                native_span_rects.append(r)
        except Exception:
            pass

        # 3. Full-Page 150-DPI OCR
        try:
            tp = page.get_textpage_ocr(tessdata=tessdata_path, language=language, dpi=150, full=True)
            ocr_data = json.loads(tp.extractJSON())
        except Exception:
            try:
                tp = page.get_textpage_ocr(tessdata=tessdata_path, language=language, dpi=150, full=False)
                ocr_data = json.loads(tp.extractJSON())
            except Exception as e:
                raise RuntimeError(f"OCR execution failed: {str(e)}")

        # 4. Render ONE single page pixmap before looping over OCR text to sample true ink and background
        try:
            page_pix = page.get_pixmap(dpi=72)
            pix_w, pix_h = page_pix.width, page_pix.height
            scale_x = pix_w / max(page.rect.width, 1.0)
            scale_y = pix_h / max(page.rect.height, 1.0)
        except Exception:
            page_pix = None
            scale_x = scale_y = 1.0

        injected_spans = 0

        for block in ocr_data.get("blocks", []):
            for line in block.get("lines", []):
                raw_spans = line.get("spans", [])
                words_list = []
                cur_word = None
                for s in raw_spans:
                    raw_text = s.get("text", "")
                    if not raw_text or raw_text.isspace():
                        if cur_word:
                            words_list.append(cur_word)
                            cur_word = None
                        continue

                    has_leading = raw_text.startswith(" ")
                    has_trailing = raw_text.endswith(" ")
                    clean = raw_text.strip()

                    if has_leading and cur_word:
                        words_list.append(cur_word)
                        cur_word = None

                    if cur_word is None:
                        cur_word = {
                            "text": clean,
                            "bbox": list(s["bbox"]),
                            "origin": s.get("origin", [s["bbox"][0], s["bbox"][3]]),
                            "size": s.get("size", 10.0),
                            "flags": s.get("flags", 0)
                        }
                    else:
                        cur_word["text"] += clean
                        cur_word["bbox"][2] = s["bbox"][2]
                        cur_word["bbox"][3] = max(cur_word["bbox"][3], s["bbox"][3])

                    if has_trailing:
                        words_list.append(cur_word)
                        cur_word = None

                if cur_word:
                    words_list.append(cur_word)

                # Skip words that overlap with existing native vector text (> 45% overlap)
                filtered_words = []
                for w in words_list:
                    w_box = pymupdf.Rect(w["bbox"])
                    w_area = w_box.width * w_box.height
                    if w_area <= 0:
                        continue
                    is_dup = False
                    for n_box in native_span_rects:
                        if w_box.intersects(n_box):
                            inter = w_box.intersect(n_box)
                            if (inter.width * inter.height) / w_area > 0.45:
                                is_dup = True
                                break
                    if not is_dup:
                        filtered_words.append(w)

                if not filtered_words:
                    continue

                # Group adjacent OCR words into coherent editable phrases/lines
                phrases = []
                current_phrase = None
                for w in filtered_words:
                    if current_phrase is None:
                        current_phrase = {
                            "text": w["text"],
                            "bbox": list(w["bbox"]),
                            "origin": list(w["origin"]),
                            "size": w["size"],
                            "flags": w["flags"]
                        }
                    else:
                        prev_origin_y = current_phrase["origin"][1]
                        curr_origin_y = w["origin"][1]
                        baseline_diff = abs(prev_origin_y - curr_origin_y)
                        size_ratio = abs(current_phrase["size"] - w["size"]) / max(current_phrase["size"], w["size"], 1.0)
                        h_gap = w["bbox"][0] - current_phrase["bbox"][2]
                        max_gap = max(current_phrase["size"] * 1.4, 14.0)

                        if baseline_diff <= 3.0 and size_ratio <= 0.25 and -2.0 <= h_gap < max_gap:
                            # Merge into current phrase
                            current_phrase["text"] += " " + w["text"]
                            current_phrase["bbox"][2] = max(current_phrase["bbox"][2], w["bbox"][2])
                            current_phrase["bbox"][3] = max(current_phrase["bbox"][3], w["bbox"][3])
                            current_phrase["bbox"][1] = min(current_phrase["bbox"][1], w["bbox"][1])
                            current_phrase["flags"] |= w.get("flags", 0)
                        else:
                            phrases.append(current_phrase)
                            current_phrase = {
                                "text": w["text"],
                                "bbox": list(w["bbox"]),
                                "origin": list(w["origin"]),
                                "size": w["size"],
                                "flags": w["flags"]
                            }
                if current_phrase:
                    phrases.append(current_phrase)

                # Process each phrase
                for phrase in phrases:
                    p_text = phrase["text"].strip()
                    if not p_text:
                        continue
                    p_origin = phrase["origin"]
                    p_size = phrase["size"]
                    w_bbox = pymupdf.Rect(phrase["bbox"])

                    # Extract foreground color and boldness from page_pix
                    detected_rgb = (0.0, 0.0, 0.0)
                    is_bold = bool(phrase.get("flags", 0) & 16)

                    if page_pix and w_bbox.width > 0 and w_bbox.height > 0:
                        try:
                            bx0 = max(0, min(int(round(w_bbox.x0 * scale_x)), pix_w - 1))
                            by0 = max(0, min(int(round(w_bbox.y0 * scale_y)), pix_h - 1))
                            bx1 = max(bx0 + 1, min(int(round(w_bbox.x1 * scale_x)), pix_w))
                            by1 = max(by0 + 1, min(int(round(w_bbox.y1 * scale_y)), pix_h))

                            # Perimeter pixels for background RGB
                            perim = []
                            for cx in range(bx0, bx1):
                                perim.append(page_pix.pixel(cx, by0))
                                if by1 - 1 > by0:
                                    perim.append(page_pix.pixel(cx, by1 - 1))
                            for cy in range(by0, by1):
                                perim.append(page_pix.pixel(bx0, cy))
                                if bx1 - 1 > bx0:
                                    perim.append(page_pix.pixel(bx1 - 1, cy))

                            if perim:
                                bg_r = sorted(p[0] for p in perim)[len(perim) // 2]
                                bg_g = sorted(p[1] for p in perim)[len(perim) // 2]
                                bg_b = sorted(p[2] for p in perim)[len(perim) // 2]
                                bg_lum = 0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b
                            else:
                                bg_r, bg_g, bg_b, bg_lum = 255, 255, 255, 255.0

                            # Interior ink pixels with high contrast against background
                            interior_pixels = []
                            for cy in range(by0 + 1, by1 - 1):
                                for cx in range(bx0 + 1, bx1 - 1):
                                    px = page_pix.pixel(cx, cy)
                                    lum = 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]
                                    diff = abs(lum - bg_lum)
                                    interior_pixels.append((diff, px))

                            if interior_pixels:
                                interior_pixels.sort(key=lambda item: item[0], reverse=True)
                                # Top 25% highest contrast pixels representing ink strokes
                                ink_sample_size = max(1, len(interior_pixels) // 4)
                                ink_samples = [item[1] for item in interior_pixels[:ink_sample_size] if item[0] > 30]

                                if ink_samples:
                                    ink_r = sorted(p[0] for p in ink_samples)[len(ink_samples) // 2]
                                    ink_g = sorted(p[1] for p in ink_samples)[len(ink_samples) // 2]
                                    ink_b = sorted(p[2] for p in ink_samples)[len(ink_samples) // 2]
                                    detected_rgb = (round(ink_r / 255.0, 3), round(ink_g / 255.0, 3), round(ink_b / 255.0, 3))
                                    # Boldness check based on glyph stroke pixel density
                                    if len(ink_samples) / max(len(interior_pixels), 1) >= 0.22:
                                        is_bold = True
                                elif bg_lum < 120:
                                    # Dark background fallback: light text
                                    detected_rgb = (1.0, 1.0, 1.0)
                        except Exception:
                            pass

                    # Calibrate font size against visual glyph height
                    visual_height = w_bbox.height
                    calibrated_size = round(visual_height * 0.82, 1)
                    if abs(p_size - calibrated_size) / max(p_size, 1.0) > 0.25:
                        final_fontsize = max(calibrated_size, 6.0)
                    else:
                        final_fontsize = max(round(p_size, 1), 6.0)

                    font_name = "hebo" if is_bold else "helv"
                    if p_origin and len(p_origin) == 2:
                        page.insert_text(
                            pymupdf.Point(p_origin[0], p_origin[1]),
                            p_text,
                            fontname=font_name,
                            fontsize=final_fontsize,
                            color=detected_rgb,
                            render_mode=3
                        )
                        injected_spans += 1

        if injected_spans > 0:
            page.clean_contents()

        return injected_spans
