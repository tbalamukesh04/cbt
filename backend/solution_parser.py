"""
solution_parser.py
==================
Parses a JEE solutions PDF into:
  - global_answers  : {q_num (int) → Answer}          ← answer + hint text
  - section_answers : [SectionAnswers]                 ← for section-level audit
  - debug_lines     : [{page, line, matched, q, ans}]  ← for UI audit panel
  - solution_images : {q_num (int) → base64 data-URL} ← cropped solution image

Each solution image is a cropped PNG of the exact region of the PDF page that
contains the answer line + solution/explanation text for that question.  This
mirrors the way the question paper pipeline renders question images.
"""

import base64
import re
import fitz

from document_model import Answer, SectionAnswers
from segmenter import _is_subject_header, _is_section_header, SUBJECT_KEYWORDS


# ── Spatial line reconstruction ────────────────────────────────────────────────
def _extract_lines_spatial(page: fitz.Page, y_threshold: float = 3.0) -> list[str]:
    """Returns reconstructed text lines (text only)."""
    words = page.get_text("words")
    if not words:
        return []
    words = sorted(words, key=lambda w: w[1])
    groups: list[list] = [[words[0]]]
    for w in words[1:]:
        if abs(w[1] - groups[-1][-1][1]) < y_threshold:
            groups[-1].append(w)
        else:
            groups.append([w])
    lines = []
    for group in groups:
        group.sort(key=lambda w: w[0])
        text = " ".join(w[4].strip() for w in group if w[4].strip())
        if text:
            lines.append(text)
    return lines


def _extract_lines_with_pos(page: fitz.Page,
                             y_threshold: float = 3.0) -> list[tuple]:
    """
    Like _extract_lines_spatial but also returns per-line bounding box.
    Returns: [(text, y0, y1), ...]
    where y0/y1 are the top/bottom of the reconstructed line in PDF points.
    """
    words = page.get_text("words")   # (x0,y0,x1,y1, text, block, line, word)
    if not words:
        return []
    words = sorted(words, key=lambda w: w[1])
    groups: list[list] = [[words[0]]]
    for w in words[1:]:
        if abs(w[1] - groups[-1][-1][1]) < y_threshold:
            groups[-1].append(w)
        else:
            groups.append([w])
    result = []
    for group in groups:
        group.sort(key=lambda w: w[0])
        text = " ".join(w[4].strip() for w in group if w[4].strip())
        if text:
            y0 = min(w[1] for w in group)
            y1 = max(w[3] for w in group)
            result.append((text, y0, y1))
    return result


# ── Answer value parser ────────────────────────────────────────────────────────
def _parse_answer_value(raw: str) -> list[str] | str:
    clean = raw.strip().upper()
    letters = re.findall(r"[A-D]", clean)
    if letters:
        stripped_core = re.sub(r"[\s,/\(\)]", "", clean)
        if re.fullmatch(r"[A-D]+", stripped_core):
            return sorted(set(letters))
    m = re.search(r"-?\d+(?:\.\d+)?", clean)
    if m:
        return m.group()
    return clean


# ── Answer line regex ──────────────────────────────────────────────────────────
_ANS_RE = re.compile(
    r"""
    ^\s*
    (\d{1,2})               # question number (1-54 for JEE)
    \.\s+                   # period + at least one space
    (
        [A-Da-d]{1,4}       # letter answer(s)
        (?:[\s,/]*[A-Da-d])*
        |
        -?\d+(?:\.\d+)?     # OR numeric answer
    )
    \s*
    (?:Sol\.?|Solution\.?|$)
    """,
    re.VERBOSE | re.IGNORECASE,
)

_PART_RE   = re.compile(r"^\s*part\s*[-–—]\s*[IVX]+\s*$", re.IGNORECASE)
_SOL_PREFIX = re.compile(r'^(Sol\.?\s*|Solution\.?\s*)', re.IGNORECASE)


# ── Image renderer ─────────────────────────────────────────────────────────────
def _crop_page_region(page: fitz.Page, y0: float, y1: float,
                      margin: float = 8.0, scale: float = 1.5) -> str:
    """
    Crop [0, y0-margin, page_width, y1+margin] from `page` and return
    as a base64-encoded PNG data URL suitable for <img src="...">.
    """
    pw = page.rect.width
    ph = page.rect.height
    rect = fitz.Rect(0, max(0, y0 - margin), pw, min(ph, y1 + margin))
    mat  = fitz.Matrix(scale, scale)
    pix  = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
    return "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode()


# ── Main parser ────────────────────────────────────────────────────────────────
def parse_solutions(pdf_bytes: bytes) -> tuple[dict, list, list, dict]:
    """
    Returns
    -------
    global_answers  : {q_num (int): Answer}
    section_answers : [SectionAnswers]
    debug_lines     : [{page, line, matched, q, answer, category}]
    solution_images : {q_num (int): base64-PNG data URL}
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    global_answers:  dict[int, Answer] = {}
    section_answers: list[SectionAnswers] = []
    debug_lines:     list[dict] = []

    current_subject      = ""
    current_section_name = "SECTION-A"
    current_sec_answers: dict[int, Answer] = {}

    # Track solution bounding boxes for image cropping.
    # _solution_bounds[q_num] = {'page': int, 'y0': float, 'y1': float}
    _solution_bounds: dict[int, dict] = {}
    _hint_q: int | None = None   # question whose solution we are collecting

    def _flush_section():
        nonlocal current_sec_answers
        if current_sec_answers:
            section_answers.append(SectionAnswers(
                subject      = current_subject,
                section_name = current_section_name,
                answers      = dict(current_sec_answers),
            ))
            current_sec_answers = {}

    for page_num, page in enumerate(doc):
        lines = _extract_lines_with_pos(page)   # (text, y0, y1) tuples

        for (raw_line, line_y0, line_y1) in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue

            if _PART_RE.match(stripped):
                continue

            # ── Subject header ──────────────────────────────────────────
            if _is_subject_header(stripped):
                _flush_section()
                _hint_q = None
                m = SUBJECT_KEYWORDS.search(stripped)
                current_subject      = m.group(0).capitalize() if m else stripped.strip()
                current_section_name = "SECTION-A"
                debug_lines.append({
                    "page": page_num + 1, "line": stripped,
                    "matched": True, "q": None,
                    "answer": f"[SUBJECT: {current_subject}]",
                    "category": "header",
                })
                continue

            # ── Section header ──────────────────────────────────────────
            if _is_section_header(stripped):
                _flush_section()
                _hint_q = None
                current_section_name = stripped
                debug_lines.append({
                    "page": page_num + 1, "line": stripped,
                    "matched": True, "q": None,
                    "answer": f"[SECTION: {current_section_name}]",
                    "category": "header",
                })
                continue

            # ── Answer line ─────────────────────────────────────────────
            m = _ANS_RE.match(stripped)
            if m:
                q_num  = int(m.group(1))
                parsed = _parse_answer_value(m.group(2))
                ans    = Answer(raw=m.group(2).strip(), parsed=parsed, confidence=1.0)

                global_answers[q_num]      = ans
                current_sec_answers[q_num] = ans

                # Start tracking this question's solution region
                _solution_bounds[q_num] = {
                    'page': page_num,
                    'y0':   line_y0,
                    'y1':   line_y1,
                }
                _hint_q = q_num

                # Hint text from same line (after Sol.)
                rest = _SOL_PREFIX.sub('', stripped[m.end():]).strip()
                if rest:
                    ans.hint = rest

                debug_lines.append({
                    "page": page_num + 1, "line": stripped,
                    "matched": True, "q": q_num,
                    "answer": str(parsed), "category": "answer",
                })
                continue

            # ── Solution / hint continuation ────────────────────────────
            if _hint_q is not None and _hint_q in global_answers:
                # Extend the bounding box (same page only)
                if (_hint_q in _solution_bounds and
                        _solution_bounds[_hint_q]['page'] == page_num):
                    _solution_bounds[_hint_q]['y1'] = max(
                        _solution_bounds[_hint_q]['y1'], line_y1
                    )

                # Accumulate hint text
                hint_line = _SOL_PREFIX.sub('', stripped).strip()
                if hint_line:
                    existing = global_answers[_hint_q].hint
                    global_answers[_hint_q].hint = (
                        (existing + " " + hint_line).strip() if existing else hint_line
                    )

            # Debug record (short lines only)
            if len(stripped) <= 80:
                debug_lines.append({
                    "page": page_num + 1, "line": stripped,
                    "matched": False, "q": None,
                    "answer": None, "category": "candidate",
                })

    _flush_section()

    # ── Render solution images ──────────────────────────────────────────────
    #
    # For each question, group all solutions on the same page and clip
    # each one to end just before the next solution on that page starts.
    #
    # Build page → sorted list of (q_num, y0, y1)
    page_crops: dict[int, list] = {}
    for q_num, bounds in _solution_bounds.items():
        pg = bounds['page']
        page_crops.setdefault(pg, []).append([q_num, bounds['y0'], bounds['y1']])

    # Clip each entry to the start of the next entry on the same page
    for pg, entries in page_crops.items():
        entries.sort(key=lambda e: e[1])   # sort by y0
        for i in range(len(entries) - 1):
            next_y0 = entries[i + 1][1]
            entries[i][2] = min(entries[i][2], next_y0 - 2)

    solution_images: dict[int, str] = {}
    for pg, entries in page_crops.items():
        page = doc[pg]
        for (q_num, y0, y1) in entries:
            if y1 > y0:
                try:
                    solution_images[q_num] = _crop_page_region(page, y0, y1)
                except Exception as e:
                    print(f"[WARN] Could not crop solution image for Q{q_num}: {e}")

    doc.close()

    # ── Logging ────────────────────────────────────────────────────────────
    n_with_hint  = sum(1 for v in global_answers.values() if v.hint)
    n_with_image = len(solution_images)
    print(f"[SOLUTION PARSER] {len(global_answers)} answers | "
          f"{n_with_hint} with hint text | {n_with_image} with images")
    for k, v in sorted(global_answers.items()):
        img_tag   = "🖼" if k in solution_images else "—"
        hint_prev = f' "{v.hint[:40]}…"' if v.hint else ''
        print(f"  Q{k:>3}: {v.parsed}  {img_tag}{hint_prev}")

    return global_answers, section_answers, debug_lines, solution_images
