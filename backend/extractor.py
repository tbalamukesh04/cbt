import fitz

def extract_lines(doc: fitz.Document, y_threshold: float = 3.0) -> list[str]:
    """
    Extract words, group them into lines by y0 proximity, sort by x0.
    """
    all_lines = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        words = page.get_text("words")  # returns tuple: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        
        if not words:
            continue
            
        # 1. Sort words primarily by y0
        # Convert to list to allow sorting and indexing
        words = list(words)
        words.sort(key=lambda w: w[1])
        
        lines_data = []
        current_line = [words[0]]
        
        # 2. Group into identical lines based on y0 threshold
        for w in words[1:]:
            prev_y0 = current_line[-1][1]
            if abs(w[1] - prev_y0) < y_threshold:
                current_line.append(w)
            else:
                lines_data.append(current_line)
                current_line = [w]
        
        if current_line:
            lines_data.append(current_line)
            
        # 3. For each line, sort words horizontally by x0 and collapse into string
        for line_words in lines_data:
            line_words.sort(key=lambda w: w[0])
            line_text = " ".join(w[4].strip() for w in line_words)
            if line_text:
                all_lines.append(line_text)
            
    return all_lines
