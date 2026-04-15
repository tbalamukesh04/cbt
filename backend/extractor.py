import fitz
from visual_recovery import is_math_token, crop_math_region

def extract_lines(doc: fitz.Document, y_threshold: float = 3.0) -> list[dict]:
    """
    Extract words, group them into lines by y0 proximity, sort by x0.
    Returns structurally aware line dicts with visual vectors inline preserving exact rendering.
    """
    all_lines = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        words = page.get_text("words")  
        
        if not words:
            continue
            
        words = list(words)
        words.sort(key=lambda w: w[1])
        
        lines_data = []
        current_line = [words[0]]
        
        for w in words[1:]:
            prev_y0 = current_line[-1][1]
            if abs(w[1] - prev_y0) < y_threshold:
                current_line.append(w)
            else:
                lines_data.append(current_line)
                current_line = [w]
        
        if current_line:
            lines_data.append(current_line)
            
        for line_words in lines_data:
            line_words.sort(key=lambda w: w[0])
            
            # Step: Detect and Group Math Regions Instantly
            final_text_parts = []
            math_group = []
            
            def flush_math():
                """Helper to calculate merged boundary of corrupted span and render immediately"""
                if math_group:
                    x0 = min(mw[0] for mw in math_group)
                    y0 = min(mw[1] for mw in math_group)
                    x1 = max(mw[2] for mw in math_group)
                    y1 = max(mw[3] for mw in math_group)
                    
                    val = crop_math_region(page, (x0, y0, x1, y1), padding=3)
                    math_group.clear()
                    return val
                return ""
            
            for w in line_words:
                text = w[4].strip()
                if not text:
                    continue
                    
                if is_math_token(text):
                    math_group.append(w)
                else:
                    if math_group:
                        final_text_parts.append(flush_math())
                    final_text_parts.append(text)
                    
            if math_group:
                final_text_parts.append(flush_math())
                
            line_text = " ".join(final_text_parts)
            
            if line_text:
                x0 = min(w[0] for w in line_words)
                y0 = min(w[1] for w in line_words)
                x1 = max(w[2] for w in line_words)
                y1 = max(w[3] for w in line_words)
                
                line_obj = {
                    "text": line_text,
                    "bbox": (x0, y0, x1, y1),
                    "page": page_num
                }
                all_lines.append(line_obj)
                
    return all_lines
