import pytesseract
from PIL import Image
import io
import fitz

def is_corrupted(line: str) -> bool:
    """Implement the stricter corruption check logic"""
    if len(line) == 0:
        return False
        
    return (
        "□" in line or
        (line.count(" ") > 0 and len([c for c in line if c.isalpha()]) / len(line) < 0.3)
    )

def run_ocr_on_region(page: fitz.Page, bbox: tuple) -> str:
    """Run selective OCR over a bounded rectangle of the PDF page."""
    try:
        # Increase region slightly to catch ascenders/descenders
        rect = fitz.Rect(bbox)
        rect.x0 = max(0, rect.x0 - 2)
        rect.y0 = max(0, rect.y0 - 2)
        rect.x1 += 2
        rect.y1 += 2
        
        # High DPI for better OCR
        pix = page.get_pixmap(clip=rect, dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        
        # PSM 7 treats the image as a single text line
        ocr_text = pytesseract.image_to_string(img, config='--psm 7').strip()
        return ocr_text
    except Exception:
        # Failsafe if Tesseract isn't installed/configured
        return ""
