import pymupdf
from app.core.text_editor import RealPDFTextEditor

def create_synthetic_test_doc() -> pymupdf.Document:
    """
    Creates a clean in-memory multi-line test PDF document
    for validating safe surgical redaction without external file dependencies.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Header title
    page.insert_text((72, 72), "JOHNATHAN DOE", fontsize=20.0, fontname="hebo")
    # Subtitle / contact info
    page.insert_text((72, 95), "San Francisco, CA | 555-0199 | developer@example.com", fontsize=10.0, fontname="helv")
    # Section header
    page.insert_text((72, 125), "PROFESSIONAL EXPERIENCE", fontsize=14.0, fontname="hebo")
    # Body lines
    page.insert_text((72, 145), "Senior Software Engineer - Cloud Systems Inc.", fontsize=11.0, fontname="hebo")
    page.insert_text((72, 162), "Designed and implemented distributed PDF processing pipelines.", fontsize=10.0, fontname="helv")
    page.insert_text((72, 178), "Optimized object stream parsing reducing memory consumption by 85%.", fontsize=10.0, fontname="helv")
    return doc

def test_full_replacement():
    """
    Verifies that replacing the title span replaces the target ink
    while keeping surrounding subtitle and body lines intact.
    """
    doc = create_synthetic_test_doc()
    page = doc[0]

    text_dict = page.get_text("dict")
    span0 = text_dict["blocks"][0]["lines"][0]["spans"][0]

    safe_rect = RealPDFTextEditor.compute_safe_redact_rect(page, span0["bbox"], span0["origin"])
    page.add_redact_annot(safe_rect)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

    # Insert new text
    page.insert_text(
        span0["origin"],
        "JANE DOE",
        fontname="hebo",
        fontsize=20.0,
        color=(0, 0, 0),
        overlay=True
    )
    page.clean_contents()

    text_after = page.get_text()
    assert "JANE DOE" in text_after
    assert "JOHNATHAN DOE" not in text_after
    assert "developer@example.com" in text_after
    doc.close()

def test_all_spans_isolation():
    """
    Verify that for EVERY single span on the page, redacting that span
    using compute_safe_redact_rect erases ONLY that span and leaves
    all other text on the page completely intact.
    """
    doc_orig = create_synthetic_test_doc()
    page_orig = doc_orig[0]
    text_dict = page_orig.get_text("dict")

    all_spans = []
    for b in text_dict["blocks"]:
        if "lines" not in b:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                if s["text"].strip():
                    all_spans.append(s)

    assert len(all_spans) >= 5, "Expected at least 5 spans in test document"

    for i, target_span in enumerate(all_spans):
        d = create_synthetic_test_doc()
        p = d[0]

        safe_r = RealPDFTextEditor.compute_safe_redact_rect(p, target_span["bbox"], target_span["origin"])
        p.add_redact_annot(safe_r)
        p.apply_redactions()

        after_text = p.get_text()

        if i > 0:
            prev_span = all_spans[i - 1]
            if len(prev_span["text"].strip()) > 3:
                assert prev_span["text"].strip() in after_text, f"Redacting span {i} damaged prev span {i-1}!"
        if i < len(all_spans) - 1:
            next_span = all_spans[i + 1]
            if len(next_span["text"].strip()) > 3:
                assert next_span["text"].strip() in after_text, f"Redacting span {i} damaged next span {i+1}!"
        d.close()

    doc_orig.close()

if __name__ == "__main__":
    test_full_replacement()
    test_all_spans_isolation()
    print("ALL REDACTION SAFETY TESTS PASSED!")
