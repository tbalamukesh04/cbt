import fitz
from ocr_recovery import is_math_region, ocr_full_page, align_and_recover

def extract_lines(doc: fitz.Document, y_threshold: float = 3.0) -> list[dict]:
    """
    Extract words, group them into lines by y0 proximity, sort by x0.
    Returns structurally aware line dicts with bboxes.
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
            line_text = " ".join(w[4].strip() for w in line_words)
            
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
                
    # Integration Step: OCR Dual-Representation Full Page Alignment
    # Determine which pages even contain math errors to avoid useless processing
    damaged_pages = {obj["page"] for obj in all_lines if is_math_region(obj["text"])}
    
    ocr_cache = {}
    for pg_num in damaged_pages:
        ocr_cache[pg_num] = ocr_full_page(doc[pg_num])
        
    for line_obj in all_lines:
        text = line_obj["text"]
        if is_math_region(text):
            pg_ocr_lines = ocr_cache.get(line_obj["page"], [])
            recovered = align_and_recover(text, pg_ocr_lines, threshold=0.5)
            # Replaces only if safely qualified by recovery parameters
            line_obj["text"] = recovered

    return all_lines
