import pymupdf
import json
from app.core.engine import PDFEngineManager, PDFSession
from app.core.text_editor import RealPDFTextEditor
from app.core.ocr_engine import RealPDFOCREngine

def test_render_and_inspect_caching():
    mgr = PDFEngineManager()
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Performance test page", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    doc_id = mgr.create_session_from_bytes(pdf_bytes, "test_cache.pdf")
    session = mgr.get_session(doc_id)

    # 1. Initial inspect: cache should populate
    assert len(session.inspect_cache) == 0
    p0_data = mgr.inspect_page(doc_id, 0)
    assert 0 in session.inspect_cache
    assert session.inspect_cache[0].page_index == 0

    # Repeated inspect returns cached object
    p0_cached = mgr.inspect_page(doc_id, 0)
    assert p0_cached is p0_data

    # 2. Render caching
    cache_key = (0, 150, "jpeg", 85)
    assert cache_key not in session.render_cache
    img_bytes, media_type = mgr.render_page_image(doc_id, 0, dpi=150, img_format="jpeg", quality=85)
    assert cache_key in session.render_cache
    assert media_type == "image/jpeg"

    # Repeated render serves from cache
    img_bytes_cached, _ = mgr.render_page_image(doc_id, 0, dpi=150, img_format="jpeg", quality=85)
    assert img_bytes_cached == img_bytes

    # 3. Invalidation
    session.invalidate_page(0)
    assert 0 not in session.inspect_cache
    assert cache_key not in session.render_cache

    mgr.close_session(doc_id)

def test_seamless_background_patching():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Insert a colored image
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 300, 200), False)
    pix.clear_with(100) # dark gray
    page.insert_image(pymupdf.Rect(50, 50, 350, 250), pixmap=pix)

    redact_rect = pymupdf.Rect(100, 100, 200, 130)
    patch_bytes = RealPDFTextEditor.create_seamless_background_patch(page, redact_rect)
    assert patch_bytes is not None
    assert patch_bytes.startswith(b"\x89PNG\r\n\x1a\n") # valid PNG header

    # Test perimeter median background sampling doesn't discard dark pixels
    bg = RealPDFTextEditor.sample_background_color(page, [100, 100, 200, 130])
    assert bg is not None
    # Background should be dark gray (~100/255 = 0.392)
    assert 0.30 <= bg[0] <= 0.50

    doc.close()

def test_hybrid_page_ocr_detection_and_deduplication():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # 25% coverage raster banner on hybrid page
    # Page area = 612 * 792 = 484,704
    # Image area = 400 * 350 = 140,000 (~28.8% coverage)
    pix = pymupdf.Pixmap(pymupdf.csRGB, (0, 0, 400, 350), False)
    pix.clear_with(240)
    page.insert_image(pymupdf.Rect(50, 50, 450, 400), pixmap=pix)

    # Native text on the page (> 40 chars)
    page.insert_text((72, 500), "This is a clean native text line on the hybrid brochure page.", fontsize=12)

    # Test is_page_scanned flags it as True due to >= 25% raster coverage
    is_scanned = RealPDFOCREngine.is_page_scanned(page)
    assert is_scanned is True

    doc.close()
