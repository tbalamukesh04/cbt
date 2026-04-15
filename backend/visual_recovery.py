import fitz
import base64
import re

def is_math_token(word: str) -> bool:
    """Implement check to strictly isolate non-text vector corruptions vs text"""
    # 1. Immediate visual garbage bounds
    if "□" in word or "\ufffd" in word:
        return True
        
    # 2. Shield specific formatting blocks to preserve segmentation logic
    # Do not treat pure question numbers (e.g. "1.", "Q 2.", "(A)") as math
    if re.match(r"^\d+[\.\)]?$|^[A-Da-d]\.?$|^\(?[A-Da-d]\)?$|^Q\s*\d+[\.\)]?$", word, re.IGNORECASE):
        return False
        
    # 3. Target strings with extremely low text-to-symbol ratios
    alpha = sum(c.isalpha() for c in word)
    if alpha / max(len(word), 1) < 0.4:
        # e.g., ^2, /, ), ( etc where text density dies
        return True
        
    return False

def crop_math_region(page: fitz.Page, bbox: tuple, padding=3) -> str:
    """Extract a defined region bounding inline vector-math and return as safe B64 image string"""
    try:
        # Add slight padding so equations aren't touching borders natively
        x0, y0, x1, y1 = bbox
        rect = fitz.Rect(max(0, x0 - padding), max(0, y0 - padding), x1 + padding, y1 + padding)
        
        # High DPI extract (approx 150-200) balances readability and base64 memory bounds
        pix = page.get_pixmap(clip=rect, dpi=150)
        img_data = pix.tobytes("png")
        b64 = base64.b64encode(img_data).decode("utf-8")
        
        return f'<math_image src="data:image/png;base64,{b64}"/>'
    except Exception:
        return ""
