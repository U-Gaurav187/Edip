import re
from typing import Optional, Dict, Any, Tuple
import pymupdf

class FontManager:
    """
    Manages font resolution, embedded font extraction, and typography matching.
    Follows Adobe Acrobat's font strategy:
    1. Check if the font is embedded and extractable.
    2. If embedded font cannot encode new characters or is a subset, match to standard 14 fonts or open-source metric equivalents.
    3. Retain exact font size, baseline origin, and color.
    """
    
    STANDARD_14_MAP: Dict[str, str] = {
        # Helvetica family
        "helvetica": "helv",
        "helv": "helv",
        "arial": "helv",
        "sans-serif": "helv",
        "helvetica-bold": "hebo",
        "arial-bold": "hebo",
        "helvetica-oblique": "heit",
        "helvetica-italic": "heit",
        "arial-italic": "heit",
        "helvetica-boldoblique": "hebi",
        "helvetica-bolditalic": "hebi",
        
        # Times family
        "times": "tiro",
        "times-roman": "tiro",
        "timesnewroman": "tiro",
        "times new roman": "tiro",
        "serif": "tiro",
        "times-bold": "tibo",
        "times-italic": "tiit",
        "times-bolditalic": "tibi",
        
        # Courier family
        "courier": "cour",
        "courier-bold": "cobo",
        "courier-oblique": "coit",
        "courier-boldoblique": "cobi",
        "couri": "cour",
        "monospace": "cour",
        
        # Symbol & Zapf
        "symbol": "symb",
        "zapfdingbats": "zadb"
    }

    @classmethod
    def resolve_font_name(cls, font_str: Optional[str], flags: int = 0) -> str:
        """
        Maps arbitrary PDF font descriptors (e.g. 'ABCDEF+Helvetica-Bold', 'Calibri')
        or standard font abbreviations ('hebo', 'helv', 'tibo') to the optimal
        standard font symbol for native PDF insertion.
        """
        if not font_str:
            return "helv"
            
        std14 = {"helv", "hebo", "heit", "hebi", "tiro", "tibo", "tiit", "tibi", "cour", "cobo", "coit", "cobi", "symb", "zadb"}
        f_lower = font_str.lower().strip()
        if f_lower in std14:
            return f_lower
            
        # Strip subset prefix if present (e.g. 'BCDFEE+Calibri' -> 'Calibri')
        clean_name = re.sub(r'^[A-Z]{6}\+', '', font_str).strip()
        lower_name = clean_name.lower().replace(" ", "").replace("-", "").replace(",", "")
        if lower_name in std14:
            return lower_name
            
        if lower_name in cls.STANDARD_14_MAP:
            return cls.STANDARD_14_MAP[lower_name]
        
        is_bold = bool(flags & 2**4) or any(k in lower_name for k in ["bold", "black", "heavy", "hebo", "tibo", "cobo", "hebi", "tibi", "cobi", "bd"])
        is_italic = bool(flags & 2**1) or any(k in lower_name for k in ["italic", "oblique", "slanted", "heit", "tiit", "coit", "hebi", "tibi", "cobi"])
        
        # Check Times family
        if any(k in lower_name for k in ["times", "georgia", "cambria", "garamond", "serif", "tiro", "tibo", "tiit", "tibi"]):
            if is_bold and is_italic:
                return "tibi"
            elif is_bold:
                return "tibo"
            elif is_italic:
                return "tiit"
            return "tiro"
            
        # Check Courier / Monospace family
        if any(k in lower_name for k in ["courier", "consolas", "mono", "sourcecode", "cour", "cobo", "coit", "cobi"]):
            if is_bold and is_italic:
                return "cobi"
            elif is_bold:
                return "cobo"
            elif is_italic:
                return "coit"
            return "cour"
            
        # Default to Helvetica / Sans-serif family
        if is_bold and is_italic:
            return "hebi"
        elif is_bold:
            return "hebo"
        elif is_italic:
            return "heit"
        return "helv"

    @classmethod
    def extract_embedded_font(cls, doc: pymupdf.Document, xref: int) -> Optional[Tuple[str, bytes]]:
        """
        Extracts embedded font data buffer and format from a PDF font XObject.
        Returns (extension, font_buffer) if available.
        """
        try:
            name, ext, font_type, buffer = doc.extract_font(xref)
            if buffer and len(buffer) > 0:
                return ext, buffer
        except Exception:
            pass
        return None

    @classmethod
    def color_int_to_rgb(cls, color_int: int) -> Tuple[float, float, float]:
        """
        Converts 24-bit integer sRGB (from PyMuPDF) to normalized (r, g, b) float tuple.
        """
        if color_int <= 0:
            return (0.0, 0.0, 0.0)
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        return (round(r, 4), round(g, 4), round(b, 4))
