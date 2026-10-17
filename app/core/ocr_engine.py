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
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    origin = span.get("origin")
                    size = span.get("size", 10.0)
                    if origin and len(origin) == 2:
                        page.insert_text(
                            pymupdf.Point(origin[0], origin[1]),
                            text,
                            fontname="helv",
                            fontsize=max(size, 6.0),
                            render_mode=3  # PDF standard invisible searchable text layer
                        )
                        injected_spans += 1

        if injected_spans > 0:
            page.clean_contents()

        return injected_spans
