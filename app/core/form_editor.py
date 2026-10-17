from typing import List, Optional, Union, Dict, Any
import pymupdf

class RealPDFFormEditor:
    """
    Production AcroForm interactive form fields manager.
    Supports inspecting, updating, and creating standard PDF forms.
    """

    TYPE_MAP = {
        "text": pymupdf.PDF_WIDGET_TYPE_TEXT,
        "checkbox": pymupdf.PDF_WIDGET_TYPE_CHECKBOX,
        "radio": pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON,
        "dropdown": pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
        "signature": pymupdf.PDF_WIDGET_TYPE_SIGNATURE
    }

    @classmethod
    def get_page_fields(cls, page: pymupdf.Page) -> List[Dict[str, Any]]:
        """
        Enumerates all interactive AcroForm widgets on a page.
        """
        results = []
        for w in page.widgets():
            results.append({
                "name": w.field_name,
                "type": w.field_type_string,
                "value": w.field_value,
                "rect": [w.rect.x0, w.rect.y0, w.rect.x1, w.rect.y1],
                "options": w.choice_values if hasattr(w, "choice_values") else None,
                "is_read_only": bool(w.field_flags & pymupdf.PDF_FIELD_IS_READ_ONLY)
            })
        return results

    @classmethod
    def update_field_value(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        field_name: str,
        value: Union[str, bool]
    ) -> bool:
        """
        Updates the value of an AcroForm widget and regenerates appearance streams.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")

        page = doc[page_index]
        for w in page.widgets():
            if w.field_name == field_name:
                w.field_value = value
                w.update()
                return True
        return False

    @classmethod
    def create_field(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        field_type_str: str,
        field_name: str,
        rect: List[float],
        options: Optional[List[str]] = None,
        default_value: Optional[str] = None
    ) -> bool:
        """
        Creates a new interactive form widget on the page.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")

        page = doc[page_index]
        widget_type = cls.TYPE_MAP.get(field_type_str.lower(), pymupdf.PDF_WIDGET_TYPE_TEXT)

        widget = pymupdf.Widget()
        widget.rect = pymupdf.Rect(rect)
        widget.field_type = widget_type
        widget.field_name = field_name
        
        if default_value is not None:
            widget.field_value = default_value

        if options and widget_type in (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, pymupdf.PDF_WIDGET_TYPE_LISTBOX):
            widget.choice_values = options

        page.add_widget(widget)
        return True
