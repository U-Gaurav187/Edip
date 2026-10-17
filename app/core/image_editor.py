import io
import math
from typing import List, Optional
import pymupdf
from PIL import Image
from .stream_parser import PDFStreamParser

class RealPDFImageEditor:
    """
    Production PDF Image Object Editor.
    Manipulates image XObjects and content stream transformation matrices directly.
    """

    @classmethod
    def find_image_name(cls, page: pymupdf.Page, xref: int) -> Optional[str]:
        """
        Finds the resource name (e.g. 'fzImg0', 'Im1') assigned to the image xref on this page.
        """
        images = page.get_images(full=True)
        for img in images:
            if img[0] == xref:
                return img[7]
        return None

    @classmethod
    def transform_image(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        xref: int,
        old_bbox: List[float],
        new_bbox: List[float],
        rotation_degrees: float = 0.0
    ) -> bool:
        """
        Updates the placement, size, and rotation of an image on a page
        by recalculating its Current Transformation Matrix (cm) in the /Contents stream.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        image_name = cls.find_image_name(page, xref)
        if not image_name:
            raise ValueError(f"Image with xref {xref} not found on page {page_index}")

        # Page height needed to convert top-left coordinates to PDF bottom-left coordinates
        page_rect = page.rect
        page_height = page_rect.height

        new_x0, new_y0, new_x1, new_y1 = new_bbox
        width = abs(new_x1 - new_x0)
        height = abs(new_y1 - new_y0)
        
        # Origin in PDF coordinates
        pdf_x = new_x0
        pdf_y = page_height - new_y0 - height

        # Compute transformation matrix
        rad = math.radians(rotation_degrees)
        cos_val = math.cos(rad)
        sin_val = math.sin(rad)
        
        a = width * cos_val
        b = width * sin_val
        c = -height * sin_val
        d = height * cos_val
        e = pdf_x
        f = pdf_y

        matrix = [a, b, c, d, e, f]

        # Update all content streams for this page
        contents = page.get_contents()
        if not contents:
            return False

        updated = False
        for c_xref in contents:
            stream_bytes = doc.xref_stream(c_xref)
            new_stream = PDFStreamParser.update_image_matrix(stream_bytes, image_name, matrix)
            if new_stream != stream_bytes:
                doc.update_stream(c_xref, new_stream)
                updated = True
                break

        if not updated:
            # If standard cm update did not match the pattern, re-inject clean content stream
            # Eradicate old operator and place at new coordinates
            for c_xref in contents:
                s_bytes = doc.xref_stream(c_xref)
                clean_bytes = PDFStreamParser.excise_image_operator(s_bytes, image_name)
                doc.update_stream(c_xref, clean_bytes)
            
            # Reinsert image at new bbox
            extracted = doc.extract_image(xref)
            if extracted and "image" in extracted:
                page.insert_image(
                    pymupdf.Rect(new_bbox), 
                    stream=extracted["image"], 
                    rotate=int(rotation_degrees) % 360
                )

        page.clean_contents()
        return True

    @classmethod
    def replace_image(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        xref: int,
        new_image_bytes: bytes
    ) -> bool:
        """
        Replaces the underlying XObject data stream at the given xref.
        This updates the image across all references while preserving placement.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        page.replace_image(xref, stream=new_image_bytes)
        return True

    @classmethod
    def delete_image(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        xref: int
    ) -> bool:
        """
        Surgically deletes the image from the page.
        Eradicates the 'Do' operator from the content stream and removes the resource reference.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        image_name = cls.find_image_name(page, xref)
        
        contents = page.get_contents()
        for c_xref in contents:
            stream_bytes = doc.xref_stream(c_xref)
            if image_name:
                cleaned = PDFStreamParser.excise_image_operator(stream_bytes, image_name)
            else:
                cleaned = stream_bytes
            doc.update_stream(c_xref, cleaned)
            
        # Clean page contents to finalize stream compaction
        page.clean_contents()
        return True

    @classmethod
    def crop_image(
        cls,
        doc: pymupdf.Document,
        page_index: int,
        xref: int,
        crop_box: List[int]
    ) -> bool:
        """
        Crops the image XObject to [left, top, right, bottom] pixel coordinates
        and updates the PDF XObject stream.
        """
        extracted = doc.extract_image(xref)
        if not extracted or "image" not in extracted:
            raise ValueError(f"Unable to extract image data for xref {xref}")

        raw_bytes = extracted["image"]
        with Image.open(io.BytesIO(raw_bytes)) as pil_img:
            cropped = pil_img.crop(crop_box)
            buf = io.BytesIO()
            fmt = pil_img.format if pil_img.format else "PNG"
            cropped.save(buf, format=fmt)
            return cls.replace_image(doc, page_index, xref, buf.getvalue())
