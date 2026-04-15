import fitz
from ocr_recovery import is_corrupted, run_ocr_on_region

def extract_lines(doc: fitz.Document, y_threshold: float = 3.0) -> list[dict]:
    """
    Extract words, group them into lines by y0 proximity, sort by x0.
    Returns structurally aware line dicts with bboxes for OCR correction.
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
                
    # Integration Step: OCR Hybrid Recovery
    for line_obj in all_lines:
        text = line_obj["text"]
        if is_corrupted(text):
            page_obj = doc[line_obj["page"]]
            ocr_text = run_ocr_on_region(page_obj, line_obj["bbox"])
            
            # Conditionally replace
            if len(ocr_text) >= len(text) and any(c.isalnum() for c in ocr_text):
                # Ensure it doesn't just look like noise
                line_obj["text"] = ocr_text

    return all_lines
