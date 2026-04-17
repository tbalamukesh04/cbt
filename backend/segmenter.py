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
    """
    A line is a section header ONLY if:
      - contains 'section' (case-insensitive)
      - AND is short (< 10 words) — avoids matching question text that mentions sections
    """
    s = text.strip()
    return "section" in s.lower() and len(s.split()) < 10


def _is_question_start(text: str) -> bool:
    s = text.strip()
    return bool(Q_START_REGEX.match(s)) and len(s) > 3


# ─────────────────────────────────────────────────────────────────────────────
# SECTION PARSER  — scoring-based, structure-aware
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase and strip punctuation that obscures keyword matching."""
    return (
        text.lower()
        .replace("(", " ")
        .replace(")", " ")
        .replace("-", " ")
        .replace(":", " ")
        .replace("_", " ")
    )


def _is_block_noise(text: str) -> bool:
    """Filter lines that would pollute the section description block."""
    t = text.strip()
    if not t:
        return True
    # Looks like a question (not instructions)
    if "which of the following" in t.lower():
        return True
    # Ends with a question mark — likely question text
    if t.endswith("?"):
        return True
    # Too long to be instructions
    if len(t.split()) > 20:
        return True
    return False


def _extract_section_block(lines: list[dict], i: int) -> str:
    """
    Collect up to 10 lines after the section header (index i) to form
    a description block.  Stops when a question start or another section
    header is encountered.  Noise lines are skipped in-place (not included
    but do not terminate the scan).
    """
    block: list[str] = []
    for j in range(i + 1, min(i + 10, len(lines))):
        t = lines[j]["text"].strip()
        if _is_question_start(t):
            break
        if _is_section_header(t):
            break
        if not _is_block_noise(t):
            block.append(t)
    return " ".join(block)


def _score_section_type(block: str) -> str:
    """
    Scoring-based classifier.  Each keyword adds a weighted score to one of
    the four answer types.  The winner is used; ties broken by first match.
    Returns 'single_correct_mcq' when all scores are 0.
    """
    desc = _normalize(block)

    score: dict[str, int] = {
        "multiple_correct_mcq": 0,
        "single_correct_mcq":   0,
        "integer_type":         0,
        "numerical_type":       0,
    }

    # Multiple correct signals
    if "more than one" in desc:          score["multiple_correct_mcq"] += 2
    if "one or more" in desc:            score["multiple_correct_mcq"] += 2
    if "multiple correct" in desc:       score["multiple_correct_mcq"] += 3
    if "multiple choice" in desc:        score["multiple_correct_mcq"] += 1

    # Single correct signals
    if "single correct" in desc:         score["single_correct_mcq"] += 3
    if "only one correct" in desc:       score["single_correct_mcq"] += 3
    if "one correct" in desc and "more" not in desc:
                                         score["single_correct_mcq"] += 2

    # Integer type signals
    if "integer" in desc:                score["integer_type"] += 3
    if "single digit" in desc:           score["integer_type"] += 2

    # Numerical type signals
    if "numerical" in desc:              score["numerical_type"] += 3
    if "decimal" in desc:                score["numerical_type"] += 2
    if "non negative" in desc:           score["numerical_type"] += 1
    if "non-negative" in desc:           score["numerical_type"] += 1

    print(f"[SECTION BLOCK] {desc[:120]}")
    print(f"[SCORES] {score}")

    winner = max(score, key=score.get)
    answer_type = winner if score[winner] > 0 else "single_correct_mcq"

    print(f"[TYPE] {answer_type}")
    return answer_type


def _parse_section(lines: list[dict], i: int) -> tuple[dict, int]:
    """
    Parse a section header at index i.

    Extracts the multi-line description block that follows the header and
    classifies it using the scoring system.  The header line itself is always
    consumed; consumed count returned so the caller can advance the index.
    """
    title = lines[i]["text"].strip()
    block = _extract_section_block(lines, i)
    answer_type = _score_section_type(block)

    section = {
        "name": title,
        "description": block.strip(),
        "answer_type": answer_type,
    }
    # Always consume exactly 1 line (the header); the block lines are scanned
    # but NOT consumed — they will be processed normally by the state machine
    # (as continuation/noise) and will not trigger section re-detection because
    # they do not pass _is_section_header.
    return section, 1


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
