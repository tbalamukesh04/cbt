"""
solution_parser.py
==================
Parses a JEE solutions PDF into:
  - global_answers : {q_num (int) → Answer}          ← for quick lookup
  - section_answers: [SectionAnswers]                 ← for section-level audit
  - debug_lines    : [{page, line, matched, q, ans}]  ← for UI audit panel

Key improvement over answer_parser.py
--------------------------------------
Uses the SAME spatial word-grouping as extractor.py.
This correctly reconstructs lines like "1.        C" that appear in
two-column PDF layouts where simple page.get_text("text") returns
"1." and "C" on separate lines.

Section/subject detection reuses the classifiers from segmenter.py so both
documents are parsed with identically-defined structural boundaries.
"""

import re
import fitz

from document_model import Answer, SectionAnswers
from segmenter import _is_subject_header, _is_section_header, SUBJECT_KEYWORDS


# ── Spatial line reconstruction (identical algorithm to extractor.py) ──────────
def _extract_lines_spatial(page: fitz.Page, y_threshold: float = 3.0) -> list[str]:
    """
    Extract and reconstruct text lines using word-level bounding boxes.
    Words within `y_threshold` pixels of each other are on the same line.
    Words are then sorted left-to-right to reconstruct the natural reading order.

    This handles two-column layouts like:
        "1.    [answer column]  C"
    which simple text extraction would split into "1." and "C" on separate lines.
    """
    words = page.get_text("words")   # (x0, y0, x1, y1, text, block, line, word_no)
    if not words:
        return []

    words = list(words)
    words.sort(key=lambda w: w[1])   # sort by y (top edge)

    # Group into lines
    groups: list[list] = [[words[0]]]
    for w in words[1:]:
        if abs(w[1] - groups[-1][-1][1]) < y_threshold:
            groups[-1].append(w)
        else:
            groups.append([w])

    # Reconstruct each line: sort words left-to-right, join with space
    lines = []
    for group in groups:
        group.sort(key=lambda w: w[0])   # sort by x (left edge)
        text = " ".join(w[4].strip() for w in group if w[4].strip())
        if text:
            lines.append(text)

    return lines


# ── Answer value parser ────────────────────────────────────────────────────────
def _parse_answer_value(raw: str) -> list[str] | str:
    """
    "C"    → ["C"]
    "AD"   → ["A","D"]
    "A,D"  → ["A","D"]
    "A D"  → ["A","D"]
    "3"    → "3"
    "2.50" → "2.50"
    """
    clean = raw.strip().upper()

    # Pure letters A-D (compact or comma/space separated)
    letters = re.findall(r"[A-D]", clean)
    if letters:
        # Make sure there are no non-letter, non-separator characters
        stripped_core = re.sub(r"[\s,/\(\)]", "", clean)
        if re.fullmatch(r"[A-D]+", stripped_core):
            return sorted(set(letters))

    # Numeric (integer or decimal)
    m = re.search(r"-?\d+(?:\.\d+)?", clean)
    if m:
        return m.group()

    return clean


# ── Answer line detector ───────────────────────────────────────────────────────
#
# Primary:  "1. C"  /  "19. AD"  /  "9. 3"
#   - number (1-2 digits for JEE) + period + spaces + short answer
#   - answer ends at EOL OR before "Sol." / "Solution"
#
# The regex is intentionally strict (EOL or Sol.) so it doesn't match
# question content lines that happen to start with a number.
#
_ANS_RE = re.compile(
    r"""
    ^\s*
    (\d{1,2})               # question number (1-54 for JEE)
    \.\s+                   # period + at least one space
    (
        [A-Da-d]{1,4}       # letter answer(s) — compact, comma, or space-sep
        (?:[\s,/]*[A-Da-d])*
        |
        -?\d+(?:\.\d+)?     # OR numeric answer
    )
    \s*                     # trailing whitespace
    (?:Sol\.?|Solution\.?|$)  # end of answer content
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Secondary: "Part – I", "Part – II" labels (not structural — skip these)
_PART_RE = re.compile(r"^\s*part\s*[-–—]\s*[IVX]+\s*$", re.IGNORECASE)

# Strip leading "Sol." / "Solution" from hint text
_SOL_PREFIX = re.compile(r'^(Sol\.?\s*|Solution\.?\s*)', re.IGNORECASE)


def parse_solutions(pdf_bytes: bytes) -> tuple[dict, list, list]:
    """
    Returns
    -------
    global_answers  : {q_num (int): Answer}
    section_answers : [SectionAnswers]  — one bucket per section detected
    debug_lines     : [{page, line, matched, q, answer, category}]
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    global_answers:  dict[int, Answer] = {}
    section_answers: list[SectionAnswers] = []
    debug_lines:     list[dict] = []

    current_subject      = ""
    current_section_name = "SECTION-A"
    current_sec_answers: dict[int, Answer] = {}

    # _hint_q tracks which question's hint we are currently appending to.
    # It is set when an answer line is matched, and cleared when a
    # subject/section header is encountered.
    _hint_q: int | None = None

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
        lines = _extract_lines_spatial(page)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # "Part – I / II / III" → skip, not structural
            if _PART_RE.match(stripped):
                continue

            # ── Subject header (Physics / Chemistry / Mathematics) ──────────
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

            # ── Section header (SECTION – A / B / C) ──────────────────────
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

            # ── Answer line ────────────────────────────────────────────────
            m = _ANS_RE.match(stripped)
            if m:
                q_num  = int(m.group(1))
                parsed = _parse_answer_value(m.group(2))
                ans    = Answer(raw=m.group(2).strip(), parsed=parsed, confidence=1.0)

                global_answers[q_num]      = ans
                current_sec_answers[q_num] = ans
                _hint_q = q_num   # subsequent lines are this question's hint

                # Capture hint text on the SAME line after the answer / "Sol."
                rest = _SOL_PREFIX.sub('', stripped[m.end():]).strip()
                if rest:
                    ans.hint = rest

                debug_lines.append({
                    "page":     page_num + 1,
                    "line":     stripped,
                    "matched":  True,
                    "q":        q_num,
                    "answer":   str(parsed),
                    "category": "answer",
                })
                continue

            # ── Hint / solution text (continuation lines) ──────────────────
            # Anything that is NOT a header and NOT an answer line is treated
            # as solution/explanation text for the current question.
            if _hint_q is not None and _hint_q in global_answers:
                hint_line = _SOL_PREFIX.sub('', stripped).strip()
                if hint_line:
                    existing = global_answers[_hint_q].hint
                    global_answers[_hint_q].hint = (
                        (existing + " " + hint_line).strip() if existing else hint_line
                    )

            # ── Debug record for audit panel ──────────────────────────────
            if len(stripped) <= 80:
                debug_lines.append({
                    "page":     page_num + 1,
                    "line":     stripped,
                    "matched":  False,
                    "q":        None,
                    "answer":   None,
                    "category": "candidate",
                })

    _flush_section()
    doc.close()

    print(f"[SOLUTION PARSER] {len(global_answers)} answers across "
          f"{len(section_answers)} sections")
    for k, v in sorted(global_answers.items()):
        hint_preview = f' | hint: {v.hint[:50]}…' if v.hint else ''
        print(f"  Q{k:>3}: {v.parsed}{hint_preview}")

    return global_answers, section_answers, debug_lines
