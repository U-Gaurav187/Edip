import pytest
import pymupdf
import io
from PIL import Image, ImageDraw
from app.core.ocr_engine import RealPDFOCREngine

def test_ocr_scanned_page_detection_and_text_injection():
    # 1. Create a scanned image page
    img = Image.new("RGB", (600, 300), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((60, 80), "PURCHASE ORDER NUMBER 98765", fill="black")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=300)
    page.insert_image(page.rect, stream=buf.getvalue())
    
    # 2. Check scanned page detection
    assert RealPDFOCREngine.is_page_scanned(page) is True
    assert len(page.get_text().strip()) == 0
    
    # 3. Run OCR
    injected_count = RealPDFOCREngine.process_ocr_page(doc, 0, language="eng")
    assert injected_count > 0
    
    # 4. Verify text is now searchable in PDF
    text_after = page.get_text()
    assert "PURCHASE" in text_after or "ORDER" in text_after or "98765" in text_after
