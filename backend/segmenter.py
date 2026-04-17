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


# Subjects detected as separate structural partition nodes
SUBJECT_KEYWORDS = re.compile(
    r"\b(mathematics|physics|chemistry|maths)\b", re.IGNORECASE
)


def _is_subject_header(text: str) -> bool:
    """
    A line is a subject header if:
      - it contains Mathematics / Physics / Chemistry / Maths
      - AND is short (< 8 words) — avoids matching question text
    """
    s = text.strip()
    return bool(SUBJECT_KEYWORDS.search(s)) and len(s.split()) < 8


def _is_section_header(text: str) -> bool:
    """
    A line is a section header ONLY if:
      - contains 'section' (case-insensitive)
      - AND is short (< 10 words)
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
    return (
        text.lower()
        .replace("(", " ").replace(")", " ")
        .replace("-", " ").replace(":", " ")
        .replace("_", " ")
    )


def _is_block_noise(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if "which of the following" in t.lower():
        return True
    if t.endswith("?"):
        return True
    if len(t.split()) > 20:
        return True
    return False


def _extract_section_block(lines: list[dict], i: int) -> str:
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
    desc = _normalize(block)

    score: dict[str, int] = {
        "multiple_correct_mcq": 0,
        "single_correct_mcq":   0,
        "integer_type":         0,
        "numerical_type":       0,
    }

    if "more than one" in desc:        score["multiple_correct_mcq"] += 2
    if "one or more" in desc:          score["multiple_correct_mcq"] += 2
    if "multiple correct" in desc:     score["multiple_correct_mcq"] += 3
    if "multiple choice" in desc:      score["multiple_correct_mcq"] += 1

    if "single correct" in desc:       score["single_correct_mcq"] += 3
    if "only one correct" in desc:     score["single_correct_mcq"] += 3
    if "one correct" in desc and "more" not in desc:
                                       score["single_correct_mcq"] += 2

    if "integer" in desc:              score["integer_type"] += 3
    if "single digit" in desc:         score["integer_type"] += 2

    if "numerical" in desc:            score["numerical_type"] += 3
    if "decimal" in desc:              score["numerical_type"] += 2
    if "non negative" in desc:         score["numerical_type"] += 1

    print(f"[SECTION BLOCK] {desc[:120]}")
    print(f"[SCORES] {score}")

    winner = max(score, key=score.get)
    answer_type = winner if score[winner] > 0 else "single_correct_mcq"

    print(f"[TYPE] {answer_type}")
    return answer_type


def _parse_section(lines: list[dict], i: int) -> dict:
    """Parse a section header at index i. Returns a section dict."""
    title = lines[i]["text"].strip()
    block = _extract_section_block(lines, i)
    answer_type = _score_section_type(block)

    return {
        "name": title,
        "description": block.strip(),
        "answer_type": answer_type,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INSTRUCTION BLOCK DETECTOR  — fires without needing a "SECTION" keyword
# ─────────────────────────────────────────────────────────────────────────────

def _is_instruction_block(text: str) -> bool:
    """
    Detects ANY line that opens an instruction block.
    Two paths:

    PATH A — Standalone answer-type declaration (no scope keyword needed).
      e.g. "One or More than one correct type"
           "Single Correct Option"
           "Numerical Value Type"
      Requires a STRONG answer signal and is very short (< 12 words).

    PATH B — Scoped instruction sentence.
      e.g. "This section contains 06 multiple choice questions..."
           "Each question has only one correct answer."
      Requires both an answer keyword and a scope keyword, < 80 words.
    """
    t = text.strip().lower()
    words = t.split()

    # Path A: short, strong answer-type label
    STRONG_SIGNALS = (
        "one or more than one correct",
        "one or more correct",
        "more than one correct",
        "multiple correct",
        "single correct",
        "only one correct",
        "single digit integer",
        "integer type",
        "numerical value",
        "numerical type",
        "decimal type",
    )
    if len(words) < 12 and any(sig in t for sig in STRONG_SIGNALS):
        return True

    # Path B: scoped sentence with answer + scope keywords
    has_answer_kw = (
        "correct" in t or "option" in t
        or "integer" in t or "numerical" in t or "decimal" in t
    )
    has_scope_kw = (
        "this section contains" in t or "each question has" in t
        or "each of the following" in t
        or ("question" in t and ("section" in t or "this" in t or "each" in t))
    )
    return has_answer_kw and has_scope_kw and len(words) < 80


def _collect_instruction_block(lines: list[dict], i: int) -> tuple[str, int]:
    """
    Starting at line i (the trigger line), collect consecutive lines that are
    part of the same instruction block.

    Stops at: question start, subject/section header, or after 6 lines.
    Returns (combined_text, number_of_lines_consumed).
    """
    block: list[str] = []
    consumed = 0
    for j in range(i, min(i + 6, len(lines))):
        t = lines[j]["text"].strip()
        if j > i and _is_question_start(t):  # never stop on the trigger line itself
            break
        if j > i and (_is_section_header(t) or _is_subject_header(t)):
            break
        if not t:
            break
        block.append(t)
        consumed += 1
    return " ".join(block), consumed



def _detect_answer_type(text: str) -> str:
    """
    Score-based answer type detection applied directly to an instruction line.
    Uses higher weights than _score_section_type to be decisive on single lines.
    """
    t = _normalize(text)

    score: dict[str, int] = {
        "multiple_correct_mcq": 0,
        "single_correct_mcq":   0,
        "integer_type":         0,
        "numerical_type":       0,
    }

    if "one or more" in t:         score["multiple_correct_mcq"] += 3
    if "more than one" in t:       score["multiple_correct_mcq"] += 3
    if "multiple correct" in t:    score["multiple_correct_mcq"] += 4

    if "only one" in t:            score["single_correct_mcq"] += 4
    if "single correct" in t:      score["single_correct_mcq"] += 3
    if "one correct" in t and "more" not in t:
                                   score["single_correct_mcq"] += 3

    if "integer" in t:             score["integer_type"] += 4
    if "single digit" in t:        score["integer_type"] += 3

    if "numerical" in t:           score["numerical_type"] += 4
    if "decimal" in t:             score["numerical_type"] += 3
    if "non negative" in t:        score["numerical_type"] += 1

    winner = max(score, key=score.get)
    return winner if score[winner] > 0 else "single_correct_mcq"


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-PASS STATE MACHINE
# Returns an ORDERED list of section + question nodes:
#   { "type": "section", "section": {...} }
#   { "type": "question", "id": "q1", "lines": [...], "section": {...}, ... }
# ─────────────────────────────────────────────────────────────────────────────

def build_questions(lines: list[dict]) -> list[dict]:
    """
    Single-pass state machine producing an ordered list of structural nodes.

    Node types:
      "section"  — emitted when a SECTION header is detected; never appended
                   to question text
      "question" — emitted when a question boundary is detected

    State (OUTSIDE the loop):
      current_section  — updated only on section detection
      pending_lines    — accumulates lines for the open question
      pending_section  — snapshot of current_section at question-open time
    """
    output: list[dict] = []          # ordered section + question nodes

    current_section: dict = dict(DEFAULT_SECTION)
    pending_lines:   list  = []
    pending_section: dict  = dict(DEFAULT_SECTION)
    q_counter: int = 0

    def _flush_question():
        nonlocal pending_lines, q_counter
        if pending_lines:
            q_counter += 1
            output.append({
                "type":    "question",
                "id":      f"q{q_counter}",
                "lines":   list(pending_lines),
                "section": dict(pending_section),   # immutable copy
                "_debug":  {"line_count": len(pending_lines)},
            })
            pending_lines = []

    i = 0
    n = len(lines)

    while i < n:
        text = lines[i]["text"].strip()

        # 1. Noise — skip entirely
        if _is_noise(text):
            i += 1
            continue

        # 2. Subject header — highest priority structural partition
        if _is_subject_header(text):
            _flush_question()                          # close any open question

            # Normalise subject name
            match = SUBJECT_KEYWORDS.search(text)
            name  = match.group(0).capitalize() if match else text.strip()

            output.append({
                "type":    "subject",
                "subject": {"name": name, "raw": text.strip()},
            })

            # Reset section to default when subject changes
            current_section = dict(DEFAULT_SECTION)

            print(f"[SUBJECT] {name}")
            i += 1
            continue

        # 3. Section header — flush current question, emit section node
        if _is_section_header(text):
            _flush_question()

            section = _parse_section(lines, i)
            current_section = section

            output.append({
                "type":    "section",
                "section": dict(current_section),
            })

            print(f"[SECTION] {current_section}")
            i += 1
            continue

        # 4. Instruction block — fires regardless of whether a question is open.
        #    Collects a multi-line block, then always flushes + emits section node.
        #    This prevents instruction text from being appended to question content.
        if _is_instruction_block(text):
            block_text, consumed = _collect_instruction_block(lines, i)
            detected_type = _detect_answer_type(block_text)

            print(f"[INSTRUCTION BLOCK] {block_text[:120]}")
            print(f"[DETECTED TYPE] {detected_type}")

            _flush_question()   # close any open question BEFORE emitting section

            current_section = {
                "name": "INFERRED",
                "description": block_text,
                "answer_type": detected_type,
            }
            output.append({
                "type":    "section",
                "section": dict(current_section),
            })
            i += consumed       # skip all consumed instruction lines
            continue

        # 5. Question start — flush previous, open new with current_section snapshot
        if _is_question_start(text):
            _flush_question()
            pending_section = dict(current_section)    # snapshot HERE
            pending_lines   = [lines[i]]
            print(f"[QUESTION START] '{text[:40]}' with section={pending_section['answer_type']}")
            i += 1
            continue

        # 6. Continuation — append to open question only
        if pending_lines:
            pending_lines.append(lines[i])

        i += 1

    _flush_question()

    # Merge sub-5-char question fragments into the previous question node
    cleaned: list[dict] = []
    for node in output:
        if node["type"] == "question":
            total = " ".join(l["text"] for l in node["lines"]).strip()
            if len(total) < 5 and cleaned and cleaned[-1]["type"] == "question":
                cleaned[-1]["lines"].extend(node["lines"])
                cleaned[-1]["_debug"]["line_count"] += node["_debug"]["line_count"]
                continue
        cleaned.append(node)

    # Re-number questions sequentially after any merges
    qi = 0
    for node in cleaned:
        if node["type"] == "question":
            qi += 1
            node["id"] = f"q{qi}"

    return cleaned
