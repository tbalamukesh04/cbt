"""
answer_parser.py  (v2 — multi-format + debug mode)
===================================================

Tries four strategies, in priority order, to extract answers from a JEE
solutions PDF and returns both the answer key AND detailed debug information
so the caller can audit which lines were matched / missed.

Supported line formats
----------------------
  9. AD               → {9: ["A","D"]}
  9. A,D              → {9: ["A","D"]}   (comma-separated)
  9. A D              → {9: ["A","D"]}   (space-separated letters)
  9. (A)(D)           → {9: ["A","D"]}   (each option in parens)
  9. A                → {9: ["A"]}
  9. 3                → {9: "3"}
  9. 2.50             → {9: "2.50"}
  9) AD / Q9. AD / Q.9 AD (prefix variants)

Table format (answers on a separate row from numbers):
  Q.No.   1   2   3   4   5
  Ans.    A   BD  C   3   A,D
"""

import re
import fitz  # PyMuPDF


# ─── Helper: extract letters from messy answer text ──────────────────────────
def _extract_letters(text: str) -> list[str] | None:
    """Return sorted, deduplicated A-D letters found in text, or None."""
    letters = re.findall(r"[A-Da-d]", text)
    upper = sorted(set(l.upper() for l in letters))
    return upper if upper else None


def _norm_decimal(s: str) -> str:
    return s.strip().replace(",", ".")


def _parse_answer(raw: str):
    """
    raw  → list[str] for letter answers, str for numeric answers.
    Handles: "AD", "A,D", "A D", "(A)(D)", "3", "2.50"
    """
    clean = raw.strip()

    # Try to extract letters (A-D) — ignoring anything between them
    letters = _extract_letters(clean)
    if letters:
        # Make sure we didn't accidentally grab a letter from "Sol." etc.
        # Only trust if ALL chars (ignoring spaces/commas/parens) are A-D
        core = re.sub(r"[\s,\(\)]", "", clean).upper()
        if re.fullmatch(r"[A-D]+", core):
            return sorted(set(core))

    # Numeric answer
    num_match = re.search(r"-?\d+(?:[.,]\d+)?", clean)
    if num_match:
        return _norm_decimal(num_match.group())

    return None


# ─── Strategy 1: Line starts with question number ────────────────────────────
# Covers:  9. AD   /  9) A,D  /  Q9. (A)(D)  /  9 AD
_LINE_RE = re.compile(
    r"""
    ^\s*
    (?:Q\.?\s*)?            # optional Q prefix
    (\d{1,3})               # question number
    [\.)\s,]+               # separator(s)
    (                       # answer —
        (?:\(?[A-Da-d]\)?   #   one option (optionally in parens)
           [\s,/]*          #   optionally separated
        ){1,4}              #   1–4 options
        |
        -?\d+(?:[.,]\d+)?   #   OR numeric answer
    )
    [\s,;]*                 # trailing noise
    (?:Sol\.?|Solution\.?|Hint\.?|\(|\d|$)   # ends at Sol./text/EOL
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ─── Strategy 2: Very short line (≤ 20 chars), any occurrence ────────────────
_SHORT_RE = re.compile(
    r"(\d{1,3})[\.)\s]+([A-Da-d]{1,4}|-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)

# ─── Strategy 3: Answer table (Q numbers row + Answers row) ──────────────────
def _parse_table(lines: list[str]) -> dict[int, object]:
    """
    Detect blocks like:
      Q.No.  1   2   3   4   5   6   7   8   9  10
      Ans.   A   BD  A  ACD  B   D   3   4  AD   C
    """
    results: dict[int, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Look for a line with ≥ 5 small integers (question numbers)
        nums = re.findall(r"\b(\d{1,2})\b", line)
        num_ints = [int(n) for n in nums if 1 <= int(n) <= 60]
        if len(num_ints) >= 5:
            # Look ahead up to 3 lines for the answers row
            for j in range(i + 1, min(i + 4, len(lines))):
                ans_line = lines[j].strip()
                # Must not be another numbers line
                if len(re.findall(r"\b\d{1,2}\b", ans_line)) >= 5:
                    break
                # Extract tokens (letters or numbers)
                tokens = re.findall(
                    r"\b([A-Da-d]{1,4}|-?\d+(?:[.,]\d+)?)\b", ans_line
                )
                if len(tokens) >= len(num_ints) // 2:
                    for k, tok in enumerate(tokens[: len(num_ints)]):
                        q = num_ints[k]
                        ans = _parse_answer(tok)
                        if ans:
                            results[q] = ans
                    break
        i += 1
    return results


def parse_solutions(pdf_bytes: bytes) -> dict:
    """
    Returns
    -------
    {
      "answers":      {q_num (int): answer},
      "debug_lines":  [ {"page": int, "line": str, "matched": bool,
                          "q": int|None, "answer": str|None} ]
    }
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    answers: dict[int, object] = {}
    debug_lines: list[dict] = []

    for page_num, page in enumerate(doc):
        raw_text = page.get_text("text")
        lines = raw_text.splitlines()

        # ── Strategy 3: table detection on this page ──────────────────────
        table_answers = _parse_table(lines)
        answers.update(table_answers)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            entry = {
                "page":    page_num + 1,
                "line":    stripped,
                "matched": False,
                "q":       None,
                "answer":  None,
            }

            # ── Strategy 1: line-start match ──────────────────────────────
            m = _LINE_RE.match(stripped)
            if m:
                q_num = int(m.group(1))
                ans   = _parse_answer(m.group(2))
                if ans is not None and 1 <= q_num <= 60:
                    answers[q_num] = ans
                    entry.update(matched=True, q=q_num,
                                 answer=str(ans))

            # ── Strategy 2: short line fallback ───────────────────────────
            elif len(stripped) <= 20:
                for sm in _SHORT_RE.finditer(stripped):
                    q_num = int(sm.group(1))
                    ans   = _parse_answer(sm.group(2))
                    if ans is not None and 1 <= q_num <= 60:
                        answers[q_num] = ans
                        entry.update(matched=True, q=q_num,
                                     answer=str(ans))
                        break

            # ── Mark table answers in debug too ───────────────────────────
            if not entry["matched"] and stripped:
                nums_in_line = [int(n) for n in re.findall(r"\b(\d{1,2})\b", stripped)
                                if 1 <= int(n) <= 60]
                for q in nums_in_line:
                    if q in table_answers:
                        entry.update(matched=True, q=q,
                                     answer=str(table_answers[q]))
                        break

            # Only keep lines that either matched or look like candidates
            # (contain a 1-2 digit number and are short/medium length)
            is_candidate = (
                len(stripped) <= 80
                and bool(re.search(r"\b\d{1,2}\b", stripped))
                and bool(re.search(r"[A-Da-d]|\d", stripped))
            )
            if entry["matched"] or is_candidate:
                debug_lines.append(entry)

    doc.close()

    # De-duplicate debug lines by line text (keep first occurrence)
    seen = set()
    unique_debug = []
    for d in debug_lines:
        key = d["line"][:60]
        if key not in seen:
            seen.add(key)
            unique_debug.append(d)

    print(f"[ANSWER KEY] {len(answers)} answers extracted")
    for k, v in sorted(answers.items()):
        print(f"  Q{k:>3}: {v}")

    return {"answers": answers, "debug_lines": unique_debug}
