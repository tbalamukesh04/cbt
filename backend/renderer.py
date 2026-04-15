import fitz
import base64

# Maximum vertical gap (px) before we stop expanding toward a neighbor
MAX_GAP_EXPANSION = 40
PADDING_X = 10
PADDING_Y = 8


def _compute_question_spans(questions: list[dict]) -> list[dict]:
    """
    For each question, compute per-page content bounds (start_y, end_y)
    from the raw line bboxes.
    Returns a list parallel to questions, each entry being:
      { page_num: { "start_y": float, "end_y": float, "x0": float, "x1": float } }
    """
    spans = []
    for q in questions:
        page_map = {}
        for line in q["lines"]:
            pg = line["page"]
            b = line["bbox"]
            if pg not in page_map:
                page_map[pg] = {
                    "start_y": b[1], "end_y": b[3],
                    "x0": b[0], "x1": b[2],
                }
            else:
                entry = page_map[pg]
                entry["start_y"] = min(entry["start_y"], b[1])
                entry["end_y"]   = max(entry["end_y"],   b[3])
                entry["x0"]      = min(entry["x0"],      b[0])
                entry["x1"]      = max(entry["x1"],      b[2])
        spans.append(page_map)
    return spans


def _safe_top(cur_start: float, prev_end: float | None) -> float:
    """Compute the safe top boundary for a question on a given page."""
    if prev_end is None:
        return cur_start - PADDING_Y

    gap = cur_start - prev_end
    if gap < 0:
        # Overlap — fallback to own content bound
        return cur_start - PADDING_Y
    if gap > MAX_GAP_EXPANSION:
        # Large gap — don't expand beyond own content
        return cur_start - PADDING_Y

    return (prev_end + cur_start) / 2


def _safe_bottom(cur_end: float, next_start: float | None) -> float:
    """Compute the safe bottom boundary for a question on a given page."""
    if next_start is None:
        return cur_end + PADDING_Y

    gap = next_start - cur_end
    if gap < 0:
        return cur_end + PADDING_Y
    if gap > MAX_GAP_EXPANSION:
        return cur_end + PADDING_Y

    return (cur_end + next_start) / 2


def render_questions(doc: fitz.Document, questions: list[dict]) -> list[dict]:
    """
    Render each question as image(s), using inter-question midpoint boundaries
    to prevent content leaking from neighboring questions.
    """
    if not questions:
        return []

    spans = _compute_question_spans(questions)
    rendered = []

    for qi, q in enumerate(questions):
        cur_span = spans[qi]
        images = []

        for page_num in sorted(cur_span.keys()):
            cur = cur_span[page_num]
            page = doc[page_num]
            pw, ph = page.rect.width, page.rect.height

            # --- Determine previous question's end_y on same page ---
            prev_end_y = None
            for pi in range(qi - 1, -1, -1):
                if page_num in spans[pi]:
                    prev_end_y = spans[pi][page_num]["end_y"]
                    break

            # --- Determine next question's start_y on same page ---
            next_start_y = None
            for ni in range(qi + 1, len(questions)):
                if page_num in spans[ni]:
                    next_start_y = spans[ni][page_num]["start_y"]
                    break

            # --- Compute safe crop boundaries ---
            top    = _safe_top(cur["start_y"], prev_end_y)
            bottom = _safe_bottom(cur["end_y"], next_start_y)

            x0 = max(0,  cur["x0"] - PADDING_X)
            x1 = min(pw, cur["x1"] + PADDING_X)
            y0 = max(0,  top)
            y1 = min(ph, bottom)

            rect = fitz.Rect(x0, y0, x1, y1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append(f"data:image/png;base64,{b64}")

        # Derive answer_type from section metadata, default to "mcq"
        section = q.get("section")
        answer_type = section["answer_type"] if section else "mcq"

        rendered.append({
            "id": q["id"],
            "type": "image_question",
            "images": images,
            "answer_type": answer_type,
            "section": section,
            "_debug": q["_debug"],
        })

    return rendered
