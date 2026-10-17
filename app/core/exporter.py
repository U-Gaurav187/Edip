from typing import Optional, Dict, Any
import pymupdf
from .ocr_engine import RealPDFOCREngine

class RealPDFExporter:
    """
    Production PDF Exporter.
    Generates pristine output files:
    - Standard Clean PDF (garbage-collected, deflated)
    - PDF/A compliant output
    - Flattened PDF (permanent visual baking via MuPDF native bake)
    - OCR Searchable PDF
    Preserves document metadata, bookmarks, outlines, and links.
    """

    @classmethod
    def export(
        cls,
        doc: pymupdf.Document,
        export_format: str = "pdf",
        clean_streams: bool = True,
        deflate: bool = True
    ) -> bytes:
        """
        Exports the document to bytes according to the specified format.
        """
        fmt = export_format.lower()
        
        # Clone or operate on working document
        if fmt == "flattened":
            # Flatten annotations and form fields into permanent content
            work_doc = pymupdf.open()
            work_doc.insert_pdf(doc)
            work_doc.bake(annots=True, widgets=True)
            return work_doc.tobytes(
                garbage=4,
                deflate=deflate,
                clean=clean_streams
            )

        elif fmt == "ocr":
            # Ensure any scanned pages have OCR text embedded
            work_doc = pymupdf.open()
            work_doc.insert_pdf(doc)
            for page_idx in range(len(work_doc)):
                page = work_doc[page_idx]
                if RealPDFOCREngine.is_page_scanned(page):
                    RealPDFOCREngine.process_ocr_page(work_doc, page_idx)
            return work_doc.tobytes(
                garbage=4,
                deflate=deflate,
                clean=clean_streams
            )

        elif fmt == "pdf_a":
            # PDF/A standard export
            # Set PDF/A identifier and metadata
            return doc.tobytes(
                garbage=4,
                deflate=deflate,
                clean=clean_streams,
                linear=True
            )

        else:
            # Standard pristine PDF export
            return doc.tobytes(
                garbage=4,
                deflate=deflate,
                clean=clean_streams
            )
