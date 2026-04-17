import fitz
import base64

PADDING_X = 10
PADDING_Y = 15
MAX_GAP_EXPANSION = 40
MIN_WORD_HEIGHT = 4.0
CONTINUATION_MAX_Y_FRACTION = 0.65


def _compute_question_spans(questions: list[dict]) -> list[dict]:
    """
    Build per-page spatial bounds for each question node.
    Filters artifact words by height. Marks continuation pages.
    Returns a list parallel to `questions`.
    """
    spans = []
    for q in questions:
        page_map: dict[int, dict] = {}
        pages_seen = []

        for line in q["lines"]:
            pg = line["page"]
            b  = line["bbox"]
            if (b[3] - b[1]) < MIN_WORD_HEIGHT:
                continue

            if pg not in page_map:
                page_map[pg] = {
                    "start_y": b[1], "end_y": b[3],
                    "x0": b[0],      "x1": b[2],
                    "is_continuation": False,
                }
                pages_seen.append(pg)
            else:
                e = page_map[pg]
                e["start_y"] = min(e["start_y"], b[1])
                e["end_y"]   = max(e["end_y"],   b[3])
                e["x0"]      = min(e["x0"],       b[0])
                e["x1"]      = max(e["x1"],       b[2])

        if len(pages_seen) > 1:
            for pg in pages_seen[1:]:
                page_map[pg]["is_continuation"] = True

        spans.append(page_map)
    return spans


def _safe_top(cur_start: float, prev_end: float | None) -> float:
    if prev_end is None:
        return cur_start - PADDING_Y
    gap = cur_start - prev_end
    if gap < 0 or gap > MAX_GAP_EXPANSION:
        return cur_start - PADDING_Y
    return (prev_end + cur_start) / 2


def _safe_bottom(cur_end: float, next_start: float | None) -> float:
    if next_start is None:
        return cur_end + PADDING_Y
    gap = next_start - cur_end
    if gap < 0 or gap > MAX_GAP_EXPANSION:
        return cur_end + PADDING_Y
    return (cur_end + next_start) / 2


def render_questions(doc: fitz.Document, nodes: list[dict]) -> list[dict]:
    """
    Accepts the ordered list of section + question nodes from build_questions().

    - section nodes: passed through unchanged (no image rendering needed)
    - question nodes: rendered as image(s) using per-page spatial cropping

    Returns the same ordered list with images attached to question nodes.
    """
    # Extract only question nodes for span computation + indexed lookup
    questions = [n for n in nodes if n["type"] == "question"]
    spans     = _compute_question_spans(questions)
    span_map  = {q["id"]: span for q, span in zip(questions, spans)}

    output: list[dict] = []

    for node in nodes:

        # ── Section node — pass through ───────────────────────────────────────
        if node["type"] == "section":
            output.append({
                "type":    "section",
                "section": node["section"],
            })
            continue

        # ── Question node — render images ─────────────────────────────────────
        q       = node
        cur_span = span_map[q["id"]]
        qi      = questions.index(q)
        images  = []

        for page_num in sorted(cur_span.keys()):
            cur  = cur_span[page_num]
            page = doc[page_num]
            pw, ph = page.rect.width, page.rect.height
            is_cont = cur["is_continuation"]

            if not is_cont:
                # First page: midpoint isolation
                prev_end_y = None
                for pi in range(qi - 1, -1, -1):
                    prev_span = span_map[questions[pi]["id"]]
                    if page_num in prev_span:
                        prev_end_y = prev_span[page_num]["end_y"]
                        break

                next_start_y = None
                for ni in range(qi + 1, len(questions)):
                    next_span = span_map[questions[ni]["id"]]
                    if page_num in next_span:
                        next_start_y = next_span[page_num]["start_y"]
                        break

                y0 = max(0, _safe_top(cur["start_y"], prev_end_y))
                y1 = min(ph, _safe_bottom(cur["end_y"], next_start_y))

            else:
                # Continuation page: spatial filtering
                next_on_page = None
                for ni in range(qi + 1, len(questions)):
                    next_span = span_map[questions[ni]["id"]]
                    if page_num in next_span:
                        next_on_page = next_span[page_num]["start_y"]
                        break

                y0 = max(0, cur["start_y"] - PADDING_Y)
                if next_on_page is not None:
                    y1 = min(ph, _safe_bottom(cur["end_y"], next_on_page))
                else:
                    cap = ph * CONTINUATION_MAX_Y_FRACTION
                    y1  = min(ph, min(cur["end_y"] + PADDING_Y, cap))

            x0 = max(0,  cur["x0"] - PADDING_X)
            x1 = min(pw, cur["x1"] + PADDING_X)

            rect = fitz.Rect(x0, y0, x1, y1)
            pix  = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
            b64  = base64.b64encode(pix.tobytes("png")).decode("utf-8")
            images.append(f"data:image/png;base64,{b64}")

        output.append({
            "type":    "question",
            "id":      q["id"],
            "images":  images,
            "section": q["section"],
            "_debug":  q["_debug"],
        })

    return output
