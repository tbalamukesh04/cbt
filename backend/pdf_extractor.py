import fitz  # PyMuPDF
from fastapi import HTTPException

def extract_raw_blocks(doc: fitz.Document) -> list[dict]:
    """
    Extract raw text blocks from the PDF document page by page.
    Returns a list of dicts with block geometry and text.
    """
    raw_blocks = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Get blocks from page: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")
        
        for b in blocks:
            block_type = b[6]
            if block_type != 0:  # We only care about text blocks (type 0)
                continue
                
            text = b[4].strip()
            if not text:
                continue

            raw_blocks.append({
                "page": page_num,
                "x0": b[0],
                "y0": b[1],
                "x1": b[2],
                "y1": b[3],
                "text": text,
                "height": b[3] - b[1]
            })

    return raw_blocks
