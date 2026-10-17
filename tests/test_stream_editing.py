import pytest
import pymupdf
import json
from app.core.text_editor import RealPDFTextEditor

def test_surgical_text_editing_no_white_rectangles():
    # 1. Create a pristine test document with known text
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Confidential Contract 2024", fontsize=14, fontname="helv")
    page.insert_text((72, 140), "Signature Required Below", fontsize=12, fontname="helv")
    
    # Verify initial text presence
    initial_text = page.get_text()
    assert "Confidential Contract 2024" in initial_text
    
    # 2. Inspect content stream before edit
    c_xrefs = page.get_contents()
    stream_before = doc.xref_stream(c_xrefs[0]).decode('latin1', errors='ignore')
    
    # 3. Target the text span
    blocks = json.loads(page.get_text("json"))["blocks"]
    target_span = blocks[0]["lines"][0]["spans"][0]
    bbox = target_span["bbox"]
    origin = target_span["origin"]
    
    # 4. Perform surgical replacement
    success = RealPDFTextEditor.edit_text_span(
        doc=doc,
        page_index=0,
        bbox=bbox,
        origin=origin,
        new_text="Public Agreement 2026",
        font_name="helv",
        font_size=14.0,
        color_rgb=[0.0, 0.0, 0.0]
    )
    assert success is True
    
    # 5. Verify text after edit
    final_text = page.get_text()
    assert "Public Agreement 2026" in final_text
    assert "Confidential Contract 2024" not in final_text, "Old text must NOT remain hidden in document"
    
    # 6. Verify Content Stream properties:
    stream_after = "".join(doc.xref_stream(x).decode('latin1', errors='ignore') for x in page.get_contents())
    
    # Old text string must not be in the stream
    assert "Confidential" not in stream_after
    assert "Public Agreement 2026" in stream_after
    
    # Verify NO white rectangle operator was placed to mask text
    # In PDF, white rectangles look like: '1 1 1 rg ... re f' or '1 g ... re f'
    assert "1 1 1 rg" not in stream_after
    assert "1 g" not in stream_after

def test_surgical_text_deletion():
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 100), "Delete This Secret Line", fontsize=12, fontname="helv")
    page.insert_text((72, 130), "Keep This Normal Line", fontsize=12, fontname="helv")
    
    blocks = json.loads(page.get_text("json"))["blocks"]
    target_span = blocks[0]["lines"][0]["spans"][0]
    
    RealPDFTextEditor.delete_text_span(doc, 0, target_span["bbox"])
    
    text_after = page.get_text()
    assert "Delete This Secret Line" not in text_after
    assert "Keep This Normal Line" in text_after
