import re
from typing import List, Dict, Any, Optional

class PDFStreamParser:
    """
    Low-level PDF content stream tokenizer and operator inspector.
    Inspects and reconstructs ISO 32000-1 graphics operators in PDF /Contents streams.
    """
    
    # Regular expressions for key PDF operators
    IMAGE_DO_PATTERN = re.compile(
        r'(?:q\s+)?([-\d\.\s]+)\s+cm\s*\n?\/([a-zA-Z0-9_\-\.]+)\s+Do(?:\s+Q)?',
        re.MULTILINE
    )
    
    TEXT_BLOCK_PATTERN = re.compile(
        r'BT\s*(.*?)\s*ET',
        re.DOTALL
    )

    @classmethod
    def find_image_operators(cls, stream_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Parses all image invocation operators in a content stream.
        Returns list of { name, cm_matrix: [a,b,c,d,e,f], raw_match }
        """
        text = stream_bytes.decode('latin1', errors='ignore')
        results = []
        for match in cls.IMAGE_DO_PATTERN.finditer(text):
            cm_str = match.group(1).strip()
            name = match.group(2).strip()
            matrix_parts = [float(x) for x in cm_str.split() if x]
            if len(matrix_parts) == 6:
                results.append({
                    "name": name,
                    "matrix": matrix_parts,
                    "raw_span": match.span(),
                    "matched_text": match.group(0)
                })
        return results

    @classmethod
    def excise_image_operator(cls, stream_bytes: bytes, image_name: str) -> bytes:
        """
        Surgically removes the specific /Image Do operator block from the content stream.
        Eliminates the drawing instructions without leaving any visual or structural artifact.
        """
        text = stream_bytes.decode('latin1', errors='ignore')
        # Match pattern specifically for this image name
        pattern = re.compile(
            r'q\s+[-\d\.\s]+cm\s*\n?\/' + re.escape(image_name) + r'\s+Do\s+Q\s*',
            re.MULTILINE
        )
        new_text = pattern.sub('', text)
        if new_text == text:
            # Fallback pattern if not wrapped in q...Q
            pattern_loose = re.compile(
                r'\/ ' + re.escape(image_name) + r'\s+Do\s*',
                re.MULTILINE
            )
            new_text = pattern_loose.sub('', text)
        return new_text.encode('latin1')

    @classmethod
    def update_image_matrix(
        cls, 
        stream_bytes: bytes, 
        image_name: str, 
        new_matrix: List[float]
    ) -> bytes:
        """
        Updates the 6-element transformation matrix [a, b, c, d, e, f] cm for an image.
        """
        text = stream_bytes.decode('latin1', errors='ignore')
        matrix_str = " ".join(f"{round(x, 4)}" for x in new_matrix)
        
        # Look for the image block
        pattern = re.compile(
            r'([-\d\.\s]+)\s+cm\s*\n?(\/' + re.escape(image_name) + r'\s+Do)',
            re.MULTILINE
        )
        
        def repl(match):
            return f"{matrix_str} cm\n{match.group(2)}"
            
        new_text = pattern.sub(repl, text, count=1)
        return new_text.encode('latin1')
