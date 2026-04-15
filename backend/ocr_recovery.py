import pytesseract
from PIL import Image
import io
import fitz
import re
import difflib

def is_math_region(line: str) -> bool:
    """Detect lines suffering from severe missing math constants/font corruption"""
    if len(line) == 0:
        return False
    return (
        "□" in line or
        "\ufffd" in line or 
        (sum(c.isalpha() for c in line) / max(len(line), 1) < 0.4)
    )

def has_math_symbols(text: str) -> bool:
    """Ensure the OCR output actually recovered mathematical structure."""
    if any(c in text for c in ['/', '(', ')', '^']):
        return True
    if re.search(r'[\u0370-\u03ff]', text):
        return True
    return False

def ocr_full_page(page: fitz.Page) -> list[str]:
    """Render full page and run OCR once. Returns list of text lines."""
    try:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        # Default psm 3 is good for full page layout
        ocr_text = pytesseract.image_to_string(img).strip()
        # Segment into lines for alignment mapping
        return [line.strip() for line in ocr_text.split('\n') if line.strip()]
    except Exception:
        return []

def align_and_recover(line_text: str, ocr_lines: list[str], threshold: float = 0.6) -> str:
    """Aligns line_text against OCR lines and returns repaired string if valid."""
    if not ocr_lines:
        return line_text
        
    # Find closest substring line
    matches = difflib.get_close_matches(line_text, ocr_lines, n=1, cutoff=threshold)
    if not matches:
        return line_text
        
    best_ocr = matches[0]
    
    # Check replacement rules
    def count_garbage(t):
        return t.count("□") + t.count("\ufffd")
        
    # We replace if it recovers math tokens and has less/equal garbage 
    # (sometimes garbage is exactly 0 but tokens are recovered, e.g. E = 1/2)
    if has_math_symbols(best_ocr) and count_garbage(best_ocr) <= count_garbage(line_text):
        if len(best_ocr) >= len(line_text) * 0.7:
            return best_ocr
            
    return line_text
