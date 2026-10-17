import json
from pathlib import Path
from typing import List, Optional
import pymupdf
from ..config import settings

class RealPDFOCREngine:
    """
    Production OCR Engine using MuPDF's native C Tesseract engine.
    Detects scanned pages and constructs clean searchable/editable text layers.
    """

    @classmethod
    def is_page_scanned(cls, page: pymupdf.Page) -> bool:
        """
        Determines whether a page is primarily a scanned image.
        Criteria:
        1. Low native text content (< 40 characters)
        2. At least one image occupies >= 60% of page area
        """
        text = page.get_text().strip()
        if len(text) > 40:
            return False

        page_area = page.rect.width * page.rect.height
        if page_area <= 0:
            return False

        images = page.get_image_info()
        for img in images:
            bbox = pymupdf.Rect(img.get("bbox", [0, 0, 0, 0]))
            img_area = bbox.width * bbox.height
            if (img_area / page_area) >= 0.60:
                return True

        return len(text) == 0 and len(images) > 0

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
        Returns the number of text spans injected.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")

        page = doc[page_index]
        tessdata_path = str(settings.TESSDATA_DIR)

        try:
            tp = page.get_textpage_ocr(tessdata=tessdata_path, language=language)
            ocr_data = json.loads(tp.extractJSON())
        except Exception as e:
            raise RuntimeError(f"OCR execution failed: {str(e)}")

        injected_spans = 0
        for block in ocr_data.get("blocks", []):
            for line in block.get("lines", []):
                raw_spans = line.get("spans", [])
                merged_words = []
                cur_word = None
                for s in raw_spans:
                    raw_text = s.get("text", "")
                    if not raw_text or raw_text.isspace():
                        if cur_word:
                            merged_words.append(cur_word)
                            cur_word = None
                        continue

                    has_leading_space = raw_text.startswith(" ")
                    has_trailing_space = raw_text.endswith(" ")
                    clean_text = raw_text.strip()

                    if has_leading_space and cur_word:
                        merged_words.append(cur_word)
                        cur_word = None

                    if cur_word is None:
                        cur_word = {
                            "text": clean_text,
                            "bbox": list(s["bbox"]),
                            "origin": s.get("origin", [s["bbox"][0], s["bbox"][3]]),
                            "size": s.get("size", 10.0),
                            "flags": s.get("flags", 0)
                        }
                    else:
                        cur_word["text"] += clean_text
                        cur_word["bbox"][2] = s["bbox"][2]
                        cur_word["bbox"][3] = max(cur_word["bbox"][3], s["bbox"][3])

                    if has_trailing_space:
                        merged_words.append(cur_word)
                        cur_word = None

                if cur_word:
                    merged_words.append(cur_word)

                for word in merged_words:
                    text = word["text"].strip()
                    if not text:
                        continue
                    origin = word["origin"]
                    size = word["size"]
                    w_bbox = pymupdf.Rect(word["bbox"])

                    # Auto-detect bold font from ink density in the scanned image
                    is_bold = bool(word.get("flags", 0) & 16)
                    if not is_bold and w_bbox.width > 0 and w_bbox.height > 0:
                        try:
                            clip = page.get_pixmap(clip=w_bbox.intersect(page.rect))
                            if clip.width > 0 and clip.height > 0:
                                total_pixels = clip.width * clip.height
                                dark_count = 0
                                for cy in range(clip.height):
                                    for cx in range(clip.width):
                                        px = clip.pixel(cx, cy)
                                        lum = 0.299 * px[0] + 0.587 * px[1] + 0.114 * px[2]
                                        if lum < 175:
                                            dark_count += 1
                                if (dark_count / total_pixels) >= 0.18:
                                    is_bold = True
                        except Exception:
                            pass

                    font_name = "hebo" if is_bold else "helv"
                    if origin and len(origin) == 2:
                        page.insert_text(
                            pymupdf.Point(origin[0], origin[1]),
                            text,
                            fontname=font_name,
                            fontsize=max(size, 6.0),
                            render_mode=3  # PDF standard invisible searchable text layer
                        )
                        injected_spans += 1

        if injected_spans > 0:
            page.clean_contents()

        return injected_spans
