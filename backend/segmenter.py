import re

Q_START_REGEX = re.compile(r"^\d+[\.\)]|^Q\s*\d+", re.IGNORECASE)

# Keywords → answer_type, checked against header + description combined
ANSWER_TYPE_PATTERNS = [
    (re.compile(r"one\s+or\s+more\s+than\s+one\s+correct", re.IGNORECASE), "multiple_correct_mcq"),
    (re.compile(r"multiple\s+correct",                      re.IGNORECASE), "multiple_correct_mcq"),
    (re.compile(r"single\s+correct",                        re.IGNORECASE), "single_correct_mcq"),
    (re.compile(r"single\s+digit\s+integer",                re.IGNORECASE), "integer_type"),
    (re.compile(r"integer\s+type",                          re.IGNORECASE), "integer_type"),
    (re.compile(r"numerical|decimal",                       re.IGNORECASE), "numerical_type"),
]

DEFAULT_SECTION = {
    "name": "General",
    "description": "",
    "answer_type": "single_correct_mcq",
}


# ─── Classifiers ───────────────────────────────────────────────────────────────

def _is_noise(text: str) -> bool:
    val = text.strip().lower()
    if not val:
        return True
    if val.isdigit():
        return True
    if any(k in val for k in ["jee", "paper", "time:", "timestamp", "date:", "page"]):
        return True
    return False


def _is_question_start(text: str) -> bool:
    return bool(Q_START_REGEX.match(text.strip())) and len(text.strip()) > 3


def _is_section_header(text: str) -> bool:
    """
    Structural detection: a line is a section header if:
      1. It contains 'SECTION'
      2. OR it is entirely uppercase and short (< 12 words),
         but NOT a question start and NOT an option line.
    """
    s = text.strip()
    if not s:
        return False
    if re.match(r"^\(?[A-Da-d][.\)]", s):   # option lines: (A) / A. / a)
        return False
    if _is_question_start(s):
        return False
    if "SECTION" in s.upper():
        return True
    words = s.split()
    if len(words) < 12 and s == s.upper() and any(c.isalpha() for c in s):
        return True
    return False


def _parse_answer_type(header: str, description: str) -> str:
    combined = header + " " + description
    for pattern, a_type in ANSWER_TYPE_PATTERNS:
        if pattern.search(combined):
            return a_type
    return "single_correct_mcq"


# ─── Single-pass state machine ─────────────────────────────────────────────────

def build_questions(lines: list[dict]) -> list[dict]:
    """
    Single-pass state machine over extracted lines.

    State:
      current_section  — set when a section header is encountered
      pending_lines    — lines accumulating for the current (open) question
      pending_section  — section snapshot taken when the question was opened
      questions        — finalized question objects

    Priority per line (in order):
      1. noise         → skip entirely
      2. question_start→ flush pending, open new question with current_section snapshot
      3. section_header→ update current_section (lookahead for description)
      4. other         → append to open question (if any)
    """
    questions: list[dict] = []

    # State
    current_section: dict = dict(DEFAULT_SECTION)
    pending_lines: list[dict] = []
    pending_section: dict = dict(DEFAULT_SECTION)

    def _flush_pending():
        """Emit the pending question to the output list."""
        nonlocal pending_lines
        if pending_lines:
            questions.append({
                "id": f"q{len(questions) + 1}",
                "lines": list(pending_lines),
                "section": dict(pending_section),   # snapshot taken at open time
                "_debug": {"line_count": len(pending_lines)},
            })
            pending_lines = []

    i = 0
    n = len(lines)
    while i < n:
        text = lines[i]["text"].strip()

        # 1. Noise — skip
        if _is_noise(text):
            i += 1
            continue

        # 2. Question start — flush previous, open new with current_section snapshot
        if _is_question_start(text):
            _flush_pending()
            pending_section = dict(current_section)  # ← snapshot HERE
            pending_lines = [lines[i]]
            i += 1
            continue

        # 3. Section header — update section state (does NOT start a question)
        if _is_section_header(text):
            header = text
            description = ""

            # Lookahead: consume next line as description if it is safe to do so
            if i + 1 < n:
                nxt = lines[i + 1]["text"].strip()
                if (not _is_question_start(nxt)
                        and not _is_section_header(nxt)
                        and not _is_noise(nxt)):
                    description = nxt
                    i += 1   # consume description line

            current_section = {
                "name": header,
                "description": description,
                "answer_type": _parse_answer_type(header, description),
            }
            i += 1
            continue

        # 4. Continuation — append to open question
        if pending_lines:
            pending_lines.append(lines[i])

        i += 1

    # Flush the final pending question
    _flush_pending()

    # Conservative cleanup: merge sub-5-char fragments into the previous question
    cleaned: list[dict] = []
    for q in questions:
        total = " ".join(l["text"] for l in q["lines"]).strip()
        if len(total) < 5 and cleaned:
            cleaned[-1]["lines"].extend(q["lines"])
            cleaned[-1]["_debug"]["line_count"] += q["_debug"]["line_count"]
        else:
            cleaned.append(q)

    for idx, q in enumerate(cleaned):
        q["id"] = f"q{idx + 1}"

    return cleaned
