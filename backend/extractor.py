import fitz


def extract_lines(doc: fitz.Document, y_threshold: float = 3.0) -> list[dict]:
    """
    Extract words from the PDF, group into lines by y-proximity.
    Returns a flat list of line dicts carrying text + spatial metadata.
    No math detection, no image cropping — just clean line construction.
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
            if abs(w[1] - current_line[-1][1]) < y_threshold:
                current_line.append(w)
            else:
                lines_data.append(current_line)
                current_line = [w]
        if current_line:
            lines_data.append(current_line)

        for line_words in lines_data:
            line_words.sort(key=lambda w: w[0])
            text = " ".join(w[4].strip() for w in line_words if w[4].strip())
            if not text:
                continue

            all_lines.append({
                "text": text,
                "bbox": (
                    min(w[0] for w in line_words),
                    min(w[1] for w in line_words),
                    max(w[2] for w in line_words),
                    max(w[3] for w in line_words),
                ),
                "page": page_num,
            })

    return all_lines
