import pytest
import pymupdf
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def create_sample_pdf_bytes():
    doc = pymupdf.open()
    page1 = doc.new_page(width=612, height=792)
    page1.insert_text((72, 100), "First Page Heading", fontsize=16, fontname="helv")
    page1.insert_text((72, 130), "Some body text here for testing.", fontsize=12, fontname="helv")
    
    page2 = doc.new_page(width=612, height=792)
    page2.insert_text((72, 100), "Second Page Details", fontsize=14, fontname="helv")
    
    buf = doc.tobytes()
    doc.close()
    return buf

def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "MuPDF" in data["engine"]

def test_upload_inspect_and_edit_pipeline():
    pdf_bytes = create_sample_pdf_bytes()
    
    # 1. Upload
    files = {"file": ("test_doc.pdf", pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/documents/upload", files=files)
    assert upload_resp.status_code == 200
    doc_data = upload_resp.json()
    doc_id = doc_data["document_id"]
    assert doc_data["page_count"] == 2
    assert len(doc_data["pages"]) == 2
    
    page0 = doc_data["pages"][0]
    assert len(page0["text_blocks"]) >= 1
    span = page0["text_blocks"][0]["lines"][0]["spans"][0]
    assert span["text"] == "First Page Heading"
    
    # 2. Edit Text
    edit_payload = {
        "page_index": 0,
        "bbox": span["bbox"],
        "origin": span["origin"],
        "new_text": "Updated Master Title",
        "font_name": span["font"],
        "font_size": span["size"],
        "color_rgb": span["color_rgb"]
    }
    edit_resp = client.post(f"/api/documents/{doc_id}/text/edit", json=edit_payload)
    assert edit_resp.status_code == 200
    updated_page = edit_resp.json()
    updated_text = " ".join(
        s["text"]
        for b in updated_page["text_blocks"]
        for l in b["lines"]
        for s in l["spans"]
    )
    assert "Updated Master Title" in updated_text
    assert "First Page Heading" not in updated_text
    
    # 3. Rotate Page
    rot_resp = client.post(f"/api/documents/{doc_id}/pages/rotate", json={
        "page_index": 0,
        "rotation_delta": 90
    })
    assert rot_resp.status_code == 200
    assert rot_resp.json()["details"]["rotation"] == 90
    
    # 4. Render Page
    render_resp = client.get(f"/api/documents/{doc_id}/pages/0/render")
    assert render_resp.status_code == 200
    assert render_resp.headers["content-type"] == "image/png"
    assert len(render_resp.content) > 1000
    
    # 5. Export PDF
    export_resp = client.get(f"/api/documents/{doc_id}/export?format=pdf")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/pdf"
    
    # Open exported PDF and verify directly
    exported_doc = pymupdf.open(stream=export_resp.content, filetype="pdf")
    assert len(exported_doc) == 2
    assert "Updated Master Title" in exported_doc[0].get_text()
    assert "First Page Heading" not in exported_doc[0].get_text()
    exported_doc.close()
    
    # 6. Close session
    close_resp = client.delete(f"/api/documents/{doc_id}")
    assert close_resp.status_code == 200

def test_render_jpeg_and_png_formats():
    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("test_render.pdf", pdf_bytes, "application/pdf")}
    upload_resp = client.post("/api/documents/upload", files=files)
    assert upload_resp.status_code == 200
    doc_id = upload_resp.json()["document_id"]
    
    # 1. Default PNG (backward-compatible)
    resp_png = client.get(f"/api/documents/{doc_id}/pages/0/render")
    assert resp_png.status_code == 200
    assert resp_png.headers["content-type"] == "image/png"
    
    # 2. Fast JPEG for progressive rendering & 0.25s priority stage loading
    resp_jpeg = client.get(f"/api/documents/{doc_id}/pages/0/render?format=jpeg&quality=85&dpi=150")
    assert resp_jpeg.status_code == 200
    assert resp_jpeg.headers["content-type"] == "image/jpeg"
    assert "public, max-age=" in resp_jpeg.headers.get("cache-control", "")
    
    # 3. Low-DPI thumbnail JPEG
    resp_thumb = client.get(f"/api/documents/{doc_id}/pages/0/render?format=jpeg&quality=75&dpi=36")
    assert resp_thumb.status_code == 200
    assert resp_thumb.headers["content-type"] == "image/jpeg"
    assert len(resp_thumb.content) < len(resp_jpeg.content)
    
    client.delete(f"/api/documents/{doc_id}")
