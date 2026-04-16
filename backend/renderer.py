import fitz
import base64

# Crop boundaries
PADDING_X = 10
PADDING_Y = 15

# Inter-question gap above which we stop including whitespace
MAX_GAP_EXPANSION = 40

# Minimum word height (pts) to be considered real text, not artifacts
MIN_WORD_HEIGHT = 4.0

# On continuation pages, only include content in the top fraction of the page
# (the rest belongs to the next question or is footer noise)
CONTINUATION_MAX_Y_FRACTION = 0.65


def _compute_question_spans(questions: list[dict]) -> list[dict]:
    """
    For each question, compute per-page spatial bounds from line bboxes.
    Words below MIN_WORD_HEIGHT are filtered as visual noise.

    Returns a list parallel to `questions`. Each entry is:
      { page_num: { start_y, end_y, x0, x1, is_continuation } }

    is_continuation = True when a question's content starts from the top of a
    page (i.e. the question began on a prior page).
    """
    spans = []
    for q in questions:
        page_map: dict[int, dict] = {}
        pages_seen = []

        for line in q["lines"]:
            pg = line["page"]
            b = line["bbox"]

            # Filter noise words by height
            h = b[3] - b[1]
            if h < MIN_WORD_HEIGHT:
                continue

            if pg not in page_map:
                page_map[pg] = {
                    "start_y": b[1], "end_y": b[3],
                    "x0": b[0], "x1": b[2],
                    "is_continuation": False,
                }
                pages_seen.append(pg)
            else:
                e = page_map[pg]
                e["start_y"] = min(e["start_y"], b[1])
                e["end_y"]   = max(e["end_y"],   b[3])
                e["x0"]      = min(e["x0"],       b[0])
                e["x1"]      = max(e["x1"],       b[2])

        # Mark any page after the first as a continuation page
        if len(pages_seen) > 1:
            for pg in pages_seen[1:]:
                page_map[pg]["is_continuation"] = True

        spans.append(page_map)

    return spans


def _safe_top(cur_start: float, prev_end: float | None) -> float:
    """Safe top crop boundary using midpoint isolation."""
    if prev_end is None:
        return cur_start - PADDING_Y
    gap = cur_start - prev_end
    if gap < 0 or gap > MAX_GAP_EXPANSION:
        return cur_start - PADDING_Y
    return (prev_end + cur_start) / 2


def _safe_bottom(cur_end: float, next_start: float | None) -> float:
    """Safe bottom crop boundary using midpoint isolation."""
    if next_start is None:
        return cur_end + PADDING_Y
    gap = next_start - cur_end
    if gap < 0 or gap > MAX_GAP_EXPANSION:
        return cur_end + PADDING_Y
    return (cur_end + next_start) / 2


def render_questions(doc: fitz.Document, questions: list[dict]) -> list[dict]:
    """
    Render each question as image(s) — one image per page the question spans.

    Cropping rules:
      - First page:        midpoint boundary isolation (prev/next question)
      - Continuation page: starts at top of content words (filtered),
                           bottom capped at CONTINUATION_MAX_Y_FRACTION of page
                           unless the next question also starts on this page.

    Spatial filters applied before bbox computation:
      - Words shorter than MIN_WORD_HEIGHT are excluded (artifacts)
      - On continuation pages, words below CONTINUATION_MAX_Y_FRACTION are
        excluded (they belong to the next question)
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

            is_cont = cur["is_continuation"]

            # ── First-page strategy: midpoint isolation ────────────────
            if not is_cont:
                prev_end_y = None
                for pi in range(qi - 1, -1, -1):
                    if page_num in spans[pi]:
                        prev_end_y = spans[pi][page_num]["end_y"]
                        break

                next_start_y = None
                for ni in range(qi + 1, len(questions)):
                    if page_num in spans[ni]:
                        next_start_y = spans[ni][page_num]["start_y"]
                        break

                y0 = max(0, _safe_top(cur["start_y"], prev_end_y))
                y1 = min(ph, _safe_bottom(cur["end_y"], next_start_y))

            # ── Continuation-page strategy: spatial filtering ──────────
            else:
                # Does the next question also start on this page?
                next_on_this_page = None
                for ni in range(qi + 1, len(questions)):
                    if page_num in spans[ni]:
                        next_on_this_page = spans[ni][page_num]["start_y"]
                        break

                # Top: content start (words already filtered for height)
                y0 = max(0, cur["start_y"] - PADDING_Y)

                if next_on_this_page is not None:
                    # Use midpoint to next question on same page
                    y1 = min(ph, _safe_bottom(cur["end_y"], next_on_this_page))
                else:
                    # No next question on this page — cap at fraction
                    cap = ph * CONTINUATION_MAX_Y_FRACTION
                    y1 = min(ph, min(cur["end_y"] + PADDING_Y, cap))

            x0 = max(0,  cur["x0"] - PADDING_X)
            x1 = min(pw, cur["x1"] + PADDING_X)

            rect = fitz.Rect(x0, y0, x1, y1)
            pix  = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
            b64  = base64.b64encode(pix.tobytes("png")).decode("utf-8")
            images.append(f"data:image/png;base64,{b64}")

        rendered.append({
            "id":   q["id"],
            "type": "image_question",
            "images": images,
            "section": q.get("section", {
                "name": "", "description": "", "answer_type": "single_correct_mcq"
            }),
            "_debug": q["_debug"],
        })

    return rendered
