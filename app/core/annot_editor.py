from typing import List, Optional, Dict, Any
import pymupdf

class RealPDFAnnotEditor:
    """
    Manages PDF Annotation dictionary objects (/Annots).
    Annotations are kept separate from the page content stream to ensure
    real editing and markup remain decoupled.
    """

    @classmethod
    def get_page_annotations(cls, page: pymupdf.Page) -> List[Dict[str, Any]]:
        """
        Retrieves all non-widget annotations on a page.
        """
        results = []
        for annot in page.annots():
            # Exclude widget annotations (which belong to AcroForms)
            if annot.type[1] == "Widget":
                continue

            info = annot.info
            colors = annot.colors
            stroke_col = colors.get("stroke", [1.0, 1.0, 0.0])
            
            results.append({
                "id": annot.xref,
                "type": annot.type[1],
                "rect": [annot.rect.x0, annot.rect.y0, annot.rect.x1, annot.rect.y1],
                "color": stroke_col if stroke_col else [1.0, 1.0, 0.0],
                "content": info.get("content", ""),
                "author": info.get("title", ""),
                "mod_date": info.get("modDate", "")
            })
        return results

    @classmethod
    def add_annotation(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        annot_type: str,
        rect: List[float],
        color: Optional[List[float]] = None,
        content: Optional[str] = None,
        points: Optional[List[List[float]]] = None
    ) -> int:
        """
        Adds a genuine PDF annotation object to the page.
        Returns the annotation xref.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")

        page = doc[page_index]
        stroke_color = color if color and len(color) == 3 else [1.0, 0.9, 0.0]
        pdf_rect = pymupdf.Rect(rect)
        annot = None

        atype = annot_type.lower()
        if atype == "highlight":
            annot = page.add_highlight_annot(pdf_rect)
        elif atype == "underline":
            annot = page.add_underline_annot(pdf_rect)
        elif atype == "strikeout":
            annot = page.add_strikeout_annot(pdf_rect)
        elif atype == "text":
            annot = page.add_text_annot(pdf_rect.tl, content or "Note")
        elif atype == "rect":
            annot = page.add_rect_annot(pdf_rect)
        elif atype == "circle":
            annot = page.add_circle_annot(pdf_rect)
        elif atype == "ink" and points:
            annot = page.add_ink_annot([[pymupdf.Point(p[0], p[1]) for p in points]])
        else:
            annot = page.add_rect_annot(pdf_rect)

        if annot:
            annot.set_colors(stroke=stroke_color)
            if content:
                annot.set_info(content=content)
            annot.update()
            return annot.xref

        return 0

    @classmethod
    def delete_annotation(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        annot_xref: int
    ) -> bool:
        """
        Removes the specified annotation from the page's /Annots array.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")

        page = doc[page_index]
        for annot in page.annots():
            if annot.xref == annot_xref:
                page.delete_annot(annot)
                return True
        return False
