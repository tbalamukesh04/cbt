"""
answer_parser.py
================
Extracts an answer key from a JEE solutions PDF.

Supported line formats
----------------------
  9. AD          → {9: ["A", "D"]}   (multiple correct MCQ)
  9. A           → {9: ["A"]}        (single correct MCQ)
  9. 3           → {9: "3"}          (integer type)
  9. 2.50        → {9: "2.50"}       (numerical type)

  Variants also handled:
    Q9. AD   /   9) AD   /   (9) A   /   9. (AD)
    Leading/trailing whitespace, trailing "Sol." or "Solution"
"""

import re
import fitz  # PyMuPDF


# ─── Primary pattern ──────────────────────────────────────────────────────────
# Group 1: question number (1-3 digits)
# Group 2: answer — one of:
#   • 1-4 uppercase/lowercase letters from {A,B,C,D}
#   • A signed or unsigned decimal/integer (e.g. "3", "2.50", "-1.5")
_ANSWER_RE = re.compile(
    r"""
    ^\s*                        # leading whitespace
    (?:\(?\s*Q\.?\s*)?          # optional prefix: "Q", "Q.", "(Q"
    (\d{1,3})                   # GROUP 1: question number
    [\.\)\s]                    # separator: . ) or space
    \s*
    \(?                         # optional opening paren
    ([A-Da-d]{1,4}              # GROUP 2a: letter answer(s)
     |-?\d+(?:[.,]\d+)?         # GROUP 2b: numeric answer
    )
    \)?                         # optional closing paren
    \s*                         # trailing whitespace
    (?:Sol\.?|Solution\.?|$)    # answer ends at Sol. / Solution. / EOL
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Fallback: table-style "1.  A | 2.  BD | …" patterns within a single line
_INLINE_RE = re.compile(
    r"(\d{1,3})[\.\)]\s*([A-Da-d]{1,4}|-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)


def _norm_decimal(s: str) -> str:
    """Normalise decimal separator: comma → period."""
    return s.replace(",", ".")


def _parse_answer(raw: str):
    """
    Given the raw answer string, return:
      list[str]  e.g. ["A", "D"]  — for letter answers
      str        e.g. "3"          — for numeric answers
    """
    upper = raw.strip().upper()
    if re.fullmatch(r"[A-D]{1,4}", upper):
        return sorted(set(upper))          # deduplicate + sort
    return _norm_decimal(raw.strip())          # keep as string


def parse_solutions(pdf_bytes: bytes) -> dict:
    """
    Parse a solutions PDF and return an answer key.

    Returns
    -------
    dict  {q_num (int): answer}
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    answers: dict[int, object] = {}

    for page_num, page in enumerate(doc):
        raw_text = page.get_text("text")
        lines = raw_text.splitlines()

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # ── Strategy 1: strict start-of-line match ──────────────────────
            m = _ANSWER_RE.match(stripped)
            if m:
                q_num = int(m.group(1))
                answer = _parse_answer(m.group(2))
                answers[q_num] = answer
                continue

            # ── Strategy 2: short line fallback (< 15 chars) ────────────────
            # e.g. a box in the PDF that only contains "9. AD"
            if len(stripped) <= 15:
                for m in _INLINE_RE.finditer(stripped):
                    q_num = int(m.group(1))
                    answer = _parse_answer(m.group(2))
                    answers[q_num] = answer

    doc.close()

    print(f"[ANSWER KEY] {len(answers)} answers extracted from solutions PDF")
    for k, v in sorted(answers.items()):
        print(f"  Q{k:>3}: {v}")

    return answers
