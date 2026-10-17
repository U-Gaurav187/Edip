import pytest
import pymupdf
import io
from PIL import Image
from app.core.image_editor import RealPDFImageEditor

def create_sample_pdf_with_image():
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=500)
    
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    
    page.insert_image(pymupdf.Rect(50, 50, 150, 150), stream=buf.getvalue())
    return doc

def test_image_replacement():
    doc = create_sample_pdf_with_image()
    page = doc[0]
    images = page.get_image_info(xrefs=True)
    assert len(images) == 1
    xref = images[0]["xref"]
    
    # Create red replacement image
    red_img = Image.new("RGB", (200, 200), color="red")
    buf = io.BytesIO()
    red_img.save(buf, format="PNG")
    
    success = RealPDFImageEditor.replace_image(doc, 0, xref, buf.getvalue())
    assert success is True
    
    # Verify XObject was updated
    extracted = doc.extract_image(xref)
    assert extracted["width"] == 200
    assert extracted["height"] == 200

def test_image_deletion():
    doc = create_sample_pdf_with_image()
    page = doc[0]
    images = page.get_image_info(xrefs=True)
    xref = images[0]["xref"]
    
    RealPDFImageEditor.delete_image(doc, 0, xref)
    
    # Verify image Do operator is gone from content streams
    for c_xref in page.get_contents():
        stream_text = doc.xref_stream(c_xref).decode("latin1", errors="ignore")
        assert "Do" not in stream_text
