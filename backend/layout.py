import re

# Identify strong option-like patterns that should force a paragraph break
OPTIONS_REGEX = re.compile(
    r"^\(?[A-D]\)?\s*[\.\)]|"
    r"^[A-D]\.\s+"
)

def _detect_columns(blocks_on_page: list[dict], page_width: float = 600.0, page_height: float = 800.0) -> list[dict]:
    """
    Given raw blocks for a SINGLE page, deterministic column detection.
    Compute horizontal gap. If empty vertical channel spans >70% height, split into 2 columns.
    """
    if not blocks_on_page:
        return []
        
    # We will simply scan the middle 30% of the page x-axis (e.g. x between 0.35 * w to 0.65 * w) 
    # to see if any block crosses it. If no block intersects the middle, we have a hard column break.
    # To be extremely robust as requested, we measure the vertical cover of blocks crossing the center.
    
    # Estimate width/height if not provided, just from blocks min/max
    min_x = min(b["x0"] for b in blocks_on_page)
    max_x = max(b["x1"] for b in blocks_on_page)
    min_y = min(b["y0"] for b in blocks_on_page)
    max_y = max(b["y1"] for b in blocks_on_page)
    
    p_width = max_x - min_x
    p_height = max_y - min_y
    
    if p_width < 100 or p_height < 100:
        for b in blocks_on_page: b["col"] = 0
        return blocks_on_page
        
    center_x = min_x + (p_width / 2.0)
    
    # Calculate how much vertical height is obscured by blocks crossing the center line
    obscured_y_intervals = []
    for b in blocks_on_page:
        if b["x0"] < center_x and b["x1"] > center_x:
            obscured_y_intervals.append((b["y0"], b["y1"]))
            
    # Sort and merge intervals to find total obscured height
    total_obscured_height = 0
    if obscured_y_intervals:
        obscured_y_intervals.sort()
        current_start, current_end = obscured_y_intervals[0]
        for start, end in obscured_y_intervals[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
            else:
                total_obscured_height += (current_end - current_start)
                current_start = start
                current_end = end
        total_obscured_height += (current_end - current_start)
        
    # If the middle is clear for >70% of the page height, it's two columns
    if (p_height - total_obscured_height) / p_height > 0.70:
        for b in blocks_on_page:
            b["col"] = 0 if b["x1"] < center_x + 20 else 1
    else:
        for b in blocks_on_page:
            b["col"] = 0
            
    return blocks_on_page


def reconstruct_reading_order(raw_blocks: list[dict]) -> list[dict]:
    """
    Sort blocks strictly: page_num -> col -> y0 -> x0
    """
    page_map = {}
    for b in raw_blocks:
        page_map.setdefault(b["page"], []).append(b)
        
    ordered_blocks = []
    for page_num in sorted(page_map.keys()):
        blocks = page_map[page_num]
        
        # Apply column detection algorithms
        blocks = _detect_columns(blocks)
        
        # Sort using snapped y0 for slight misalignments
        blocks.sort(key=lambda b: (b["col"], round(b["y0"] / 5), b["x0"]))
        ordered_blocks.extend(blocks)
        
    return ordered_blocks


def build_lines(ordered_blocks: list[dict]) -> list[dict]:
    """
    Group blocks into lines if they share vertical proximity, similar height, and horizontal alignment.
    """
    if not ordered_blocks:
        return []
        
    lines = []
    current_line_blocks = [ordered_blocks[0]]
    
    for block in ordered_blocks[1:]:
        prev = current_line_blocks[-1]
        
        # Check alignment conditions
        y_distance = abs(block["y0"] - prev["y0"])
        height_diff = abs(block["height"] - prev["height"])
        
        same_page_col = (block["page"] == prev["page"] and block["col"] == prev["col"])
        
        # Thresholds: y-dist < 5px for same line, height diff < 4px, and x must be strictly to the right
        if same_page_col and y_distance <= 5 and height_diff <= 4 and block["x0"] > prev["x0"] - 5:
            current_line_blocks.append(block)
        else:
            # Finalize line
            text = " ".join(b["text"] for b in current_line_blocks)
            min_x0 = min(b["x0"] for b in current_line_blocks)
            max_x1 = max(b["x1"] for b in current_line_blocks)
            min_y0 = min(b["y0"] for b in current_line_blocks)
            max_y1 = max(b["y1"] for b in current_line_blocks)
            
            lines.append({
                "page": current_line_blocks[0]["page"],
                "col": current_line_blocks[0]["col"],
                "x0": min_x0,
                "y0": min_y0,
                "x1": max_x1,
                "y1": max_y1,
                "text": text,
                "height": max_y1 - min_y0
            })
            current_line_blocks = [block]
            
    # Finalize last line
    if current_line_blocks:
        text = " ".join(b["text"] for b in current_line_blocks)
        min_x0 = min(b["x0"] for b in current_line_blocks)
        lines.append({
            "page": current_line_blocks[0]["page"],
            "col": current_line_blocks[0]["col"],
            "x0": min_x0,
            "y0": min(b["y0"] for b in current_line_blocks),
            "text": text,
            "height": max(b["y1"] for b in current_line_blocks) - min(b["y0"] for b in current_line_blocks)
        })
        
    return lines


def _calc_left_margin(lines: list[dict]) -> float:
    if not lines:
        return 0.0
    x_coords = sorted(l["x0"] for l in lines)
    # Take 10th percentile to avoid outliers
    idx = int(len(x_coords) * 0.1)
    return x_coords[idx]


def build_paragraphs(lines: list[dict]) -> tuple[list[dict], float]:
    """
    Groups lines into structural paragraphs.
    Returns (paragraphs, global_left_margin).
    """
    if not lines:
        return [], 0.0
        
    left_margin = _calc_left_margin(lines)
    paragraphs = []
    
    current_lines = [lines[0]]
    
    for line in lines[1:]:
        prev = current_lines[-1]
        
        # Evaluate break condition
        same_space = (line["page"] == prev["page"] and line["col"] == prev["col"])
        
        # Calculate gap
        vertical_gap = line["y0"] - prev["y0"]
        
        # Determine if it's a new paragraph based on vertical distance
        is_large_gap = vertical_gap > (prev["height"] * 1.8) or vertical_gap < 0
        indent_shift = abs(line["x0"] - prev["x0"]) > 10
        is_option = OPTIONS_REGEX.match(line["text"])
        
        if not same_space or is_large_gap or indent_shift or is_option:
            # Break paragraph
            para_text = "\n".join(l["text"] for l in current_lines)
            paragraphs.append({
                "page": current_lines[0]["page"],
                "col": current_lines[0]["col"],
                "x0": current_lines[0]["x0"],
                "y0": current_lines[0]["y0"],
                "text": para_text.strip()
            })
            current_lines = [line]
        else:
            current_lines.append(line)
            
    if current_lines:
        para_text = "\n".join(l["text"] for l in current_lines)
        paragraphs.append({
            "page": current_lines[0]["page"],
            "col": current_lines[0]["col"],
            "x0": current_lines[0]["x0"],
            "y0": current_lines[0]["y0"],
            "text": para_text.strip()
        })
        
    return paragraphs, left_margin
