import re

Q_START_REGEX = re.compile(r"^\d+[\.\)]|^Q\s*\d+", re.IGNORECASE)

# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT SECTION  (used before any SECTION header is encountered)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_SECTION = {
    "name": "General",
    "description": "",
    "answer_type": "single_correct_mcq",
}


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFIERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_noise(text: str) -> bool:
    val = text.strip().lower()
    if not val:
        return True
    if val.isdigit():
        return True
    if any(k in val for k in ["jee", "paper", "time:", "timestamp", "date:", "page"]):
        return True
    return False


def _is_section_header(text: str) -> bool:
    """A line is a section header if it contains the word SECTION."""
    return "SECTION" in text.upper()


def _is_question_start(text: str) -> bool:
    s = text.strip()
    return bool(Q_START_REGEX.match(s)) and len(s) > 3


# ─────────────────────────────────────────────────────────────────────────────
# SECTION PARSER  — two-line: header + description
# ─────────────────────────────────────────────────────────────────────────────

def _parse_section(lines: list[dict], i: int) -> tuple[dict, int]:
    """
    Parse a section starting at index i.

    Reads:
      lines[i]   → title  (contains "SECTION")
      lines[i+1] → description (if present and not a question / noise)

    Returns (section_dict, new_index) where new_index points to the line
    AFTER whatever was consumed.
    """
    title = lines[i]["text"].strip()

    desc = ""
    consumed = 1  # we always consume at least the header line

    if i + 1 < len(lines):
        nxt = lines[i + 1]["text"].strip()
        # Only consume the next line as description if it is not a question
        # and does not itself look like another section header
        if (not _is_question_start(nxt)
                and not _is_section_header(nxt)
                and not _is_noise(nxt)):
            desc = nxt.lower()
            consumed = 2  # consumed header + description

    # Map description → answer_type using simple substring checks (per spec)
    if "one or more than one correct" in desc:
        answer_type = "multiple_correct_mcq"
    elif "one or more correct" in desc:
        answer_type = "multiple_correct_mcq"
    elif "multiple correct" in desc:
        answer_type = "multiple_correct_mcq"
    elif "single correct" in desc:
        answer_type = "single_correct_mcq"
    elif "single digit integer" in desc:
        answer_type = "integer_type"
    elif "integer" in desc:
        answer_type = "integer_type"
    elif "numerical" in desc or "decimal" in desc:
        answer_type = "numerical_type"
    else:
        # Fallback: also check the title itself
        title_lower = title.lower()
        if "one or more" in title_lower or "multiple correct" in title_lower:
            answer_type = "multiple_correct_mcq"
        elif "integer" in title_lower:
            answer_type = "integer_type"
        elif "numerical" in title_lower or "decimal" in title_lower:
            answer_type = "numerical_type"
        else:
            answer_type = "single_correct_mcq"

    section = {
        "name": title,
        "description": desc,
        "answer_type": answer_type,
    }

    return section, consumed


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-PASS STATE MACHINE
# ─────────────────────────────────────────────────────────────────────────────

def build_questions(lines: list[dict]) -> list[dict]:
    """
    Single-pass state machine.

    State (defined OUTSIDE the loop — never reset inside):
      current_section   — updated only when a SECTION header is seen
      pending_lines     — lines accumulating for the open question
      pending_section   — copy of current_section at the moment the question opened

    Priority per line:
      1. noise          → skip
      2. section header → _parse_section; update current_section; continue
      3. question start → flush pending; snapshot current_section; open new question
      4. other          → append to open question
    """
    questions: list[dict] = []

    # ── State (defined OUTSIDE loop) ─────────────────────────────────────────
    current_section: dict = dict(DEFAULT_SECTION)
    pending_lines:   list  = []
    pending_section: dict  = dict(DEFAULT_SECTION)

    def _flush():
        nonlocal pending_lines
        if pending_lines:
            questions.append({
                "id":      f"q{len(questions) + 1}",
                "lines":   list(pending_lines),
                "section": dict(pending_section),   # snapshot — never a shared ref
                "_debug":  {"line_count": len(pending_lines)},
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

        # 2. Section header
        if _is_section_header(text):
            section, consumed = _parse_section(lines, i)
            current_section = section
            print(f"[SECTION] {current_section}")   # DEBUG CHECKPOINT
            i += consumed
            continue

        # 3. Question start
        if _is_question_start(text):
            _flush()
            pending_section = dict(current_section)  # ← snapshot HERE (copy)
            pending_lines   = [lines[i]]
            print(f"[QUESTION START] '{text[:40]}...' with section={pending_section['answer_type']}")  # DEBUG CHECKPOINT
            i += 1
            continue

        # 4. Continuation — only if a question is open
        if pending_lines:
            pending_lines.append(lines[i])

        i += 1

    # Flush the last open question
    _flush()

    # Conservative cleanup: merge fragments shorter than 5 chars into previous
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
