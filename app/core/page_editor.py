from typing import List
import pymupdf

class RealPDFPageEditor:
    """
    Page tree manipulations: reordering, rotations, insertions, deletions, duplications,
    merging, and splitting.
    """

    @classmethod
    def reorder_pages(cls, doc: pymupdf.Document, new_order: List[int]) -> bool:
        """
        Reorders document pages according to new_order list of zero-based indices.
        """
        if len(new_order) != len(doc):
            raise ValueError(f"new_order length ({len(new_order)}) does not match document page count ({len(doc)})")
        if sorted(new_order) != list(range(len(doc))):
            raise ValueError("new_order must be a permutation of all page indices")
            
        doc.select(new_order)
        return True

    @classmethod
    def rotate_page(cls, doc: pymupdf.Document, page_index: int, delta: int) -> int:
        """
        Rotates page by delta (90, 180, 270 degrees). Returns new total rotation.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        page = doc[page_index]
        new_rot = (page.rotation + delta) % 360
        page.set_rotation(new_rot)
        return new_rot

    @classmethod
    def delete_pages(cls, doc: pymupdf.Document, page_indices: List[int]) -> bool:
        """
        Deletes the specified pages from the document.
        """
        # Sort in descending order to avoid index shifting
        sorted_indices = sorted(set(page_indices), reverse=True)
        for idx in sorted_indices:
            if 0 <= idx < len(doc):
                doc.delete_page(idx)
        return True

    @classmethod
    def duplicate_page(cls, doc: pymupdf.Document, page_index: int) -> int:
        """
        Duplicates a page and inserts it immediately after the original page.
        Returns the index of the newly created duplicate page.
        """
        if page_index < 0 or page_index >= len(doc):
            raise ValueError(f"Page index {page_index} out of bounds")
            
        doc.copy_page(page_index, page_index + 1)
        return page_index + 1

    @classmethod
    def insert_blank_page(
        cls,
        doc: pymupdf.Document,
        at_index: int,
        width: float = 612.0,
        height: float = 792.0
    ) -> int:
        """
        Inserts a blank page at the given index.
        """
        if at_index < 0 or at_index > len(doc):
            at_index = len(doc)
            
        doc.new_page(at_index, width=width, height=height)
        return at_index

    @classmethod
    def merge_documents(cls, primary_doc: pymupdf.Document, other_docs: List[pymupdf.Document]) -> int:
        """
        Merges other documents into primary_doc in order. Returns total new page count.
        """
        for doc in other_docs:
            primary_doc.insert_pdf(doc)
        return len(primary_doc)

    @classmethod
    def extract_pages(
        cls,
        doc: pymupdf.Document,
        from_page: int,
        to_page: int
    ) -> pymupdf.Document:
        """
        Extracts a page range into a new independent document.
        """
        new_doc = pymupdf.open()
        new_doc.insert_pdf(doc, from_page=from_page, to_page=to_page)
        return new_doc
